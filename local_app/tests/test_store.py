import copy, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from store import Store
from fixtures import history

class StoreTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.s=Store(Path(self.temp.name)/'a.db')
 def tearDown(self):self.temp.cleanup()
 def a(self,name='无职转生 第一季',**kw):return self.s.save_anime(dict(name=name,total_episodes=12,tags=['奇幻'],series_name='无职转生',**kw))
 def r(self,aid,**kw):return self.s.save_round(aid,dict(kind='first',status='watching',progress=0,**kw))
 def history(self,key='A123::online',bid=123,name='第一季'):
  return {'history_key':key,'hive_key':key,'bangumi':{'id':bid,'name':name,'name_cn':name,'images':{},'tags':[],'aliases':[],'summary':'','air_date':'2026-01-01'},'last_watch_episode':2,'last_watch_time':'2026-01-03T00:00:00Z','progresses':[{'key':1,'episode':1,'road':0,'progress_ms':10000,'updated_at_ms':0}]}
 def imp(self,*hs):return self.s.import_doc({'format':'kazumi-history-v1','histories':list(hs)})
 def test_add_edit_rating_tags_and_persistence(self):
  a=self.a();self.s.save_anime({'name':'改名','personal_rating':8.5,'tags':['科幻'],'aliases':['别名'],'notes':'我的评论'},a)
  saved=Store(self.s.path).state()['anime'][0]
  self.assertEqual(saved['personal_rating'],8.5);self.assertEqual(saved['tags'],['科幻']);self.assertEqual(saved['aliases'],['别名'])
 def test_bangumi_id_for_manual_anime_and_imported_source(self):
  a=self.a(bangumi_id='123')
  self.assertEqual(self.s.state()['anime'][0]['bangumi_id'],123)
  self.s.save_anime({'name':'改名'},a)
  self.assertEqual(self.s.state()['anime'][0]['bangumi_id'],123)
  with self.assertRaisesRegex(ValueError,'已用于另一部动漫'):
   self.a('重复 ID',bangumi_id='123')
  self.assertEqual(self.imp(self.history())['imported'],1)
  self.assertEqual(len(self.s.state()['anime']),1)
  with self.assertRaisesRegex(ValueError,'不可修改'):
   self.s.save_anime({'name':'改名','bangumi_id':'456'},a)
  self.assertEqual(self.s.state()['anime'][0]['bangumi_id'],123)
 def test_bangumi_metadata_fills_blanks_without_touching_personal_records(self):
  a=self.s.save_anime({'name':'我的标题','bangumi_id':123,'notes':'私人笔记','status':'watching','personal_rating':9})
  r=self.r(a);self.s.add_session(r,{'episode':1})
  subject={'id':123,'type':2,'name':'原名','name_cn':'中文名','summary':'作品简介','date':'2026-01-01','eps':12,'images':{'large':'https://example.org/cover.jpg'}}
  self.assertEqual(set(self.s.update_bangumi(a,subject)['updated']),{'name_cn','description','release_year','total_episodes','cover'})
  row=self.s.state()['anime'][0]
  self.assertEqual((row['name'],row['notes'],row['status'],row['personal_rating']),('我的标题','私人笔记','watching',9))
  self.assertEqual(len(self.s.state()['sessions']),1)
  self.assertEqual(self.s.update_bangumi(a,subject)['updated'],[])
  with self.assertRaisesRegex(ValueError,'ID 不一致'):
   self.s.update_bangumi(a,{**subject,'id':456})
  with self.assertRaisesRegex(ValueError,'不是动画'):
   self.s.update_bangumi(a,{**subject,'type':1})
 def test_search_selection_creates_and_links_without_overwriting_records(self):
  subject={'id':140001,'type':2,'name':'Re:ゼロ','name_cn':'从零开始','date':'2016-04-03','eps':25,
           'summary':'作品简介','images':{'large':'https://example.org/re0.jpg'}}
  aid=self.s.save_bangumi(subject)['id']
  created=self.s.state()['anime'][0]
  self.assertEqual((created['bangumi_id'],created['release_year'],created['total_episodes']),(140001,2016,25))
  self.assertEqual(created['name_cn'],'从零开始')
  with self.assertRaisesRegex(ValueError,'已用于另一部动漫'):
   self.s.save_bangumi(subject)
  manual=self.s.save_anime({'name':'我起的名字','notes':'保留','personal_rating':8,'status':'completed'})
  rid=self.s.save_round(manual,{'kind':'first','status':'completed','progress':2})
  self.s.save_bangumi({**subject,'id':140002},manual)
  row=next(x for x in self.s.state()['anime'] if x['id']==manual)
  self.assertEqual((row['name'],row['notes'],row['personal_rating'],row['status']),('我起的名字','保留',8,'completed'))
  self.assertEqual(row['bangumi_id'],140002)
  self.assertEqual(len([x for x in self.s.state()['rounds'] if x['anime_id']==manual]),1)
  with self.assertRaisesRegex(ValueError,'已有不同'):
   self.s.save_bangumi({**subject,'id':140003},manual)
  with self.assertRaisesRegex(ValueError,'不是动画'):
   self.s.save_bangumi({**subject,'type':1})
  self.assertEqual(len(self.s.state()['anime']),2)
 def test_seasons_share_series_but_not_identity(self):
  a=self.a();b=self.a('无职转生 第二季');state=self.s.state()
  self.assertNotEqual(a,b);self.assertEqual(len(state['series']),1);self.assertEqual(state['stats']['works'],1);self.assertEqual(state['stats']['seasons'],2)
 def test_rewatch_preserves_original_dates_and_records(self):
  a=self.a();r1=self.s.save_round(a,dict(kind='first',status='completed',progress=12,started_at='2026-01-01',finished_at='2026-01-05'))
  r2=self.s.save_round(a,dict(kind='rewatch',status='watching',progress=2,started_at='2026-08-10'))
  self.s.add_session(r2,dict(episode=3,watched_at='2026-08-12'))
  rr={r['id']:r for r in self.s.state()['rounds']}
  self.assertEqual(rr[r1]['finished_at'],'2026-01-05');self.assertEqual(rr[r1]['progress'],12);self.assertEqual(rr[r2]['progress'],3)
  self.assertEqual(self.s.state()['stats']['rewatches'],1)
 def test_edit_older_round_does_not_change_current_status(self):
  a=self.a();r1=self.r(a);r2=self.s.save_round(a,dict(kind='rewatch',status='paused',progress=2))
  self.s.save_round(a,dict(kind='first',status='completed',progress=12,finished_at='2026-01-05'),r1)
  self.assertEqual(self.s.state()['anime'][0]['status'],'paused')
 def test_invalid_inputs_and_dates_are_atomic(self):
  for val in [-1,11,float('nan'),float('inf'),True]:
   with self.assertRaises(ValueError):self.a(personal_rating=val)
  a=self.a()
  for data in [dict(started_at='2026-08-10',finished_at='2026-01-01'),dict(started_at='bad'),dict(progress=13),dict(progress=-1)]:
   with self.assertRaises(ValueError):self.s.save_round(a,dict(kind='first',status='watching',**data))
  self.assertEqual(len(self.s.state()['rounds']),0)
 def test_same_title_different_subjects_not_merged(self):
  self.imp(self.history(bid=123),self.history(key='A456::online',bid=456))
  self.assertEqual(len(self.s.state()['anime']),2)
 def test_multiple_sources_same_subject_and_idempotence(self):
  hs=[self.history(),self.history(key='B123::online')]
  r=self.imp(*hs);self.assertEqual(r['imported'],2);self.assertEqual(len(self.s.state()['anime']),1)
  r=self.imp(*hs);self.assertEqual(r['skipped'],2);self.assertEqual(len(self.s.state()['rounds']),2)
  self.assertEqual(self.s.state()['stats']['rewatches'],0);self.assertEqual(self.s.state()['stats']['rounds'],0)
 def test_unknown_dates_preserved(self):
  self.imp(self.history());state=self.s.state()
  self.assertIsNone(state['rounds'][0]['started_at']);self.assertIsNone(state['rounds'][0]['finished_at']);self.assertIsNone(state['sessions'][0]['watched_at'])
  self.assertEqual(state['anime'][0]['status'],'unreviewed')
 def test_missing_subject_does_not_merge_on_title(self):
  self.imp(self.history(bid=None),self.history(key='B123::online',bid=None));self.assertEqual(len(self.s.state()['anime']),2)
 def test_update_snapshot_does_not_overwrite_manual_edits(self):
  h=self.history();self.imp(h);a=self.s.state()['anime'][0];self.s.save_anime(dict(name='我的改名',notes='重要',personal_rating=9),a['id'])
  h['last_watch_episode']=5;h['last_watch_time']='2026-02-01T00:00:00Z'
  self.assertEqual(self.imp(h)['updated'],1);self.assertEqual(self.s.state()['anime'][0]['notes'],'重要');self.assertEqual(self.s.state()['rounds'][0]['progress'],5)
  older=self.history();self.assertEqual(self.imp(older)['skipped'],1)
 def test_source_identity_conflict(self):
  self.imp(self.history());r=self.imp(self.history(bid=456))
  self.assertEqual(r['conflicts'],1);self.assertEqual(self.s.state()['anime'][0]['bangumi_id'],123)
 def test_bad_history_does_not_block_good_history(self):
  bad=self.history(key='bad');bad['progresses'][0]['episode']='invalid'
  r=self.imp(bad,self.history());self.assertEqual(r['errors'],1);self.assertEqual(r['imported'],1);self.assertEqual(len(self.s.state()['anime']),1)
 def test_json_roundtrip_complete_and_repeat(self):
  a=self.a();r=self.r(a);self.s.add_session(r,dict(episode=1,watched_at='2026-01-01'));self.imp(self.history())
  doc=self.s.export();other=Store(Path(self.temp.name)/'other.db');other.import_doc(doc)
  self.assertEqual(other.export()['tables'],doc['tables']);r=other.import_doc(doc);self.assertEqual(r['imported'],0)
 def test_csv_full_roundtrip(self):
  self.a(name='含逗号,换行\n与引号"');self.imp(self.history())
  other=Store(Path(self.temp.name)/'b.db');other.import_csv(self.s.export_csv());self.assertEqual(other.export()['tables'],self.s.export()['tables'])
 def test_json_conflict_is_all_or_nothing(self):
  a=self.a();doc=self.s.export();doc['tables']['anime'][0]['notes']='改变';doc['tables']['series'].append(dict(id='new',name='New'))
  r=self.s.import_doc(doc);self.assertEqual(r['conflicts'],1);self.assertEqual(len(self.s.state()['series']),1);self.assertNotEqual(self.s.state()['anime'][0]['notes'],'改变')
 def test_invalid_native_relationship_rolls_back(self):
  a=self.a();doc=self.s.export();doc['tables']['anime'][0]['series_id']='missing'
  with self.assertRaises(Exception):self.s.import_doc(doc)
  self.assertEqual(len(self.s.state()['anime']),1)
 def test_backup_restore_and_restore_safety_backup(self):
  a=self.a();self.imp(self.history());before=self.s.export()['tables'];backup=self.s.backup();self.a('新增')
  result=self.s.restore(backup.read_bytes(),True)
  self.assertTrue(Path(result['safety_backup']).exists());self.assertEqual(self.s.export()['tables'],before)
  self.assertEqual(len(Store(result['safety_backup']).state()['anime']),3)
 def test_bad_restore_does_not_touch_database(self):
  self.a();before=self.s.export()['tables']
  for raw in [b'not db',b'SQLite format 3\x00invalid']:
   with self.assertRaises(Exception):self.s.restore(raw,True)
  self.assertEqual(self.s.export()['tables'],before)
 def test_manual_merge_preserves_metadata_and_import_identity(self):
  self.imp(self.history(),self.history(key='B456::online',bid=456,name='第二季'))
  aa=self.s.state()['anime'];source,target=aa[0]['id'],aa[1]['id'];self.s.merge(source,target,True)
  state=self.s.state();self.assertEqual(len(state['anime']),1);self.assertEqual(len(state['sources']),2);self.assertIn('人工合并',state['anime'][0]['notes'])
  self.assertEqual(self.imp(self.history())['skipped'],1)
 def test_delete_confirmation_and_cascade(self):
  self.imp(self.history());a=self.s.state()['anime'][0]['id']
  with self.assertRaises(ValueError):self.s.delete('anime',a)
  self.s.delete('anime',a,True);state=self.s.state()
  for key in ['anime','rounds','sources','sessions']:self.assertEqual(state[key],[])
 def test_batch_transaction_and_status(self):
  a=self.a();b=self.a('第二季');self.s.batch([a,b],'completed');self.assertTrue(all(x['status']=='completed' for x in self.s.state()['anime']))
  with self.assertRaises(ValueError):self.s.batch([a,'missing'],delete=True,confirm=True)
  self.assertEqual(len(self.s.state()['anime']),2)
 def test_synthetic_bulk_history(self):
  doc={'format':'kazumi-history-v1','histories':[history(i) for i in range(369)]}
  r=self.s.import_doc(doc);self.assertEqual(r['raw'],369);self.assertEqual(r['imported'],369);self.assertEqual(r['errors'],0)
  state=self.s.state();self.assertEqual(len(state['anime']),191);self.assertEqual(len(state['sessions']),369)
  self.assertEqual(self.s.import_doc(doc)['skipped'],369)
  self.assertEqual(len(self.s.state()['sessions']),369)
if __name__=='__main__':unittest.main()
