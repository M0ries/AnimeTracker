// Shared by the GitHub Pages build and the Tauri desktop build.
const ROOT='https://uwvyyouukyenwlasxyqc.supabase.co';
const KEY='sb_publishable_rNqhz8Oq4gNMvmLE7vbkLA_Yss0Sb8u';
const SESSION='at.cloud.session';
const BASE='at.cloud.baseline.';
let session=JSON.parse(localStorage.getItem(SESSION)||'null'),inFlight=null;
const onStatus=message=>window.dispatchEvent(new CustomEvent('at-sync-status',{detail:message}));
async function request(path,{method='GET',body,token=session?.access_token,prefer}={}){
 const headers={'apikey':KEY};if(token)headers.Authorization=`Bearer ${token}`;
 if(body!==undefined)headers['Content-Type']='application/json';if(prefer)headers.Prefer=prefer;
 const response=await fetch(ROOT+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});
 const raw=await response.text();let data;try{data=raw?JSON.parse(raw):null;}catch{data=raw;}
 if(!response.ok)throw Error(data?.msg||data?.message||data?.error_description||data?.error||`同步服务返回 ${response.status}`);
 return data;
}
function saveSession(data){session=data;localStorage.setItem(SESSION,JSON.stringify(data));onStatus('已登录，准备同步');}
async function validSession(){
 if(!session)throw Error('请先登录同步账号');
 if(Date.now()<session.expires_at*1000-60000)return session;
 const next=await request('/auth/v1/token?grant_type=refresh_token',{method:'POST',body:{refresh_token:session.refresh_token},token:null});
 saveSession({...next,expires_at:Math.floor(Date.now()/1000)+next.expires_in});return session;
}
const stable=value=>Array.isArray(value)?value.map(stable):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(k=>[k,stable(value[k])])):value;
const fingerprint=doc=>JSON.stringify(stable(doc.tables));
const count=doc=>Object.values(doc.tables).reduce((n,rows)=>n+rows.length,0);
async function localDocument(){const response=await fetch('/api/export/json');if(!response.ok)throw Error('无法读取本地记录');
 const result=await response.json();return result.content?JSON.parse(result.content):result;}
async function localReplace(doc,expected){const response=await fetch('/api/sync/replace',{method:'POST',headers:{'Content-Type':'application/json','X-AnimeTracker-Token':(await (await fetch('/api/state')).json()).csrf_token},body:JSON.stringify({document:doc,expected})});
 const result=await response.json();if(!response.ok)throw Error(result.error||'无法安全写入本地记录');return result;}
async function remoteRow(userId){const result=await request(`/rest/v1/at_snapshots?user_id=eq.${encodeURIComponent(userId)}&select=revision,document`);return result[0]||null;}
async function synchronize(){
 await validSession();const userId=session.user.id, key=BASE+userId;
 const before=await localDocument(), localHash=fingerprint(before),baseline=JSON.parse(localStorage.getItem(key)||'null');
 const remote=await remoteRow(userId);
 if(!remote){
  if(baseline)throw Error('云端资料已消失；已停止同步以保护本地数据');
  await request('/rest/v1/at_snapshots',{method:'POST',body:{user_id:userId,revision:1,document:before}});
  localStorage.setItem(key,JSON.stringify({revision:1,hash:localHash}));onStatus('已上传本地记录');return;
 }
 if(!baseline && count(before)>0 && fingerprint(remote.document)!==localHash)
  throw Error('本地和云端都有记录；请先导出本地完整 JSON 备份，再决定如何合并');
 const localChanged=baseline&&localHash!==baseline.hash;
 const remoteChanged=baseline&&remote.revision!==baseline.revision;
 if(localChanged&&remoteChanged)throw Error('两台设备都修改了资料；已停止同步，请先导出备份');
 if(!baseline||remoteChanged){
  if(fingerprint(remote.document)!==localHash)await localReplace(remote.document,before);
  localStorage.setItem(key,JSON.stringify({revision:remote.revision,hash:fingerprint(remote.document)}));
  onStatus('已获取云端记录');window.dispatchEvent(new Event('at-sync-updated'));return;
 }
 if(localChanged){
  const revision=await request('/rest/v1/rpc/at_compare_and_swap',{method:'POST',body:{expected_revision:baseline.revision,next_document:before}});
  localStorage.setItem(key,JSON.stringify({revision,hash:localHash}));onStatus('已上传本地记录');return;
 }
 onStatus('已同步');
}
export const ATSync={
 get signedIn(){return Boolean(session);},
 get email(){return session?.user?.email||'';},
 async login(email,password,register=false){
  if(register){const data=await request('/auth/v1/signup',{method:'POST',body:{email,password},token:null});
   if(!data.access_token){onStatus('已发送确认邮件；确认后再登录');return false;}
   saveSession({...data,expires_at:Math.floor(Date.now()/1000)+data.expires_in});return true;
  }
  const data=await request('/auth/v1/token?grant_type=password',{method:'POST',body:{email,password},token:null});
  saveSession({...data,expires_at:Math.floor(Date.now()/1000)+data.expires_in});return true;
 },
 logout(){session=null;localStorage.removeItem(SESSION);onStatus('已退出同步账号');},
 async syncNow(){if(inFlight)return inFlight;inFlight=synchronize().catch(e=>{onStatus('同步暂停：'+e.message);throw e;}).finally(()=>{inFlight=null;});return inFlight;},
 changed(){if(!session)return;this.syncNow().catch(()=>{});}
};
