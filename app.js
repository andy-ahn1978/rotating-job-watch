let targets=[],payload={last_checked:null,jobs:[]},config={},view='new';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const APPKEY='rotating-job-watch.v4.apps';

async function init(){
 try{
  [targets,payload,config]=await Promise.all([
    fetch('targets.json?ts='+Date.now()).then(r=>r.json()),
    fetch('jobs.json?ts='+Date.now()).then(r=>r.json()),
    fetch('search_config.json?ts='+Date.now()).then(r=>r.json())
  ]);
  $('#liveBadge').textContent='LIVE';
 }catch(e){$('#liveBadge').textContent='OFFLINE'}
 bindNav();render();
}
function bindNav(){
 $$('nav button').forEach(b=>b.onclick=()=>{view=b.dataset.view;$$('nav button').forEach(x=>x.classList.toggle('active',x===b));render()})
}
function appsState(){try{return JSON.parse(localStorage.getItem(APPKEY))||{}}catch(e){return{}}}
function appsFor(t){const s=appsState();return s[t.id]??t.applications??0}
function setApps(id,n){const s=appsState();s[id]=Math.max(0,Number(n)||0);localStorage.setItem(APPKEY,JSON.stringify(s));render()}
function esc(s=''){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function fmt(s){if(!s)return'Not yet';try{return new Date(s).toLocaleString()}catch(e){return s}}
function money(j){
 const a=j.salary_min,b=j.salary_max;
 if(!a&&!b)return'';
 const fmt=x=>'$'+Math.round(Number(x)).toLocaleString();
 if(a&&b)return `${fmt(a)}–${fmt(b)}`;
 return a?`From ${fmt(a)}`:`Up to ${fmt(b)}`;
}
function render(){
 const jobs=payload.jobs||[],newJobs=jobs.filter(j=>j.is_new);
 $('#newCount').textContent=newJobs.length;$('#jobCount').textContent=jobs.length;$('#companyCount').textContent=targets.length;$('#lastChecked').textContent=fmt(payload.last_checked);
 if(view==='new')jobView(newJobs,true);
 if(view==='all')jobView(jobs,false);
 if(view==='companies')companyView();
 if(view==='applications')applicationsView();
}
function jobView(jobs,newOnly){
 $('#content').innerHTML=`<div class="toolbar"><input id="search" class="input" placeholder="Search jobs, companies, cities"><select id="sourceFilter" class="select"><option value="">All sources</option><option>Official</option><option>Adzuna</option></select></div><div id="jobList"></div>`;
 const paint=()=>{
  const q=$('#search').value.toLowerCase(),src=$('#sourceFilter').value;
  const arr=jobs.filter(j=>[j.title,j.company,j.location,(j.matched_keywords||[]).join(' ')].join(' ').toLowerCase().includes(q)).filter(j=>!src||j.source===src);
  $('#jobList').innerHTML=arr.length?arr.map(j=>{
    const strong=Number(j.score)>=Number(config.strong_match_score||8);
    const salary=money(j);
    return `<article class="card ${j.is_new?'new':''}"><div class="top"><div><div class="title">${esc(j.title)}</div><div class="company">${esc(j.company)}</div></div>${j.is_new?'<span class="badge new">NEW</span>':''}</div><div class="meta">${esc(j.location||'')} · ${esc(j.source||'')} ${salary?'· '+esc(salary):''}</div><div class="badges"><span class="badge fit">Fit ${esc(j.score)}/10</span>${strong?'<span class="badge strong">Strong match</span>':''}${j.target_company?'<span class="badge target">Target company</span>':''}${(j.matched_keywords||[]).slice(0,4).map(k=>`<span class="badge">${esc(k)}</span>`).join('')}</div><div class="actions"><a class="btn primary" href="${esc(j.url)}" target="_blank" rel="noopener">Open Job</a><a class="btn linkedin" href="https://www.linkedin.com/jobs/search/?keywords=${encodeURIComponent(j.company+' '+j.title)}&location=Ontario%2C%20Canada" target="_blank" rel="noopener">LinkedIn</a><a class="btn indeed" href="https://ca.indeed.com/jobs?q=${encodeURIComponent(j.company+' '+j.title)}&l=Ontario" target="_blank" rel="noopener">Indeed</a></div></article>`;
  }).join(''):`<div class="empty">${newOnly?'No new qualifying jobs.':'No qualifying jobs found yet.'}</div>`;
 };
 $('#search').oninput=paint;$('#sourceFilter').onchange=paint;paint();
}
function companyView(){
 $('#content').innerHTML=`<div class="toolbar"><input id="companySearch" class="input" placeholder="Search target companies"><select id="fitFilter" class="select"><option value="0">All fit scores</option><option value="9">Fit 9+</option><option value="8">Fit 8+</option></select></div><div id="companies"></div>`;
 const paint=()=>{
  const q=$('#companySearch').value.toLowerCase(),f=Number($('#fitFilter').value);
  const arr=targets.filter(t=>[t.name,t.region].join(' ').toLowerCase().includes(q)).filter(t=>t.fit>=f).sort((a,b)=>b.fit-a.fit);
  $('#companies').innerHTML=arr.map(t=>{
   const current=(payload.jobs||[]).filter(j=>(j.company||'').toLowerCase().includes(t.name.toLowerCase().split('/')[0].trim())).length;
   return `<article class="card"><div class="company-row"><div><div class="title">${esc(t.name)}</div><div class="company">${esc(t.region)}</div><div class="badges"><span class="badge fit">Target Fit ${t.fit}/10</span><span class="badge">${current} discovered jobs</span></div></div><div class="right"><div class="application-count">${appsFor(t)}</div><div class="small">applications</div></div></div><div class="source-row"><a class="btn primary" href="${esc(t.careers_url)}" target="_blank" rel="noopener">Official</a><a class="btn linkedin" href="${esc(t.linkedin_url)}" target="_blank" rel="noopener">LinkedIn</a><a class="btn indeed" href="${esc(t.indeed_url)}" target="_blank" rel="noopener">Indeed</a><a class="btn" href="${esc(t.jobbank_url)}" target="_blank" rel="noopener">Job Bank</a></div><div class="actions"><button class="btn" data-plus="${t.id}">+ Application</button><button class="btn" data-minus="${t.id}">−1</button></div></article>`;
  }).join('');
  $$('[data-plus]').forEach(b=>b.onclick=()=>{const t=targets.find(x=>x.id===b.dataset.plus);setApps(t.id,appsFor(t)+1)});
  $$('[data-minus]').forEach(b=>b.onclick=()=>{const t=targets.find(x=>x.id===b.dataset.minus);setApps(t.id,appsFor(t)-1)});
 };
 $('#companySearch').oninput=paint;$('#fitFilter').onchange=paint;paint();
}
function applicationsView(){
 const arr=targets.filter(t=>appsFor(t)>0).sort((a,b)=>appsFor(b)-appsFor(a));
 const total=arr.reduce((a,t)=>a+appsFor(t),0);
 $('#content').innerHTML=`<div class="notice"><b>${total}</b> applications across <b>${arr.length}</b> target companies. Counts stay on this device.</div>${arr.map(t=>`<article class="card"><div class="company-row"><div><div class="title">${esc(t.name)}</div><div class="company">${esc(t.region)}</div></div><div class="right"><div class="application-count">${appsFor(t)}</div><div class="small">applications</div></div></div><div class="source-row"><a class="btn primary" href="${esc(t.careers_url)}" target="_blank" rel="noopener">Official</a><a class="btn linkedin" href="${esc(t.linkedin_url)}" target="_blank" rel="noopener">LinkedIn</a><a class="btn indeed" href="${esc(t.indeed_url)}" target="_blank" rel="noopener">Indeed</a><a class="btn" href="${esc(t.jobbank_url)}" target="_blank" rel="noopener">Job Bank</a></div><div class="actions"><button class="btn" data-plus="${t.id}">+1</button><button class="btn" data-minus="${t.id}">−1</button></div></article>`).join('')}`;
 $$('[data-plus]').forEach(b=>b.onclick=()=>{const t=targets.find(x=>x.id===b.dataset.plus);setApps(t.id,appsFor(t)+1)});
 $$('[data-minus]').forEach(b=>b.onclick=()=>{const t=targets.find(x=>x.id===b.dataset.minus);setApps(t.id,appsFor(t)-1)});
}
init();
