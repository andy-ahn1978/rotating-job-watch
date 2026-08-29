let targets=[],payload={last_checked:null,jobs:[]},config={},profile={},seedApplications=[],view='new';
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];

const APPKEY='career-job-watch.v6.applications';
const STATUS=['Applied','Screening','Assessment','Interview','Final Interview','Offer','Rejected','No Response','Withdrawn'];
const HIDDENKEY='career-job-watch.v6.hiddenJobs';
const REASONS=['Wrong occupation','Contract / Temporary','Part-time','Too junior','Too senior','Canadian experience required','Wrong industry','Wrong location','Compensation too low','Other'];

let jobSearchPreset='';

async function safeJson(path,fallback){
  try{
    const r=await fetch(path+'?ts='+Date.now());
    if(!r.ok) throw new Error(path);
    return await r.json();
  }catch(e){ return fallback; }
}

async function init(){
  [targets,payload,config,profile,seedApplications]=await Promise.all([
    safeJson('targets.json',[]),
    safeJson('jobs.json',{last_checked:null,jobs:[]}),
    safeJson('search_config.json',{}),
    safeJson('profile.json',{}),
    safeJson('applications_seed.json',[])
  ]);
  $('#liveBadge').textContent=(payload&&Array.isArray(payload.jobs))?'LIVE':'OFFLINE';
  bindNav();
  render();
}

function bindNav(){
  $$('nav button').forEach(b=>b.onclick=()=>{
    view=b.dataset.view;
    $$('nav button').forEach(x=>x.classList.toggle('active',x===b));
    render();
  });
}

function esc(s=''){
  return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
}
function fmt(s){
  if(!s)return'Not yet';
  try{return new Date(s).toLocaleString()}catch(e){return s}
}
function dateOnly(s){
  if(!s)return'';
  const d=new Date(s+'T12:00:00');
  return isNaN(d)?s:d.toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'});
}
function today(){return new Date().toISOString().slice(0,10)}
function money(j){
  const a=j.salary_min,b=j.salary_max;
  if(!a&&!b)return'';
  const f=x=>'$'+Math.round(Number(x)).toLocaleString();
  if(a&&b)return `${f(a)} - ${f(b)}`;
  return a?`From ${f(a)}`:`Up to ${f(b)}`;
}
function slug(s=''){return String(s).toLowerCase().replace(/[^a-z0-9]+/g,' ').trim()}

function localApps(){
  try{
    const x=JSON.parse(localStorage.getItem(APPKEY));
    return Array.isArray(x)?x:[];
  }catch(e){return[]}
}
function allApps(){
  const map=new Map();
  seedApplications.forEach(a=>map.set(a.id,{...a,_seed:true}));
  localApps().forEach(a=>{
    if(a._deleted) map.delete(a.id);
    else map.set(a.id,{...map.get(a.id),...a,_seed:false});
  });
  return [...map.values()];
}
function saveLocal(records){
  localStorage.setItem(APPKEY,JSON.stringify(records));
}
function upsertApp(record){
  const local=localApps();
  const i=local.findIndex(a=>a.id===record.id);
  if(i>=0)local[i]={...local[i],...record};
  else local.push(record);
  saveLocal(local);
  render();
}
function deleteApp(id){
  const local=localApps();
  const seed=seedApplications.some(a=>a.id===id);
  const i=local.findIndex(a=>a.id===id);
  if(seed){
    const tomb={id,_deleted:true};
    if(i>=0)local[i]=tomb; else local.push(tomb);
  }else if(i>=0)local.splice(i,1);
  saveLocal(local);
  render();
}
function applicationForJob(j){
  const u=(j.url||'').trim();
  return allApps().find(a=>
    (u&&a.url===u) ||
    (slug(a.company)===slug(j.company)&&slug(a.title)===slug(j.title))
  );
}
function companyApps(name){
  const n=slug(name);
  return allApps().filter(a=>{
    const c=slug(a.company);
    return c===n || c.includes(n) || n.includes(c);
  });
}
function markApplied(j){
  if(applicationForJob(j))return;
  upsertApp({
    id:'job-'+Date.now(),
    company:j.company||'',
    title:j.title||'',
    date:today(),
    status:'Applied',
    source:j.source||'Job Watch',
    url:j.url||'',
    notes:'Added from Job Watch'
  });
}
function statusClass(status){
  return 'status-'+slug(status).replace(/\s+/g,'-');
}
function activePipeline(a){
  return ['Screening','Assessment','Interview','Final Interview'].includes(a.status);
}


