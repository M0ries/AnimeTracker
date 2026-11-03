// Read-only InfiniCLOUD bridge for AT. Credentials are supplied per request and never stored.
const ORIGIN='https://m0ries.github.io';
const SNAPSHOT='https://ajiro.infini-cloud.net/dav/kazumiSync/history/snapshot.json';
const MAX_BYTES=12*1024*1024;
const cors={'Access-Control-Allow-Origin':ORIGIN,'Access-Control-Allow-Methods':'GET, OPTIONS',
  'Access-Control-Allow-Headers':'Authorization','Cache-Control':'no-store','Vary':'Origin'};
const error=(status,message)=>new Response(message,{status,headers:{...cors,'Content-Type':'text/plain; charset=utf-8'}});
export default {
  async fetch(request){
    const url=new URL(request.url);
    if(request.headers.get('Origin')!==ORIGIN)return error(403,'Origin not allowed');
    if(url.pathname!=='/snapshot'||url.search)return error(404,'Not found');
    if(request.method==='OPTIONS')return new Response(null,{status:204,headers:cors});
    if(request.method!=='GET')return error(405,'Read-only endpoint');
    const authorization=request.headers.get('Authorization')||'';
    if(!/^Basic [A-Za-z0-9+/]+={0,2}$/.test(authorization)||authorization.length>4096)
      return error(401,'WebDAV credentials required');
    try{
      const response=await fetch(SNAPSHOT,{headers:{Authorization:authorization},redirect:'manual',cache:'no-store'});
      if(response.status===401||response.status===403)return error(401,'WebDAV username or password rejected');
      if(!response.ok)return error(502,`WebDAV returned ${response.status}`);
      const length=Number(response.headers.get('Content-Length')||0);
      if(length>MAX_BYTES)return error(413,'Snapshot too large');
      const reader=response.body.getReader();const chunks=[];let size=0;
      for(;;){const {value,done}=await reader.read();if(done)break;size+=value.byteLength;
        if(size>MAX_BYTES){await reader.cancel();return error(413,'Snapshot too large');}chunks.push(value);}
      return new Response(new Blob(chunks),{status:200,headers:{...cors,'Content-Type':'application/json; charset=utf-8'}});
    }catch{return error(502,'WebDAV unavailable');}
  }
};
