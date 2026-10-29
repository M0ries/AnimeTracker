'use strict';
const $=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels={planned:'想看',watching:'正在看',completed:'已看完',paused:'暂停',dropped:'弃番',unreviewed:'待整理'};
const kindLabels={first:'首次观看',rewatch:'重看',imported:'Kazumi 来源快照'};
let state,page='library',filter='all',query='',tag='',sort='recent',pageNum=1,selected=new Set(),remote=localStorage.getItem('at.remote')==='yes',lastImport=null;
const pageSize=24;
const iconPaths={
 library:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
 clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 chart:'<path d="M4 3v17h17M8 16v-5m5 5V6m5 10V9"/>',
 archive:'<rect x="3" y="4" width="18" height="5" rx="1.5"/><path d="M5 9v11h14V9m-9 4h4"/>',
 plus:'<path d="M12 5v14M5 12h14"/>',
 moon:'<path d="M20 14a8 8 0 0 1-10-10A8.8 8.8 0 1 0 20 14Z"/>',
 info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-11v1"/>',
 search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
 check:'<path d="m5 12 4 4L19 6"/>',
 repeat:'<path d="m16 3 4 4-4 4M4 11V9a2 2 0 0 1 2-2h14M8 21l-4-4 4-4m12 0v2a2 2 0 0 1-2 2H4"/>',
 list:'<path d="M9 5h12M9 12h12M9 19h12M3 5h1m-1 7h1m-1 7h1"/>',
 import:'<path d="M12 3v11m-4-4 4 4 4-4M4 15v5h16v-5"/>'
};
function icon(name){return `<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[name]||iconPaths.library}</svg>`;}
document.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=icon(el.dataset.icon));
let viewMode=localStorage.getItem('at.view')==='list'?'list':'grid';