function hiddenJobs(){
  try{const x=JSON.parse(localStorage.getItem(HIDDENKEY));return Array.isArray(x)?x:[];}catch(e){return[]}
}
function saveHidden(x){localStorage.setItem(HIDDENKEY,JSON.stringify(x))}
function jobId(j){return String(j.key||j.external_id||j.url||[j.company,j.title,j.location].join('|'))}
function isHidden(j){return hiddenJobs().some(x=>x.job_id===jobId(j))}
function hideJob(j){
  const reason=prompt('Why is this not a match?\n\n'+REASONS.map((x,i)=>`${i+1}. ${x}`).join('\n')+'\n\nEnter number or short reason:','1');
  if(reason===null)return;
  let label=reason.trim();
  const n=Number(label);
  if(Number.isInteger(n)&&n>=1&&n<=REASONS.length)label=REASONS[n-1];
  if(!label)label='Other';
  const rows=hiddenJobs().filter(x=>x.job_id!==jobId(j));
  rows.push({
    job_id:jobId(j), company:j.company||'', title:j.title||'', location:j.location||'',
    url:j.url||'', reason:label, hidden_date:today(),
    features:learningFeatures(j)
  });
  saveHidden(rows); render();
}
function restoreHidden(id){saveHidden(hiddenJobs().filter(x=>x.job_id!==id));render()}

function targetForCompany(company){
  return targets.find(t=>targetMatchesCompany(t,company||''))||null;
}
function companyFit(j){
  const t=targetForCompany(j.company);
  return t?Number(t.fit||0):0;
}
function employmentInfo(j){
  const ct=String(j.contract_time||'').toLowerCase();
  const typ=String(j.contract_type||'').toLowerCase();
  const text=[j.title,j.description,j.contract_time,j.contract_type].join(' ').toLowerCase();
  const bad=[
    [/\bpart[- ]time\b/,'Part-time'],
    [/\btemporary\b|\btemp position\b/,'Temporary'],
    [/\bintern(ship)?\b/,'Internship'],
    [/\bco[- ]?op\b/,'Co-op'],
    [/\bseasonal\b/,'Seasonal'],
    [/\bcasual\b/,'Casual'],
    [/\bfixed[- ]term\b/,'Fixed-term'],
    [/\b\d+\s*[- ]?(month|months|year|years)\s+contract\b/,'Contract'],
    [/\bcontract (role|position|employment|term)\b/,'Contract']
  ];
  if(ct==='part_time')return {grade:'NO',label:'Part-time',eligible:false};
  if(typ==='contract')return {grade:'NO',label:'Contract',eligible:false};
  for(const [rx,label] of bad)if(rx.test(text))return {grade:'NO',label,eligible:false};
  const full=ct==='full_time'||/\bfull[- ]time\b/.test(text);
  const perm=typ==='permanent'||/\bpermanent\b/.test(text);
  if(full&&perm)return {grade:'BEST',label:'Full-time · Permanent',eligible:true};
  if(full)return {grade:'OK',label:'Full-time',eligible:true};
  if(perm)return {grade:'OK',label:'Permanent',eligible:true};
  return {grade:'?',label:'Employment not stated',eligible:true};
}
function canadaExpInfo(j){
  const text=[j.title,j.description].join(' ').toLowerCase();
  if(/\b(no canadian experience required|canadian experience (is )?not required|experience in canada (is )?not required)\b/.test(text))
    return {grade:'A+',label:'Canadian exp. not required'};
  if(/\b\d+\+?\s*(years?|yrs?)\s+(of )?(canadian|canada|in canada).{0,35}(required|must|mandatory)|\b(required|must have|mandatory).{0,35}\d+\+?\s*(years?|yrs?).{0,20}(canadian|canada)\b/.test(text))
    return {grade:'F',label:'Years of Canadian exp. required'};
  if(/\b(canadian experience|experience in canada|canadian market experience).{0,30}(required|must have|mandatory)\b|\b(required|must have|mandatory).{0,30}(canadian experience|experience in canada)\b/.test(text))
    return {grade:'E',label:'Canadian exp. required'};
  if(/\b(canadian experience|canadian market experience).{0,25}strongly preferred\b|\bstrongly preferred.{0,25}(canadian experience|canadian market experience)\b/.test(text))
    return {grade:'D',label:'Canadian exp. strongly preferred'};
  if(/\b(canadian market|canada market).{0,30}(knowledge|familiarity|understanding).{0,30}(preferred|asset|nice to have)\b/.test(text))
    return {grade:'C',label:'Canadian market familiarity preferred'};
  if(/\b(canadian experience|experience in canada|canadian market experience).{0,30}(preferred|asset|nice to have)\b/.test(text))
    return {grade:'B',label:'Canadian exp. preferred'};
  return {grade:'A',label:'Canadian exp. not mentioned'};
}
function learningFeatures(j){
  const e=employmentInfo(j),c=canadaExpInfo(j);
  return {
    job_fit:Number(j.score||0), company_fit:companyFit(j),
    canada_experience:c.grade, employment:e.label,
    target_company:!!j.target_company, source:j.source||'',
    matched_keywords:j.matched_keywords||[]
  };
}

