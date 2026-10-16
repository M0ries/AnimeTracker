import json,os,subprocess,sys,tempfile,time,unittest,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from store import Store
APP=Path(__file__).resolve().parents[1]/'app.py'
class StartupTests(unittest.TestCase):
 def test_clean_start_and_existing_database_persist(self):
  with tempfile.TemporaryDirectory() as td:
   env=dict(os.environ,ANIMETRACKER_DATA_DIR=td)
   def launch():
    proc=subprocess.Popen([sys.executable,str(APP),'--port','0','--no-browser'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
     line=proc.stdout.readline();url=line.split('http://',1)[1].strip()
     with urllib.request.urlopen('http://'+url+'api/state',timeout=5) as r:return json.load(r)
    finally:
     proc.terminate();proc.communicate(timeout=5)
   state=launch();self.assertEqual(len(state['anime']),0);self.assertEqual(len(state['sources']),0)
   store=Store(Path(td)/'anime_tracker.db');aid=store.save_anime({'name':'Synthetic saved item'})
   state=launch();self.assertEqual(state['anime'][0]['id'],aid)
   store.batch([aid],delete=True,confirm=True)
   state=launch();self.assertEqual(len(state['anime']),0)
if __name__=='__main__':unittest.main()
