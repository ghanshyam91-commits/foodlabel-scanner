import io, json, re, sys, os
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from scanner.demo import demo_label
from scanner.rules import assess
from PIL import Image
from playwright.sync_api import sync_playwright
checks=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_EXECUTABLE'),headless=True,args=['--no-sandbox'])
 for width,height in [(390,844),(1440,1000)]:
  context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=1)
  page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_default_timeout(7000)
  html=(ROOT/'scanner/templates/scanner/index.html').read_text().replace('{% load static %}','')
  html=re.sub(r'<link[^>]*>', '', html)
  html=re.sub(r'<script[^>]*>.*?</script>', '', html)
  page.set_content(html,wait_until='domcontentloaded')
  page.add_style_tag(content=(ROOT/'scanner/static/scanner/app.css').read_text())
  fixtures={}
  for name in ['oats','chocolate','sweets','bread']:
   for pref in ['vegan','vegetarian_no_eggs','vegetarian_with_eggs']:
    l=demo_label(name);fixtures[name+':'+pref]={'label':l.model_dump(),'assessment':assess(l,pref),'is_demo':True,'provider':'fictional example'}
  page.evaluate("""fixtures => {
    const memory={};
    Object.defineProperty(window,'localStorage',{value:{getItem:k=>memory[k]??null,setItem:(k,v)=>memory[k]=String(v),removeItem:k=>delete memory[k]}});
    Object.defineProperty(document,'cookie',{get:()=> 'csrftoken=ui-fixture'});
    window.fetch=async path => {
      const u=new URL(path,'https://foodlens.test');
      let data;
      if(u.pathname==='/api/config/')data={ai_configured:false,access_required:false,unlocked:true,max_bytes:8388608};
      else if(u.pathname.startsWith('/api/examples/'))data=fixtures[u.pathname.split('/')[3]+':'+(u.searchParams.get('preference')||'vegetarian_no_eggs')];
      else throw new Error('Unexpected request in offline UI fixture: '+path);
      return new Response(JSON.stringify(data),{status:200,headers:{'content-type':'application/json'}});
    };
  }""",fixtures)
  page.add_script_tag(content=(ROOT/'scanner/static/scanner/app.js').read_text())
  page.wait_for_function('!document.getElementById("configuration-notice").hidden')
  assert page.locator('h1').first.inner_text().startswith('Know what’s inside.')
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Overflow at {width}'
  if width==390:page.screenshot(path=str(ROOT/'docs'/'foodlabel-mobile-preview.png'),full_page=True)
  if width==1440:page.screenshot(path=str(ROOT/'docs'/'foodlabel-desktop-preview.png'),full_page=True)
  for name,expected in [('oats','Vegan-compatible ingredients'),('chocolate','Vegetarian · not vegan'),('sweets','Non-vegetarian ingredient found'),('bread','Uncertain — needs checking')]:
   page.locator(f'[data-example="{name}"]').click()
   page.wait_for_function('(expected) => document.getElementById("result-title").textContent===expected',arg=expected)
   assert 'FICTIONAL EXAMPLE' in page.locator('#result-source').inner_text()
  page.locator('[data-example="oats"]').click()
  page.wait_for_function('document.getElementById("result-title").textContent==="Vegan-compatible ingredients"')
  assert page.locator('#may-contain').inner_text()=='Milk'
  if width==390:page.screenshot(path=str(ROOT/'docs'/'foodlabel-result-preview.png'),full_page=True)
  page.locator('#save-result').click()
  page.locator('[data-page="history"]').click()
  assert page.locator('.history-item').count()==1
  page.locator('.history-item').click()
  assert page.locator('#result').is_visible()
  page.locator('input[value="vegan"]').check()
  page.locator('[data-example="chocolate"]').click()
  page.wait_for_function('document.getElementById("result-title").textContent==="Vegetarian · not vegan"')
  assert 'Does not match' in page.locator('#preference-match').inner_text()
  page.locator('[data-page="about"]').click();assert page.locator('#about-page').is_visible()
  page.locator('[data-page="scan"]').click()
  b=io.BytesIO();Image.new('RGB',(400,500),'white').save(b,'PNG')
  page.locator('#upload-input').set_input_files({'name':'label.png','mimeType':'image/png','buffer':b.getvalue()})
  assert page.locator('#preview').is_visible()
  page.locator('#analyze-button').click();assert 'confirm' in page.locator('#error').inner_text()
  page.locator('#consent').check();page.locator('#analyze-button').click();assert 'not configured' in page.locator('#error').inner_text()
  page.locator('#remove-photo').click();assert page.locator('#preview').is_hidden()
  assert not errors,errors
  checks.append({'viewport':f'{width}x{height}','status':'PASS','checks':'no horizontal overflow; four demo verdicts; cross-contact separation; save/reopen history; vegan preference; tab navigation; upload preview; consent gate; no-key error; remove photo; no JS runtime errors'})
  print('PASS',width,height,flush=True)
  open(str(ROOT/'docs'/'foodlabel-ui-tests.json'),'w').write(json.dumps(checks,indent=2))
  context.close()
 browser.close()
open(str(ROOT/'docs'/'foodlabel-ui-tests.json'),'w').write(json.dumps(checks,indent=2))
print(json.dumps(checks,indent=2))