function render(){
  const jobs=(payload.jobs||[]).filter(j=>!isHidden(j));
  const newJobs=jobs.filter(j=>j.is_new);
  const apps=allApps();
  $('#newCount').textContent=newJobs.length;
  $('#jobCount').textContent=jobs.length;
  $('#companyCount').textContent=targets.length;
  $('#applicationCount').textContent=apps.length;
  $('#interviewCount').textContent=apps.filter(activePipeline).length;
  $('#lastChecked').textContent=fmt(payload.last_checked);

  if(view==='new')jobView(newJobs,true);
  if(view==='all')jobView(jobs,false);
  if(view==='companies')companyView();
  if(view==='applications')applicationsView();
  if(view==='hidden')hiddenView();
  if(view==='profile')profileView();
}

function jobView(jobs,newOnly){
  $('#content').innerHTML=`
    <div class="toolbar jobs-toolbar">
      <input id="search" class="input" placeholder="Search jobs, companies, cities">
      <select id="sourceFilter" class="select">
        <option value="">All sources</option><option>Official</option><option>Adzuna</option>
      </select>
      <select id="targetFilter" class="select">
        <option value="">All companies</option><option value="target">Target companies only</option>
      </select>
      <select id="employmentFilter" class="select">
        <option value="eligible">Hide explicit contract / part-time</option>
        <option value="">Show all employment types</option>
        <option value="best">Full-time + Permanent stated</option>
      </select>
    </div>
    <div id="jobList"></div>`;

  if(jobSearchPreset){
    $('#search').value=jobSearchPreset;
    jobSearchPreset='';
  }

  const paint=()=>{
    const q=$('#search').value.toLowerCase();
    const src=$('#sourceFilter').value;
    const target=$('#targetFilter').value;
    const emp=$('#employmentFilter').value;
    const arr=jobs
      .filter(j=>[j.title,j.company,j.location,(j.matched_keywords||[]).join(' ')].join(' ').toLowerCase().includes(q))
      .filter(j=>!src||j.source===src)
      .filter(j=>target!=='target'||j.target_company)
      .filter(j=>!isHidden(j))
      .filter(j=>emp==='' || (emp==='eligible'&&employmentInfo(j).eligible) || (emp==='best'&&employmentInfo(j).grade==='BEST'));

    $('#jobList').innerHTML=arr.length?arr.map(j=>{
      const strong=Number(j.score)>=Number(config.strong_match_score||8);
      const salary=money(j);
      const applied=applicationForJob(j);
      return `<article class="card ${j.is_new?'new':''}">
        <div class="top">
          <div>
            <div class="title">${esc(j.title)}</div>
            <div class="company">${esc(j.company)}</div>
          </div>
          <div class="top-badges">
            ${j.is_new?'<span class="badge new">NEW</span>':''}
            ${applied?`<span class="badge applied">APPLIED</span>`:''}
          </div>
        </div>
        <div class="meta">${esc(j.location||'')} · ${esc(j.source||'')} ${salary?'· '+esc(salary):''}</div>
        <div class="badges">
          <span class="badge fit">Job Fit ${esc(j.score)}/10</span>
          ${companyFit(j)?`<span class="badge company-fit">Company Fit ${esc(companyFit(j))}/10</span>`:''}
          <span class="badge employment ${employmentInfo(j).eligible?'good':'warning'}">${esc(employmentInfo(j).label)}</span>
          <span class="badge canada canada-${esc(canadaExpInfo(j).grade).replace('+','plus')}">Canada Exp ${esc(canadaExpInfo(j).grade)} · ${esc(canadaExpInfo(j).label.replace('Canadian exp. ','').replace('Canadian market ',''))}</span>
          ${strong?'<span class="badge strong">Strong match</span>':''}
          ${j.target_company?'<span class="badge target">Target company</span>':''}
          ${(j.matched_keywords||[]).slice(0,5).map(k=>`<span class="badge">${esc(k)}</span>`).join('')}
        </div>
        <div class="actions">
          <a class="btn primary" href="${esc(j.url)}" target="_blank" rel="noopener">Open Job</a>
          ${applied
            ? `<button class="btn applied-btn" disabled>Applied ${dateOnly(applied.date)}</button>`
            : `<button class="btn apply-btn" data-apply="${esc(j.key||j.external_id||'')}">Mark Applied</button>`}
          <button class="btn not-match" data-hide="${esc(jobId(j))}">Not a Match</button>
          <a class="btn linkedin" href="https://www.linkedin.com/jobs/search/?keywords=${encodeURIComponent(j.company+' '+j.title)}&location=Ontario%2C%20Canada" target="_blank" rel="noopener">LinkedIn</a>
          <a class="btn indeed" href="https://ca.indeed.com/jobs?q=${encodeURIComponent(j.company+' '+j.title)}&l=Ontario" target="_blank" rel="noopener">Indeed</a>
        </div>
      </article>`;
    }).join(''):`<div class="empty">${newOnly?'No new qualifying jobs.':'No qualifying jobs found yet.'}</div>`;

    $$('[data-apply]').forEach(b=>b.onclick=()=>{
      const id=b.dataset.apply;
      const j=jobs.find(x=>(x.key||x.external_id||'')===id);
      if(j)markApplied(j);
    });
    $$('[data-hide]').forEach(b=>b.onclick=()=>{
      const j=jobs.find(x=>jobId(x)===b.dataset.hide);
      if(j)hideJob(j);
    });
  };
  $('#search').oninput=paint;
  $('#sourceFilter').onchange=paint;
  $('#targetFilter').onchange=paint;
  $('#employmentFilter').onchange=paint;
  paint();
}

