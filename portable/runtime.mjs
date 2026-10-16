// All database mutations are serialized and only succeed after durable persistence.
export async function createRuntime({loadPyodide,indexURL,storeSource,apiSource,storage}) {
  const py=await loadPyodide({indexURL});
  py.FS.writeFile('/home/pyodide/store.py',storeSource);
  py.FS.writeFile('/home/pyodide/portable_api.py',apiSource);
  await py.runPythonAsync('import sys; sys.path.insert(0,"/home/pyodide")\nimport portable_api');
  let current=await storage.load();
  const setFiles=files=>{py.globals.set('_snapshot_json',JSON.stringify(files));py.runPython('portable_api.initialize_json(_snapshot_json)');};
  const getFiles=()=>JSON.parse(py.runPython('portable_api.snapshot_json()'));
  setFiles(current.files||{});
  if(!current.files?.['anime_tracker.db'])current=await storage.save(getFiles(),current.revision);
  const readOnly=new Set(['state','health','export/json','export/csv','export/list.csv','template.csv']);
  let queue=Promise.resolve();
  const call=(path,body={})=>{
    const task=queue.then(async()=>{
      const before=readOnly.has(path)?null:getFiles();
      try {
        py.globals.set('_request_json',JSON.stringify({path,body}));
        const result=JSON.parse(py.runPython('portable_api.handle_json(_request_json)'));
        if(before)current=await storage.save(getFiles(),current.revision);
        return result;
      } catch(error) {
        if(before)setFiles(before);
        throw error;
      }
    });
    queue=task.catch(()=>{});
    return task;
  };
  return {call,py};
}
