import csv,io,json,subprocess,sys,tempfile,threading,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_server
from store import Store
from fixtures import history
APP=Path(__file__).resolve().parents[1]/'app.py'
class FollowupTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.s=Store(Path(self.temp.name)/'a.db')
 def tearDown(self):self.temp.cleanup()
 def test_edit_session_keeps_identity_and_other_round(self):
  a=self.s.save_anime({'name':'测试','total_episodes':12})
  r=self.s.save_round(a,{'kind':'first','status':'watching','progress':0,'started_at':'2026-01-01'})
  sess=self.s.add_session(r,{'episode':3,'watched_at':'2026-01-03'})
  other=self.s.save_round(a,{'kind':'rewatch','status':'watching','progress':1,'started_at':'2026-08-01'})
  self.s.edit_session(sess,{'episode':2,'watched_at':'2026-01-02','notes':'纠正日期'})
  st=self.s.state();self.assertEqual(len(st['sessions']),1);self.assertEqual(st['sessions'][0]['id'],sess);self.assertEqual(st['sessions'][0]['episode'],2)
  rounds={x['id']:x for x in st['rounds']};self.assertEqual(rounds[r]['last_watched_at'],'2026-01-02');self.assertEqual(rounds[r]['progress'],3);self.assertEqual(rounds[other]['started_at'],'2026-08-01')
 def test_edit_session_validation_is_atomic(self):
  a=self.s.save_anime({'name':'测试','total_episodes':12});r=self.s.save_round(a,{'kind':'first','status':'watching','progress':0,'started_at':'2026-01-01'})
  sid=self.s.add_session(r,{'episode':1,'watched_at':'2026-01-02'});before=self.s.export()['tables']
  for values in [{'episode':13},{'episode':1,'watched_at':'2025-01-01'}]:
   with self.assertRaises(ValueError):self.s.edit_session(sid,values)
  self.assertEqual(before,self.s.export()['tables'])
 def test_imported_session_cannot_be_edited(self):
  doc={'format':'kazumi-history-v1','histories':[history()]};self.s.import_doc(doc);sid=self.s.state()['sessions'][0]['id']
  with self.assertRaises(ValueError):self.s.edit_session(sid,{'episode':1})
 def test_plain_csv_chinese_headers_and_repeat(self):
  content='编号,名称,系列,季度,状态,评分,标签,总集数\ns1,同名作品,系列A,第一季,已看完,8.5,奇幻;校园,12\ns2,同名作品,系列A,第二季,正在看,,奇幻,12\n'
  r=self.s.import_csv(content);self.assertEqual(r['imported'],2);state=self.s.state();self.assertEqual(len(state['series']),1);self.assertEqual(len(state['anime']),2)
  self.assertEqual(state['anime'][0]['tags'],['奇幻','校园']);self.assertEqual(state['anime'][0]['personal_rating'],8.5)
  self.assertEqual(self.s.import_csv(content)['skipped'],2)
 def test_same_id_changed_csv_does_not_overwrite(self):
  self.s.import_csv('id,name,notes\na,作品,保留\n')
  r=self.s.import_csv('id,name,notes\na,作品,替换\n');self.assertEqual(r['conflicts'],1);self.assertEqual(self.s.state()['anime'][0]['notes'],'保留')
 def test_csv_missing_id_unsupported_columns_and_malformed(self):
  for content in ['name\n作品\n','id,name,unknown\na,作品,x\n','id,name\na,作品,extra\n','id,编号,name\na,b,作品\n','id,name,id\na,作品,b\n']:
   with self.assertRaises(ValueError):self.s.import_csv(content)
  self.assertEqual(len(self.s.state()['anime']),0)
 def test_bad_row_keeps_good_rows_and_no_series_orphans(self):
  r=self.s.import_csv('id,name,series,personal_rating\na,作品,系列A,99\nb,另一部,系列B,8\n')
  self.assertEqual(r['errors'],1);self.assertEqual(r['imported'],1);self.assertEqual(r['details'][0]['line'],2);self.assertEqual([s['name'] for s in self.s.state()['series']],['系列B'])
 def test_plain_list_export_roundtrip_and_partial_columns(self):
  self.s.save_anime({'name':'作品,带逗号','aliases':['别名;分号','别名2'],'tags':['a,b','c;d'],'notes':'第一行\n第二行','series_name':'测试系列','personal_rating':8.5})
  content=self.s.export_list_csv();other=Store(Path(self.temp.name)/'b.db');report=other.import_csv(content);self.assertEqual(report['imported'],1)
  a=other.state()['anime'][0];self.assertEqual(a['tags'],['a,b','c;d']);self.assertEqual(a['aliases'],['别名;分号','别名2']);self.assertEqual(a['notes'],'第一行\n第二行')
  self.assertEqual(self.s.import_csv(content)['skipped'],1)
  buf=io.StringIO();w=csv.writer(buf);w.writerow(['id','name']);w.writerow([a['id'],a['name']]);self.assertEqual(other.import_csv(buf.getvalue())['skipped'],1)
 def test_template_has_no_fake_rows(self):
  template=self.s.export_list_csv(template=True);self.assertEqual(list(csv.DictReader(io.StringIO(template.lstrip('\ufeff')))),[])
  self.assertEqual(self.s.import_csv(template)['imported'],0)
 def test_reopening_same_local_database_uses_existing_server(self):
  server=create_server(self.s,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   result=subprocess.run([sys.executable,str(APP),'--port',str(server.server_address[1]),'--db',str(self.s.path),'--no-browser'],capture_output=True,text=True,timeout=5)
   self.assertEqual(result.returncode,0);self.assertIn('已在运行',result.stdout)
   different=subprocess.run([sys.executable,str(APP),'--port',str(server.server_address[1]),'--db',str(Path(self.temp.name)/'different.db'),'--no-browser'],capture_output=True,text=True,timeout=5)
   self.assertEqual(different.returncode,1);self.assertIn('不同资料库',different.stdout)
  finally:server.shutdown();thread.join();server.server_close()
if __name__=='__main__':unittest.main()