function targetMatchesCompany(t,company){
  const c=slug(company), candidates=[t.name,...(t.aliases||[])].map(slug).filter(Boolean);
  return candidates.some(a=>a===c||a.includes(c)||c.includes(a));
}
function companyView(){
  $('#content').innerHTML=`
    <div class="toolbar company-toolbar">
      <input id="companySearch" class="input" placeholder="Search target companies, equipment, category">
      <select id="fitFilter" class="select">
        <option value="0">All fit scores</option>
        <option value="9">Fit 9+</option>
        <option value="8.5">Fit 8.5+</option>
        <option value="8">Fit 8+</option>
      </select>
      <select id="openFilter" class="select">
        <option value="">All targets</option>
        <option value="open">With discovered jobs</option>
      </select>
    </div>
    <div id="companies"></div>`;

  const paint=()=>{
    const q=$('#companySearch').value.toLowerCase();
    const f=Number($('#fitFilter').value);
    const of=$('#openFilter').value;

    const arr=targets.map(t=>{
      const current=(payload.jobs||[]).filter(j=>targetMatchesCompany(t,j.company||''));
      return {...t,_jobs:current};
    }).filter(t=>
      [t.name,t.region,t.scope,t.category,(t.equipment||[]).join(' ')].join(' ').toLowerCase().includes(q)
    ).filter(t=>Number(t.fit||0)>=f)
     .filter(t=>of!=='open'||t._jobs.length>0)
     .sort((a,b)=>(b._jobs.length-a._jobs.length)||(Number(b.fit)-Number(a.fit)));

    $('#companies').innerHTML=arr.length?arr.map(t=>{
      const apps=companyApps(t.name);
      const links=[];
      if(t.careers_url)links.push(`<a class="btn primary" href="${esc(t.careers_url)}" target="_blank" rel="noopener">Official</a>`);
      const lnk=t.linkedin_url||`https://www.linkedin.com/jobs/search/?keywords=${encodeURIComponent(t.name)}&location=Ontario%2C%20Canada`;
      const ind=t.indeed_url||`https://ca.indeed.com/jobs?q=${encodeURIComponent(t.name)}&l=Ontario`;
      links.push(`<a class="btn linkedin" href="${esc(lnk)}" target="_blank" rel="noopener">LinkedIn</a>`);
      links.push(`<a class="btn indeed" href="${esc(ind)}" target="_blank" rel="noopener">Indeed</a>`);
      return `<article class="card">
        <div class="company-row">
          <div>
            <div class="title">${esc(t.name)}</div>
            <div class="company">${esc(t.category||'Target company')}${t.scope?' · '+esc(t.scope):''}</div>
          </div>
          <div class="right">
            <div class="application-count">${t._jobs.length}</div>
            <div class="small">current jobs</div>
          </div>
        </div>
        <div class="badges">
          <span class="badge fit">Target Fit ${esc(t.fit)}/10</span>
          ${(t.equipment||[]).slice(0,5).map(x=>`<span class="badge">${esc(x)}</span>`).join('')}
          ${apps.length?`<span class="badge applied">${apps.length} applications</span>`:''}
        </div>
        <div class="source-row">${links.join('')}</div>
        <div class="actions">
          <button class="btn" data-viewjobs="${esc(t.name)}">View discovered jobs (${t._jobs.length})</button>
          <button class="btn" data-addcompany="${esc(t.name)}">+ Add application</button>
        </div>
      </article>`;
    }).join(''):'<div class="empty">No target companies match this filter.</div>';

    $$('[data-viewjobs]').forEach(b=>b.onclick=()=>{
      view='all'; jobSearchPreset=b.dataset.viewjobs;
      $$('nav button').forEach(x=>x.classList.toggle('active',x.dataset.view==='all'));
      render();
    });
    $$('[data-addcompany]').forEach(b=>b.onclick=()=>{
      view='applications';
      $$('nav button').forEach(x=>x.classList.toggle('active',x.dataset.view==='applications'));
      render();
      setTimeout(()=>{
        const c=$('#newCompany'); if(c){c.value=b.dataset.addcompany; $('#newTitle').focus();}
      },0);
    });
  };
  $('#companySearch').oninput=paint;
  $('#fitFilter').onchange=paint;
  $('#openFilter').onchange=paint;
  paint();
}

