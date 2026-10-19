"""In-process API shared by native and browser builds; no HTTP server."""
import base64
import json
import re
from pathlib import Path
from store import Store

DATA = Path('/data')
DATA.mkdir(exist_ok=True)
store = None

def read_snapshot():
    return {str(p.relative_to(DATA)): base64.b64encode(p.read_bytes()).decode()
            for p in DATA.rglob('*') if p.is_file()}

def restore_snapshot(files):
    global store
    decoded = {}
    for name, data in files.items():
        if name != 'anime_tracker.db' and not re.fullmatch(r'backups/anime_tracker_[A-Za-z0-9_]+\.db', name):
            raise ValueError('Invalid storage filename')
        decoded[name] = base64.b64decode(data, validate=True)
    for p in DATA.rglob('*'):
        if p.is_file(): p.unlink()
    for name, data in decoded.items():
        p = DATA / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    store = Store(DATA / 'anime_tracker.db')

def initialize_json(raw):
    restore_snapshot(json.loads(raw))

def snapshot_json():
    return json.dumps(read_snapshot())

def dispatch(path, d):
    s = store
    if path == 'state':
        return dict(s.state(), csrf_token='local', database_path='此设备 · 应用资料库')
    if path == 'health': return {'application':'AnimeTracker','version':'2.0.0'}
    if path == 'anime/save': return {'id':s.save_anime(d.get('data',{}),d.get('id'))}
    if path == 'anime/bangumi': return s.update_bangumi(d['id'],d['subject'])
    if path == 'anime/bangumi/link': return s.save_bangumi(d['subject'],d.get('id'))
    if path == 'round/save': return {'id':s.save_round(d['anime_id'],d.get('data',{}),d.get('id'))}
    if path == 'session/edit': return {'id':s.edit_session(d['id'],d.get('data',{}))}
    if path == 'session/add': return {'id':s.add_session(d['round_id'],d.get('data',{}))}
    if path == 'delete':
        s.delete(d['table'],d['id'],d.get('confirm'));return {'deleted':True}
    if path == 'batch':
        s.batch(d['ids'],d.get('status'),d.get('delete',False),d.get('confirm',False));return {'updated':True}
    if path == 'merge':
        s.merge(d['source'],d['target'],d.get('confirm',False));return {'merged':True}
    if path == 'import/json': return s.import_doc(d['document'])
    if path == 'import/csv': return s.import_csv(d['content'])
    if path == 'backup':
        f=s.backup();return {'filename':f.name,'base64':base64.b64encode(f.read_bytes()).decode()}
    if path == 'restore': return s.restore(base64.b64decode(d['base64'],validate=True),d.get('confirm',False))
    if path == 'export/json':
        return {'filename':'AnimeTracker-export.json','content':json.dumps(s.export(),ensure_ascii=False,indent=2),'mime':'application/json'}
    if path in ('export/csv','export/list.csv','template.csv'):
        content=s.export_csv() if path=='export/csv' else s.export_list_csv(template=path=='template.csv')
        return {'filename':'AnimeTracker-'+('template' if path=='template.csv' else 'list' if path=='export/list.csv' else 'export')+'.csv','content':content,'mime':'text/csv'}
    raise ValueError('不支持的操作')

def handle_json(raw):
    request=json.loads(raw)
    return json.dumps(dispatch(request['path'],request.get('body') or {}),ensure_ascii=False)
