// ── To switch to SheetDB: replace getListings() body with:
//    const res = await fetch('https://sheetdb.io/api/v1/YOUR_ID');
//    return res.json();

async function getListings() {
  return PLACEHOLDER_LISTINGS;
}

let allListings = [];
let filteredListings = [];

async function initCatalog() {
  await Promise.all([fetchRate(), initI18n()]);

  allListings = await getListings();
  populateBrandFilter();
  applyFilters();
  setupFilterListeners();
}

function populateBrandFilter() {
  const brands = [...new Set(allListings.map(l => l.brand))].sort();
  const sel = document.getElementById('filter-brand');
  brands.forEach(brand => {
    const opt = document.createElement('option');
    opt.value = brand;
    opt.textContent = brand;
    sel.appendChild(opt);
  });
}

function applyFilters() {
  const category = document.getElementById('filter-category').value;
  const brand    = document.getElementById('filter-brand').value;
  const minM     = parseFloat(document.getElementById('filter-price-min').value) || 0;
  const maxM     = parseFloat(document.getElementById('filter-price-max').value) || Infinity;

  filteredListings = allListings.filter(l => {
    if (category && l.category !== category) return false;
    if (brand    && l.brand    !== brand)    return false;
    const m = l.price_krw / 1_000_000;
    if (m < minM || m > maxM) return false;
    return true;
  });

  renderCards();
  updateCount();
}

function renderCards() {
  const grid      = document.getElementById('listings-grid');
  const noResults = document.getElementById('no-results');

  if (!filteredListings.length) {
    grid.innerHTML = '';
    noResults.style.display = 'block';
    return;
  }

  noResults.style.display = 'none';
  grid.innerHTML = filteredListings.map(cardHTML).join('');
}

function cardHTML(l) {
  const name  = l[`name_${currentLang}`] || l.name_en;
  const photo = l.photos.split(',')[0].trim();
  const usd   = krwToUsd(l.price_krw);

  const catKey = l.category === 'excavator' ? 'filter_excavators'
               : l.category === 'parts'     ? 'filter_parts'
               :                              'filter_other';

  const badge = l.status !== 'available'
    ? `<span class="badge badge--${l.status}">${t('card_' + l.status)}</span>`
    : '';

  const meta = [];
  if (l.year)  meta.push(`${l.year} ${t('card_year')}`);
  if (l.hours) meta.push(`${l.hours.toLocaleString()} ${t('card_hours')}`);

  return `
<article class="card${l.status !== 'available' ? ' card--inactive' : ''}"
         onclick="location.href='listing.html?id=${l.id}'"
         role="link" tabindex="0"
         onkeydown="if(event.key==='Enter')location.href='listing.html?id=${l.id}'">
  <div class="card__img-wrap">
    <img class="card__img" src="${photo}" alt="${name}" loading="lazy">
    <span class="card__cat">${t(catKey)}</span>
    ${badge}
  </div>
  <div class="card__body">
    <div class="card__brand">${l.brand} · ${l.model}</div>
    <h3 class="card__name">${name}</h3>
    ${meta.length ? `<div class="card__meta">${meta.join(' · ')}</div>` : ''}
    <div class="card__price">
      <span class="card__price-main">${formatKrw(l.price_krw)}</span>
      <span class="card__price-usd">${formatUsd(usd)}</span>
    </div>
    <div class="btn btn--outline">${t('card_details')}</div>
  </div>
</article>`;
}

function updateCount() {
  const el = document.getElementById('results-count');
  if (el) el.textContent = filteredListings.length;
}

function setupFilterListeners() {
  ['filter-category', 'filter-brand'].forEach(id => {
    document.getElementById(id).addEventListener('change', applyFilters);
  });
  ['filter-price-min', 'filter-price-max'].forEach(id => {
    document.getElementById(id).addEventListener('input', applyFilters);
  });
  document.getElementById('filter-reset').addEventListener('click', () => {
    ['filter-category', 'filter-brand'].forEach(id => {
      document.getElementById(id).value = '';
    });
    ['filter-price-min', 'filter-price-max'].forEach(id => {
      document.getElementById(id).value = '';
    });
    applyFilters();
  });
}

// Re-render cards when language changes
document.addEventListener('langchange', () => {
  if (allListings.length > 0) renderCards();
});

document.addEventListener('DOMContentLoaded', initCatalog);
