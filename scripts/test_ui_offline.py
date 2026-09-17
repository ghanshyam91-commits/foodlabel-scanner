"""Offline Playwright smoke test for the responsive FoodLens experience."""
import io
import json
import os
import re
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scanner.demo import demo_label
from scanner.rules import assess

DOCS = ROOT / 'docs'
DOCS.mkdir(exist_ok=True)
checks = []


def fixture(name, preference='vegetarian_no_eggs'):
    label = demo_label(name)
    return {'label': label.model_dump(), 'assessment': assess(label, preference),
            'is_demo': True, 'provider': 'fictional example'}


SHOP_FIXTURE = {
    'query_en': 'oat milk', 'query_nl': 'haverdrink', 'preference_query_nl': 'haverdrink',
    'preference': 'vegan', 'preference_label': 'Vegan', 'location_label': 'Nijmegen',
    'location_name': 'Nijmegen', 'stores_without_matches': 1,
    'price_data_updated': '2026-09-17', 'eur_to_inr': 100, 'exchange_rate_date': '2026-09-17',
    'notice': 'Verify current price and package ingredients before buying.',
    'nearby_stores': [
        {'name': 'Albert Heijn', 'code': 'ah', 'distance_km': .8, 'map_url': 'https://www.openstreetmap.org/',
         'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=51.845000%2C5.860000&travelmode=walking'},
        {'name': 'Jumbo', 'code': 'jumbo', 'distance_km': 1.2, 'map_url': 'https://www.openstreetmap.org/',
         'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=51.860000%2C5.860000&travelmode=walking'},
    ],
    'results': [
        {'code': 'ah', 'supermarket': 'Albert Heijn', 'distance_km': .8, 'available': True,
         'product_name': 'AH Terra vegan haverdrink', 'amount': '1 l', 'price_eur': 1.25,
         'price_inr': 125, 'unit_price_eur': 1.25, 'unit_price_inr': 125, 'unit': 'l',
         'dietary_status': 'compatible', 'dietary_note': 'Explicitly marked vegan; verify the package.',
         'vegan_confidence': 92, 'vegan_confidence_note': 'Explicitly marked plant-based.',
         'product_url': '', 'product_url_is_exact': False,
         'search_url': 'https://www.ah.nl/zoeken?query=haverdrink', 'map_url': 'https://www.openstreetmap.org/',
         'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=51.845000%2C5.860000&travelmode=walking',
         'is_lowest_pack': True, 'is_best_value': True},
        {'code': 'jumbo', 'supermarket': 'Jumbo', 'distance_km': 1.2, 'available': True,
         'product_name': 'Jumbo haverdrink', 'amount': '1 l', 'price_eur': 1.49,
         'price_inr': 149, 'unit_price_eur': 1.49, 'unit_price_inr': 149, 'unit': 'l',
         'dietary_status': 'uncertain', 'dietary_note': 'Scan the package before buying.',
         'vegan_confidence': 72, 'vegan_confidence_note': 'Likely plant-based from the name.',
         'product_url': 'https://www.jumbo.com/producten/jumbo-haverdrink-1-l', 'product_url_is_exact': True,
         'search_url': 'https://www.jumbo.com/zoeken?searchTerms=haverdrink', 'map_url': 'https://www.openstreetmap.org/',
         'directions_url': 'https://www.google.com/maps/dir/?api=1&destination=51.860000%2C5.860000&travelmode=walking',
         'is_lowest_pack': False, 'is_best_value': False},
        {'code': 'aldi', 'supermarket': 'ALDI', 'distance_km': 1.8, 'available': False,
         'search_url': 'https://www.aldi.nl/zoeken.html?query=haverdrink',
         'is_lowest_pack': False, 'is_best_value': False},
    ],
}

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ.get('CHROMIUM_EXECUTABLE'),
                                         headless=True, args=['--no-sandbox'])
    for width, height in [(390, 844), (1440, 1000)]:
        context = browser.new_context(viewport={'width': width, 'height': height}, device_scale_factor=1)
        page = context.new_page(); errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.set_default_timeout(7000)
        html = (ROOT / 'scanner/templates/scanner/index.html').read_text().replace('{% load static %}', '')
        html = re.sub(r'<link[^>]*>', '', html); html = re.sub(r'<script[^>]*>.*?</script>', '', html)
        page.set_content(html, wait_until='domcontentloaded')
        page.add_style_tag(content=(ROOT / 'scanner/static/scanner/app.css').read_text())
        page.add_style_tag(content=(ROOT / 'scanner/static/scanner/lavender.css').read_text())
        examples = {f'{name}:{preference}': fixture(name, preference)
                    for name in ['oats', 'chocolate', 'sweets', 'bread']
                    for preference in ['vegan', 'vegetarian_no_eggs', 'vegetarian_with_eggs', 'non_vegetarian']}
        page.evaluate("""({examples, shop}) => {
          const memory={'foodlens.onboarding.v1':'done','foodlens.preference':'vegan','foodlens.consent.gemini.v1':'yes'};
          Object.defineProperty(window,'localStorage',{value:{getItem:k=>memory[k]??null,setItem:(k,v)=>memory[k]=String(v),removeItem:k=>delete memory[k]}});
          Object.defineProperty(document,'cookie',{get:()=> 'csrftoken=ui-fixture'});
          Object.defineProperty(navigator,'geolocation',{value:{getCurrentPosition:ok=>ok({coords:{latitude:51.84,longitude:5.86}})}});
          window.fetch=async (path, options={}) => {
            const url=new URL(path,'https://foodlens.test');let data;
            if(url.pathname==='/api/config/')data={ai_configured:true,access_required:false,unlocked:true,max_bytes:8388608};
            else if(url.pathname==='/api/usage/')data={scans:2,estimated_usd:.001,input_tokens:10,output_tokens:5,model:'Flash-Lite'};
            else if(url.pathname==='/api/shop-search/')data=shop;
            else if(url.pathname==='/api/scan/')data=examples['oats:vegan'];
            else if(url.pathname.startsWith('/api/examples/'))data=examples[url.pathname.split('/')[3]+':'+(url.searchParams.get('preference')||'vegetarian_no_eggs')];
            else throw new Error('Unexpected request: '+path);
            return new Response(JSON.stringify(data),{status:200,headers:{'content-type':'application/json'}});
          };
        }""", {'examples': examples, 'shop': SHOP_FIXTURE})
        page.add_script_tag(content=(ROOT / 'scanner/static/scanner/app.js').read_text())
        page.wait_for_function('document.getElementById("home-page").hidden===false')
        assert page.locator('h1').first.inner_text().startswith('A little clarity.')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Overflow at {width}'
        page.locator('#product-search-query').fill('oat milk')
        page.locator('#product-search-form').evaluate('(form)=>form.requestSubmit()')
        page.wait_for_function('!document.getElementById("shop-search-results").hidden')
        assert page.locator('#translated-query').inner_text() == '“haverdrink”'
        assert page.locator('.shop-price-card').count() == 2
        assert page.locator('.shop-price-card', has_text='ALDI').count() == 0
        assert page.locator('.vegan-confidence').count() == 3
        assert '₹125' in page.locator('#cheapest-result').inner_text()
        assert page.locator('.shop-price-card', has_text='Jumbo').get_by_role('link', name='View', exact=True).count() == 1
        assert page.locator('.shop-price-card', has_text='Albert Heijn').get_by_role('link', name='Search', exact=True).count() == 1
        assert page.evaluate("localStorage.getItem('foodlens.shop-location.v1')") == 'Nijmegen'
        page.locator('.shop-price-card', has_text='Albert Heijn').get_by_role('button', name='Add to My List').click()
        page.locator('.shop-price-card', has_text='Jumbo').get_by_role('button', name='Add to My List').click()
        page.locator('[data-page="history"]').click()
        assert page.locator('.buy-store-group').count() == 2
        assert page.locator('.store-directions').first.get_attribute('href').startswith('https://www.google.com/maps/dir/')
        assert page.locator('#buy-list-count').inner_text() == '2'
        page.locator('[data-page="home"]').click()
        if width == 390:
            page.screenshot(path=str(DOCS / 'foodlens-search-mobile.png'), full_page=True)
        else:
            page.screenshot(path=str(DOCS / 'foodlens-search-desktop.png'), full_page=True)
        page.locator('[data-page="scan"]').click()
        image = io.BytesIO(); Image.new('RGB', (400, 500), 'white').save(image, 'PNG')
        page.locator('#upload-input').set_input_files({'name': 'label.png', 'mimeType': 'image/png', 'buffer': image.getvalue()})
        page.wait_for_function('!document.getElementById("result").hidden')
        assert page.locator('#preview').is_visible()
        assert not errors, errors
        checks.append({'viewport': f'{width}x{height}', 'status': 'PASS',
                       'checks': 'responsive home search; location; translation; INR; cheapest card; auto-scan; no runtime errors'})
        print('PASS', width, height, flush=True)
        context.close()
    browser.close()

(DOCS / 'foodlabel-ui-tests.json').write_text(json.dumps(checks, indent=2))
print(json.dumps(checks, indent=2))
