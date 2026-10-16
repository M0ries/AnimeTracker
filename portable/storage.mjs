export class BrowserStorage {
  constructor(){this.database=new Promise((resolve,reject)=>{
    const request=indexedDB.open('animetracker-local-v2',1);
    request.onupgradeneeded=()=>request.result.createObjectStore('storage');
    request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
  });}
  async load(){
    const db=await this.database;
    return new Promise((resolve,reject)=>{
      const transaction=db.transaction('storage','readonly');
      const request=transaction.objectStore('storage').get('snapshot');
      request.onsuccess=()=>resolve(request.result||{revision:0,files:{}});
      request.onerror=()=>reject(request.error);
    });
  }
  async save(files,revision){
    const db=await this.database;
    return new Promise((resolve,reject)=>{
      const transaction=db.transaction('storage','readwrite');
      const store=transaction.objectStore('storage');const request=store.get('snapshot');
      let error,result;
      request.onsuccess=()=>{
        if((request.result?.revision||0)!==revision){error=new Error('其他窗口修改了资料库，请重新打开应用后再操作。');transaction.abort();return;}
        result={revision:revision+1,files};store.put(result,'snapshot');
      };
      transaction.oncomplete=()=>resolve(result);
      transaction.onerror=()=>reject(error||transaction.error||new Error('本地存储失败'));
      transaction.onabort=()=>reject(error||transaction.error||new Error('本地存储失败'));
    });
  }
}
export class NativeStorage {
  async load(){return window.__TAURI__.core.invoke('storage_load');}
  async save(files,revision){return window.__TAURI__.core.invoke('storage_save',{files,revision});}
}
