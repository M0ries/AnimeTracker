use std::{collections::BTreeMap, fs::{self, File, OpenOptions}, io::{Read, Write}, path::{Path, PathBuf}};
use base64::{engine::general_purpose::STANDARD, Engine};
use fs2::FileExt;
use serde::{Deserialize, Serialize};
use tauri::Manager;
use tauri_plugin_opener::OpenerExt;

const MAX_BYTES: u64 = 512 * 1024 * 1024;
#[derive(Default, Serialize, Deserialize)]
struct Snapshot { revision: u64, files: BTreeMap<String, String> }
fn app_dir(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let dir = app.path().app_data_dir().map_err(|e|e.to_string())?;
    fs::create_dir_all(&dir).map_err(|e|e.to_string())?; Ok(dir)
}
fn lock(dir: &Path) -> Result<File, String> {
    let f = OpenOptions::new().read(true).write(true).create(true).truncate(false).open(dir.join("storage.lock")).map_err(|e|e.to_string())?;
    f.lock_exclusive().map_err(|e|e.to_string())?; Ok(f)
}
fn read_snapshot(dir: &Path) -> Result<Snapshot, String> {
    let path = dir.join("storage.json");
    let mut f = match File::open(path) { Ok(f)=>f, Err(e) if e.kind()==std::io::ErrorKind::NotFound=>return Ok(Snapshot::default()), Err(e)=>return Err(e.to_string()) };
    if f.metadata().map_err(|e|e.to_string())?.len()>MAX_BYTES {return Err("资料库超过大小限制".into());}
    let mut bytes=Vec::new();f.read_to_end(&mut bytes).map_err(|e|e.to_string())?;
    let snapshot: Snapshot=serde_json::from_slice(&bytes).map_err(|e|format!("资料库无法读取，原文件已保留：{e}"))?;
    validate(&snapshot.files)?; Ok(snapshot)
}
fn validate(files: &BTreeMap<String,String>) -> Result<(),String> {
    if !files.contains_key("anime_tracker.db") {return Err("缺少数据库".into());}
    let mut total=0usize;
    for (name,data) in files {
        let backup=name.strip_prefix("backups/anime_tracker_").and_then(|s|s.strip_suffix(".db"));
        if name!="anime_tracker.db" && !backup.is_some_and(|s| !s.is_empty() && s.bytes().all(|b|b.is_ascii_alphanumeric()||b==b'_')) {return Err("无效的资料库文件名".into());}
        total=total.checked_add(data.len()).ok_or("资料库过大")?;
        if total>MAX_BYTES as usize-65536 {return Err("资料库过大，请先导出备份".into());}
        let bytes=STANDARD.decode(data).map_err(|e|e.to_string())?;
        if !bytes.starts_with(b"SQLite format 3\0") {return Err("无效的 SQLite 数据".into());}
    } Ok(())
}
#[tauri::command]
fn storage_load(app: tauri::AppHandle) -> Result<Snapshot,String> {
    let dir=app_dir(&app)?;let _lock=lock(&dir)?;read_snapshot(&dir)
}
#[tauri::command]
fn storage_save(app: tauri::AppHandle, files: BTreeMap<String,String>, revision:u64) -> Result<Snapshot,String> {
    validate(&files)?;let dir=app_dir(&app)?;let _lock=lock(&dir)?;
    if read_snapshot(&dir)?.revision!=revision {return Err("其他窗口修改了资料库，请重新打开应用后再操作。".into());}
    let snapshot=Snapshot{revision:revision.checked_add(1).ok_or("版本号超限")?,files};
    let bytes=serde_json::to_vec(&snapshot).map_err(|e|e.to_string())?;
    if bytes.len() as u64>MAX_BYTES {return Err("资料库过大".into());}
    let mut temp=tempfile::NamedTempFile::new_in(&dir).map_err(|e|e.to_string())?;
    temp.write_all(&bytes).map_err(|e|e.to_string())?;temp.as_file().sync_all().map_err(|e|e.to_string())?;
    temp.persist(dir.join("storage.json")).map_err(|e|e.to_string())?;
    // Atomic replacement is the commit point. Do not report failure after committing.
    #[cfg(unix)] { if let Ok(directory)=File::open(&dir) {let _=directory.sync_all();} }
    Ok(snapshot)
}
#[tauri::command]
fn open_bangumi(app: tauri::AppHandle, id: u32) -> Result<(),String> {
    if id == 0 || id > 2147483647 { return Err("无效的 Bangumi ID".into()); }
    app.opener().open_url(format!("https://bgm.tv/subject/{id}"), None::<&str>).map_err(|e|e.to_string())
}
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![storage_load,storage_save,open_bangumi])
        .run(tauri::generate_context!())
        .expect("AnimeTracker failed to start");
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn refuses_paths_and_invalid_sqlite() {
        let mut files=BTreeMap::new(); files.insert("anime_tracker.db".into(),STANDARD.encode(b"SQLite format 3\0test"));
        assert!(validate(&files).is_ok()); files.insert("../secret".into(),"".into()); assert!(validate(&files).is_err());
        files.remove("../secret");files.insert("anime_tracker.db".into(),"not sqlite".into());assert!(validate(&files).is_err());
    }
    #[test] fn corrupt_storage_is_not_treated_as_empty() {
        let dir=tempfile::tempdir().unwrap();fs::write(dir.path().join("storage.json"),b"broken").unwrap();assert!(read_snapshot(dir.path()).is_err());
    }
}