function appStats(apps){
  return {
    total:apps.length,
    applied:apps.filter(a=>a.status==='Applied').length,
    pipeline:apps.filter(activePipeline).length,
    interview:apps.filter(a=>['Interview','Final Interview'].includes(a.status)).length,
    rejected:apps.filter(a=>a.status==='Rejected').length,
    offers:apps.filter(a=>a.status==='Offer').length
  };
}

function applicationsView(){
  const apps=allApps().sort((a,b)=>(b.date||'').localeCompare(a.date||''));
  const s=appStats(apps);
  $('#content').innerHTML=`
    <section class="application-stats">
      <div><b>${s.total}</b><span>Total</span></div>
      <div><b>${s.applied}</b><span>Applied</span></div>
      <div><b>${s.pipeline}</b><span>Pipeline</span></div>
      <div><b>${s.interview}</b><span>Interview</span></div>
      <div><b>${s.rejected}</b><span>Rejected</span></div>
      <div><b>${s.offers}</b><span>Offers</span></div>
    </section>

    <details class="panel add-panel">
      <summary>+ Add application manually</summary>
      <div class="form-grid">
        <input id="newCompany" class="input" placeholder="Company">
        <input id="newTitle" class="input" placeholder="Position title">
        <input id="newDate" class="input" type="date" value="${today()}">
        <select id="newStatus" class="select">${STATUS.map(x=>`<option>${x}</option>`).join('')}</select>
        <input id="newUrl" class="input wide" placeholder="Job URL (optional)">
        <input id="newNotes" class="input wide" placeholder="Notes (optional)">
      </div>
      <button id="saveApplication" class="btn primary">Save Application</button>
    </details>

    <div class="toolbar application-toolbar">
      <input id="appSearch" class="input" placeholder="Search company or position">
      <select id="appFilter" class="select">
        <option value="">All statuses</option>
        ${STATUS.map(x=>`<option>${x}</option>`).join('')}
      </select>
    </div>

    <div class="data-actions">
      <button id="exportApps" class="btn">Export application data</button>
      <label class="btn file-btn">Import data<input id="importApps" type="file" accept=".json,application/json"></label>
    </div>
    <div class="notice">Application edits are saved in this browser. Export a backup if you use both phone and PC.</div>
    <div id="applicationList"></div>`;

  const paint=()=>{
    const q=$('#appSearch').value.toLowerCase();
    const sf=$('#appFilter').value;
    const arr=allApps().sort((a,b)=>(b.date||'').localeCompare(a.date||''))
      .filter(a=>[a.company,a.title,a.notes,a.source].join(' ').toLowerCase().includes(q))
      .filter(a=>!sf||a.status===sf);

    $('#applicationList').innerHTML=arr.length?arr.map(a=>`
      <article class="card application-card">
        <div class="top">
          <div>
            <div class="title">${esc(a.title||'Untitled role')}</div>
            <div class="company">${esc(a.company||'Unknown company')}</div>
          </div>
          <span class="badge status ${statusClass(a.status)}">${esc(a.status||'Applied')}</span>
        </div>
        <div class="meta">${a.date?`Applied: ${esc(dateOnly(a.date))}`:'Date not recorded'}${a.source?' · '+esc(a.source):''}</div>
        ${a.notes?`<div class="application-notes">${esc(a.notes)}</div>`:''}
        <div class="application-controls">
          <select class="select compact" data-status="${esc(a.id)}">
            ${STATUS.map(x=>`<option ${x===a.status?'selected':''}>${x}</option>`).join('')}
          </select>
          ${a.url?`<a class="btn primary" href="${esc(a.url)}" target="_blank" rel="noopener">Open Job</a>`:''}
          <button class="btn danger" data-delete="${esc(a.id)}">Delete</button>
        </div>
      </article>`).join(''):'<div class="empty">No application records match this filter.</div>';

    $$('[data-status]').forEach(el=>el.onchange=()=>{
      const a=allApps().find(x=>x.id===el.dataset.status);
      if(a)upsertApp({...a,status:el.value,_seed:undefined});
    });
    $$('[data-delete]').forEach(el=>el.onclick=()=>{
      if(confirm('Delete this application record?'))deleteApp(el.dataset.delete);
    });
  };

  $('#saveApplication').onclick=()=>{
    const company=$('#newCompany').value.trim(),title=$('#newTitle').value.trim();
    if(!company||!title){alert('Company and position title are required.');return;}
    upsertApp({
      id:'manual-'+Date.now(),
      company,title,
      date:$('#newDate').value||today(),
      status:$('#newStatus').value,
      source:'Manual',
      url:$('#newUrl').value.trim(),
      notes:$('#newNotes').value.trim()
    });
  };
  $('#appSearch').oninput=paint;
  $('#appFilter').onchange=paint;

  $('#exportApps').onclick=()=>{
    const blob=new Blob([JSON.stringify(allApps(),null,2)],{type:'application/json'});
    const a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download='career_job_watch_applications_'+today()+'.json';
    a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href),500);
  };
  $('#importApps').onchange=async e=>{
    const f=e.target.files?.[0]; if(!f)return;
    try{
      const data=JSON.parse(await f.text());
      if(!Array.isArray(data))throw new Error('Expected an array');
      const local=localApps();
      const map=new Map(local.map(x=>[x.id,x]));
      data.forEach((x,i)=>{
        if(!x.id)x.id='import-'+Date.now()+'-'+i;
        map.set(x.id,x);
      });
      saveLocal([...map.values()]);
      render();
    }catch(err){alert('Could not import this JSON file.');}
  };
  paint();
}


