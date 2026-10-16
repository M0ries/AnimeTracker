"""Regression tests for a missing/broken macOS login-shell PATH."""
import json,os,selectors,shutil,subprocess,tempfile,unittest,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class LauncherTests(unittest.TestCase):
 def launch(self,relative=False):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'Folder with spaces';root.mkdir()
   shutil.copytree(ROOT/'local_app',root/'local_app',ignore=shutil.ignore_patterns('__pycache__'))
   shutil.copy2(ROOT/'Start-AnimeTracker.command',root/'Start-AnimeTracker.command')
   env=dict(os.environ,PATH='/deliberately/missing',ANIMETRACKER_DATA_DIR=str(Path(td)/'data'))
   script='Start-AnimeTracker.command' if relative else str(root/'Start-AnimeTracker.command')
   proc=subprocess.Popen(['/bin/bash',script,'--port','0','--no-browser'],cwd=root if relative else '/',env=env,
                         stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
   try:
    selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
    try:
     self.assertTrue(selector.select(8),'Launcher did not report startup')
     line=proc.stdout.readline()
    finally:selector.close()
    self.assertIn('http://127.0.0.1:',line)
    url='http://'+line.split('http://',1)[1].strip()
    with urllib.request.urlopen(url+'api/health',timeout=5) as response:health=json.load(response)
    self.assertEqual(health['application'],'AnimeTracker')
    self.assertEqual(health['database_path'],str(Path(td)/'data/anime_tracker.db'))
   finally:
    import signal
    os.killpg(proc.pid,signal.SIGTERM)
    stdout,stderr=proc.communicate(timeout=5)
   self.assertNotIn('dirname: command not found',stderr)
   self.assertNotIn("can't open file",stderr)
 def test_absolute_launcher_broken_path_and_different_cwd(self):self.launch()
 def test_relative_launcher_broken_path_and_spaces(self):self.launch(relative=True)
 def test_exporter_broken_path_can_cancel_without_touching_data(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'With spaces';root.mkdir()
   fake=root/'bin';fake.mkdir();dart=fake/'dart';dart.write_text('#!/bin/bash\nexit 0\n');dart.chmod(0o755)
   shutil.copy2(ROOT/'Export-Kazumi.command',root/'Export-Kazumi.command')
   env=dict(os.environ,PATH=str(fake))
   r=subprocess.run(['/bin/bash',str(root/'Export-Kazumi.command')],cwd='/',env=env,input='no\n',capture_output=True,text=True,timeout=5)
   self.assertEqual(r.returncode,0);self.assertIn('先完全退出 Kazumi',r.stdout);self.assertNotIn('command not found',r.stderr)
if __name__=='__main__':unittest.main()
