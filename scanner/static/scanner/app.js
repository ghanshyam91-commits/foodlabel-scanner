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
    shopSearchBusy: false,
  };
  const storageKey = 'foodlens.saved.v1';
  const buyListKey = 'foodlens.buy-list.v1';
  const locationKey = 'foodlens.shop-location.v1';
  const defaultLocation = 'Nijmegen';
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

  function icon(symbol) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    svg.setAttribute('class', 'icon');
    use.setAttribute('href', `#${symbol}`);
    svg.append(use);
    return svg;
  }

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

  function navigationLink(row, className = '') {
    const rawLatitude = row.latitude ?? row.lat;
    const rawLongitude = row.longitude ?? row.lon;
    const latitude = Number(rawLatitude);
    const longitude = Number(rawLongitude);
    const hasCoordinates = rawLatitude != null && rawLatitude !== ''
      && rawLongitude != null && rawLongitude !== ''
      && Number.isFinite(latitude) && Number.isFinite(longitude);
    const isAppleMobile = /iPad|iPhone|iPod/.test(navigator.userAgent)
      || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    let url = row.directions_url || row.directionsUrl || row.map_url || row.mapUrl || '';
    if (hasCoordinates && isAppleMobile) {
      const destination = encodeURIComponent(row.supermarket || row.name || 'Supermarket');
      url = `https://maps.apple.com/?daddr=${latitude},${longitude}&dirflg=w&q=${destination}`;
    } else if (hasCoordinates && !url) {
      url = `https://www.google.com/maps/dir/?api=1&destination=${latitude},${longitude}&travelmode=walking`;
    }
    const link = externalLink('Navigate', url, className);
    link.setAttribute('aria-label', `Navigate to ${row.supermarket || row.name || 'store'}`);
    return link;
  }

  function productDestination(row, className = '') {
    const url = row.product_url || row.productUrl || row.search_url || row.searchUrl || '';
    const exact = row.product_url_is_exact ?? row.productUrlIsExact;
    const supermarket = row.supermarket || 'store';
    if (!url) {
      const note = text('span', 'Search', 'product-link-note');
      note.title = `${supermarket} does not expose a usable public catalogue link for this result.`;
      return note;
    }
    return externalLink(exact ? 'View' : 'Search', url, className);
  }

  function retailerLogo(code, name, className = 'retailer-logo') {
    const frame = text('span', '', className);
    const safeCode = /^[a-z0-9-]{1,24}$/.test(code || '') ? code : 'unknown';
    const image = document.createElement('img');
    image.src = `/api/shop-logo/${safeCode}/`;
    image.alt = `${name} logo`;
    image.loading = 'lazy';
    image.addEventListener('error', () => {
      frame.replaceChildren(text('span', (name || '?').slice(0, 2), 'logo-fallback'));
    }, { once: true });
    frame.append(image);
    return frame;
  }

  function savedLocation() {
    try {
      const value = localStorage.getItem(locationKey) || '';
      return value.trim().slice(0, 80) || defaultLocation;
    } catch {
      return defaultLocation;
    }
  }

  function rememberLocation(name) {
    const value = String(name || '').trim().slice(0, 80);
    if (!value || value === 'Current location' || value === 'Netherlands-wide comparison') return;
    try { localStorage.setItem(locationKey, value); } catch {}
    setLocationLabel(value);
  }

  function applySavedLocation() {
    setLocationLabel(savedLocation());
  }

  function setShopSearchBusy(busy) {
    state.shopSearchBusy = busy;
    $('shop-search-progress').hidden = !busy;
    ['product-search-button', 'product-search-query'].forEach((id) => {
      $(id).disabled = busy;
    });
  }

  function setLocationLabel(label) {
    $('header-location-label').textContent = label;
  }

  function locationError(message) {
    setLocationLabel(savedLocation());
    $('location-error').textContent = message;
    $('location-error').hidden = false;
  }

  async function requestCurrentLocation() {
    const coordinates = await new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        const error = new Error('Location is not available in this browser. Enter a Dutch city or postcode.');
        locationError(error.message);
        reject(error);
        return;
      }
      setLocationLabel('Finding…');
      $('location-error').hidden = true;
      navigator.geolocation.getCurrentPosition((position) => {
        resolve({
          lat: Number(position.coords.latitude.toFixed(3)),
          lon: Number(position.coords.longitude.toFixed(3)),
        });
      }, () => {
        const error = new Error('Allow location access, or enter a Dutch city or postcode.');
        locationError(error.message);
        reject(error);
      }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
    });
    const form = new FormData();
    form.append('lat', coordinates.lat);
    form.append('lon', coordinates.lon);
    const data = await api('/api/location-name/', { method: 'POST', body: form });
    rememberLocation(data.location_name);
    return data.location_name;
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

  function veganConfidenceBadge(row) {
    const confidence = Math.max(0, Math.min(100, Number(row.vegan_confidence) || 0));
    const tone = confidence >= 85 ? 'green' : (confidence >= 65 ? 'orange' : (confidence >= 40 ? 'yellow' : 'red'));
    const badge = text('span', '', `vegan-confidence ${tone}`);
    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.classList.add('icon');
    icon.setAttribute('aria-hidden', 'true');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', '#i-leaf');
    icon.append(use);
    badge.append(icon, text('span', 'Confidence'), text('strong', `${confidence}%`));
    badge.title = `${row.vegan_confidence_note || 'Name-based estimate only.'} Scan the package to confirm.`;
    badge.setAttribute('aria-label', `Confidence ${confidence} percent. ${badge.title}`);
    return badge;
  }

  function buyList() {
    try {
      const data = JSON.parse(localStorage.getItem(buyListKey) || '[]');
      if (!Array.isArray(data)) return [];
      return data
        .filter((item) => item && /^[a-z0-9-]{1,24}$/.test(item.code || '') && typeof item.productName === 'string')
        .slice(0, 100);
    } catch {
      return [];
    }
  }

  function buyItemId(row) {
    return [row.code || '', row.product_name || row.productName || '', row.amount || ''].join('|').toLowerCase();
  }

  function saveBuyList(items) {
    localStorage.setItem(buyListKey, JSON.stringify(items.slice(0, 100)));
    updateBuyListCount(items);
    syncBuyButtons(items);
  }

  function updateBuyListCount(items = buyList()) {
    const count = items
      .filter((item) => !item.bought)
      .reduce((total, item) => total + Math.max(1, Number(item.quantity) || 1), 0);
    const badge = $('buy-list-count');
    badge.textContent = String(count);
    badge.hidden = !count;
  }

  function syncBuyButtons(items = buyList()) {
    const ids = new Set(items.map((item) => item.id));
    document.querySelectorAll('[data-buy-id]').forEach((button) => {
      const added = ids.has(button.dataset.buyId);
      button.disabled = added;
      button.replaceChildren(icon(added ? 'i-check' : 'i-cart-plus'));
      button.setAttribute('aria-label', added ? 'Added to My List' : 'Add to My List');
      button.title = added ? 'Added to My List' : 'Add to My List';
    });
  }

  function buyActionButton(row, className) {
    const button = text('button', '', `${className} buy-button icon-action`);
    button.type = 'button';
    button.dataset.buyId = buyItemId(row);
    button.setAttribute('aria-label', 'Add to My List');
    button.title = 'Add to My List';
    button.append(icon('i-cart-plus'));
    button.addEventListener('click', () => addToBuyList(row));
    return button;
  }

  function addToBuyList(row) {
    try {
      const items = buyList();
      const id = buyItemId(row);
      if (items.some((item) => item.id === id)) {
        toast('This product is already in your buy list.');
        syncBuyButtons(items);
        return;
      }
      items.unshift({
        id,
        code: row.code,
        supermarket: row.supermarket,
        productName: row.product_name,
        amount: row.amount || '',
        priceEur: row.price_eur,
        priceInr: row.price_inr,
        productUrl: row.product_url,
        productUrlIsExact: Boolean(row.product_url_is_exact),
        searchUrl: row.search_url,
        distanceKm: row.distance_km,
        latitude: row.latitude,
        longitude: row.longitude,
        mapUrl: row.map_url,
        directionsUrl: row.directions_url,
        quantity: 1,
        bought: false,
        addedAt: new Date().toISOString(),
      });
      saveBuyList(items);
      toast(`${row.product_name} added under ${row.supermarket}.`);
    } catch {
      toast('This browser could not save the buy list. Storage may be full or disabled.');
    }
  }

  function changeBuyItem(id, action) {
    try {
      const items = buyList();
      const index = items.findIndex((item) => item.id === id);
      if (index < 0) return;
      if (action === 'remove') items.splice(index, 1);
      else if (action === 'toggle') items[index].bought = !items[index].bought;
      else if (action === 'increase') items[index].quantity = Math.min(99, Math.max(1, Number(items[index].quantity) || 1) + 1);
      else if (action === 'decrease') items[index].quantity = Math.max(1, (Number(items[index].quantity) || 1) - 1);
      saveBuyList(items);
      renderBuyList();
    } catch {
      toast('The buy list could not be updated.');
    }
  }

  function renderBuyList() {
    const items = buyList();
    const host = $('buy-list-groups');
    const active = items.filter((item) => !item.bought);
    const activeQuantity = active.reduce((total, item) => total + Math.max(1, Number(item.quantity) || 1), 0);
    host.replaceChildren();
    $('clear-bought').hidden = !items.some((item) => item.bought);
    updateBuyListCount(items);
    if (!items.length) {
      $('buy-list-summary').textContent = 'Add a product after comparing supermarket prices.';
      host.append(text('div', 'Your buy list is empty. Search on Home, then choose the cart icon.', 'empty-state'));
      return;
    }
    const groups = new Map();
    items.forEach((item) => {
      if (!groups.has(item.code)) groups.set(item.code, []);
      groups.get(item.code).push(item);
    });
    $('buy-list-summary').textContent = `${activeQuantity} item${activeQuantity === 1 ? '' : 's'} left across ${groups.size} store${groups.size === 1 ? '' : 's'}.`;
    [...groups.entries()].sort((a, b) => {
      const ad = a[1][0].distanceKm != null && Number.isFinite(Number(a[1][0].distanceKm))
        ? Number(a[1][0].distanceKm) : Number.POSITIVE_INFINITY;
      const bd = b[1][0].distanceKm != null && Number.isFinite(Number(b[1][0].distanceKm))
        ? Number(b[1][0].distanceKm) : Number.POSITIVE_INFINITY;
      return ad - bd || (a[1][0].supermarket || '').localeCompare(b[1][0].supermarket || '');
    }).forEach(([code, storeItems]) => {
      const section = text('section', '', 'buy-store-group');
      const header = text('div', '', 'buy-store-header');
      const identity = text('div', '', 'buy-store-identity');
      const storeName = storeItems[0].supermarket || code;
      const remaining = storeItems
        .filter((item) => !item.bought)
        .reduce((total, item) => total + Math.max(1, Number(item.quantity) || 1), 0);
      const title = text('div', '', 'buy-store-title');
      const distance = storeItems[0].distanceKm != null && Number.isFinite(Number(storeItems[0].distanceKm))
        ? `${Number(storeItems[0].distanceKm).toFixed(1)} km away · ` : '';
      title.append(text('h3', storeName), text('span', `${distance}${remaining} left · ${storeItems.length} product${storeItems.length === 1 ? '' : 's'}`));
      const directionsUrl = storeItems[0].directionsUrl || storeItems[0].mapUrl;
      if (directionsUrl) title.append(navigationLink(storeItems[0], 'store-directions'));
      identity.append(retailerLogo(code, storeName, 'buy-store-logo'), title);
      const subtotalEur = storeItems.filter((item) => !item.bought)
        .reduce((sum, item) => sum + (Number(item.priceEur) || 0) * Math.max(1, Number(item.quantity) || 1), 0);
      const subtotalInr = storeItems.filter((item) => !item.bought)
        .reduce((sum, item) => sum + (Number(item.priceInr) || 0) * Math.max(1, Number(item.quantity) || 1), 0);
      const subtotal = text('div', formatEuro(subtotalEur), 'buy-store-subtotal');
      if (subtotalInr) subtotal.append(text('small', `≈ ${formatInr(subtotalInr)}`));
      header.append(identity, subtotal);
      section.append(header);
      const list = text('div', '', 'buy-store-items');
      storeItems.forEach((item) => {
        const row = text('article', '', `buy-item${item.bought ? ' bought' : ''}`);
        const check = document.createElement('input');
        check.type = 'checkbox';
        check.checked = Boolean(item.bought);
        check.setAttribute('aria-label', `Mark ${item.productName} as bought`);
        check.addEventListener('change', () => changeBuyItem(item.id, 'toggle'));
        const copy = text('div', '', 'buy-item-copy');
        copy.append(
          text('strong', item.productName),
          text('span', `${item.amount || 'Package size not listed'} · ${formatEuro(Number(item.priceEur))}${item.priceInr ? ` · ≈ ${formatInr(Number(item.priceInr))}` : ''}`),
        );
        const actions = text('div', '', 'buy-item-actions');
        const quantity = text('div', '', 'quantity-control');
        const minus = text('button', '−');
        const plus = text('button', '+');
        minus.type = plus.type = 'button';
        minus.setAttribute('aria-label', `Decrease quantity of ${item.productName}`);
        plus.setAttribute('aria-label', `Increase quantity of ${item.productName}`);
        minus.disabled = (Number(item.quantity) || 1) <= 1;
        minus.addEventListener('click', () => changeBuyItem(item.id, 'decrease'));
        plus.addEventListener('click', () => changeBuyItem(item.id, 'increase'));
        quantity.append(minus, text('span', String(Math.max(1, Number(item.quantity) || 1))), plus);
        actions.append(quantity, productDestination(item, 'text-button'));
        const remove = text('button', 'Remove', 'text-button remove-buy-item');
        remove.type = 'button';
        remove.addEventListener('click', () => changeBuyItem(item.id, 'remove'));
        actions.append(remove);
        row.append(check, copy, actions);
        list.append(row);
      });
      section.append(list);
      host.append(section);
    });
  }

  function renderCheapest(row) {
    const host = $('cheapest-result');
    host.replaceChildren();
    host.hidden = !row;
    if (!row) return;
    const copy = document.createElement('div');
    const storeLine = text('div', '', 'cheapest-store-line');
    storeLine.append(retailerLogo(row.code, row.supermarket, 'cheapest-logo'), text('h3', row.supermarket));
    copy.append(
      text('div', row.is_best_value ? 'BEST VALUE NEAR YOU' : 'LOWEST PACK PRICE', 'section-kicker'),
      storeLine,
      text('p', row.product_name),
    );
    const meta = text('div', '', 'cheapest-meta');
    meta.append(priceBlock(row));
    meta.append(veganConfidenceBadge(row));
    const locationLabel = row.distance_km == null ? 'Online catalogue' : `${row.distance_km.toFixed(1)} km away`;
    meta.append(text('span', `${locationLabel} · ${row.amount || 'Package size not listed'}`));
    const actions = text('div', '', 'cheapest-actions');
    if (row.directions_url || row.latitude != null) actions.append(navigationLink(row, 'button navigate-button small'));
    actions.append(productDestination(row, 'button primary small'));
    actions.append(buyActionButton(row, 'button light small'));
    host.append(copy, meta, actions);
    syncBuyButtons();
  }

  function renderShopResult(row) {
    const card = text('article', '', `shop-price-card${row.available ? '' : ' unavailable'}`);
    const top = text('div', '', 'shop-price-top');
    const brand = retailerLogo(row.code, row.supermarket, 'shop-price-logo');
    const heading = document.createElement('div');
    heading.append(
      text('h3', row.supermarket),
      text('small', row.distance_km == null ? 'Dutch online catalogue' : `${row.distance_km.toFixed(1)} km away`),
    );
    top.append(brand, heading);
    if (row.available) {
      const label = row.dietary_status === 'compatible' ? 'Preference match' : (row.dietary_status === 'excluded' ? 'Does not match' : 'Scan to confirm');
      top.append(text('span', label, `diet-badge ${row.dietary_status}`));
      card.append(top, veganConfidenceBadge(row), text('p', row.product_name, 'shop-product-name'));
      if (row.amount) card.append(text('span', row.amount, 'shop-pack-size'));
      card.append(priceBlock(row));
      const flags = text('div', '', 'price-flags');
      if (row.is_best_value) flags.append(text('span', 'Best unit value'));
      if (row.is_lowest_pack) flags.append(text('span', 'Lowest pack price'));
      if (flags.childNodes.length) card.append(flags);
      card.append(text('p', row.dietary_note, 'diet-note'));
      const actions = text('div', '', 'shop-card-actions');
      if (row.directions_url || row.latitude != null) actions.append(navigationLink(row, 'button navigate-button small'));
      actions.append(productDestination(row, 'button secondary small'));
      actions.append(buyActionButton(row, 'button small'));
      if (row.dietary_status !== 'compatible') {
        const scanButton = text('button', 'Scan label', 'text-button');
        scanButton.type = 'button';
        scanButton.addEventListener('click', () => changePage('scan'));
        actions.append(scanButton);
      }
      card.append(actions);
    } else {
      top.append(text('span', 'Not found', 'availability-badge'));
      card.append(
        top,
        text('p', `This item was not found at ${row.supermarket}.`, 'shop-product-name'),
        text('p', 'No matching product or comparable catalogue price is available here right now.', 'diet-note'),
        externalLink(`Search ${row.supermarket}`, row.search_url, 'button secondary small'),
      );
    }
    return card;
  }

  function renderShopSearch(data) {
    $('searched-query').textContent = `“${data.query_en}”`;
    $('translated-query').textContent = `“${data.preference_query_nl}”`;
    setLocationLabel(data.location_name || data.location_label || savedLocation());
    const list = $('shop-result-list');
    list.replaceChildren();
    const visibleResults = (data.results || []).filter((row) => row.available).sort((left, right) => {
      const leftDistance = left.distance_km == null ? Number.POSITIVE_INFINITY : Number(left.distance_km);
      const rightDistance = right.distance_km == null ? Number.POSITIVE_INFINITY : Number(right.distance_km);
      return leftDistance - rightDistance || Number(left.price_eur || 0) - Number(right.price_eur || 0);
    });
    visibleResults.forEach((row) => list.append(renderShopResult(row)));
    if (!visibleResults.length) {
      const area = data.search_radius_km ? ` within ${data.search_radius_km} km` : '';
      list.append(text('div', `No matching products were found${area}.`, 'empty-state shop-empty-state'));
    }
    syncBuyButtons();
    const hiddenCount = Math.max(0, Number(data.stores_without_matches) || 0);
    $('result-count').textContent = `${visibleResults.length} match${visibleResults.length === 1 ? '' : 'es'}${hiddenCount ? ` · ${hiddenCount} without results hidden` : ''}`;
    const best = visibleResults.find((row) => row.is_best_value) || visibleResults.find((row) => row.is_lowest_pack);
    renderCheapest(best);
    const stores = $('nearby-store-list');
    stores.replaceChildren();
    (data.nearby_stores || []).forEach((store) => {
      const label = `${store.name}${store.distance_km == null ? '' : ` · ${store.distance_km.toFixed(1)} km`}`;
      const chip = navigationLink(store, 'nearby-store-chip');
      chip.replaceChildren();
      if (store.code) chip.append(retailerLogo(store.code, store.name, 'nearby-store-logo'));
      chip.append(text('span', label), text('strong', 'Navigate'));
      stores.append(chip);
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
    const location = savedLocation();
    if (query.length < 2) return;
    $('shop-search-error').hidden = true;
    $('shop-search-results').hidden = true;
    const form = new FormData();
    form.append('query', query);
    form.append('preference', preference());
    form.append('location', location);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 45000);
    setShopSearchBusy(true);
    try {
      const data = await api('/api/shop-search/', { method: 'POST', body: form, signal: controller.signal });
      rememberLocation(data.location_name || location);
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
    message.textContent = match === 'yes' ? 'Buy' : (match === 'no' ? "Don't buy" : 'Check');
    box.hidden = false;
    box.getAnimations().forEach((animation) => animation.cancel());
    void box.offsetWidth;
    box.classList.add('play');
    if (match === 'no' && navigator.vibrate) navigator.vibrate([160, 80, 220]);
    setTimeout(() => { box.hidden = true; }, 2600);
  }

  function resultConfidence(data) {
    const assessment = data.assessment;
    const supplied = Number(assessment.confidence);
    if (Number.isFinite(supplied) && supplied > 0) {
      return Math.max(25, Math.min(98, Math.round(supplied)));
    }
    const ingredientCount = Array.isArray(assessment.ingredients) ? assessment.ingredients.length : 0;
    const verified = (assessment.ingredients || []).filter((row) => row.evidence_verified).length;
    const resolved = (assessment.ingredients || []).filter((row) => row.evidence_verified && row.kind !== 'uncertain').length;
    let score = ingredientCount ? 35 + (25 * verified / ingredientCount) + (25 * resolved / ingredientCount) : 25;
    if (data.label?.ingredients_complete) score += 8;
    if (assessment.preference_match === 'no') score = Math.max(score, 92);
    if (assessment.preference_match === 'uncertain') score = Math.min(score, 84);
    return Math.max(25, Math.min(98, Math.round(score)));
  }

  function checkSummary(assessment) {
    const issues = Array.isArray(assessment.issues)
      ? assessment.issues.map((value) => String(value || '').trim()).filter(Boolean) : [];
    const issue = issues.find((value) => /ingredient source needs checking/i.test(value))
      || issues.find((value) => /not visible|unreadable|could not be matched/i.test(value))
      || issues[0] || '';
    const summary = String(issue || assessment.explanation || 'The label could not be confirmed clearly.').trim();
    return summary.length > 150 ? `${summary.slice(0, 147)}…` : summary;
  }

  function renderResult(data, announce = false) {
    if (!data?.assessment?.title || !Array.isArray(data.assessment.ingredients) || !data.label) {
      throw new Error('Invalid result. Please scan again.');
    }
    state.result = data;
    const assessment = data.assessment;
    const label = data.label;
    $('product-name').textContent = label.product_name || 'Your food label';
    const match = ['yes', 'no'].includes(assessment.preference_match) ? assessment.preference_match : 'uncertain';
    const resultCopy = match === 'yes' ? 'Buy' : (match === 'no' ? "Don't buy" : 'Check');
    $('verdict-card').className = `verdict-card minimal-verdict ${match === 'yes' ? 'buy' : (match === 'no' ? 'dont-buy' : 'check')}`;
    $('result-title').textContent = resultCopy;
    $('result-confidence').textContent = `${resultConfidence(data)}%`;
    $('result-verdict-icon').setAttribute('href', match === 'yes' ? '#i-check' : (match === 'no' ? '#i-close' : '#i-info'));
    $('result-check-summary').hidden = match !== 'uncertain';
    $('result-check-summary').textContent = match === 'uncertain' ? checkSummary(assessment) : '';
    $('result').hidden = false;
    $('scan-page').classList.add('has-result');
    $('scan-page-title').textContent = 'Scan result';
    completeProgress();
    $('result').focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (announce && match === 'no' && navigator.vibrate) navigator.vibrate([160, 80, 220]);
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
    renderBuyList();
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
  $('product-search-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    await searchProducts();
  });
  $('header-location').addEventListener('click', () => {
    $('location-input').value = savedLocation();
    $('location-error').hidden = true;
    $('location-dialog').showModal();
  });
  $('location-close').addEventListener('click', () => $('location-dialog').close());
  $('location-current-button').addEventListener('click', async () => {
    $('location-current-button').disabled = true;
    try {
      const name = await requestCurrentLocation();
      $('location-dialog').close();
      toast(`Location saved: ${name}`);
    } catch (error) {
      locationError(error.message);
    } finally {
      $('location-current-button').disabled = false;
    }
  });
  $('location-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const value = $('location-input').value.trim();
    if (!value) return;
    rememberLocation(value);
    $('location-dialog').close();
    toast(`Location saved: ${value}`);
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

  $('clear-bought').addEventListener('click', () => {
    if (!confirm('Remove every checked item from your buy list?')) return;
    try {
      saveBuyList(buyList().filter((item) => !item.bought));
      renderBuyList();
      toast('Bought items removed.');
    } catch {
      toast('The buy list could not be updated.');
    }
  });

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
  $('close-result').addEventListener('click', () => {
    $('result').hidden = true;
    $('scan-page').classList.remove('has-result');
    $('scan-page-title').textContent = 'Barcode Scanner';
  });
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

  applySavedLocation();
  updateBuyListCount();
  updateHome();
  changePage('home');
  let onboarded = false;
  try {
    onboarded = localStorage.getItem('foodlens.onboarding.v1') === 'done' && Object.hasOwn(names, localStorage.getItem('foodlens.preference'));
  } catch {}
  if (!onboarded) $('onboarding-dialog').showModal();
  configure();
})();
