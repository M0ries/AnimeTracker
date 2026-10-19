"""AnimeTracker: SQLite persistence. Python standard library only."""
import base64, csv, hashlib, io, json, math, os, re, sqlite3, tempfile, uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

VERSION = 1
APP_ID = 0x414E5452
STATUSES = ('planned','watching','completed','paused','dropped','unreviewed')
TABLES = ('series','anime','rounds','sources','sessions')
SCHEMA = '''
CREATE TABLE series(id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE anime(
 id TEXT PRIMARY KEY, series_id TEXT REFERENCES series(id), bangumi_id INTEGER,
 name TEXT NOT NULL, name_cn TEXT NOT NULL DEFAULT '', aliases TEXT NOT NULL DEFAULT '[]',
 cover TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', release_year INTEGER,
 season TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '[]', total_episodes INTEGER,
 status TEXT NOT NULL DEFAULT 'planned', personal_rating REAL, notes TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX anime_subject ON anime(bangumi_id);
CREATE TABLE rounds(
 id TEXT PRIMARY KEY, anime_id TEXT NOT NULL REFERENCES anime(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
 started_at TEXT, finished_at TEXT, last_watched_at TEXT, notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE sources(
 id TEXT PRIMARY KEY, source_key TEXT UNIQUE NOT NULL, anime_id TEXT NOT NULL REFERENCES anime(id) ON DELETE CASCADE,
 round_id TEXT NOT NULL REFERENCES rounds(id) ON DELETE CASCADE, payload TEXT NOT NULL, imported_at TEXT NOT NULL
);
CREATE TABLE sessions(
 id TEXT PRIMARY KEY, round_id TEXT NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
 episode INTEGER NOT NULL, watched_at TEXT, progress_ms INTEGER, road INTEGER,
 source_id TEXT REFERENCES sources(id) ON DELETE CASCADE, import_key TEXT, notes TEXT NOT NULL DEFAULT '',
 UNIQUE(source_id, import_key)
);
'''

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def uid(): return str(uuid.uuid4())
def js(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def text(v, limit=20000):
    if not isinstance(v,str) or len(v)>limit: raise ValueError('文字格式或长度不正确')
    return v.strip()
def integer(v, low=0, high=100000, nullable=False):
    if v in (None,'') and nullable: return None
    if isinstance(v,bool): raise ValueError('数字格式不正确')
    if isinstance(v,str):
        if not v.isdigit(): raise ValueError('请输入非负整数')
        v=int(v)
    if not isinstance(v,int) or not low<=v<=high: raise ValueError(f'整数须在 {low}–{high} 之间')
    return v

def day(v):
    if v in (None,''): return None
    v=text(v,50)
    try:
        if len(v)==10: return date.fromisoformat(v).isoformat()
        parsed=datetime.fromisoformat(v.replace('Z','+00:00'))
        if parsed.tzinfo is None: raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat()
    except (ValueError,OverflowError): raise ValueError('日期须为 YYYY-MM-DD 或包含时区的 ISO 时间')
def sequence(v):
    if not isinstance(v,list) or len(v)>500: raise ValueError('标签或别名须为列表（最多 500 项）')
    return list(dict.fromkeys(text(x,300) for x in v if x))
def status(v):
    if v not in STATUSES: raise ValueError('观看状态无效')
    return v

def defaults_path():
    if os.environ.get('ANIMETRACKER_DATA_DIR'): return Path(os.environ['ANIMETRACKER_DATA_DIR']).expanduser()
    import sys
    return (Path.home()/'Library/Application Support/AnimeTracker' if sys.platform=='darwin'
            else Path.home()/'.local/share/AnimeTracker')

class Store:
    def __init__(self,path=None):
        self.path=Path(path) if path else defaults_path()/'anime_tracker.db'
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as c:
            ver=c.execute('PRAGMA user_version').fetchone()[0]
            tables=c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if ver==0 and not tables:
                c.executescript(SCHEMA)
                c.execute(f'PRAGMA user_version={VERSION}')
                c.execute(f'PRAGMA application_id={APP_ID}')
            elif ver!=VERSION or c.execute('PRAGMA application_id').fetchone()[0]!=APP_ID:
                raise ValueError('不支持此数据库版本；已保留原文件，请勿覆盖')
    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=20)
        c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback(); raise
        finally: c.close()
    def required(self,c,table,id):
        r=c.execute(f'SELECT * FROM {table} WHERE id=?',(id,)).fetchone()
        if r is None: raise ValueError('记录不存在或已被删除')
        return dict(r)
    def insert(self,c,table,row):
        columns=tuple(row)
        c.execute(f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})',tuple(row.values()))
    def update(self,c,table,id,row):
        c.execute(f'UPDATE {table} SET '+','.join(k+'=?' for k in row)+' WHERE id=?',(*row.values(),id))
    def anime_values(self,data):
        name=text(data.get('name',''),500)
        if not name: raise ValueError('请填写动漫名称')
        rating=data.get('personal_rating')
        if rating in ('',None): rating=None
        else:
            if isinstance(rating,bool): raise ValueError('评分须在 0–10 之间')
            rating=float(rating)
            if not math.isfinite(rating) or not 0<=rating<=10: raise ValueError('评分须在 0–10 之间')
        cover=text(data.get('cover',''),3000)
        if cover and not cover.startswith(('https://','http://')): raise ValueError('封面请使用 http/https 地址')
        return dict(name=name,name_cn=text(data.get('name_cn',''),500),
            aliases=js(sequence(data.get('aliases',[]))),cover=cover,
            description=text(data.get('description','')), release_year=integer(data.get('release_year'),1800,3000,True),
            season=text(data.get('season',''),100),tags=js(sequence(data.get('tags',[]))),
            total_episodes=integer(data.get('total_episodes'),0,100000,True),status=status(data.get('status','planned')),
            personal_rating=rating,notes=text(data.get('notes','')))
    def save_anime(self,data,id=None):
        v=self.anime_values(data)
        with self.connect() as c:
            old=self.required(c,'anime',id) if id else None
            bangumi_id=integer(data['bangumi_id'],1,2147483647,True) if 'bangumi_id' in data else (old['bangumi_id'] if old else None)
            if old and old['bangumi_id']!=bangumi_id and c.execute('SELECT 1 FROM sources WHERE anime_id=?',(id,)).fetchone():
                raise ValueError('Kazumi 来源条目的 Bangumi ID 不可修改')
            if bangumi_id and c.execute('SELECT id FROM anime WHERE bangumi_id=? AND id<>?',(bangumi_id,id or '')).fetchone():
                raise ValueError('这个 Bangumi ID 已用于另一部动漫')
            series_name=text(data.get('series_name',''),500)
            series_id=None
            if series_name:
                existing=c.execute('SELECT id FROM series WHERE name=? ORDER BY id',(series_name,)).fetchone()
                series_id=existing[0] if existing else uid()
                if not existing: self.insert(c,'series',dict(id=series_id,name=series_name))
            v.update(series_id=series_id,bangumi_id=bangumi_id,updated_at=now())
            if old: self.update(c,'anime',id,v)
            else:
                id=uid();v.update(id=id,created_at=now());self.insert(c,'anime',v)
        return id
    def update_bangumi(self,id,subject):
        """Refresh a linked subject, rejecting a different subject ID."""
        with self.connect() as c:
            old=self.required(c,'anime',id)
            if not old['bangumi_id'] or not isinstance(subject,dict) or subject.get('id')!=old['bangumi_id']:
                raise ValueError('Bangumi 条目 ID 不一致或不是动画')
        return self.save_bangumi(subject,id)
    def save_bangumi(self,subject,id=None):
        """Create or link an anime and fill only missing catalog fields atomically."""
        if not isinstance(subject,dict): raise ValueError('Bangumi 资料格式不正确')
        bid=integer(subject.get('id'),1,2147483647)
        if subject.get('type')!=2: raise ValueError('Bangumi 条目不是动画')
        images=subject.get('images') or {}
        if not isinstance(images,dict): images={}
        date_value=subject.get('date') or ''
        fields={
            'name':subject.get('name'), 'name_cn':subject.get('name_cn'),
            'description':subject.get('summary'), 'cover':images.get('large') or images.get('common'),
            'release_year':int(date_value[:4]) if isinstance(date_value,str) and re.match(r'^\d{4}(?:-|$)',date_value) else None,
            'total_episodes':subject.get('eps') if isinstance(subject.get('eps'),int) and not isinstance(subject.get('eps'),bool) and subject['eps']>0 else None,
        }
        with self.connect() as c:
            old=self.required(c,'anime',id) if id else None
            if old and old['bangumi_id'] not in (None,bid):
                raise ValueError('已有不同的 Bangumi ID，请先核对条目')
            if c.execute('SELECT 1 FROM anime WHERE bangumi_id=? AND id<>?',(bid,id or '')).fetchone():
                raise ValueError('这个 Bangumi ID 已用于另一部动漫')
            if old:
                changes={key:value for key,value in fields.items() if old[key] in ('',None) and value not in ('',None)}
                data={key:old[key] for key in ('name','name_cn','cover','description','release_year','season','total_episodes','status','personal_rating','notes')}
                data['aliases']=json.loads(old['aliases']);data['tags']=json.loads(old['tags'])
                data.update(changes)
                normalized=self.anime_values(data)
                changes={key:normalized[key] for key in changes}
                changed=list(changes)
                if old['bangumi_id'] is None: changes['bangumi_id']=bid
                if changes:
                    changes['updated_at']=now();self.update(c,'anime',id,changes)
                return {'id':id,'updated':changed}
            data={key:value for key,value in fields.items() if value not in ('',None)}
            if not data.get('name'): data['name']=data.get('name_cn','')
            values=self.anime_values(data)
            id=uid();values.update(id=id,series_id=None,bangumi_id=bid,created_at=now(),updated_at=now())
            self.insert(c,'anime',values)
            return {'id':id,'updated':list(data)}
    def round_values(self,data):
        kind=data.get('kind','first')
        if kind not in ('first','rewatch','imported'): raise ValueError('观看轮次类型无效')
        start,end,last=day(data.get('started_at')),day(data.get('finished_at')),day(data.get('last_watched_at'))
        if start and end and start[:10]>end[:10]: raise ValueError('结束日期不能早于开始日期')
        if start and last and start[:10]>last[:10]: raise ValueError('最近观看日期不能早于开始日期')
        return dict(kind=kind,status=status(data.get('status','watching')),progress=integer(data.get('progress',0)),
            started_at=start,finished_at=end,last_watched_at=last,notes=text(data.get('notes','')))
    def save_round(self,anime_id,data,id=None):
        v=self.round_values(data)
        with self.connect() as c:
            a=self.required(c,'anime',anime_id)
            if a['total_episodes'] and v['progress']>a['total_episodes']: raise ValueError('进度超过总集数，请先修改总集数')
            if id:
                old=self.required(c,'rounds',id)
                if old['anime_id']!=anime_id: raise ValueError('轮次不属于此动漫')
                if old['kind']=='imported': raise ValueError('来源快照请保留原样；可另建手动观看轮次')
                latest=c.execute("SELECT id FROM rounds WHERE anime_id=? AND kind!='imported' ORDER BY created_at DESC,rowid DESC LIMIT 1",(anime_id,)).fetchone()
                self.update(c,'rounds',id,v)
                if latest and latest[0]==id: self.update(c,'anime',anime_id,dict(status=v['status'],updated_at=now()))
            else:
                if v['kind']=='imported': raise ValueError('手动轮次请选择首看或重看')
                id=uid();v.update(id=id,anime_id=anime_id,created_at=now());self.insert(c,'rounds',v)
                self.update(c,'anime',anime_id,dict(status=v['status'],updated_at=now()))
        return id
    def add_session(self,round_id,data):
        v=dict(id=uid(),round_id=round_id,episode=integer(data.get('episode'),1),watched_at=day(data.get('watched_at')),
               progress_ms=None,road=None,source_id=None,import_key=None,notes=text(data.get('notes','')))
        with self.connect() as c:
            r=self.required(c,'rounds',round_id)
            if r['kind']=='imported': raise ValueError('请在手动观看轮次中记录观看')
            a=self.required(c,'anime',r['anime_id'])
            if a['total_episodes'] and v['episode']>a['total_episodes']: raise ValueError('集数超过总集数')
            if r['started_at'] and v['watched_at'] and v['watched_at'][:10]<r['started_at'][:10]: raise ValueError('观看日期早于轮次开始日期')
            self.insert(c,'sessions',v)
            self.update(c,'rounds',round_id,dict(progress=max(r['progress'],v['episode']),last_watched_at=max(filter(None,[r['last_watched_at'],v['watched_at']]),default=None)))
        return v['id']
    def edit_session(self,id,data):
        v=dict(episode=integer(data.get('episode'),1),watched_at=day(data.get('watched_at')),
               notes=text(data.get('notes','')))
        with self.connect() as c:
            old=self.required(c,'sessions',id)
            r=self.required(c,'rounds',old['round_id'])
            if old['source_id'] or r['kind']=='imported':raise ValueError('Kazumi 来源快照保留原样；请编辑手动记录')
            a=self.required(c,'anime',r['anime_id'])
            if a['total_episodes'] and v['episode']>a['total_episodes']:raise ValueError('集数超过总集数')
            if r['started_at'] and v['watched_at'] and v['watched_at'][:10]<r['started_at'][:10]:raise ValueError('观看日期早于轮次开始日期')
            self.update(c,'sessions',id,v)
            recorded_dates=[row[0] for row in c.execute('SELECT watched_at FROM sessions WHERE round_id=? AND watched_at IS NOT NULL',(r['id'],))]
            # If this record supplied the round's last date, correct it too.
            # Otherwise retain the independently entered round date.
            if r['last_watched_at'] and r['last_watched_at']!=old['watched_at']:
                recorded_dates.append(r['last_watched_at'])
            self.update(c,'rounds',r['id'],dict(progress=max(r['progress'],v['episode']),
                        last_watched_at=max(recorded_dates,default=None)))
        return id
    def delete(self,table,id,confirm=False):
        if table not in ('anime','rounds','sessions') or confirm is not True: raise ValueError('请确认删除')
        with self.connect() as c:
            r=self.required(c,table,id)
            if table=='rounds' and r['kind']=='imported': raise ValueError('来源快照不能单独删除')
            if table=='sessions' and r['source_id']: raise ValueError('来源快照不能单独删除')
            c.execute(f'DELETE FROM {table} WHERE id=?',(id,))
    def batch(self,ids,new_status=None,delete=False,confirm=False):
        if not isinstance(ids,list) or not 1<=len(ids)<=1000: raise ValueError('请选择 1–1000 条动漫')
        if delete and confirm is not True: raise ValueError('请确认批量删除')
        if not delete: status(new_status)
        with self.connect() as c:
            for id in ids:
                self.required(c,'anime',id)
                if delete:c.execute('DELETE FROM anime WHERE id=?',(id,))
                else:self.update(c,'anime',id,dict(status=new_status,updated_at=now()))
    def merge(self,source,target,confirm=False):
        if not confirm or source==target: raise ValueError('请确认将两个条目合并')
        with self.connect() as c:
            a=self.required(c,'anime',source);b=self.required(c,'anime',target)
            # Preserve all rounds, source snapshots and personal metadata of the source.
            archive='\n\n[人工合并的原条目信息]\n'+js(a)
            self.update(c,'anime',target,dict(notes=b['notes']+archive,updated_at=now()))
            c.execute('UPDATE rounds SET anime_id=? WHERE anime_id=?',(target,source))
            c.execute('UPDATE sources SET anime_id=? WHERE anime_id=?',(target,source))
            c.execute('DELETE FROM anime WHERE id=?',(source,))
    def export(self):
        with self.connect() as c:
            return dict(format='animetracker-v1',schema_version=VERSION,exported_at=now(),
                        tables={t:[dict(r) for r in c.execute(f'SELECT * FROM {t} ORDER BY id')] for t in TABLES})
    def state(self):
        out=self.export()['tables']
        for a in out['anime']:
            a['tags']=json.loads(a['tags']);a['aliases']=json.loads(a['aliases'])
        out['sources']=[{k:v for k,v in s.items() if k!='payload'} for s in out['sources']]
        return dict(**out,stats=self.stats(out),database_path=str(self.path),schema_version=VERSION)
    def stats(self,out):
        aa=out['anime'];rr=[r for r in out['rounds'] if r['kind']!='imported'];year=str(date.today().year)
        months={f'{year}-{m:02}':0 for m in range(1,13)}
        for r in rr:
            if r['status']=='completed' and r['finished_at'] and r['finished_at'][:7] in months:months[r['finished_at'][:7]]+=1
        genres={}
        for a in aa:
            for t in a['tags']:genres[t]=genres.get(t,0)+1
        return dict(works=len({a['series_id'] or a['id'] for a in aa}),seasons=len(aa),
            watched_seasons=len({r['anime_id'] for r in out['rounds'] if r['progress']>0}),
            rounds=len(rr),rewatches=sum(r['kind']=='rewatch' for r in rr),
            records=sum(s['source_id'] is None for s in out['sessions']),
            snapshot_records=sum(s['source_id'] is not None for s in out['sessions']),
            marked_episode_progress=sum(r['progress'] for r in rr),
            completed_this_year=len({r['anime_id'] for r in rr if r['status']=='completed' and (r['finished_at'] or '').startswith(year)}),
            imported_snapshots=len(out['sources']),monthly_completed_rounds=months,genres=genres)
    def import_kazumi(self,doc):
        histories=doc.get('histories')
        if doc.get('format')!='kazumi-history-v1' or not isinstance(histories,list): raise ValueError('不是支持的 Kazumi JSON 格式')
        if len(histories)>50000:raise ValueError('单次导入最多 50000 条')
        report=dict(raw=len(histories),parsed=0,imported=0,updated=0,skipped=0,conflicts=0,errors=0,details=[])
        with self.connect() as c:
            for index,h in enumerate(histories):
                c.execute('SAVEPOINT item')
                try:
                    b=h['bangumi'];key=text(h['history_key'],1000)
                    if not key:raise ValueError('缺少稳定 History key')
                    bid=integer(b.get('id'),0,2147483647,True)
                    name=text(b.get('name',''),500) or text(b.get('name_cn',''),500)
                    if not name:raise ValueError('缺少名称')
                    last=day(h.get('last_watch_time'));ep=integer(h.get('last_watch_episode',0))
                    progresses=h.get('progresses',[])
                    if not isinstance(progresses,list):raise ValueError('progresses 不是列表')
                    pvals=[];pkeys=set()
                    for p in progresses:
                        pk=str(p['key'])
                        if pk in pkeys:raise ValueError('重复进度 key')
                        pkeys.add(pk)
                        stamp=integer(p.get('updated_at_ms',0),0,253402300799000)
                        watched=datetime.fromtimestamp(stamp/1000,timezone.utc).isoformat() if stamp else None
                        pvals.append(dict(episode=integer(p['episode'],0),road=integer(p.get('road',0)),progress_ms=integer(p.get('progress_ms',0),0,10**12),watched_at=watched,import_key=pk,notes='Kazumi 最新进度快照；不代表完整看完或首次观看'))
                    tags=[t['name'] for t in b.get('tags',[]) if isinstance(t,dict) and isinstance(t.get('name'),str)]
                    images=b.get('images',{})
                    cover=next((images.get(k) for k in ('large','common','medium','small') if images.get(k)), '')
                    air=b.get('air_date','');yr=int(air[:4]) if len(air)>=4 and air[:4].isdigit() else None
                    vals=self.anime_values(dict(name=name,name_cn=b.get('name_cn',''),aliases=b.get('aliases',[]),cover=cover,
                       description=b.get('summary',''),release_year=yr,tags=tags,status='unreviewed'))
                    report['parsed']+=1
                    payload=js(h);sid='kazumi:'+hashlib.sha256(key.encode()).hexdigest()
                    source=c.execute('SELECT * FROM sources WHERE source_key=?',(key,)).fetchone()
                    if source and source['payload']==payload:
                        report['skipped']+=1;c.execute('RELEASE item');continue
                    if source:
                        previous=json.loads(source['payload'])
                        if previous['bangumi'].get('id')!=b.get('id'):
                            report['conflicts']+=1;report['details'].append({'index':index,'key':key,'reason':'相同来源 key 对应不同 Bangumi ID，已保留旧记录'});c.execute('RELEASE item');continue
                        previous_time=day(previous.get('last_watch_time'))
                        if previous_time and last and last<previous_time:
                            report['skipped']+=1;c.execute('RELEASE item');continue
                        aid=source['anime_id'];rid=source['round_id']
                        self.update(c,'rounds',rid,dict(progress=ep,last_watched_at=last))
                        self.update(c,'sources',source['id'],dict(payload=payload,imported_at=now()))
                        sid=source['id'];c.execute('DELETE FROM sessions WHERE source_id=?',(sid,));report['updated']+=1
                    else:
                        # Only globally scoped positive Bangumi IDs can join sources automatically.
                        # Missing IDs use the full History identity; names never determine identity.
                        match=c.execute('SELECT id FROM anime WHERE bangumi_id=? ORDER BY id',(bid,)).fetchall() if bid else []
                        if len(match)>1:
                            report['conflicts']+=1;report['details'].append({'index':index,'key':key,'reason':'多个候选条目拥有同一 Bangumi ID，需人工处理'});c.execute('RELEASE item');continue
                        aid=match[0][0] if match else ('bgm:'+str(bid) if bid else sid)
                        if not match:
                            vals.update(id=aid,series_id=None,bangumi_id=bid or None,created_at=now(),updated_at=now());self.insert(c,'anime',vals)
                        rid=sid+':snapshot'
                        self.insert(c,'rounds',dict(id=rid,anime_id=aid,kind='imported',status='unreviewed',progress=ep,started_at=None,finished_at=None,last_watched_at=last,notes='来源快照：首次/重看及开始结束日期未知',created_at=now()))
                        self.insert(c,'sources',dict(id=sid,source_key=key,anime_id=aid,round_id=rid,payload=payload,imported_at=now()));report['imported']+=1
                    for p in pvals:self.insert(c,'sessions',dict(id=sid+':'+p['import_key'],round_id=rid,source_id=sid,**p))
                    c.execute('RELEASE item')
                except (ValueError,TypeError,KeyError,OverflowError,sqlite3.IntegrityError,AttributeError) as e:
                    c.execute('ROLLBACK TO item');c.execute('RELEASE item')
                    report['errors']+=1;report['details'].append({'index':index,'reason':str(e)})
        return report
    def _validate_native(self,doc):
        if doc.get('format')!='animetracker-v1' or doc.get('schema_version')!=VERSION or set(doc.get('tables',{}))!=set(TABLES):raise ValueError('备份格式或版本不支持')
        ts=doc['tables']
        if any(not isinstance(ts[t],list) for t in TABLES) or sum(len(ts[t]) for t in TABLES)>200000:raise ValueError('备份表无效或过大')
        for r in ts['series']:
            if not text(r['name'],500):raise ValueError('系列名称为空')
        for r in ts['anime']:
            self.anime_values({**r,'tags':json.loads(r['tags']),'aliases':json.loads(r['aliases'])})
            integer(r['bangumi_id'],0,2147483647,True);day(r['created_at']);day(r['updated_at'])
        for r in ts['rounds']:self.round_values(r);day(r['created_at'])
        for r in ts['sessions']:
            integer(r['episode']);day(r['watched_at']);integer(r['progress_ms'],0,10**12,True);integer(r['road'],0,100000,True)
        for r in ts['sources']:
            if not text(r['source_key'],1000):raise ValueError('来源 key 为空')
            json.loads(r['payload']);day(r['imported_at'])
        # Validate full relational structure in a fresh database before touching real data.
        c=sqlite3.connect(':memory:');c.execute('PRAGMA foreign_keys=ON');c.executescript(SCHEMA)
        try:
            for table in TABLES:
                cols={r[1] for r in c.execute(f'PRAGMA table_info({table})')}
                for r in ts[table]:
                    if set(r)!=cols or not text(r['id'],1000):raise ValueError('备份列或主键不合法')
                    self.insert(c,table,r)
            for s in ts['sources']:
                r=c.execute('SELECT anime_id,kind FROM rounds WHERE id=?',(s['round_id'],)).fetchone()
                if not r or r[0]!=s['anime_id'] or r[1]!='imported':raise ValueError('来源与轮次关系无效')
            for s in ts['sessions']:
                if s['source_id']:
                    r=c.execute('SELECT round_id FROM sources WHERE id=?',(s['source_id'],)).fetchone()
                    if not r or r[0]!=s['round_id']:raise ValueError('来源与观看记录关系无效')
        finally:c.close()
    def import_native(self,doc):
        self._validate_native(doc)
        report=dict(imported=0,skipped=0,conflicts=0,errors=0,details=[])
        # A changed primary key is a conflict. Preserve existing manual edits.
        # Abort the entire merge on conflicts to prevent partial parent/child joins.
        with self.connect() as c:
            for t in TABLES:
                for r in doc['tables'][t]:
                    old=c.execute(f'SELECT * FROM {t} WHERE id=?',(r['id'],)).fetchone()
                    if old and dict(old)!=r: report['conflicts']+=1;report['details'].append({'table':t,'id':r['id'],'reason':'相同 ID 内容不同；整批未导入，请使用恢复功能替换完整备份'})
            if report['conflicts']:return report
            for t in TABLES:
                for r in doc['tables'][t]:
                    if c.execute(f'SELECT 1 FROM {t} WHERE id=?',(r['id'],)).fetchone(): report['skipped']+=1
                    else:self.insert(c,t,r);report['imported']+=1
        return report
    def import_doc(self,doc):
        if not isinstance(doc,dict):raise ValueError('JSON 根节点须为对象')
        return self.import_kazumi(doc) if doc.get('format')=='kazumi-history-v1' else self.import_native(doc)
    def export_csv(self):
        buf=io.StringIO(newline='');w=csv.writer(buf);w.writerow(['table','id','name','payload_json'])
        for t,rows in self.export()['tables'].items():
            for r in rows:w.writerow([t,r['id'],r.get('name',''),js(r)])
        return '\ufeff'+buf.getvalue()
    def export_list_csv(self,template=False):
        fields=['id','name','name_cn','series','season','release_year','status','total_episodes',
                'personal_rating','tags','aliases','cover','description','notes']
        buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=fields);writer.writeheader()
        if not template:
            state=self.state();series_names={r['id']:r['name'] for r in state['series']}
            for a in state['anime']:
                row={k:a.get(k,'') for k in fields}
                row['series']=series_names.get(a['series_id'],'')
                row['tags']=js(a['tags']);row['aliases']=js(a['aliases'])
                writer.writerow(row)
        return '\ufeff'+buf.getvalue()
    def import_csv(self,content):
        reader=csv.DictReader(io.StringIO(content.lstrip('\ufeff')))
        headers=reader.fieldnames or []
        if not headers:raise ValueError('CSV 缺少表头')
        if len(headers)!=len(set(headers)):raise ValueError('CSV 有重复列名')
        rows=[]
        for row in reader:
            if len(rows)>=200000:raise ValueError('CSV 过大')
            if None in row or any(v is None for v in row.values()):raise ValueError('CSV 行的列数与表头不一致')
            rows.append(row)
        if 'payload_json' not in headers:return self.import_list_csv(headers,rows)
        if set(headers)!={'table','id','name','payload_json'}:raise ValueError('完整备份 CSV 的表头无效')
        ts={t:[] for t in TABLES}
        for row in rows:
            t=row.get('table')
            if t not in TABLES or not row.get('payload_json'):raise ValueError('完整备份 CSV 的表名或内容无效')
            r=json.loads(row['payload_json'])
            if r.get('id')!=row.get('id'):raise ValueError('CSV ID 与数据不一致')
            ts[t].append(r)
        return self.import_native(dict(format='animetracker-v1',schema_version=VERSION,tables=ts))
    def import_list_csv(self,headers,rows):
        aliases={'编号':'id','ID':'id','名称':'name','中文名':'name_cn','系列':'series','季度':'season',
                 '年份':'release_year','状态':'status','总集数':'total_episodes','评分':'personal_rating',
                 '标签':'tags','别名':'aliases','封面':'cover','简介':'description','笔记':'notes'}
        allowed=set(['id','name','name_cn','series','season','release_year','status','total_episodes',
                     'personal_rating','tags','aliases','cover','description','notes'])
        mapped=[aliases.get(h.strip(),h.strip()) for h in headers]
        if len(mapped)!=len(set(mapped)):raise ValueError('CSV 多个列名指向同一字段')
        if set(mapped)-allowed:raise ValueError('不支持的 CSV 列：'+', '.join(sorted(set(mapped)-allowed)))
        if not {'id','name'}.issubset(mapped):raise ValueError('普通 CSV 至少需要 id（编号）和 name（名称）；每个季度使用独立且稳定的编号')
        status_names={'想看':'planned','正在看':'watching','已看完':'completed','暂停':'paused','弃番':'dropped','待整理':'unreviewed'}
        report=dict(raw=len(rows),parsed=0,imported=0,updated=0,skipped=0,conflicts=0,errors=0,details=[])
        with self.connect() as c:
            for number,row in enumerate(rows,start=2):
                c.execute('SAVEPOINT csv_row')
                try:
                    values={dest:row[src].strip() for src,dest in zip(headers,mapped)}
                    id=text(values.pop('id'),1000)
                    if not id:raise ValueError('编号不能为空；不能仅凭名称判断同一作品')
                    old_row=c.execute('SELECT * FROM anime WHERE id=?',(id,)).fetchone()
                    old=dict(old_row) if old_row else None
                    base=({**old,'tags':json.loads(old['tags']),'aliases':json.loads(old['aliases'])}
                          if old else {'status':'unreviewed'})
                    for k in ('tags','aliases'):
                        if k in values:
                            raw=values[k]
                            values[k]=sequence(json.loads(raw)) if raw.startswith('[') else sequence([x.strip() for x in re.split('[,，;；|]',raw) if x.strip()])
                    if 'status' in values:values['status']=status_names.get(values['status'],values['status']) or 'unreviewed'
                    normalized=self.anime_values({**base,**values})
                    series_id=old['series_id'] if old else None
                    series_name=values.get('series')
                    pending_series=None
                    if series_name is not None:
                        series_name=text(series_name,500)
                        match=c.execute('SELECT id FROM series WHERE name=? ORDER BY id',(series_name,)).fetchone() if series_name else None
                        series_id=match[0] if match else ('csv-series:'+hashlib.sha256(series_name.encode()).hexdigest() if series_name else None)
                        if series_id and not match:pending_series={'id':series_id,'name':series_name}
                    normalized['series_id']=series_id
                    report['parsed']+=1
                    if old:
                        if all(old[k]==v for k,v in normalized.items()):report['skipped']+=1
                        else:
                            report['conflicts']+=1;report['details'].append({'line':number,'id':id,'reason':'同一编号内容不同，保留现有资料；请在界面确认后编辑'})
                    else:
                        if pending_series:self.insert(c,'series',pending_series)
                        self.insert(c,'anime',dict(id=id,bangumi_id=None,created_at=now(),updated_at=now(),**normalized))
                        report['imported']+=1
                    c.execute('RELEASE csv_row')
                except (ValueError,TypeError,KeyError,sqlite3.IntegrityError) as e:
                    c.execute('ROLLBACK TO csv_row');c.execute('RELEASE csv_row')
                    report['errors']+=1;report['details'].append({'line':number,'reason':str(e)})
        return report
    def backup(self):
        directory=self.path.parent/'backups';directory.mkdir(exist_ok=True)
        target=directory/('anime_tracker_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]+'.db')
        with self.connect() as src:
            dest=sqlite3.connect(target)
            try:src.backup(dest)
            finally:dest.close()
        return target
    def restore(self,raw,confirm=False):
        if confirm is not True:raise ValueError('请确认恢复；当前数据库将自动备份后替换')
        if len(raw)>100*1024*1024 or not raw.startswith(b'SQLite format 3\x00'):raise ValueError('不是支持的 SQLite 备份')
        with tempfile.TemporaryDirectory(dir=self.path.parent) as td:
            candidate=Path(td)/'incoming.db';candidate.write_bytes(raw)
            c=sqlite3.connect(f'file:{candidate}?mode=ro',uri=True);c.row_factory=sqlite3.Row
            try:
                if c.execute('PRAGMA application_id').fetchone()[0]!=APP_ID or c.execute('PRAGMA user_version').fetchone()[0]!=VERSION:raise ValueError('不是 AnimeTracker 兼容备份')
                if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('备份完整性检查失败')
                with self.connect() as current:
                    expected=[tuple(r) for r in current.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
                actual=[tuple(r) for r in c.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
                if actual!=expected:raise ValueError('备份结构与当前版本不一致')
                doc=dict(format='animetracker-v1',schema_version=VERSION,tables={t:[dict(r) for r in c.execute(f'SELECT * FROM {t}')] for t in TABLES})
            finally:c.close()
            self._validate_native(doc)
            fresh=Store(Path(td)/'clean.db');fresh.import_native(doc)
            backup=self.backup()
            os.replace(fresh.path,self.path)
        return dict(restored=True,safety_backup=str(backup))