let toastTimer;
function toast(msg){$('#toast').textContent=msg;$('#toast').style.display='block';clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').style.display='none',4500);}
async function api(path,body){const r=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-AnimeTracker-Token':state.csrf_token},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.error||'操作失败');return d;}
async function bangumiFetch(url,options={}){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);try{return await fetch(url,{...options,signal:controller.signal});}finally{clearTimeout(timer);}}
async function load(){const r=await fetch('/api/state');const result=await r.json();if(!r.ok)throw Error(result.error||'无法读取本地数据库');state=result;$('#nav-count').textContent=state.anime.length;selected=new Set([...selected].filter(id=>state.anime.some(a=>a.id===id)));render();}
const title=a=>a.name_cn||a.name;
const anime=id=>state.anime.find(a=>a.id===id);
const bangumiUrl=id=>Number.isSafeInteger(id)&&id>0?`https://bgm.tv/subject/${id}`:null;
const kazumiUrl=id=>Number.isSafeInteger(id)&&id>0?`kazumi://bangumi/${id}`:null;
const series=a=>state.series.find(s=>s.id===a.series_id)?.name||'';
const rounds=a=>state.rounds.filter(r=>r.anime_id===a.id);
function latest(a){const rs=rounds(a),manual=rs.filter(r=>r.kind!=='imported');return (manual.length?manual:rs).slice().sort((a,b)=>(b.kind==='imported'?(b.last_watched_at||''):(b.created_at||'')).localeCompare(a.kind==='imported'?(a.last_watched_at||''):(a.created_at||'')))[0];}
function recent(a){return rounds(a).map(r=>r.last_watched_at||r.finished_at||r.started_at||'').sort().at(-1)||'';}
function dateFmt(d){if(!d)return '未记录';if(d.length===10)return d;return new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:Intl.DateTimeFormat().resolvedOptions().timeZone}).format(new Date(d));}
function dateInput(d){if(!d)return '';if(d.length===10)return d;return new Intl.DateTimeFormat('en-CA',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:Intl.DateTimeFormat().resolvedOptions().timeZone}).format(new Date(d));}
function heading(name,sub,buttons=''){return `<div class="page-heading"><div><h1>${name}</h1>${sub?`<p>${sub}</p>`:''}</div><div class="actions">${buttons}</div></div>`;}
function statCard(label,n,unit,symbol='',featured=false){return `<div class="metric ${featured?'featured':''}"><label>${label}</label><strong>${n}</strong><small>${unit}</small><span class="symbol">${icon({'▦':'library','◷':'clock','✓':'check','↻':'repeat','◈':'chart'}[symbol]||'chart')}</span></div>`;}
function render(){
 document.querySelectorAll('[data-page]').forEach(b=>{b.classList.toggle('active',b.dataset.page===page);if(b.dataset.page===page)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
 const names={library:'动漫书架',timeline:'观看时间线',stats:'数据统计',data:'导入与备份'};$('#breadcrumb').textContent=names[page];document.title=names[page]+' · AnimeTracker';
 if(page==='library')renderLibrary();else if(page==='timeline')renderTimeline();else if(page==='stats')renderStats();else renderData();
}

function renderLibrary(){
 const counts=Object.fromEntries(Object.keys(labels).map(k=>[k,state.anime.filter(a=>a.status===k).length]));
 $('#content').innerHTML=heading('书架','',`<button data-action="go-data">${icon('import')} 导入记录</button><button data-action="bangumi-search">${icon('search')} 搜索 Bangumi</button><button class="primary" data-action="new-anime">${icon('plus')} 添加动漫</button>`)+
 `<div class="overview">${statCard('动漫',state.stats.seasons,'部','▦',true)}${statCard('正在看',counts.watching,'部','◷')}${statCard('已看完',counts.completed,'部','✓')}${statCard('重看',state.stats.rewatches,'次','↻')}</div>
 <div class="toolbar"><div class="tabs">${[['all','全部'],...Object.entries(labels)].map(([k,l])=>`<button data-filter="${k}" class="${filter===k?'selected':''}">${l} <small>${k==='all'?state.anime.length:counts[k]}</small></button>`).join('')}</div><label class="checkbox-label"><input type="checkbox" id="remote-covers" ${remote?'checked':''}>加载远程封面</label></div>
 <div class="search-row"><div class="search">${icon('search')}<input id="search" aria-label="搜索动漫" placeholder="搜索名称、别名、系列或笔记…" value="${esc(query)}"></div><select id="tag-filter" aria-label="标签筛选"><option value="">全部分类</option>${[...new Set(state.anime.flatMap(a=>a.tags))].sort().map(t=>`<option ${tag===t?'selected':''}>${esc(t)}</option>`).join('')}</select><select id="sort" aria-label="排序">${[['recent','最近观看'],['name','名称顺序'],['rating','个人评分'],['year','播出年份'],['added','最近添加']].map(([k,l])=>`<option value="${k}" ${sort===k?'selected':''}>${l}</option>`).join('')}</select><div class="view-switch" aria-label="书架显示方式"><button data-view="grid" aria-label="网格视图" aria-pressed="${viewMode==='grid'}" class="${viewMode==='grid'?'selected':''}">${icon('library')}</button><button data-view="list" aria-label="列表视图" aria-pressed="${viewMode==='list'}" class="${viewMode==='list'?'selected':''}">${icon('list')}</button></div></div><div id="book-results"></div>`;
 $('#search').oninput=e=>{query=e.target.value;pageNum=1;renderBooks();};$('#tag-filter').onchange=e=>{tag=e.target.value;pageNum=1;renderBooks();};$('#sort').onchange=e=>{sort=e.target.value;pageNum=1;renderBooks();};
 $('#remote-covers').onchange=e=>{remote=e.target.checked;localStorage.setItem('at.remote',remote?'yes':'no');renderBooks();if(remote)toast('封面将由浏览器向原图片网站请求');};renderBooks();
}
function filtered(){const q=query.trim().toLowerCase();return state.anime.filter(a=>(filter==='all'||a.status===filter)&&(!tag||a.tags.includes(tag))&&(!q||[a.name,a.name_cn,...a.aliases,a.notes,series(a)].join(' ').toLowerCase().includes(q))).sort((a,b)=>{if(sort==='name')return title(a).localeCompare(title(b),'zh');if(sort==='rating')return (b.personal_rating??-1)-(a.personal_rating??-1);if(sort==='year')return (b.release_year||0)-(a.release_year||0);return sort==='added'?b.created_at.localeCompare(a.created_at):recent(b).localeCompare(recent(a));});}
function palette(a){let h=0;for(const c of a.id)h=(h*31+c.charCodeAt(0))>>>0;const choices=[['#b9a6bc','#514869'],['#c4a386','#66524d'],['#93afb0','#3b5c70'],['#a8b4a0','#46645f'],['#bea3b1','#744e68'],['#b3adc6','#4b557d']];return choices[h%choices.length];}
function card(a){const r=latest(a),prog=r?.progress||0,total=a.total_episodes,[c1,c2]=palette(a);return `<article class="card"><div class="cover" data-open="${esc(a.id)}" role="button" tabindex="0" aria-label="打开 ${esc(title(a))}"><div class="poster-art" style="background:linear-gradient(150deg,${c1},${c2})"><div class="letter">${esc([...title(a)][0]||'A')}</div></div>${remote&&a.cover?`<img src="${esc(a.cover)}" alt="" loading="lazy" referrerpolicy="no-referrer">`:''}<span class="badge" data-status="${esc(a.status)}">${labels[a.status]}</span></div><label class="card-check"><input type="checkbox" data-select="${esc(a.id)}" aria-label="选择 ${esc(title(a))}" ${selected.has(a.id)?'checked':''}></label>${a.personal_rating!==null?`<span class="rating">★ ${a.personal_rating.toFixed(1)}</span>`:''}<h3 data-open="${esc(a.id)}" title="${esc(title(a))}">${esc(title(a))}</h3><div class="card-meta"><span>${esc(a.season||a.tags[0]||'未分类')}</span><span>${a.release_year||'年份待补'}</span></div><div class="progress"><i style="--width:${total?Math.min(100,prog/total*100):0}%"></i></div><div class="card-bottom"><span>${r?.kind==='imported'?'来源进度':'观看进度'}</span><span>${prog} / ${total??'?'} 集</span></div></article>`;}
function renderBooks(){const arr=filtered(),max=Math.max(1,Math.ceil(arr.length/pageSize));pageNum=Math.min(pageNum,max);const current=arr.slice((pageNum-1)*pageSize,pageNum*pageSize);
 $('#book-results').innerHTML=`${selected.size?`<div class="batch"><b>已选 ${selected.size} 部</b><select id="batch-status">${Object.entries(labels).map(([k,l])=>`<option value="${k}">${l}</option>`).join('')}</select><button class="small" data-action="batch-status">修改状态</button><button class="small danger" data-action="batch-delete">删除所选</button><button class="small" data-action="clear-select">取消选择</button></div>`:''}<div class="toolbar"><span class="muted shelf-caption">书架 · ${arr.length} 部动漫</span><button class="text small" data-action="select-page">选择本页</button></div><div class="grid ${viewMode==='list'?'list-view':''}">${current.map(card).join('')||`<div class="empty"><div class="glyph">${icon('library')}</div><h3>${state.anime.length?'没有找到匹配的动漫':'暂无动漫'}</h3><p>${state.anime.length?'试试其他关键词，或清除筛选条件。':'添加第一部动漫，或导入你的 Kazumi 观看记录。'}</p><div class="actions">${state.anime.length?'<button data-action="reset-filters">清除筛选</button>':'<button class="primary" data-action="new-anime">＋ 添加动漫</button><button data-action="go-data">导入记录</button>'}</div></div>`}</div><div class="pagination"><button class="small" data-action="prev" ${pageNum<=1?'disabled':''}>← 上一页</button><span>${pageNum} / ${max}</span><button class="small" data-action="next" ${pageNum>=max?'disabled':''}>下一页 →</button></div>`;
 $('#book-results').querySelectorAll('img').forEach(im=>im.onerror=()=>im.remove());
}
function renderTimeline(){
 const entries=[];
 for(const r of state.rounds){const a=anime(r.anime_id);if(!a)continue;if(r.kind==='imported'){if(r.last_watched_at)entries.push({a,r,d:r.last_watched_at,label:'来源最近观看 · 第 '+r.progress+' 集'});}else{if(r.started_at)entries.push({a,r,d:r.started_at,label:kindLabels[r.kind]+' · 开始'});if(r.finished_at)entries.push({a,r,d:r.finished_at,label:kindLabels[r.kind]+' · 结束'});}}
 for(const s of state.sessions.filter(s=>!s.source_id&&s.watched_at)){const r=state.rounds.find(r=>r.id===s.round_id),a=r&&anime(r.anime_id);if(a)entries.push({a,r,d:s.watched_at,label:'观看第 '+s.episode+' 集'});}
 entries.sort((a,b)=>b.d.localeCompare(a.d));
 $('#content').innerHTML=heading('时间线','')+'<div class="notice">来源快照仅显示 Kazumi 的最近观看时间；没有记录的日期保持未知。时间按当前设备时区显示。</div><div class="panel"><div class="search-row"><label class="field">从<input type="date" id="from-date"></label><label class="field">至<input type="date" id="to-date"></label><label class="checkbox-label"><input type="checkbox" id="only-manual">只看手动记录</label></div><div id="timeline-results"></div></div>';
 function draw(){const from=$('#from-date').value,to=$('#to-date').value,manual=$('#only-manual').checked;const filtered=entries.filter(x=>(!from||dateInput(x.d)>=from)&&(!to||dateInput(x.d)<=to)&&(!manual||x.r.kind!=='imported'));$('#timeline-results').innerHTML='<p class="muted">'+filtered.length+' 条时间记录</p>'+filtered.map(x=>`<div class="timeline-row"><div class="timeline-date">${esc(dateFmt(x.d))}</div><div><h3>${esc(title(x.a))}</h3><span class="muted">${esc(x.label)}</span></div><button class="text small" data-open="${esc(x.a.id)}">查看记录 →</button></div>`).join('')||'<p class="muted">尚无日期记录</p>';}
 for(const sel of ['#from-date','#to-date','#only-manual'])$(sel).onchange=draw;draw();
}
function bars(entries){const max=Math.max(1,...entries.map(x=>x[1]));return entries.map(([name,count])=>`<div class="bar-row"><span>${esc(name)}</span><div class="bar"><i style="--width:${count/max*100}%"></i></div><b>${count}</b></div>`).join('');}
function renderStats(){const s=state.stats;$('#content').innerHTML=heading('统计','')+`<div class="overview">${statCard('作品 / 系列',s.works,'组','◈',true)}${statCard('动漫季度',s.seasons,'部','▦')}${statCard('手动观看轮次',s.rounds,'轮','↻')}${statCard('手动观看记录',s.records,'条','◷')}</div><div class="overview">${statCard('今年完成的季度',s.completed_this_year,'部')}${statCard('手动重看轮次',s.rewatches,'次')}${statCard('各手动轮次进度合计',s.marked_episode_progress,'集')}${statCard('Kazumi 来源快照',s.imported_snapshots,'份')}</div><div class="notice">作品数按你设置的系列归组；未归组条目各计一组。进度合计是各手动轮次标记到的集数之和，不等于实际完整观看集数。来源快照不计为首看或重看。另有 ${s.snapshot_records} 条来源进度记录。</div><div class="cols"><section class="panel"><h2>每月完成的观看轮次</h2>${bars(Object.entries(s.monthly_completed_rounds).map(([k,v])=>[k.slice(5)+' 月',v]))}<p class="helper">仅统计已看完且填写了结束日期的手动轮次。</p></section><section class="panel"><h2>类型分布 · 前 12 项</h2>${bars(Object.entries(s.genres).sort((a,b)=>b[1]-a[1]).slice(0,12))||'<p class="muted">给动漫添加标签后，这里会出现分类。</p>'}<p class="helper">一部动漫可以属于多个类型。</p></section></div>`;}
function renderData(){
 $('#content').innerHTML=heading('数据','')+`<div class="notice break">存储位置：${esc(state.database_path)}</div><div class="cols"><section class="panel"><h2>导入观看记录</h2><p class="muted">支持独立导出工具生成的 Kazumi JSON，以及 AnimeTracker 完整备份或普通 CSV 动漫清单。重复导入会跳过相同数据。</p><div class="actions"><button class="primary" data-action="import-json">导入 JSON</button><button data-action="import-csv">导入 CSV</button><a class="button" href="/api/template.csv" download>下载清单模板</a></div><p class="helper">普通 CSV 至少包含 id（编号）和 name（名称），也支持中文表头。每个季度使用不同编号；编号相同但内容不同会报告冲突。</p><div class="result">${lastImport?'<h3>最近一次导入结果</h3><pre class="pre">'+esc(reportText(lastImport))+'</pre>':''}</div></section><section class="panel"><h2>导出完整资料库</h2><p class="muted">包含动漫、系列、首看 / 重看轮次、观看记录和原始来源数据，可在新数据库中重新导入。</p><div class="actions"><a class="button" href="/api/export/json" download>↓ 完整 JSON</a><a class="button" href="/api/export/csv" download>↓ 完整 CSV</a><a class="button" href="/api/export/list.csv" download>↓ 动漫清单 CSV</a></div><p class="helper">完整备份包含观看轮次与来源；动漫清单 CSV 只包含条目资料。完整备份遇到 ID 内容冲突时整批停止，普通清单按行报告结果。</p></section><section class="panel"><h2>数据库备份</h2><p class="muted">生成一致的 SQLite 备份，保存在此设备，并可另存为文件。</p><button data-action="backup">保存数据库备份</button></section><section class="panel"><h2>从备份恢复</h2><p class="muted">选择 AnimeTracker 的 .db 备份，验证通过后替换整个资料库。恢复前会自动保存当前数据库。</p><button class="danger" data-action="restore">选择备份恢复</button></section></div><section class="panel"><h2>Kazumi 导入说明</h2><p class="muted">导出工具只打开临时副本。请先退出 Kazumi，再运行项目中的 Export-Kazumi.command。原始 History key、Bangumi ID、全部进度、来源、标签和别名保存在导出文件及数据库中。</p><p class="muted">同一正数 Bangumi ID 的不同来源归入同一条目；不会按名称合并。不同季度保留独立条目，你可以手动设置共同系列。导入不会猜测首看日期、看完日期或重看次数。</p></section>`;
}
function reportText(r){const names={raw:'原始 History 条数',parsed:'成功解析',imported:'新增导入',updated:'更新来源快照',skipped:'跳过',conflicts:'冲突',errors:'异常'};return Object.entries(names).filter(([k])=>k in r).map(([k,v])=>`${v}：${r[k]}`).join('\n')+(r.details?.length?'\n\n详情：\n'+JSON.stringify(r.details,null,2):'');}
function modal(title,html){$('#dialog-title').textContent=title;$('#dialog-body').innerHTML=html;if(!$('#dialog').open)$('#dialog').showModal();$('#dialog').scrollTop=0;$('#dialog-body').querySelectorAll('img').forEach(im=>im.onerror=()=>im.remove());}
function field(label,name,value='',type='text',full=false,extra=''){return `<label class="field ${full?'full':''}">${label}<input name="${name}" type="${type}" value="${esc(value??'')}" ${extra}></label>`;}
function statusSelect(value){return `<label class="field">观看状态<select name="status">${Object.entries(labels).map(([k,v])=>`<option value="${k}" ${k===value?'selected':''}>${v}</option>`).join('')}</select></label>`;}
function formFooter(){return '<p class="form-error" role="alert"></p><div class="form-actions"><button type="button" data-action="close">取消</button><button class="primary" type="submit">保存记录</button></div>';}
function bindForm(fn){$('#edit-form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,b=form.querySelector('[type=submit]');b.disabled=true;form.querySelector('.form-error').textContent='';try{await fn(Object.fromEntries(new FormData(form)));}catch(err){if(form.isConnected)form.querySelector('.form-error').textContent=err.message;else toast(err.message);}finally{b.disabled=false;}};}
function editAnime(id){const a=id?anime(id):{name:'',name_cn:'',aliases:[],tags:[],status:'planned'};
 modal(id?'编辑动漫':'添加一部动漫',`<form id="edit-form"><div class="form-grid">${field('原名 / 动漫名称 *','name',a.name,'text',true,'required maxlength="500"')}${field('中文名称','name_cn',a.name_cn)}${field('所属系列（不同季度填写相同系列名）','series_name',id?series(a):'')}${field('季度标记，如 第一季 / S2','season',a.season)}${field('播出年份','release_year',a.release_year,'number',false,'min="1800" max="3000"')}${field('Bangumi 条目 ID（网址 /subject/ 后的数字）','bangumi_id',a.bangumi_id,'number',false,`min="1" max="2147483647" ${id&&state.sources.some(s=>s.anime_id===id)?'readonly title="Kazumi 来源条目不可修改 ID"':''}`)}${statusSelect(a.status)}${field('总集数（未知可留空）','total_episodes',a.total_episodes,'number',false,'min="0" max="100000"')}${field('个人评分 / 10（可留空）','personal_rating',a.personal_rating,'number',false,'min="0" max="10" step="0.1"')}${field('标签，用逗号分隔','tags',a.tags.join('，'))}${field('别名，用逗号分隔','aliases',a.aliases.join('，'),'text',true)}${field('封面图片 URL','cover',a.cover,'url',true)}<label class="field full">简介<textarea name="description">${esc(a.description)}</textarea></label><label class="field full">个人评价 / 笔记<textarea name="notes">${esc(a.notes)}</textarea></label></div>${formFooter()}</form>`);
 bindForm(async d=>{d.tags=d.tags.split(/[,，]/).map(s=>s.trim()).filter(Boolean);d.aliases=d.aliases.split(/[,，]/).map(s=>s.trim()).filter(Boolean);const r=await api('anime/save',{id,data:d});await load();detail(r.id);toast('动漫已保存');});
}
function detail(id){const a=anime(id);if(!a)return;const rs=rounds(a).slice().sort((a,b)=>b.created_at.localeCompare(a.created_at));
 modal('动漫档案',`<div class="detail-head"><div class="mini-cover">${esc([...title(a)][0]||'A')}${remote&&a.cover?`<img src="${esc(a.cover)}" alt="" referrerpolicy="no-referrer">`:''}</div><div><h2>${esc(title(a))}</h2><p class="muted">${esc(a.name)} · ${a.release_year||'年份未知'} ${a.season?'· '+esc(a.season):''}</p><p><span class="badge">${labels[a.status]}</span> ${a.personal_rating!==null?'★ '+a.personal_rating+' / 10':''}</p>${series(a)?`<p class="muted">系列：${esc(series(a))}</p>`:''}</div></div><div>${a.tags.map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>${a.description?`<p class="detail-description">${esc(a.description)}</p>`:''}${a.notes?`<p class="detail-description">个人笔记：${esc(a.notes)}</p>`:''}<div class="actions">${bangumiUrl(a.bangumi_id)?`<a class="button" href="${bangumiUrl(a.bangumi_id)}" data-bangumi-id="${a.bangumi_id}" target="_blank" rel="noopener noreferrer">Bangumi 条目 ↗</a>`:''}${kazumiUrl(a.bangumi_id)?`<a class="button" href="${kazumiUrl(a.bangumi_id)}" data-kazumi-id="${a.bangumi_id}">在 Kazumi 打开 ↗</a>`:''}${bangumiUrl(a.bangumi_id)?`<button data-bangumi-refresh="${esc(id)}">获取 Bangumi 资料</button>`:''}${!a.bangumi_id?`<button data-bangumi-search="${esc(id)}">关联 Bangumi</button>`:''}<button data-edit-anime="${esc(id)}">编辑资料</button><button class="primary" data-new-round="${esc(id)}">＋ 添加首看 / 重看</button><button class="small" data-merge="${esc(id)}">人工合并</button><button class="small danger" data-delete-anime="${esc(id)}">删除动漫</button></div><div class="hr"></div><h3>观看轮次与来源</h3><p class="helper">首看和每次重看分别保存。来源快照不代表一个已确认的观看轮次。</p>${rs.map(r=>{const sessions=state.sessions.filter(s=>s.round_id===r.id).sort((a,b)=>(b.watched_at||'').localeCompare(a.watched_at||''));const src=state.sources.find(s=>s.round_id===r.id);return `<section class="round"><div class="round-header"><strong>${kindLabels[r.kind]} <span class="badge">${r.kind==='imported'?'进度快照':labels[r.status]}</span></strong><span>${r.progress} / ${a.total_episodes??'?'} 集</span></div><div class="round-dates"><span>开始 ${dateFmt(r.started_at)}</span><span>结束 ${dateFmt(r.finished_at)}</span><span>最近 ${dateFmt(r.last_watched_at)}</span></div>${src?`<p class="helper break">来源：${esc(src.source_key)}</p>`:''}${r.notes?`<p class="muted">${esc(r.notes)}</p>`:''}${r.kind!=='imported'?`<div class="actions"><button class="small" data-edit-round="${esc(r.id)}">修改日期 / 进度</button><button class="small" data-add-session="${esc(r.id)}">记录一集</button><button class="text small danger" data-delete-round="${esc(r.id)}">删除轮次</button></div>`:''}<details><summary class="helper">${sessions.length} 条${r.kind==='imported'?'来源进度':'观看'}记录</summary>${sessions.map(s=>`<div class="session-row"><span>第 ${s.episode} 集 · ${dateFmt(s.watched_at)} ${s.progress_ms!==null?'· 播放至 '+Math.floor(s.progress_ms/60000)+' 分钟':''}${s.notes&&!s.source_id?' · '+esc(s.notes):''}</span>${!s.source_id?`<span class="actions"><button class="text small" data-edit-session="${esc(s.id)}">编辑</button><button class="text small danger" data-delete-session="${esc(s.id)}">删除</button></span>`:''}</div>`).join('')}</details></section>`;}).join('')||'<p class="muted">暂无观看轮次。</p>'}`);
}
async function refreshBangumi(id){
 const a=anime(id),subjectId=a?.bangumi_id;
 if(!Number.isSafeInteger(subjectId)||subjectId<=0)throw Error('请先填写 Bangumi 条目 ID');
 let response;
 try{response=await bangumiFetch(`https://api.bgm.tv/v0/subjects/${subjectId}`);}
 catch(err){throw Error('无法连接 Bangumi，请检查网络后重试');}
 if(!response.ok)throw Error(response.status===404?'Bangumi 没有找到该条目':`Bangumi 请求失败（${response.status}）`);
 const subject=await response.json();
 const result=await api('anime/bangumi',{id,subject});
 await load();detail(id);
 toast(result.updated.length?`已补充 ${result.updated.length} 项 Bangumi 资料`:'已有资料完整，未改动个人记录');
}
function searchBangumi(targetId){
 const existing=targetId?anime(targetId):null;
 modal(existing?'关联 Bangumi':'从 Bangumi 添加',`<form id="edit-form"><label class="field">动画名称<input name="keyword" required maxlength="100" value="${esc(existing?.name_cn||existing?.name||'')}" placeholder="输入中文名或原名"></label><div class="actions"><button class="primary" type="submit">搜索动画</button></div><p class="form-error" role="alert"></p></form><div id="bangumi-results" aria-live="polite"></div>`);
 bindForm(async d=>{
  const keyword=d.keyword.trim();if(!keyword)throw Error('请输入动画名称');
  const box=$('#bangumi-results');box.textContent='正在搜索…';
  let response;
  try{response=await bangumiFetch('https://api.bgm.tv/v0/search/subjects?limit=10',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keyword,filter:{type:[2]}})});}
  catch{box.textContent='';throw Error('无法连接 Bangumi，请检查网络后重试');}
  if(!response.ok){box.textContent='';throw Error(`Bangumi 搜索失败（${response.status}）`);}
  const payload=await response.json();
  const results=Array.isArray(payload.data)?payload.data.filter(x=>x.type===2&&Number.isSafeInteger(x.id)&&x.id>0):[];
  box.innerHTML=results.length?`<p class="helper">请核对季度和年份，选择正确的条目。</p>${results.map(x=>`<div class="bangumi-result"><div><strong>${esc(x.name_cn||x.name)}</strong><p class="muted">${esc(x.name)} · ${esc(x.date||'日期未知')} · ${esc(x.eps||'?')} 集 · ID ${x.id}</p></div><div class="actions"><a class="button small" href="${bangumiUrl(x.id)}" target="_blank" rel="noopener noreferrer">查看 ↗</a><button class="small primary" data-bangumi-pick="${x.id}" data-bangumi-target="${esc(targetId||'')}">选择</button></div></div>`).join('')}`:'<p class="muted">未找到匹配的动画。可以换个名称，或手动填写 Bangumi ID。</p>';
 });
}
async function pickBangumi(subjectId,targetId){
 const existing=targetId?anime(targetId):null;
 if(existing?.bangumi_id)throw Error('这部动漫已有 Bangumi ID');
 let response;
 try{response=await bangumiFetch(`https://api.bgm.tv/v0/subjects/${subjectId}`);}
 catch{throw Error('无法读取 Bangumi 条目，请检查网络后重试');}
 if(!response.ok)throw Error(`读取 Bangumi 条目失败（${response.status}）`);
 const subject=await response.json();
 if(subject.id!==subjectId||subject.type!==2)throw Error('Bangumi 返回的条目不一致或不是动画');
 const result=await api('anime/bangumi/link',{id:targetId||null,subject});
 await load();detail(result.id);toast(existing?'已关联 Bangumi，个人记录已保留':'已从 Bangumi 添加动漫');
}
function editRound(aid,rid){const a=anime(aid),r=rid?state.rounds.find(r=>r.id===rid):{kind:rounds(a).some(r=>r.kind!=='imported')?'rewatch':'first',status:'watching',progress:0};
 modal(rid?'修改观看轮次':'新增观看轮次',`<p class="muted">${esc(title(a))} · 新轮次会保留以前的观看日期和进度。</p><form id="edit-form"><div class="form-grid"><label class="field">轮次类型<select name="kind"><option value="first" ${r.kind==='first'?'selected':''}>首次观看</option><option value="rewatch" ${r.kind==='rewatch'?'selected':''}>重看</option></select></label>${statusSelect(r.status)}${field('开始日期（未知可留空）','started_at',dateInput(r.started_at),'date')}${field('结束日期（未知可留空）','finished_at',dateInput(r.finished_at),'date')}${field('最近观看日期','last_watched_at',dateInput(r.last_watched_at),'date')}${field('进度：已看到第几集','progress',r.progress,'number',false,`min="0" max="${a.total_episodes||100000}" required`)}<label class="field full">轮次笔记<textarea name="notes">${esc(r.notes)}</textarea></label></div>${formFooter()}</form>`);
 bindForm(async d=>{await api('round/save',{anime_id:aid,id:rid,data:d});await load();detail(aid);toast('观看轮次已保存');});
}
function addSession(rid,sid){const r=state.rounds.find(r=>r.id===rid),s=sid?state.sessions.find(s=>s.id===sid):null;modal(sid?'编辑观看记录':'记录一次观看',`<p class="muted">${esc(title(anime(r.anime_id)))} · ${kindLabels[r.kind]}</p><form id="edit-form"><div class="form-grid">${field('集数','episode',s?.episode??r.progress+1,'number',false,'required min="1"')}${field('观看日期（未知可留空）','watched_at',dateInput(s?.watched_at),'date')}<label class="field full">备注<textarea name="notes">${esc(s?.notes)}</textarea></label></div><p class="helper">修改集数不会自动降低轮次总进度；需要时可在“修改日期 / 进度”中调整。</p>${formFooter()}</form>`);bindForm(async d=>{await api(sid?'session/edit':'session/add',sid?{id:sid,data:d}:{round_id:rid,data:d});await load();detail(r.anime_id);toast(sid?'观看记录已修改':'观看记录已添加');});}
function mergeForm(id){modal('人工合并条目',`<div class="notice">只在确认是同一季度的同一作品时合并。源条目的所有轮次和来源会转移；原资料会附在目标笔记中。不同季度应设置共同系列。</div><form id="edit-form"><label class="field">将「${esc(title(anime(id)))}」合并到<select name="target" required><option value="">选择保留的条目</option>${state.anime.filter(a=>a.id!==id).sort((a,b)=>title(a).localeCompare(title(b))).map(a=>`<option value="${esc(a.id)}">${esc(title(a))} ${esc(a.season)} [${esc(a.bangumi_id||'手动')}]</option>`).join('')}</select></label>${formFooter()}</form>`);bindForm(async d=>{if(!await askConfirm('确认是同一季度的同一作品？合并后保留目标条目。'))return;await api('merge',{source:id,target:d.target,confirm:true});await load();detail(d.target);toast('条目已合并');});}
async function askConfirm(message){return window.ATPlatform?window.ATPlatform.confirm(message):confirm(message);}
async function chooseFile(accept,fn){if(window.ATPlatform?.native){try{const file=await window.ATPlatform.chooseFile(accept);if(file)await fn(file);}catch(e){toast(e.message);}return;}const el=document.createElement('input');el.type='file';el.accept=accept;el.onchange=async()=>{if(el.files[0]){try{await fn(el.files[0]);}catch(e){toast(e.message);}}};el.click();}
async function downloadBytes(b64,name){const bytes=Uint8Array.from(atob(b64),c=>c.charCodeAt(0));if(window.ATPlatform)return window.ATPlatform.save(bytes,name);const url=URL.createObjectURL(new Blob([bytes]));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function toBase64(buffer){const b=new Uint8Array(buffer);let str='';for(let i=0;i<b.length;i+=32768)str+=String.fromCharCode(...b.subarray(i,i+32768));return btoa(str);}
async function act(action){
 if(action==='new-anime')editAnime();
 else if(action==='bangumi-search')searchBangumi();
 else if(action==='reset-filters'){filter='all';query='';tag='';pageNum=1;renderLibrary();}
 else if(action==='focus-search'){if(page!=='library'){page='library';render();}$('#search').focus();$('#search').select();}
 else if(action==='about')modal('设置',`<div class="about-head"><img src="/icons/at.svg" alt="AT"><div><h2>AnimeTracker</h2><p>2.0.0</p></div></div><div class="actions"><button data-action="toggle-theme">切换深浅主题</button></div><div class="hr"></div><p class="muted">同步：尚未启用</p><p class="helper">当前记录保存在此设备。可通过“数据”导出或迁移资料库。</p><div class="about-shortcuts"><span><kbd>⌘ / Ctrl K</kbd> 搜索</span><span><kbd>Esc</kbd> 关闭</span></div>`);
 else if(action==='toggle-theme')toggleTheme();
 else if(action==='go-data'){page='data';render();}
 else if(action==='close')$('#dialog').close();
 else if(action==='prev'){pageNum--;renderBooks();}
 else if(action==='next'){pageNum++;renderBooks();}
 else if(action==='clear-select'){selected.clear();renderBooks();}
 else if(action==='select-page'){filtered().slice((pageNum-1)*pageSize,pageNum*pageSize).forEach(a=>selected.add(a.id));renderBooks();}
 else if(action==='batch-status'){await api('batch',{ids:[...selected],status:$('#batch-status').value});await load();toast('已修改所选动漫状态');}
 else if(action==='batch-delete'){if(!await askConfirm(`删除 ${selected.size} 部动漫及其全部轮次和来源？建议先备份。`))return;await api('batch',{ids:[...selected],delete:true,confirm:true});selected.clear();await load();toast('所选动漫已删除');}
 else if(action==='import-json'||action==='import-csv'){chooseFile(action==='import-json'?'.json':'.csv',async file=>{toast('正在导入…');const content=await file.text();lastImport=await api(action==='import-json'?'import/json':'import/csv',action==='import-json'?{document:JSON.parse(content)}:{content});await load();toast(`新增 ${lastImport.imported}，跳过 ${lastImport.skipped}，冲突 ${lastImport.conflicts}，异常 ${lastImport.errors}`);});}
 else if(action==='backup'){const r=await api('backup',{});const saved=await downloadBytes(r.base64,r.filename);toast(saved===false?'本地备份已保留；未另存文件':'备份已保存');}
 else if(action==='restore'){chooseFile('.db',async file=>{if(!await askConfirm('恢复将替换当前整个资料库，当前版本会自动备份。确认继续？'))return;const r=await api('restore',{base64:toBase64(await file.arrayBuffer()),confirm:true});lastImport=null;await load();toast('恢复完成；旧数据库已自动备份');});}
}
document.addEventListener('click',async e=>{
 const b=e.target.closest('button,[data-open],[data-filter]');if(!b)return;
 try{
  if(b.dataset.page){page=b.dataset.page;render();return;}
  if(b.dataset.view){viewMode=b.dataset.view;localStorage.setItem('at.view',viewMode);document.querySelectorAll('[data-view]').forEach(el=>{el.classList.toggle('selected',el.dataset.view===viewMode);el.setAttribute('aria-pressed',String(el.dataset.view===viewMode));});renderBooks();return;}
  if(b.dataset.filter){filter=b.dataset.filter;pageNum=1;renderLibrary();return;}
  if(b.dataset.open){detail(b.dataset.open);return;}
  if(b.dataset.editAnime){editAnime(b.dataset.editAnime);return;}
  if(b.dataset.bangumiSearch){searchBangumi(b.dataset.bangumiSearch);return;}
  if(b.dataset.bangumiPick){b.disabled=true;try{await pickBangumi(Number(b.dataset.bangumiPick),b.dataset.bangumiTarget);}finally{b.disabled=false;}return;}
  if(b.dataset.bangumiRefresh){b.disabled=true;try{await refreshBangumi(b.dataset.bangumiRefresh);}finally{b.disabled=false;}return;}
  if(b.dataset.newRound){editRound(b.dataset.newRound);return;}
  if(b.dataset.editRound){const r=state.rounds.find(r=>r.id===b.dataset.editRound);editRound(r.anime_id,r.id);return;}
  if(b.dataset.editSession){const s=state.sessions.find(s=>s.id===b.dataset.editSession);addSession(s.round_id,s.id);return;}
  if(b.dataset.addSession){addSession(b.dataset.addSession);return;}
  if(b.dataset.merge){mergeForm(b.dataset.merge);return;}
  if(b.dataset.deleteAnime){if(!await askConfirm('删除这部动漫及其所有轮次、观看记录和来源？'))return;await api('delete',{table:'anime',id:b.dataset.deleteAnime,confirm:true});$('#dialog').close();await load();toast('动漫已删除');return;}
  if(b.dataset.deleteRound){const r=state.rounds.find(r=>r.id===b.dataset.deleteRound);if(!await askConfirm('删除此观看轮次及其观看记录？'))return;await api('delete',{table:'rounds',id:r.id,confirm:true});await load();detail(r.anime_id);return;}
  if(b.dataset.deleteSession){const s=state.sessions.find(s=>s.id===b.dataset.deleteSession),r=state.rounds.find(r=>r.id===s.round_id);if(!await askConfirm('删除这条观看记录？轮次进度将保留，可在修改轮次中调整。'))return;await api('delete',{table:'sessions',id:s.id,confirm:true});await load();detail(r.anime_id);return;}
  if(b.dataset.action){b.disabled=true;try{await act(b.dataset.action);}finally{b.disabled=false;}}
 }catch(err){toast(err.message);}
});
document.addEventListener('change',e=>{if(e.target.dataset.select){if(e.target.checked)selected.add(e.target.dataset.select);else selected.delete(e.target.dataset.select);renderBooks();}});
document.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'&&!$('#dialog').open){e.preventDefault();act('focus-search');}if((e.key==='Enter'||e.key===' ')&&e.target.matches('.cover[data-open]')){e.preventDefault();detail(e.target.dataset.open);}});
$('#close-dialog').onclick=()=>$('#dialog').close();
if(localStorage.getItem('at.theme')==='dark')document.body.classList.add('dark');
function toggleTheme(){document.body.classList.toggle('dark');const dark=document.body.classList.contains('dark');localStorage.setItem('at.theme',dark?'dark':'light');$('#theme').setAttribute('aria-pressed',String(dark));}
$('#theme').setAttribute('aria-pressed',String(document.body.classList.contains('dark')));$('#theme').onclick=toggleTheme;
load().catch(e=>{$('#fatal').hidden=false;$('#fatal').textContent='启动失败：'+e.message+(window.ATPlatform?'。请重新打开应用。':'。请确认本地服务仍在运行，然后刷新页面。');$('#content').innerHTML='';});
