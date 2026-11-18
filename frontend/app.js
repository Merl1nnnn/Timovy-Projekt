'use strict';
const $ = id => document.getElementById(id);
let jobs = [], filtered = [], visible = 20, rankMode = 'required', dataset = null, loadError = null, selectedJob = null;
const text = (tag, value, className) => { const n=document.createElement(tag); n.textContent=value; if(className)n.className=className; return n; };
const required = j => [...new Set(j.required_skills || [])];
const nice = j => [...new Set(j.nice_to_have_skills || [])];
const skills = j => [...new Set([...required(j), ...nice(j)])];
const experience = j => j.min_experience_years == null ? t('unspecified') : j.min_experience_years === 0 ? t('noExperience') : t('experienceYears', {n: j.min_experience_years});
const education = j => j.education ? t('edu_' + j.education) : t('unspecified');
function tags(items){ const box=text('div','','tags'); for(const item of items)box.append(text('span',item,'tag')); return box; }
function salary(j){ if(j.salary_min==null&&j.salary_max==null)return t('unspecified'); const fmt=n=>new Intl.NumberFormat(MESSAGES[language].locale).format(n); return `${j.salary_min!=null?fmt(j.salary_min):'…'}${j.salary_max!=null?' – '+fmt(j.salary_max):'+'} ${j.salary_currency||''}`; }
function matches(j){const q=$('search').value.toLocaleLowerCase().trim();return (!q||[j.title,j.company,j.location,j.summary,...skills(j)].join(' ').toLocaleLowerCase().includes(q))&&['specialization','seniority','site'].every(k=>!$(k).value||j[k]===$(k).value)&&(!$('doubtful').checked||j.low_confidence);}
function render(){filtered=jobs.filter(matches);$('count').textContent=filtered.length;$('skills').textContent=new Set(filtered.flatMap(skills)).size;$('review').textContent=filtered.filter(j=>j.low_confidence).length;$('remote').textContent=filtered.length?Math.round(100*filtered.filter(j=>j.remote).length/filtered.length)+'%':'—';$('shown').textContent=t('results',{n:filtered.length});$('jobs').replaceChildren();$('status').textContent=filtered.length?'':t('empty');
const counts=new Map();filtered.forEach(j=>(rankMode==='nice'?nice(j):required(j)).forEach(s=>counts.set(s,(counts.get(s)||0)+1)));const ranked=[...counts].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).slice(0,8);$('bars').replaceChildren();for(const [name,n]of ranked){const row=text('div','');const label=text('div','','bar-label');label.append(text('span',name),text('span',n));const track=text('div','','track'),fill=text('div','','fill');fill.style.width=(100*n/filtered.length)+'%';track.append(fill);row.append(label,track);$('bars').append(row);}
for(const j of filtered.slice(0,visible)){const card=text('article','','job');const left=text('div','');left.append(text('h3',j.title||t('untitled')),text('p',`${j.company||'—'} · ${j.location||t('noLocation')} · ${j.seniority||t('noLevel')} · ${t('experience')}: ${experience(j)}`));const list=tags(required(j).slice(0,7));for(const s of nice(j).slice(0,3))list.append(text('span',s,'tag nice'));if(j.low_confidence)list.prepend(text('span',t('needsReview'),'tag flag'));left.append(list);const right=text('div',''),pay=text('div',salary(j),'salary');pay.append(text('small',t('salaryNote')));const open=text('button',t('details'),'secondary');open.addEventListener('click',()=>detail(j));right.append(pay,open);card.append(left,right);$('jobs').append(card);}$('more').hidden=filtered.length<=visible;$('export').disabled=!filtered.length;}
function detail(j){selectedJob=j;const box=$('detail-content');box.replaceChildren(text('div',j.site||'','eyebrow'),text('h2',j.title||t('untitled')),text('p',`${j.company||'—'} · ${j.location||t('noLocation')}`));box.append(text('h3',t('summary')),text('p',j.summary||t('noSummary'),'summary'));const facts=text('div','','facts');for(const [label,value]of [[t('experience'),experience(j)],[t('education'),education(j)],[t('seniority'),j.seniority||t('unspecified')]]){const f=text('span',label+': ');f.append(text('strong',value));facts.append(f);}box.append(text('h3',t('facts')),facts);for(const [label,values]of [[t('required'),required(j)],[t('nice'),nice(j)]]){box.append(text('h3',label),tags(values));}box.append(text('h3',t('quality')),text('p',t('confidence',{score:j.confidence??'—'})));const ul=text('ul','');for(const issue of j.quality_issues||[])ul.append(text('li',issue));box.append(ul);box.append(text('p',`${t('model')} ${j.model||'—'} · ${j.language||'—'} · ${salary(j)}`));if(j.source_url){try{const u=new URL(j.source_url);if(['http:','https:'].includes(u.protocol)&&!['localhost','127.0.0.1','::1','[::1]'].includes(u.hostname)){const a=text('a',t('sourceLink'));a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';box.append(a);}else box.append(text('p',t('localSource')));}catch{}}box.append(text('p',t('evidence')));if(!$('detail').open)$('detail').showModal();}
$('close').onclick=()=>$('detail').close();$('detail').addEventListener('click',e=>{if(e.target===$('detail'))$('detail').close();});for(const id of ['search','specialization','seniority','site','doubtful'])$(id).addEventListener('input',()=>{visible=20;render();if(!dataset)renderMetadata();});$('reset').onclick=()=>{for(const id of ['search','specialization','seniority','site'])$(id).value='';$('doubtful').checked=false;visible=20;render();if(!dataset)renderMetadata();};$('more').onclick=()=>{visible+=20;render();};
for(const mode of ['required','nice'])$('rank-'+mode).addEventListener('click',()=>{rankMode=mode;for(const m of ['required','nice']){$('rank-'+m).classList.toggle('active',m===mode);$('rank-'+m).setAttribute('aria-pressed',String(m===mode));}render();});
function csvCell(v){let s=String(v??'');if(/^[=+\-@\t\r]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';}
$('export').onclick=()=>{const fields=['title','company','location','seniority','specialization','min_experience_years','education','required_skills','nice_to_have_skills','salary_min','salary_max','salary_currency','summary','low_confidence','source_url'];const csv='\uFEFF'+[fields,...filtered.map(j=>fields.map(k=>Array.isArray(j[k])?j[k].join('; '):j[k]))].map(r=>r.map(csvCell).join(',')).join('\r\n');const u=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=u;a.download='skillminer.csv';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};
// Each dataset kind is published to its own file; jobs_real.json exists only after the team publishes real data.
const SOURCES={synthetic:'data/jobs.json',real:'data/jobs_real.json'};
const cache={};
let kind=initialKind(), missing=false, loadToken=0;
function initialKind(){const q=new URLSearchParams(location.search).get('data');if(q==='real')return 'real';if(q==='mock')return 'synthetic';return readPreference('skillminer-dataset')==='real'?'real':'synthetic';}
function renderMetadata(){
  const shownKind=dataset?(dataset.dataset_kind==='real'?'real':'synthetic'):kind;
  document.body.dataset.dataset=shownKind;
  for(const k of ['synthetic','real']){$('data-'+k).classList.toggle('active',k===kind);$('data-'+k).setAttribute('aria-pressed',String(k===kind));}
  $('dataset').textContent=t(loadError?'unavailable':missing?'realMissingShort':dataset?(shownKind==='real'?'published':'synthetic'):'loading');
  $('notice').textContent=t(missing?'realMissing':shownKind==='real'?'realNotice':'syntheticNotice');
  $('updated').textContent=dataset?t('updated')+' '+new Date(dataset.generated_at).toLocaleString(MESSAGES[language].locale):'';
  if(!dataset){for(const id of ['count','skills','review','remote'])$(id).textContent='—';$('shown').textContent='';}
  if(loadError)$('status').textContent=t('loadError',{error:loadError});
  else if(missing)$('status').textContent=t('realMissing');
  else if(!dataset)$('status').textContent=t('loading');
}
function renderTheme(){const dark=document.documentElement.dataset.theme==='dark';$('theme').textContent=(dark?'☀ ':'☾ ')+t(dark?'light':'dark');$('theme').setAttribute('aria-label',t('theme')+': '+t(dark?'light':'dark'));$('theme').setAttribute('aria-pressed',String(dark));}
function applyLanguage(){
  document.documentElement.lang=language;document.title=t('title');$('language').value=language;
  document.querySelectorAll('[data-i18n]').forEach(el=>el.textContent=t(el.dataset.i18n));
  document.querySelectorAll('[data-i18n-aria]').forEach(el=>el.setAttribute('aria-label',t(el.dataset.i18nAria)));
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el=>el.setAttribute('placeholder',t(el.dataset.i18nPlaceholder)));
  renderTheme();if(dataset)render();renderMetadata();
  if($('detail').open&&selectedJob)detail(selectedJob);
}
$('language').addEventListener('change',()=>{if(!Object.hasOwn(MESSAGES,$('language').value))return;language=$('language').value;savePreference('skillminer-language',language);applyLanguage();});
$('theme').addEventListener('click',()=>{const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=theme;savePreference('skillminer-theme',theme);renderTheme();});
function fillOptions(){for(const k of ['specialization','seniority','site']){const sel=$(k);while(sel.options.length>1)sel.remove(1);for(const v of [...new Set(jobs.map(j=>j[k]).filter(Boolean))].sort()){const o=text('option',v);o.value=v;sel.append(o);}}}
async function fetchKind(k){
  if(cache[k])return cache[k];
  const res=await fetch(`${SOURCES[k]}?t=${Date.now()}`,{cache:'no-store'});
  if(res.status===404&&k==='real')return {missing:true};  // not cached: it may be published while the page is open
  if(!res.ok)throw new Error(`HTTP ${res.status}`);
  const data=await res.json();if(!Array.isArray(data.jobs))throw new Error(t('invalidData'));
  return cache[k]={data};
}
async function load(){
  const token=++loadToken;
  dataset=null;loadError=null;missing=false;jobs=[];selectedJob=null;if($('detail').open)$('detail').close();
  for(const id of ['search','specialization','seniority','site'])$(id).value='';$('doubtful').checked=false;visible=20;
  fillOptions();render();renderMetadata();
  try{const r=await fetchKind(kind);if(token!==loadToken)return;if(r.missing)missing=true;else{dataset=r.data;jobs=r.data.jobs;}}
  catch(e){if(token!==loadToken)return;loadError=e.message;}
  fillOptions();render();renderMetadata();
}
for(const k of ['synthetic','real'])$('data-'+k).addEventListener('click',()=>{if(k===kind)return;kind=k;savePreference('skillminer-dataset',k);const u=new URL(location.href);u.searchParams.set('data',k==='real'?'real':'mock');history.replaceState(null,'',u);load();});
applyLanguage();load();
