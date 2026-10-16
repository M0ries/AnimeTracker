#!/usr/bin/env python3
"""Local-only HTTP application, no third-party Python packages required."""
import argparse, base64, json, secrets, sys, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from store import Store, defaults_path

STATIC=Path(__file__).parent/'static'

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args): pass
    def send(self,status,body,mime='application/json; charset=utf-8',filename=None):
        if isinstance(body,(dict,list)):body=json.dumps(body,ensure_ascii=False).encode()
        elif isinstance(body,str):body=body.encode()
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' https: http: data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        self.end_headers();self.wfile.write(body)
    def host_ok(self):
        port=self.server.server_address[1]
        return self.headers.get('Host') in (f'127.0.0.1:{port}',f'localhost:{port}')
    def do_GET(self):
        if not self.host_ok():self.send(403,{'error':'仅允许本机访问'});return
        path=urlparse(self.path).path
        try:
            if path=='/api/health':self.send(200,{'application':'AnimeTracker','version':'2.0.0','database_path':str(self.server.store.path.resolve())});return
            if path=='/api/export/list.csv':self.send(200,self.server.store.export_list_csv(),'text/csv; charset=utf-8','AnimeTracker-list.csv');return
            if path=='/api/template.csv':self.send(200,self.server.store.export_list_csv(template=True),'text/csv; charset=utf-8','AnimeTracker-template.csv');return
            if path=='/api/state': self.send(200,dict(self.server.store.state(),csrf_token=self.server.token));return
            if path=='/api/export/json':self.send(200,self.server.store.export(),filename='AnimeTracker-export.json');return
            if path=='/api/export/csv':self.send(200,self.server.store.export_csv(),'text/csv; charset=utf-8','AnimeTracker-export.csv');return
            assets={'/':('index.html','text/html; charset=utf-8'),
                    '/app.js':('app.js','text/javascript; charset=utf-8'),
                    '/style.css':('style.css','text/css; charset=utf-8'),
                    '/app-shell.css':('app-shell.css','text/css; charset=utf-8'),
                    '/minimal.css':('minimal.css','text/css; charset=utf-8'),
                    '/manifest.webmanifest':('manifest.webmanifest','application/manifest+json'),
                    '/icons/at.svg':('icons/at.svg','image/svg+xml')}
            for size in (32,180,192,512):
                assets[f'/icons/at-{size}.png']=(f'icons/at-{size}.png','image/png')
            asset=assets.get(path)
            if asset and (STATIC/asset[0]).is_file():
                self.send(200,(STATIC/asset[0]).read_bytes(),asset[1]);return
            self.send(404,{'error':'未找到页面'})
        except Exception as e:self.send(500,{'error':'读取失败：'+str(e)})
    def do_POST(self):
        if not self.host_ok() or not secrets.compare_digest(self.headers.get('X-AnimeTracker-Token',''),self.server.token):self.send(403,{'error':'请从本机页面操作'});return
        origin=self.headers.get('Origin')
        if origin and origin!=f'http://{self.headers.get("Host")}':self.send(403,{'error':'请求来源无效'});return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=140*1024*1024:raise ValueError('请求为空或超过 140MB')
            d=json.loads(self.rfile.read(size))
            if not isinstance(d,dict):raise ValueError('请求须为 JSON 对象')
            s=self.server.store;p=urlparse(self.path).path
            if p=='/api/anime/save': result={'id':s.save_anime(d.get('data',{}),d.get('id'))}
            elif p=='/api/round/save':result={'id':s.save_round(d['anime_id'],d.get('data',{}),d.get('id'))}
            elif p=='/api/session/edit':result={'id':s.edit_session(d['id'],d.get('data',{}))}
            elif p=='/api/session/add':result={'id':s.add_session(d['round_id'],d.get('data',{}))}
            elif p=='/api/delete':s.delete(d['table'],d['id'],d.get('confirm'));result={'deleted':True}
            elif p=='/api/batch':s.batch(d['ids'],d.get('status'),d.get('delete',False),d.get('confirm',False));result={'updated':True}
            elif p=='/api/merge':s.merge(d['source'],d['target'],d.get('confirm'));result={'merged':True}
            elif p=='/api/import/json':result=s.import_doc(d['document'])
            elif p=='/api/import/csv':result=s.import_csv(d['content'])
            elif p=='/api/backup':
                f=s.backup();result={'filename':f.name,'path':str(f),'base64':base64.b64encode(f.read_bytes()).decode()}
            elif p=='/api/restore':result=s.restore(base64.b64decode(d['base64'],validate=True),d.get('confirm',False))
            else:self.send(404,{'error':'未知操作'});return
            self.send(200,result)
        except (ValueError,TypeError,KeyError) as e:self.send(400,{'error':str(e)})
        except Exception as e:self.send(500,{'error':'操作失败，当前事务已回滚：'+str(e)})

def create_server(store,port=8765):
    server=HTTPServer(('127.0.0.1',port),Handler)
    server.store=store;server.token=secrets.token_urlsafe(32)
    return server

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);p.add_argument('--db');p.add_argument('--no-browser',action='store_true');p.add_argument('--import-json',type=Path)
    args=p.parse_args()
    database=Path(args.db) if args.db else defaults_path()/'anime_tracker.db'
    s=Store(database)
    if args.import_json:
        print(json.dumps(s.import_doc(json.loads(args.import_json.read_text())),ensure_ascii=False,indent=2));return
    try:server=create_server(s,args.port)
    except OSError:
        existing=f'http://127.0.0.1:{args.port}/'
        try:
            with urlopen(existing+'api/health',timeout=2) as response:health=json.load(response)
            if health.get('application')=='AnimeTracker' and health.get('database_path')==str(database.resolve()):
                print('AnimeTracker 已在运行：'+existing,flush=True)
                if not args.no_browser:webbrowser.open(existing)
                return
        except Exception:pass
        print('端口已被其他程序或不同资料库占用，请使用 --port 8766。');sys.exit(1)
    url=f'http://127.0.0.1:{server.server_address[1]}/'
    print(f'AnimeTracker 已启动：{url}\n数据库：{s.path}\n按 Control+C 退出。',flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
