/* Offline shell only. User records stay in IndexedDB; they are never cached by this worker. */
const VERSION='animetracker-static-2.0.2';
const ASSETS=['./','./index.html','./bridge.mjs','./worker.mjs','./runtime.mjs','./storage.mjs','./api.py','./store.py','./app.js','./style.css','./app-shell.css','./minimal.css','./manifest.webmanifest','./icons/at.svg','./icons/at-32.png','./icons/at-180.png','./icons/at-192.png','./icons/at-512.png','./vendor/pyodide/pyodide.mjs','./vendor/pyodide/pyodide.asm.mjs','./vendor/pyodide/pyodide.asm.wasm','./vendor/pyodide/python_stdlib.zip','./vendor/pyodide/pyodide-lock.json'];
self.addEventListener('install',event=>event.waitUntil((async()=>{
  const cache=await caches.open(VERSION);
  try{await cache.addAll(ASSETS);await self.skipWaiting();}
  catch(error){await caches.delete(VERSION);throw error;}
})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{
  for(const key of await caches.keys())if(key.startsWith('animetracker-static-')&&key!==VERSION)await caches.delete(key);
  await self.clients.claim();
})()));
const files=new Set(ASSETS.map(asset=>new URL(asset,self.registration.scope).pathname));
self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET')return;
  const url=new URL(event.request.url);
  if(url.origin!==self.location.origin||url.pathname.includes('/api/'))return;
  const path=event.request.mode==='navigate'?new URL('./index.html',self.registration.scope).pathname:url.pathname;
  if(!files.has(path))return;
  event.respondWith((async()=>{
    const cache=await caches.open(VERSION);
    const hit=await cache.match(new URL(path,self.location.origin).href);
    if(hit)return hit;
    return fetch(event.request);
  })());
});
