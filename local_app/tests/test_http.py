import base64,json,sys,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_server
from store import Store

class HTTPTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'http.db');self.server=create_server(self.store,0)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.url=f'http://127.0.0.1:{self.server.server_address[1]}'
 def tearDown(self):self.server.shutdown();self.thread.join();self.server.server_close();self.temp.cleanup()
 def get(self,path):
  with urllib.request.urlopen(self.url+path) as r:return r.status,r.headers,r.read()
 def post(self,path,data,token=True,**headers):
  h={'Content-Type':'application/json',**headers}
  if token:h['X-AnimeTracker-Token']=self.server.token
  req=urllib.request.Request(self.url+'/api/'+path,data=json.dumps(data).encode(),headers=h,method='POST')
  with urllib.request.urlopen(req) as r:return json.load(r)
 def test_static_and_state_headers(self):
  for path in ['/','/app.js','/style.css','/app-shell.css','/api/state','/icons/at.svg','/icons/at-32.png','/icons/at-180.png','/icons/at-192.png','/icons/at-512.png','/manifest.webmanifest']:
   code,headers,body=self.get(path);self.assertEqual(code,200);self.assertTrue(body);self.assertEqual(headers['X-Content-Type-Options'],'nosniff')
  data=json.loads(self.get('/api/state')[2]);self.assertEqual(data['csrf_token'],self.server.token)
 def test_manifest_icons_and_asset_boundaries(self):
  _,headers,body=self.get('/manifest.webmanifest')
  self.assertEqual(headers['Content-Type'],'application/manifest+json')
  manifest=json.loads(body);self.assertEqual(manifest['display'],'standalone')
  for asset in manifest['icons']:
   _,headers,data=self.get('/'+asset['src'].removeprefix('./'))
   self.assertEqual(headers['Content-Type'],'image/png');self.assertTrue(data.startswith(b'\x89PNG'))
  for path in ['/icons/../../store.py','/icons/AT.icns','/store.py']:
   with self.assertRaises(urllib.error.HTTPError) as error:self.get(path)
   self.assertEqual(error.exception.code,404)
 def test_csrf_and_origin_rejected(self):
  for kwargs in [{'token':False},{'Origin':'https://example.com'}]:
   with self.assertRaises(urllib.error.HTTPError) as ctx:self.post('backup',{},**kwargs)
   self.assertEqual(ctx.exception.code,403)
 def test_http_complete_workflow(self):
  a=self.post('anime/save',{'data':{'name':'HTTP 动漫','total_episodes':12}})['id']
  r=self.post('round/save',{'anime_id':a,'data':{'kind':'first','status':'watching','progress':1,'started_at':'2026-01-01'}})['id']
  self.post('session/add',{'round_id':r,'data':{'episode':2,'watched_at':'2026-01-02'}})
  doc=json.loads(self.get('/api/export/json')[2]);self.assertEqual(len(doc['tables']['sessions']),1)
  self.assertIn('payload_json',self.get('/api/export/csv')[2].decode())
  self.assertIn('total_episodes',self.get('/api/template.csv')[2].decode())
  self.assertIn('HTTP 动漫',self.get('/api/export/list.csv')[2].decode())
  edited=self.post('session/edit',{'id':doc['tables']['sessions'][0]['id'],'data':{'episode':2,'watched_at':'2026-01-03','notes':'修正'}})
  self.assertEqual(edited['id'],doc['tables']['sessions'][0]['id'])
  health=json.loads(self.get('/api/health')[2]);self.assertEqual(health['application'],'AnimeTracker')
  backup=self.post('backup',{});self.post('delete',{'table':'anime','id':a,'confirm':True})
  restored=self.post('restore',{'base64':backup['base64'],'confirm':True});self.assertTrue(restored['restored'])
  state=json.loads(self.get('/api/state')[2]);self.assertEqual(len(state['anime']),1);self.assertEqual(state['rounds'][0]['progress'],2)
 def test_bad_validation_returns_400(self):
  with self.assertRaises(urllib.error.HTTPError) as e:self.post('anime/save',{'data':{'name':''}})
  self.assertEqual(e.exception.code,400)
if __name__=='__main__':unittest.main()
