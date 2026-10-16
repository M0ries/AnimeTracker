import {loadPyodide} from './vendor/pyodide/pyodide.mjs';
import {createRuntime} from './runtime.mjs';
let id=0;
const pending=new Map();
function persist(method,payload={}){
  const requestId=++id;
  return new Promise((resolve,reject)=>{pending.set(requestId,{resolve,reject});postMessage({type:'storage',id:requestId,method,...payload});});
}
let runtime;
self.onmessage=async({data})=>{
  if(data.type==='storage-result'){
    const cb=pending.get(data.id);if(!cb)return;pending.delete(data.id);
    if(data.error)cb.reject(new Error(data.error));else cb.resolve(data.result);return;
  }
  if(data.type==='init'){
    try{
      const [storeSource,apiSource]=await Promise.all(['store.py','api.py'].map(async path=>{const r=await fetch(new URL(path,import.meta.url));if(!r.ok)throw Error('缺少应用文件：'+path);return r.text();}));
      runtime=await createRuntime({loadPyodide,indexURL:new URL('./vendor/pyodide/',import.meta.url).href,storeSource,apiSource,
        storage:{load:()=>persist('load'),save:(files,revision)=>persist('save',{files,revision})}});
      postMessage({type:'ready'});
    }catch(e){postMessage({type:'fatal',error:String(e)});}return;
  }
  if(data.type==='call'){
    try{const result=await runtime.call(data.path,data.body);postMessage({type:'result',id:data.id,result});}
    catch(e){postMessage({type:'result',id:data.id,error:String(e)});}
  }
};
