'use strict';
(() => {
  const $ = (id) => document.getElementById(id);
  const names = {non_vegetarian:'Non-vegetarian', vegan:'Vegan', vegetarian_no_eggs:'Vegetarian without eggs', vegetarian_with_eggs:'Vegetarian with eggs'};
  const state = {file:null, url:null, result:null, config:null, busy:false};
  const storageKey = 'foodlens.saved.v1';
  let toastTimer;
  const preference = () => document.querySelector('input[name="preference"]:checked').value;
  const csrf = () => document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
  const text = (tag, value, className) => { const e=document.createElement(tag); e.textContent=String(value || ''); if(className)e.className=className; return e; };
  function toast(message) { $('toast').textContent=message; $('toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(() => $('toast').hidden=true, 3600); }
  function showError(message) { $('error').textContent=message; $('error').hidden=false; }
  async function api(path, options={}) {
    const response=await fetch(path,{credentials:'same-origin',...options,headers:{'X-CSRFToken':csrf(),...(options.headers||{})}});
    let data;
    try { data=await response.json(); } catch { throw new Error('The server returned an unexpected response. Refresh the page and try again.'); }
    if(!response.ok) throw new Error(data.error || 'This request could not be completed. Refresh and try again.');
    return data;
  }
  function setBusy(busy) {
    state.busy=busy; $('progress').hidden=!busy;
    ['analyze-button','camera-button','upload-button','remove-photo'].forEach(id => $(id).disabled=busy);
    document.querySelectorAll('[data-example],input[name="preference"]').forEach(e=>e.disabled=busy);
  }
  function changePage(page) {
    ['home','scan','history','about','settings'].forEach(p=>$(p+'-page').hidden=p!==page);
    document.querySelectorAll('[data-page]').forEach(b=>{if(b.dataset.page===page)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
    if(page==='history')renderHistory();if(page==='settings')loadUsage();
    window.scrollTo({top:0,behavior:'smooth'});
  }
  async function loadUsage(){try{const u=await api('/api/usage/');$('usage-scans').textContent=u.scans;$('usage-cost').textContent='$'+Number(u.estimated_usd).toFixed(4);$('usage-model').textContent=u.model;$('usage-tokens').textContent=u.input_tokens.toLocaleString()+' input · '+u.output_tokens.toLocaleString()+' output tokens';const o=document.querySelector('.usage-orbit');o?.classList.remove('pulse');requestAnimationFrame(()=>o?.classList.add('pulse'));}catch{}}
  function clearPhoto() {
    $('capture-hint').replaceChildren(text('strong','The ingredients side, please.'),text('p','Keep the whole list sharp and in frame.'));
    if(state.url)URL.revokeObjectURL(state.url);
    state.file=null;state.url=null;$('preview').removeAttribute('src');$('preview').hidden=true;
    $('camera-illustration').hidden=false;$('capture-hint').hidden=false;$('scan-options').hidden=true;
    $('remove-photo').hidden=true;$('camera-input').value='';$('upload-input').value='';
  }
  function selectPhoto(file) {
    if(!file)return;
    $('error').hidden=true;
    if(!['image/jpeg','image/png','image/webp','image/heic','image/heif'].includes(file.type)&&!(/\.(heic|heif)$/i.test(file.name))){showError('Use JPEG, PNG, WebP, HEIC or HEIF.');return;}
    if(file.size>8*1024*1024){showError('Choose a photo smaller than 8 MB.');return;}
    clearPhoto();state.file=file;state.url=URL.createObjectURL(file);
    $('preview').src=state.url;$('preview').hidden=false;$('camera-illustration').hidden=true;
    $('capture-hint').hidden=true;$('scan-options').hidden=false;$('remove-photo').hidden=false;
    state.result=null;$('result').hidden=true;
  }
  function listInto(id, values) { const host=$(id);host.replaceChildren();values.forEach(v=>host.append(text('li',v))); }
  function renderResult(data) {
    if(!data?.assessment?.title||!Array.isArray(data.assessment.ingredients)||!data.label)throw new Error('Invalid result. Please scan again.');
    state.result=data;const a=data.assessment,l=data.label;
    $('product-name').textContent=l.product_name||'Your food label';
    $('result-source').textContent=data.is_demo?'FICTIONAL EXAMPLE — NOT A REAL PRODUCT CHECK':'YOUR LABEL, EXPLAINED';
    $('result-basis').textContent=a.basis;
    $('verdict-card').className='verdict-card '+(['vegan','vegetarian','uncertain','non_vegetarian'].includes(a.verdict)?a.verdict:'uncertain');
    $('result-title').textContent=a.title;$('result-explanation').textContent=a.explanation;
    const matches={yes:'No excluded ingredient identified',no:'Does not match your preference',uncertain:'Suitability needs checking'};
    $('preference-match').textContent=(matches[a.preference_match]||matches.uncertain)+' · Checked for: '+(names[a.preference]||a.preference);
    $('issues-box').hidden=!a.issues?.length;listInto('issues-list',a.issues||[]);
    $('ingredients-list').replaceChildren();
    a.ingredients.forEach(i=>{
      const row=text('div','','ingredient-row'), title=text('div','','ingredient-title');
      title.append(text('span',i.english));const kind=['plant','dairy','egg','honey','animal','uncertain'].includes(i.kind)?i.kind:'uncertain';
      title.append(text('span',kind==='plant'?'Plant / mineral':kind,'ingredient-kind '+kind));
      row.append(title,text('div',i.original,'ingredient-original'),text('p',i.reason,'ingredient-reason'));$('ingredients-list').append(row);
    });
    if(!a.ingredients.length)$('ingredients-list').append(text('p','No complete ingredient list was read. Photograph the back of the package.','small-note'));
    $('contains').textContent=l.contains?.length?l.contains.join(', '):'No explicit “contains” statement read — not an absence guarantee.';
    $('may-contain').textContent=l.may_contain?.length?l.may_contain.join(', '):'No precautionary statement read — not an absence guarantee.';
    $('translation').textContent=l.translated_text||'No readable text to translate.';$('original').textContent=l.original_text||'No original text read.';
    $('claims-wrap').hidden=!l.visible_claims?.length;$('claims').textContent=(l.visible_claims||[]).join(' · ');
    listInto('limitations-list',a.limitations||[]);$('ruleset').textContent='Rule version: '+a.ruleset_version;
    $('save-result').textContent='Save scan';$('result').hidden=false;
    $('result').focus({preventScroll:true});$('result').scrollIntoView({behavior:'smooth',block:'start'});
  }
  async function scan() {
    if(state.busy)return;
    $('error').hidden=true;
    if(!state.file)return showError('Take or upload a photo first.');
    if(!hasConsent()){changePage('settings');toast('Enable photo processing permission to use AI scanning.');return;}
    if(!state.config?.ai_configured)return showError('Scanning is not configured. The app owner needs to add GEMINI_API_KEY. The examples are available below.');
    if(state.config.access_required&&!state.config.unlocked){$('access-dialog').showModal();return;}
    const form=new FormData();form.append('photo',state.file);form.append('preference',preference());form.append('consent','yes');
    state.result=null;$('result').hidden=true;setBusy(true);
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),85000);
    try { renderResult(await api('/api/scan/',{method:'POST',body:form,signal:controller.signal})); }
    catch(error){showError(error.name==='AbortError'?'This scan timed out. No result was accepted; please try again.':error.message);}
    finally{clearTimeout(timer);setBusy(false);}
  }
  function history() { try{const data=JSON.parse(localStorage.getItem(storageKey)||'[]');return Array.isArray(data)?data.slice(0,20):[];}catch{return [];} }
  function saveResult() {
    if(!state.result)return;
    try{
      const saved=history();saved.unshift({id:Date.now(),at:new Date().toISOString(),data:state.result});
      localStorage.setItem(storageKey,JSON.stringify(saved.slice(0,20)));$('save-result').textContent='Saved';
      toast('Text result saved on this device. Your photo was not saved.');
    }catch{toast('This browser could not save the result. Storage may be full or disabled.');}
  }
  function renderHistory() {
    const saved=history();$('history-list').replaceChildren();$('clear-history').hidden=!saved.length;
    if(!saved.length){$('history-list').append(text('div','Your saved scans will appear here. Save a result after scanning.','empty-state'));return;}
    saved.forEach(item=>{
      if(!item?.data?.label||!item?.data?.assessment)return;
      const b=text('button','','history-item'),left=document.createElement('div');
      left.append(text('strong',item.data.label.product_name||'Food label'),text('small',(item.data.is_demo?'Example · ':'')+item.data.assessment.title),text('small',new Date(item.at).toLocaleDateString()+' · '+(names[item.data.assessment.preference]||'Saved preference')));
      b.append(left,text('span','↗'));b.addEventListener('click',()=>{changePage('scan');try{renderResult(item.data);}catch{toast('This saved result could not be read.');}});$('history-list').append(b);
    });
  }
  async function configure(){
    try{
      state.config=await api('/api/config/');const c=state.config;
      $('configuration-notice').replaceChildren();$('configuration-notice').hidden=true;
      if(!c.ai_configured){$('configuration-notice').textContent='Preview mode: the app owner must add an AI key to enable photo scanning. The examples below are fictional demonstrations.';$('configuration-notice').hidden=false;}
      else if(c.access_required&&!c.unlocked){$('configuration-notice').append(text('span','Private beta. '));const b=text('button','Enter access code','text-button');b.addEventListener('click',()=>$('access-dialog').showModal());$('configuration-notice').append(b);$('configuration-notice').hidden=false;}
      $('logout-button').hidden=!(c.access_required&&c.unlocked);
    }catch{showError('Cannot reach the app server. Check your connection and refresh.');}
  }
  $('camera-button').addEventListener('click',()=>$('camera-input').click());$('upload-button').addEventListener('click',()=>$('upload-input').click());
  ['camera-input','upload-input'].forEach(id=>$(id).addEventListener('change',e=>selectPhoto(e.target.files[0])));
  $('remove-photo').addEventListener('click',clearPhoto);$('analyze-button').addEventListener('click',scan);
  $('privacy-open').addEventListener('click',()=>changePage('about'));$('save-result').addEventListener('click',saveResult);
  document.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>changePage(b.dataset.page)));
  document.querySelectorAll('[data-example]').forEach(b=>b.addEventListener('click',async()=>{
    if(state.busy)return;changePage('scan');$('error').hidden=true;
    try{renderResult(await api('/api/examples/'+b.dataset.example+'/?preference='+encodeURIComponent(preference())));}
    catch(e){showError(e.message);}
  }));
  document.querySelectorAll('input[name="preference"]').forEach(e=>e.addEventListener('change',()=>{try{localStorage.setItem('foodlens.preference',preference());}catch{toast('Preference could not be saved in this browser.');}updateHome();}));
  try{const p=localStorage.getItem('foodlens.preference');if(Object.hasOwn(names,p))document.querySelector('input[value="'+p+'"]').checked=true;}catch{}
  $('clear-history').addEventListener('click',()=>{if(confirm('Delete every saved scan on this device?')){try{localStorage.removeItem(storageKey);renderHistory();toast('Saved text results deleted.');}catch{toast('Unable to clear browser storage.');}}});
  $('access-form').addEventListener('submit',async(e)=>{
    e.preventDefault();$('access-error').hidden=true;
    try{await api('/api/unlock/',{method:'POST',body:new FormData(e.target)});$('access-code').value='';$('access-dialog').close();await configure();toast('Scanning unlocked.');}
    catch(err){$('access-error').textContent=err.message;$('access-error').hidden=false;}
  });
  $('access-cancel').addEventListener('click',()=>$('access-dialog').close());
  $('logout-button').addEventListener('click',async()=>{try{await api('/api/logout/',{method:'POST'});await configure();toast('Private-beta access locked.');}catch(e){toast(e.message);}});
  const consentKey='foodlens.consent.gemini.v1';
  let consentGranted=false;
  try{consentGranted=localStorage.getItem(consentKey)==='yes';}catch{}
  const hasConsent=()=>consentGranted;
  function saveConsent(value){
    consentGranted=value;
    $('remember-consent').checked=value;
    try{localStorage.setItem(consentKey,value?'yes':'no');}catch{toast('Permission applies only to this visit because browser storage is unavailable.');}
  }
  function updateHome(){
    const p=preference();
    document.querySelector('.shop-card').href=p==='non_vegetarian'?'https://www.ah.nl/':'https://www.ah.nl/producten/20128/vegetarisch-vegan-en-plantaardig';
    $('home-preference').textContent=names[p]+' picks, with the label always in reach.';
    $('shopping-words').textContent=p==='vegan'?'Vegan / veganistisch · plantaardig (plant-based). Try tofu, lentils and oat drinks.':p==='non_vegetarian'?'Explore any range. Scan labels to understand ingredients and allergen statements.':'Vegetarisch (vegetarian) · zonder ei (without egg). Try chickpeas, tofu and lentils.';
    document.querySelectorAll('.shop-card p').forEach(el=>el.textContent=p==='vegan'?'Look for vegan ranges':p==='non_vegetarian'?'Browse the full food range':'Look for vegetarian ranges');
  }
  $('remember-consent').checked=consentGranted;
  $('remember-consent').addEventListener('change',e=>{saveConsent(e.target.checked);toast(e.target.checked?'Photo permission saved.':'Future AI scans disabled.');});
  $('onboarding-dialog').addEventListener('cancel',e=>e.preventDefault());
  $('onboarding-form').addEventListener('submit',e=>{
    e.preventDefault();const p=$('onboarding-preference').value;
    if(!Object.hasOwn(names,p))return;
    document.querySelector('input[name="preference"][value="'+p+'"]').checked=true;
    saveConsent($('onboarding-consent').checked);
    try{localStorage.setItem('foodlens.preference',p);localStorage.setItem('foodlens.onboarding.v1','done');}catch{toast('Settings could not be saved. You may see setup again next visit.');}
    updateHome();$('onboarding-dialog').close();changePage('home');
  });
  $('scan-launch').addEventListener('click',()=>{if(!state.busy)$('scan-dialog').showModal();});
  $('sheet-close').addEventListener('click',()=>$('scan-dialog').close());
  for(const [button,input] of [['sheet-camera','camera-input'],['sheet-gallery','upload-input']]){
    $(button).addEventListener('click',()=>{$('scan-dialog').close();changePage('scan');$(input).click();});
  }
  $('preview').addEventListener('error',()=>{
    if(!state.file)return;
    $('preview').hidden=true;$('capture-hint').hidden=false;
    $('capture-hint').replaceChildren(text('strong','Photo selected'),text('p','Preview unavailable on this browser. The server will convert HEIC when you scan.'));
  });
  updateHome();changePage('home');
  let onboarded=false;
  try{onboarded=localStorage.getItem('foodlens.onboarding.v1')==='done'&&Object.hasOwn(names,localStorage.getItem('foodlens.preference'));}catch{}
  if(!onboarded)$('onboarding-dialog').showModal();
  configure();
})();