function hiddenView(){
  const rows=hiddenJobs().sort((a,b)=>(b.hidden_date||'').localeCompare(a.hidden_date||''));
  $('#content').innerHTML=`
    <section class="panel">
      <h3>Hidden Jobs / Learning Data</h3>
      <p class="meta">Not a Match decisions are kept as training data. Restore a job at any time.</p>
      <div class="data-actions">
        <button id="exportLearning" class="btn">Export learning data</button>
        <button id="clearHidden" class="btn danger">Clear hidden jobs</button>
      </div>
    </section>
    <div id="hiddenList">${rows.length?rows.map(x=>`
      <article class="card">
        <div class="top"><div><div class="title">${esc(x.title)}</div><div class="company">${esc(x.company)}</div></div>
        <span class="badge warning">${esc(x.reason)}</span></div>
        <div class="meta">${esc(x.location||'')} · Hidden ${esc(dateOnly(x.hidden_date))}</div>
        <div class="badges">
          <span class="badge fit">Job Fit ${esc(x.features?.job_fit||0)}/10</span>
          ${x.features?.company_fit?`<span class="badge company-fit">Company Fit ${esc(x.features.company_fit)}/10</span>`:''}
          <span class="badge">Canada Exp ${esc(x.features?.canada_experience||'A')}</span>
        </div>
        <div class="actions">
          ${x.url?`<a class="btn primary" href="${esc(x.url)}" target="_blank" rel="noopener">Open Job</a>`:''}
          <button class="btn" data-restore="${esc(x.job_id)}">Restore</button>
        </div>
      </article>`).join(''):'<div class="empty">No hidden jobs yet.</div>'}</div>`;
  $$('[data-restore]').forEach(b=>b.onclick=()=>restoreHidden(b.dataset.restore));
  $('#clearHidden').onclick=()=>{if(confirm('Restore all hidden jobs and clear learning records?')){saveHidden([]);render();}};
  $('#exportLearning').onclick=()=>{
    const data={exported:today(),hidden_jobs:hiddenJobs(),applications:allApps()};
    const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);
    a.download='career_job_watch_learning_'+today()+'.json';a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href),500);
  };
}

