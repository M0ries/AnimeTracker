import assert from 'node:assert/strict';
import worker from './kazumi-webdav-worker.mjs';
const origin='https://m0ries.github.io';
const original=globalThis.fetch;let upstream;
try{
 globalThis.fetch=async(url,options)=>{upstream={url,options};return new Response('{"schemaVersion":1,"histories":[]}',{status:200});};
 const request=(path,opts={})=>new Request('https://my-at.workers.dev'+path,{headers:{Origin:origin,...opts.headers},method:opts.method||'GET'});
 assert.equal((await worker.fetch(request('/snapshot',{method:'OPTIONS'}))).status,204);
 assert.equal((await worker.fetch(request('/other',{headers:{Authorization:'Basic dTpw'}}))).status,404);
 assert.equal((await worker.fetch(new Request('https://my-at.workers.dev/snapshot',{headers:{Authorization:'Basic dTpw'}}))).status,403);
 assert.equal((await worker.fetch(request('/snapshot',{method:'POST',headers:{Authorization:'Basic dTpw'}}))).status,405);
 assert.equal((await worker.fetch(request('/snapshot'))).status,401);
 const response=await worker.fetch(request('/snapshot',{headers:{Authorization:'Basic dTpw'}}));
 assert.equal(response.status,200);assert.equal((await response.json()).schemaVersion,1);
 assert.equal(upstream.url,'https://ajiro.infini-cloud.net/dav/kazumiSync/history/snapshot.json');
 assert.equal(upstream.options.headers.Authorization,'Basic dTpw');
 assert.equal(response.headers.get('Access-Control-Allow-Origin'),origin);
 console.log('Worker route, CORS and credential forwarding checks passed');
}finally{globalThis.fetch=original;}
