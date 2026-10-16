import {BrowserStorage,NativeStorage} from './storage.mjs';
const native=Boolean(window.__TAURI__?.core);
const storage=native?new NativeStorage():new BrowserStorage();
const worker=new Worker(new URL('./worker.mjs',import.meta.url),{type:'module'});
const calls=new Map();let counter=0;
let readyResolve,readyReject;
const ready=new Promise((resolve,reject)=>{readyResolve=resolve;readyReject=reject;});
worker.onerror=event=>{const error=new Error(event.message||'应用运行环境无法启动');readyReject(error);for(const cb of calls.values())cb.reject(error);calls.clear();};
worker.onmessage=async({data})=>{
  if(data.type==='ready')readyResolve();
  else if(data.type==='fatal')readyReject(new Error(data.error));
  else if(data.type==='result'){
    const cb=calls.get(data.id);if(!cb)return;calls.delete(data.id);
    if(data.error)cb.reject(new Error(data.error));else cb.resolve(data.result);
  } else if(data.type==='storage'){
    try{const result=data.method==='load'?await storage.load():await storage.save(data.files,data.revision);worker.postMessage({type:'storage-result',id:data.id,result});}
    catch(e){worker.postMessage({type:'storage-result',id:data.id,error:String(e)});}
  }
};
worker.postMessage({type:'init'});
async function call(path,body){await ready;const id=++counter;return new Promise((resolve,reject)=>{calls.set(id,{resolve,reject});worker.postMessage({type:'call',id,path,body});});}
const originalFetch=window.fetch.bind(window);
window.fetch=async(resource,options={})=>{
  const url=new URL(typeof resource==='string'?resource:resource.url,location.href);
  if(url.origin===location.origin&&url.pathname.includes('/api/')){
    const path=url.pathname.split('/api/')[1];
    try{const result=await call(path,options.body?JSON.parse(options.body):{});return new Response(JSON.stringify(result),{headers:{'Content-Type':'application/json'}});}
    catch(e){return new Response(JSON.stringify({error:String(e)}),{status:400,headers:{'Content-Type':'application/json'}});}
  }
  return originalFetch(resource,options);
};
window.ATPlatform={
  async confirm(message){return native?window.__TAURI__.dialog.ask(message,{title:'AnimeTracker',kind:'warning'}):window.confirm(message);},
  async chooseFile(accept){
    if(!native)return null;
    const path=await window.__TAURI__.dialog.open({multiple:false,directory:false,filters:[{name:'AnimeTracker',extensions:accept.split(',').map(s=>s.trim().replace(/^\./,''))}]});
    if(!path)return null;
    const bytes=await window.__TAURI__.fs.readFile(path);
    return new File([bytes],String(path).split('/').at(-1)||'import');
  },
  native,
  async save(bytes,name,mime='application/octet-stream'){
    if(native){
      const path=await window.__TAURI__.dialog.save({defaultPath:name,filters:[{name:'AnimeTracker',extensions:[name.split('.').at(-1)]}]});
      if(path)await window.__TAURI__.fs.writeFile(path,bytes);
      return Boolean(path);
    }
    const file=new File([bytes],name,{type:mime});
    if(navigator.canShare?.({files:[file]})){
      try{await navigator.share({files:[file],title:name});return true;}catch(e){if(e.name==='AbortError')return false;}
    }
    const url=URL.createObjectURL(file),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);return true;
  }
};
document.addEventListener('click',async event=>{
  const anchor=event.target.closest('a[download]');if(!anchor)return;
  const url=new URL(anchor.href);if(!url.pathname.includes('/api/'))return;
  event.preventDefault();
  try{const result=await call(url.pathname.split('/api/')[1]);await window.ATPlatform.save(new TextEncoder().encode(result.content),result.filename,result.mime);}
  catch(e){document.querySelector('#toast').textContent=String(e);document.querySelector('#toast').style.display='block';}
},true);
// Load the existing UI only after the bridge is installed. Database init may continue in the worker.
const script=document.createElement('script');script.src=new URL('./app.js',import.meta.url).href;document.head.append(script);
if(!native&&navigator.storage?.persist)navigator.storage.persist().catch(()=>{});
if(!native&&'serviceWorker' in navigator&&location.protocol==='https:'){
  navigator.serviceWorker.register(new URL('./sw.js',import.meta.url),{scope:'./'}).catch(()=>{});
}