function profileView(){
  const exp=(profile.experience||[]).map(x=>`
    <article class="timeline-item">
      <div class="timeline-head">
        <div><div class="title">${esc(x.role)}</div><div class="company">${esc(x.company)}</div></div>
        <div class="period">${esc(x.period||'')}</div>
      </div>
      <ul>${(x.bullets||[]).map(b=>`<li>${esc(b)}</li>`).join('')}</ul>
    </article>`).join('');

  $('#content').innerHTML=`
    <section class="profile-hero">
      <div class="eyebrow">CAREER PROFILE</div>
      <h2>${esc(profile.name||'Career Profile')}</h2>
      <div class="profile-headline">${esc(profile.headline||'')}</div>
      <div class="meta">${esc(profile.location||'')}</div>
      <p>${esc(profile.summary||'')}</p>
    </section>

    <section class="profile-grid">
      <div class="profile-panel">
        <h3>Career Highlights</h3>
        <ul>${(profile.highlights||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>
      </div>
      <div class="profile-panel">
        <h3>Core Competencies</h3>
        <div class="badges">${(profile.competencies||[]).map(x=>`<span class="badge">${esc(x)}</span>`).join('')}</div>
      </div>
      <div class="profile-panel">
        <h3>Equipment & Technical Background</h3>
        <div class="badges">${(profile.equipment||[]).map(x=>`<span class="badge">${esc(x)}</span>`).join('')}</div>
      </div>
      <div class="profile-panel">
        <h3>Target Roles</h3>
        <div class="badges">${(profile.target_roles||[]).map(x=>`<span class="badge target">${esc(x)}</span>`).join('')}</div>
      </div>
    </section>

    <section class="profile-section">
      <h3>Professional Experience</h3>
      <div class="timeline">${exp}</div>
    </section>

    <section class="profile-grid">
      <div class="profile-panel">
        <h3>Certifications</h3>
        <ul>${(profile.certifications||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>
      </div>
    </section>
    <div class="notice privacy-note">This public profile intentionally excludes phone number, email address, immigration documents, and other private information.</div>`;
}

init();
