'use strict';

(() => {
  const $ = (id) => document.getElementById(id);
  const names = {
    non_vegetarian: 'Non-vegetarian',
    vegan: 'Vegan',
    vegetarian_no_eggs: 'Vegetarian without eggs',
    vegetarian_with_eggs: 'Vegetarian with eggs',
  };
  const badgeNames = {
    non_vegetarian: 'Non-veg',
    vegan: 'Vegan',
    vegetarian_no_eggs: 'Vegetarian',
    vegetarian_with_eggs: 'Vegetarian + eggs',
  };
  const state = {
    file: null,
    url: null,
    result: null,
    config: null,
    busy: false,
    ingredientLanguage: 'english',
    progressInterval: null,
    progressTimers: [],
    searchLocation: null,
    shopSearchBusy: false,
  };
  const storageKey = 'foodlens.saved.v1';
  const consentKey = 'foodlens.consent.gemini.v1';
  let toastTimer;
  let consentGranted = false;

  const preference = () => document.querySelector('input[name="preference"]:checked')?.value || 'vegetarian_no_eggs';
  const csrf = () => document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
  const text = (tag, value, className) => {
    const element = document.createElement(tag);
    element.textContent = String(value || '');
    if (className) element.className = className;
    return element;
  };

  function toast(message) {
    $('toast').textContent = message;
    $('toast').hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { $('toast').hidden = true; }, 3600);
  }

  function showError(message) {
    $('error').textContent = message;
    $('error').hidden = false;
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      credentials: 'same-origin',
      ...options,
      headers: { 'X-CSRFToken': csrf(), ...(options.headers || {}) },
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error('The server returned an unexpected response. Refresh the page and try again.');
    }
    if (!response.ok) throw new Error(data.error || 'This request could not be completed. Refresh and try again.');
    return data;
  }

  function resetProgress() {
    clearInterval(state.progressInterval);
    state.progressInterval = null;
    state.progressTimers.forEach(clearTimeout);
    state.progressTimers = [];
    $('scan-elapsed').textContent = '0.0s';
    const steps = document.querySelectorAll('[data-scan-step]');
    steps.forEach((step, index) => {
      step.className = index === 0 ? 'ready' : (index === 1 ? 'active' : '');
      step.querySelector('span').textContent = index === 0 ? '✓' : (index === 2 ? '3' : '');
      step.querySelector('em').textContent = index === 0 ? 'Ready' : (index === 1 ? 'In progress…' : 'Queued');
    });
  }

  function startProgress() {
    resetProgress();
    const started = performance.now();
    state.progressInterval = setInterval(() => {
      $('scan-elapsed').textContent = `${((performance.now() - started) / 1000).toFixed(1)}s`;
    }, 100);
    state.progressTimers.push(setTimeout(() => {
      const second = document.querySelector('[data-scan-step="2"]');
      const third = document.querySelector('[data-scan-step="3"]');
      second.className = 'ready';
      second.querySelector('span').textContent = '✓';
      second.querySelector('em').textContent = 'Ready';
      third.className = 'active';
      third.querySelector('span').textContent = '';
      third.querySelector('em').textContent = 'In progress…';
    }, 1150));
  }

  function completeProgress() {
    clearInterval(state.progressInterval);
    state.progressInterval = null;
    state.progressTimers.forEach(clearTimeout);
    state.progressTimers = [];
    document.querySelectorAll('[data-scan-step]').forEach((step) => {
      step.className = 'ready';
      step.querySelector('span').textContent = '✓';
      step.querySelector('em').textContent = 'Ready';
    });
  }

  function setBusy(busy) {
    state.busy = busy;
    $('progress').hidden = !busy;
    ['camera-button', 'scan-launch', 'remove-photo'].forEach((id) => {
      if ($(id)) $(id).disabled = busy;
    });
    document.querySelectorAll('[data-example], input[name="preference"]').forEach((element) => { element.disabled = busy; });
    if (busy) startProgress();
    else if (!$('result').hidden) completeProgress();
    else resetProgress();
  }

  function changePage(page) {
    const pages = ['home', 'scan', 'history', 'about', 'settings'];
    if (!pages.includes(page)) return;
    pages.forEach((name) => { $(name + '-page').hidden = name !== page; });
    document.body.dataset.page = page;
    document.querySelectorAll('[data-page]').forEach((button) => {
      if (button.dataset.page === page) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
    if (page === 'history') renderHistory();
    if (page === 'settings') loadUsage();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function loadUsage() {
    try {
      const usage = await api('/api/usage/');
      const scans = Number(usage.scans) || 0;
      const usd = Number(usage.estimated_usd) || 0;
      const inr = Number.isFinite(Number(usage.estimated_inr)) ? Number(usage.estimated_inr) : usd * 90;
      const activity = Math.min(100, scans);
      $('usage-scans').textContent = scans.toLocaleString('en-IN');
      $('usage-cost').textContent = new Intl.NumberFormat('en-IN', {
        style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: inr > 0 && inr < .01 ? 3 : 2,
      }).format(inr);
      $('usage-cost-usd').textContent = `$${usd.toFixed(4)} USD`;
      $('usage-model').textContent = usage.model;
      $('usage-tokens').textContent = `${Number(usage.input_tokens).toLocaleString('en-IN')} input · ${Number(usage.output_tokens).toLocaleString('en-IN')} output tokens`;
      $('usage-percent').textContent = `${activity}% used`;
      $('usage-progress').value = activity;
      $('usage-progress').textContent = `${activity}%`;
      const orbit = document.querySelector('.usage-orbit');
      orbit?.classList.remove('pulse');
      requestAnimationFrame(() => orbit?.classList.add('pulse'));
    } catch {
      $('usage-model').textContent = 'Usage unavailable';
    }
  }

  const formatEuro = (value) => (typeof value === 'number'
    ? `€${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : 'Price unavailable');
  const formatInr = (value) => (typeof value === 'number' ? `₹${Math.round(value).toLocaleString('en-IN')}` : '');

  function externalLink(label, url, className = '') {
    let valid = false;
    try { valid = new URL(url).protocol === 'https:'; } catch {}
    if (!valid) return text('span', label, className);
    const link = text('a', label, className);
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    return link;
  }

  function setShopSearchBusy(busy) {
    state.shopSearchBusy = busy;
    $('shop-search-progress').hidden = !busy;
    ['product-search-button', 'product-search-query', 'manual-location'].forEach((id) => {
      $(id).disabled = busy;
    });
  }

  function setLocationLabel(label) {
    $('header-location-label').textContent = label;
  }

  function locationError(message) {
    $('manual-location-wrap').hidden = false;
    $('shop-search-error').textContent = message;
    $('shop-search-error').hidden = false;
    setLocationLabel('Set location');
    $('manual-location').focus();
  }

  function requestCurrentLocation() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        const error = new Error('Location is not available in this browser. Enter a Dutch city or postcode.');
        locationError(error.message);
        reject(error);
        return;
      }
      setLocationLabel('Finding…');
      $('shop-search-error').hidden = true;
      navigator.geolocation.getCurrentPosition((position) => {
        state.searchLocation = {
          lat: Number(position.coords.latitude.toFixed(3)),
          lon: Number(position.coords.longitude.toFixed(3)),
        };
        $('manual-location').value = '';
        $('manual-location-wrap').hidden = true;
        setLocationLabel('Current location');
        resolve(state.searchLocation);
      }, () => {
        const error = new Error('Allow location access, or enter a Dutch city or postcode.');
        locationError(error.message);
        reject(error);
      }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
    });
  }

  function priceBlock(row) {
    const prices = text('div', '', 'shop-price');
    prices.append(text('strong', formatEuro(row.price_eur)));
    prices.append(text('span', row.price_inr == null ? 'INR temporarily unavailable' : `≈ ${formatInr(row.price_inr)}`));
    if (row.unit_price_eur && row.unit) {
      const unitName = row.unit === 'item' ? 'item' : row.unit;
      const converted = row.unit_price_inr ? ` · ≈ ${formatInr(row.unit_price_inr)}` : '';
      prices.append(text('small', `${formatEuro(row.unit_price_eur)} / ${unitName}${converted}`));
    }
    return prices;
  }

  function renderCheapest(row) {
    const host = $('cheapest-result');
    host.replaceChildren();
    host.hidden = !row;
    if (!row) return;
    const copy = document.createElement('div');
    copy.append(
      text('div', row.is_best_value ? 'BEST VALUE NEAR YOU' : 'LOWEST PACK PRICE', 'section-kicker'),
      text('h3', row.supermarket),
      text('p', row.product_name),
    );
    const meta = text('div', '', 'cheapest-meta');
    meta.append(priceBlock(row));
    const locationLabel = row.distance_km == null ? 'Online catalogue' : `${row.distance_km.toFixed(1)} km away`;
    meta.append(text('span', `${locationLabel} · ${row.amount || 'Package size not listed'}`));
    host.append(copy, meta, externalLink(`View at ${row.supermarket}`, row.product_url, 'button primary small'));
  }

  function renderShopResult(row) {
    const card = text('article', '', `shop-price-card${row.available ? '' : ' unavailable'}`);
    const top = text('div', '', 'shop-price-top');
    const brand = text('span', row.supermarket.slice(0, 2), 'shop-price-monogram');
    const heading = document.createElement('div');
    heading.append(
      text('h3', row.supermarket),
      text('small', row.distance_km == null ? 'Dutch online catalogue' : `${row.distance_km.toFixed(1)} km away`),
    );
    top.append(brand, heading);
    if (row.available) {
      const label = row.dietary_status === 'compatible' ? 'Preference match' : (row.dietary_status === 'excluded' ? 'Does not match' : 'Scan to confirm');
      top.append(text('span', label, `diet-badge ${row.dietary_status}`));
      card.append(top, text('p', row.product_name, 'shop-product-name'));
      if (row.amount) card.append(text('span', row.amount, 'shop-pack-size'));
      card.append(priceBlock(row));
      const flags = text('div', '', 'price-flags');
      if (row.is_best_value) flags.append(text('span', 'Best unit value'));
      if (row.is_lowest_pack) flags.append(text('span', 'Lowest pack price'));
      if (flags.childNodes.length) card.append(flags);
      card.append(text('p', row.dietary_note, 'diet-note'));
      const actions = text('div', '', 'shop-card-actions');
      actions.append(externalLink('View product', row.product_url, 'button secondary small'));
      if (row.dietary_status !== 'compatible') {
        const scanButton = text('button', 'Scan label', 'text-button');
        scanButton.type = 'button';
        scanButton.addEventListener('click', () => changePage('scan'));
        actions.append(scanButton);
      }
      card.append(actions);
    } else {
      card.append(
        top,
        text('p', 'No comparable catalogue price found for this item.', 'shop-product-name'),
        text('p', 'Open the supermarket search to check its current range.', 'diet-note'),
        externalLink(`Search ${row.supermarket}`, row.search_url, 'button secondary small'),
      );
    }
    return card;
  }

  function renderShopSearch(data) {
    $('searched-query').textContent = `“${data.query_en}”`;
    $('translated-query').textContent = `“${data.preference_query_nl}”`;
    $('search-scope').textContent = `${data.preference_label} · ${data.location_label}`;
    $('header-location-label').textContent = data.location_label;
    $('price-update').textContent = data.eur_to_inr
      ? `€1 ≈ ${formatInr(data.eur_to_inr)}${data.exchange_rate_date ? ` · ${data.exchange_rate_date}` : ''}`
      : 'INR conversion temporarily unavailable';
    const list = $('shop-result-list');
    list.replaceChildren();
    (data.results || []).forEach((row) => list.append(renderShopResult(row)));
    $('result-count').textContent = `${(data.results || []).length} checked`;
    const best = (data.results || []).find((row) => row.is_best_value) || (data.results || []).find((row) => row.is_lowest_pack);
    renderCheapest(best);
    const stores = $('nearby-store-list');
    stores.replaceChildren();
    (data.nearby_stores || []).forEach((store) => {
      const label = `${store.name}${store.distance_km == null ? '' : ` · ${store.distance_km.toFixed(1)} km`}`;
      stores.append(externalLink(label, store.map_url, 'nearby-store-chip'));
    });
    const source = $('price-source-note');
    source.replaceChildren(
      document.createTextNode(`${data.notice} Prices: `),
      externalLink('Checkjebon.nl open data', 'https://www.checkjebon.nl/'),
      document.createTextNode(data.price_data_updated ? ` · updated ${data.price_data_updated}. ` : '. '),
      externalLink('Distances: OpenStreetMap contributors', 'https://www.openstreetmap.org/copyright'),
      document.createTextNode('.'),
    );
    $('shop-search-results').hidden = false;
  }

  async function searchProducts() {
    if (state.shopSearchBusy) return;
    const query = $('product-search-query').value.trim();
    const manual = $('manual-location').value.trim();
    if (query.length < 2) return;
    $('shop-search-error').hidden = true;
    $('shop-search-results').hidden = true;
    if (!manual && !state.searchLocation) {
      try { await requestCurrentLocation(); } catch { return; }
    }
    const form = new FormData();
    form.append('query', query);
    form.append('preference', preference());
    if (manual) form.append('location', manual);
    else if (state.searchLocation) {
      form.append('lat', state.searchLocation.lat);
      form.append('lon', state.searchLocation.lon);
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 45000);
    setShopSearchBusy(true);
    try {
      const data = await api('/api/shop-search/', { method: 'POST', body: form, signal: controller.signal });
      renderShopSearch(data);
      $('shop-search-results').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (error) {
      $('shop-search-error').textContent = error.name === 'AbortError' ? 'Price comparison took too long. Please try again.' : error.message;
      $('shop-search-error').hidden = false;
    } finally {
      clearTimeout(timer);
      setShopSearchBusy(false);
    }
  }

  function clearPhoto() {
    if (state.url) URL.revokeObjectURL(state.url);
    state.file = null;
    state.url = null;
    state.result = null;
    $('preview').removeAttribute('src');
    $('preview').hidden = true;
    $('camera-illustration').hidden = false;
    $('capture-hint').replaceChildren(
      text('strong', 'Scan Dutch food label'),
      text('p', 'Use the complete ingredients side of the package.'),
    );
    $('capture-hint').hidden = false;
    $('remove-photo').hidden = true;
    $('camera-input').value = '';
    $('upload-input').value = '';
    $('result').hidden = true;
    $('error').hidden = true;
    $('scan-page').classList.remove('has-photo', 'has-result');
    $('scan-page-title').textContent = 'Barcode Scanner';
    resetProgress();
  }

  async function selectPhoto(file) {
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'].includes(file.type) && !(/\.(heic|heif)$/i.test(file.name))) {
      changePage('scan');
      showError('Use JPEG, PNG, WebP, HEIC or HEIF.');
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      changePage('scan');
      showError('Choose a photo smaller than 8 MB.');
      return;
    }
    clearPhoto();
    changePage('scan');
    state.file = file;
    state.url = URL.createObjectURL(file);
    $('preview').src = state.url;
    $('preview').hidden = false;
    $('camera-illustration').hidden = true;
    $('capture-hint').hidden = true;
    $('remove-photo').hidden = false;
    $('scan-page').classList.add('has-photo');
    await scan();
  }

  function listInto(id, values) {
    const host = $(id);
    host.replaceChildren();
    values.forEach((value) => host.append(text('li', value)));
  }

  function setIngredientLanguage(language) {
    state.ingredientLanguage = language;
    document.querySelectorAll('[data-ingredients-lang]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.ingredientsLang === language));
    });
    document.querySelectorAll('.ingredient-english').forEach((element) => { element.hidden = language !== 'english'; });
    document.querySelectorAll('.ingredient-original').forEach((element) => { element.hidden = language !== 'original'; });
  }

  function flashVerdict(match) {
    const box = $('verdict-flash');
    const icon = $('verdict-flash-icon');
    const message = $('verdict-flash-text');
    box.className = `verdict-flash ${match}`;
    icon.textContent = match === 'yes' ? '✓' : (match === 'no' ? '×' : '?');
    message.textContent = match === 'yes' ? 'Matches your food preference' : (match === 'no' ? "Don't eat for your selected preference" : 'Check the package before deciding');
    box.hidden = false;
    box.getAnimations().forEach((animation) => animation.cancel());
    void box.offsetWidth;
    box.classList.add('play');
    if (match === 'no' && navigator.vibrate) navigator.vibrate([160, 80, 220]);
    setTimeout(() => { box.hidden = true; }, 2600);
  }

  function renderResult(data, announce = false) {
    if (!data?.assessment?.title || !Array.isArray(data.assessment.ingredients) || !data.label) {
      throw new Error('Invalid result. Please scan again.');
    }
    state.result = data;
    const assessment = data.assessment;
    const label = data.label;
    $('product-name').textContent = label.product_name || 'Your food label';
    $('result-source').textContent = data.is_demo ? 'FICTIONAL EXAMPLE' : (data.provider === 'Tesseract local OCR' ? 'LOCAL OCR · CHECK THE PACKAGE' : 'PACKAGE ANALYSIS');
    $('result-basis').textContent = assessment.basis;
    $('verdict-card').className = `verdict-card ${['vegan', 'vegetarian', 'uncertain', 'non_vegetarian'].includes(assessment.verdict) ? assessment.verdict : 'uncertain'}`;
    $('result-title').textContent = assessment.title;
    $('result-explanation').textContent = assessment.explanation;
    const matches = {
      yes: 'No excluded ingredient identified',
      no: 'Does not match your preference',
      uncertain: 'Suitability needs checking',
    };
    $('preference-match').textContent = `${matches[assessment.preference_match] || matches.uncertain} · Checked for ${names[assessment.preference] || assessment.preference}`;
    $('rationale-copy').textContent = assessment.issues?.length
      ? `FoodLens found ${assessment.issues.length} point${assessment.issues.length === 1 ? '' : 's'} that need a closer look before deciding.`
      : `FoodLens checked all ${assessment.ingredients.length} extracted ingredient${assessment.ingredients.length === 1 ? '' : 's'} against its reviewed dietary rules.`;
    $('issues-box').hidden = !assessment.issues?.length;
    listInto('issues-list', assessment.issues || []);
    $('ingredients-list').replaceChildren();
    assessment.ingredients.forEach((ingredient) => {
      const row = text('div', '', 'ingredient-row');
      const title = text('div', '', 'ingredient-title');
      title.append(text('span', ingredient.english, 'ingredient-english'));
      const kind = ['plant', 'dairy', 'egg', 'honey', 'animal', 'uncertain'].includes(ingredient.kind) ? ingredient.kind : 'uncertain';
      title.append(text('span', kind === 'plant' ? 'Plant / mineral' : kind, `ingredient-kind ${kind}`));
      row.append(title, text('div', ingredient.original, 'ingredient-original'), text('p', ingredient.reason, 'ingredient-reason'));
      $('ingredients-list').append(row);
    });
    if (!assessment.ingredients.length) {
      $('ingredients-list').append(text('p', 'No complete ingredient list was read. Photograph the back of the package.', 'small-note'));
    }
    setIngredientLanguage(state.ingredientLanguage);
    $('contains').textContent = label.contains?.length ? label.contains.join(', ') : 'No explicit “contains” statement read — not an absence guarantee.';
    $('may-contain').textContent = label.may_contain?.length ? label.may_contain.join(', ') : 'No precautionary statement read — not an absence guarantee.';
    $('translation').textContent = label.translated_text || 'No readable text to translate.';
    $('original').textContent = label.original_text || 'No original text read.';
    $('claims-wrap').hidden = !label.visible_claims?.length;
    $('claims').textContent = (label.visible_claims || []).join(' · ');
    listInto('limitations-list', assessment.limitations || []);
    $('ruleset').textContent = `Rule version: ${assessment.ruleset_version}`;
    $('save-result').lastChild.textContent = 'Save to list';
    $('result').hidden = false;
    $('scan-page').classList.add('has-result');
    $('scan-page-title').textContent = 'Product Breakdown';
    completeProgress();
    $('result').focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (announce) flashVerdict(assessment.preference_match);
  }

  async function scan() {
    if (state.busy) return;
    $('error').hidden = true;
    if (!state.file) return showError('Take or upload a photo first.');
    if (!hasConsent()) {
      changePage('settings');
      toast('Enable photo processing permission to scan a label.');
      return;
    }
    if (!state.config) await configure();
    if (!state.config?.ai_configured) return showError('Scanning is not configured yet.');
    if (state.config.access_required && !state.config.unlocked) {
      $('access-dialog').showModal();
      return;
    }
    const form = new FormData();
    form.append('photo', state.file);
    form.append('preference', preference());
    form.append('consent', 'yes');
    state.result = null;
    $('result').hidden = true;
    $('scan-page').classList.remove('has-result');
    setBusy(true);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 85000);
    try {
      renderResult(await api('/api/scan/', { method: 'POST', body: form, signal: controller.signal }), true);
    } catch (error) {
      showError(error.name === 'AbortError' ? 'This scan timed out. No result was accepted; please try again.' : error.message);
    } finally {
      clearTimeout(timer);
      setBusy(false);
    }
  }

  function history() {
    try {
      const data = JSON.parse(localStorage.getItem(storageKey) || '[]');
      return Array.isArray(data) ? data.slice(0, 20) : [];
    } catch {
      return [];
    }
  }

  function saveResult() {
    if (!state.result) return;
    try {
      const saved = history();
      saved.unshift({ id: Date.now(), at: new Date().toISOString(), data: state.result });
      localStorage.setItem(storageKey, JSON.stringify(saved.slice(0, 20)));
      $('save-result').lastChild.textContent = 'Saved';
      toast('Text result saved on this device. Your photo was not saved.');
    } catch {
      toast('This browser could not save the result. Storage may be full or disabled.');
    }
  }

  function renderHistory() {
    const saved = history();
    $('history-list').replaceChildren();
    $('clear-history').hidden = !saved.length;
    if (!saved.length) {
      $('history-list').append(text('div', 'Your saved scans will appear here. Save a result after scanning.', 'empty-state'));
      return;
    }
    saved.forEach((item) => {
      if (!item?.data?.label || !item?.data?.assessment) return;
      const button = text('button', '', 'history-item');
      const left = document.createElement('div');
      left.append(
        text('strong', item.data.label.product_name || 'Food label'),
        text('small', `${item.data.is_demo ? 'Example · ' : ''}${item.data.assessment.title}`),
        text('small', `${new Date(item.at).toLocaleDateString()} · ${names[item.data.assessment.preference] || 'Saved preference'}`),
      );
      button.append(left, text('span', '↗'));
      button.addEventListener('click', () => {
        changePage('scan');
        try { renderResult(item.data); } catch { toast('This saved result could not be read.'); }
      });
      $('history-list').append(button);
    });
  }

  async function configure() {
    try {
      state.config = await api('/api/config/');
      const config = state.config;
      $('configuration-notice').replaceChildren();
      $('configuration-notice').hidden = true;
      if (!config.ai_configured) {
        $('configuration-notice').textContent = 'Preview mode: the app owner must add an AI key to enable photo scanning. The examples below are fictional demonstrations.';
        $('configuration-notice').hidden = false;
      } else if (config.scan_provider?.startsWith('Private')) {
        $('configuration-notice').textContent = 'Free local mode: Tesseract reads this label on the server. Translation coverage is limited, so compare every result with the package.';
        $('configuration-notice').hidden = false;
      } else if (config.access_required && !config.unlocked) {
        $('configuration-notice').append(text('span', 'Private beta. '));
        const button = text('button', 'Enter access code', 'text-button');
        button.addEventListener('click', () => $('access-dialog').showModal());
        $('configuration-notice').append(button);
        $('configuration-notice').hidden = false;
      }
      $('logout-button').hidden = !(config.auth_required && config.authenticated);
    } catch {
      showError('Cannot reach the app server. Check your connection and refresh.');
    }
  }

  function hasConsent() { return consentGranted; }

  function saveConsent(value) {
    consentGranted = value;
    $('remember-consent').checked = value;
    try {
      localStorage.setItem(consentKey, value ? 'yes' : 'no');
    } catch {
      toast('Permission applies only to this visit because browser storage is unavailable.');
    }
  }

  function updateHome() {
    const current = preference();
    document.querySelector('.shop-card').href = current === 'non_vegetarian' ? 'https://www.ah.nl/' : 'https://www.ah.nl/producten/20128/vegetarisch-vegan-en-plantaardig';
    $('header-preference-label').textContent = badgeNames[current];
    $('header-preference').dataset.preference = current;
  }

  function openScanDialog() {
    if (state.busy) return;
    if (!hasConsent()) {
      changePage('settings');
      toast('Enable photo processing permission before scanning.');
      return;
    }
    $('scan-dialog').showModal();
  }

  async function shareResult() {
    if (!state.result) return;
    const label = state.result.label;
    const assessment = state.result.assessment;
    const message = `${label.product_name || 'Food label'} — ${assessment.title}. Checked for ${names[assessment.preference] || assessment.preference} with FoodLens. Always verify the package.`;
    try {
      if (navigator.share) await navigator.share({ title: 'FoodLens result', text: message });
      else if (navigator.clipboard) {
        await navigator.clipboard.writeText(message);
        toast('Result summary copied.');
      } else toast('Sharing is not available in this browser.');
    } catch (error) {
      if (error.name !== 'AbortError') toast('The result could not be shared.');
    }
  }

  ['camera-input', 'upload-input'].forEach((id) => {
    $(id).addEventListener('change', async (event) => { await selectPhoto(event.target.files[0]); });
  });
  $('remove-photo').addEventListener('click', clearPhoto);
  $('save-result').addEventListener('click', saveResult);
  $('share-result').addEventListener('click', shareResult);
  $('product-search-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    await searchProducts();
  });
  $('header-location').addEventListener('click', async () => {
    try {
      await requestCurrentLocation();
      toast('Current location is ready for nearby comparisons.');
    } catch {}
  });
  $('manual-location-toggle').addEventListener('click', () => {
    $('manual-location-wrap').hidden = false;
    $('manual-location').focus();
  });
  $('manual-location').addEventListener('input', () => {
    const manual = $('manual-location').value.trim();
    setLocationLabel(manual || 'Use location');
  });
  document.querySelectorAll('[data-page]').forEach((button) => button.addEventListener('click', () => changePage(button.dataset.page)));
  document.querySelectorAll('[data-ingredients-lang]').forEach((button) => button.addEventListener('click', () => setIngredientLanguage(button.dataset.ingredientsLang)));
  document.querySelectorAll('[data-example]').forEach((button) => button.addEventListener('click', async () => {
    if (state.busy) return;
    clearPhoto();
    changePage('scan');
    $('error').hidden = true;
    try {
      renderResult(await api(`/api/examples/${button.dataset.example}/?preference=${encodeURIComponent(preference())}`));
    } catch (error) {
      showError(error.message);
    }
  }));
  document.querySelectorAll('input[name="preference"]').forEach((input) => input.addEventListener('change', () => {
    try { localStorage.setItem('foodlens.preference', preference()); }
    catch { toast('Preference could not be saved in this browser.'); }
    $('shop-search-results').hidden = true;
    updateHome();
  }));
  try {
    const savedPreference = localStorage.getItem('foodlens.preference');
    if (Object.hasOwn(names, savedPreference)) document.querySelector(`input[value="${savedPreference}"]`).checked = true;
  } catch {}

  $('clear-history').addEventListener('click', () => {
    if (!confirm('Delete every saved scan on this device?')) return;
    try {
      localStorage.removeItem(storageKey);
      renderHistory();
      toast('Saved text results deleted.');
    } catch {
      toast('Unable to clear browser storage.');
    }
  });
  $('access-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    $('access-error').hidden = true;
    try {
      await api('/api/unlock/', { method: 'POST', body: new FormData(event.target) });
      $('access-code').value = '';
      $('access-dialog').close();
      await configure();
      toast('Scanning unlocked.');
    } catch (error) {
      $('access-error').textContent = error.message;
      $('access-error').hidden = false;
    }
  });
  $('access-cancel').addEventListener('click', () => $('access-dialog').close());
  $('logout-button').addEventListener('click', async () => {
    try {
      await api('/auth/logout/', { method: 'POST' });
      location.href = '/';
    } catch (error) {
      toast(error.message);
    }
  });

  try { consentGranted = localStorage.getItem(consentKey) === 'yes'; } catch {}
  $('remember-consent').checked = consentGranted;
  $('remember-consent').addEventListener('change', (event) => {
    saveConsent(event.target.checked);
    toast(event.target.checked ? 'Photo permission saved.' : 'Future photo scans disabled.');
  });
  $('onboarding-dialog').addEventListener('cancel', (event) => event.preventDefault());
  $('onboarding-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const selected = $('onboarding-preference').value;
    if (!Object.hasOwn(names, selected)) return;
    document.querySelector(`input[name="preference"][value="${selected}"]`).checked = true;
    saveConsent($('onboarding-consent').checked);
    try {
      localStorage.setItem('foodlens.preference', selected);
      localStorage.setItem('foodlens.onboarding.v1', 'done');
    } catch {
      toast('Settings could not be saved. You may see setup again next visit.');
    }
    updateHome();
    $('onboarding-dialog').close();
    changePage('home');
  });

  $('scan-launch').addEventListener('click', openScanDialog);
  $('camera-button').addEventListener('click', openScanDialog);
  $('sheet-close').addEventListener('click', () => $('scan-dialog').close());
  [['sheet-camera', 'camera-input'], ['sheet-gallery', 'upload-input']].forEach(([button, input]) => {
    $(button).addEventListener('click', () => {
      $('scan-dialog').close();
      $(input).click();
    });
  });
  $('scan-back').addEventListener('click', () => changePage('home'));
  $('cancel-scan').addEventListener('click', () => { clearPhoto(); changePage('home'); });
  $('scan-another').addEventListener('click', () => { clearPhoto(); openScanDialog(); });
  $('preview').addEventListener('error', () => {
    if (!state.file) return;
    $('preview').hidden = true;
    $('capture-hint').hidden = false;
    $('capture-hint').replaceChildren(
      text('strong', 'Photo selected'),
      text('p', 'Preview unavailable. Scanning continues in the background.'),
    );
  });

  updateHome();
  changePage('home');
  let onboarded = false;
  try {
    onboarded = localStorage.getItem('foodlens.onboarding.v1') === 'done' && Object.hasOwn(names, localStorage.getItem('foodlens.preference'));
  } catch {}
  if (!onboarded) $('onboarding-dialog').showModal();
  configure();
})();
