import copy, tempfile, unittest
from pathlib import Path
from store import Store

class SnapshotTests(unittest.TestCase):
 def test_import_repeat_and_personal_records(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(Path(d)/'test.db')
   doc={'schemaVersion':1,'histories':[{'bangumiItem':{'id':123,'name':'Test','nameCn':'测试','images':{},'alias':[]},'adapterName':'source','entryKind':'online','lastWatchTime':1700000000000,'lastWatchEpisode':2,'progresses':{'2':{'episode':2,'progressMs':1200,'updatedAtMs':1700000000000}}}]}
   self.assertEqual(s.import_doc(doc)['imported'],1)
   self.assertEqual(s.import_doc(doc)['skipped'],1)
   a=s.state()['anime'][0];a['notes']='keep';s.save_anime(a,a['id'])
   s.save_round(a['id'],{'kind':'rewatch','status':'watching','progress':1})
   doc['histories'][0]['lastWatchEpisode']=3;doc['histories'][0]['lastWatchTime']+=1000
   self.assertEqual(s.import_doc(doc)['updated'],1)
   self.assertEqual(s.state()['anime'][0]['notes'],'keep')
   self.assertEqual([r['progress'] for r in s.state()['rounds'] if r['kind']=='rewatch'],[1])
   doc['schemaVersion']=2
   with self.assertRaises(ValueError):s.import_doc(doc)
   doc['schemaVersion']=1;doc['histories'].append(copy.deepcopy(doc['histories'][0]))
   with self.assertRaises(ValueError):s.import_doc(doc)
