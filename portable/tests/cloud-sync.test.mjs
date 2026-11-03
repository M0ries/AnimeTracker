import assert from 'node:assert/strict';
const memory=new Map();globalThis.localStorage={getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v),removeItem:k=>memory.delete(k)};
globalThis.window={dispatchEvent:()=>{}};globalThis.CustomEvent=class{constructor(type,options){this.type=type;this.detail=options.detail;}};
let local={format:'animetracker-v1',schema_version:1,tables:{series:[],anime:[],rounds:[],sources:[],sessions:[]}},remote=null;
const response=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
globalThis.fetch=async(url,options={})=>{
 const pathname=new URL(url,'https://local.test').pathname;
 if(pathname==='/auth/v1/token')return response({access_token:'user-jwt',refresh_token:'refresh',expires_in:3600,user:{id:'user-id',email:'test@example.com'}});
 if(pathname==='/api/export/json')return response({content:JSON.stringify(local)});
 if(pathname==='/api/state')return response({csrf_token:'test'});
 if(pathname==='/api/sync/replace'){const body=JSON.parse(options.body);assert.deepEqual(body.expected.tables,local.tables);local=body.document;return response({restored:true});}
 if(pathname==='/rest/v1/at_snapshots'&&options.method==='POST'){
  assert.equal(options.headers.Authorization,'Bearer user-jwt');
  if(remote)return response({message:'duplicate'},409);remote=JSON.parse(options.body);return response(null,201);
 }
 if(pathname==='/rest/v1/at_snapshots')return response(remote?[remote]:[]);
 if(pathname==='/rest/v1/rpc/at_compare_and_swap'){
  const body=JSON.parse(options.body);if(body.expected_revision!==remote.revision)return response({message:'sync conflict'},409);
  remote.document=body.next_document;return response(++remote.revision);
 }
 throw Error('Unexpected '+pathname);
};
const {ATSync}=await import('../cloud-sync.mjs');
assert.equal(await ATSync.login('test@example.com','pw'),true);
await ATSync.syncNow();assert.equal(remote.revision,1);
local.tables.anime.push({id:'one'});await ATSync.syncNow();assert.equal(remote.revision,2);
remote.revision=3;remote.document=structuredClone(local);remote.document.tables.anime.push({id:'two'});
await ATSync.syncNow();assert.equal(local.tables.anime.length,2);
local.tables.anime.push({id:'local'});remote.revision=4;
await assert.rejects(ATSync.syncNow(),/两台设备都修改了资料/);
assert.equal(local.tables.anime.length,3);
console.log('Cloud sync bootstrap, upload, download, conflict checks passed');
