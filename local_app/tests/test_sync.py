import tempfile, unittest
from pathlib import Path
from store import Store

class SyncTests(unittest.TestCase):
 def test_remote_replace_validates_and_saves_local_backup(self):
  with tempfile.TemporaryDirectory() as folder:
   a=Store(Path(folder)/'local.db');b=Store(Path(folder)/'remote.db')
   before=a.export();b.save_anime({'name':'remote','status':'watching'})
   result=a.sync_replace(b.export(),before)
   self.assertEqual(a.state()['anime'][0]['name'],'remote')
   self.assertTrue(Path(result['safety_backup']).exists())
   before=a.export();a.save_anime({'name':'later'},a.state()['anime'][0]['id'])
   with self.assertRaises(ValueError):a.sync_replace(b.export(),before)
   self.assertEqual(a.state()['anime'][0]['name'],'later')
