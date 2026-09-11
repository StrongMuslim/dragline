const PAGE_SIZE = 12;

let allListings = [];
let filteredListings = [];
let visibleCount = PAGE_SIZE;
let newIds = new Set();

async function initCatalog() {
  try {
    await Promise.all([fetchRate(), initI18n()]);
    allListings = await fetchListings();
  } catch (err) {
    showErrorState('catalog-status');
    return;
  }

  newIds = computeNewIds(allListings);
  try {
    populateBrandFilter();
    applyFilters();
    setupFilterListeners();
    document.getElementById('catalog-status').style.display = 'none';
  } catch (err) {
    console.error('Dragline: failed to render catalog', err);
    showErrorState('catalog-status', 'error_render');
  }
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
  const query    = document.getElementById('filter-search').value.trim().toLowerCase();
  const hideSold = document.getElementById('filter-hide-sold').checked;
  const sortBy   = document.getElementById('filter-sort').value;

  filteredListings = allListings.filter(l => {
    if (category && l.category !== category) return false;
    if (brand    && l.brand    !== brand)    return false;
    const m = l.price_krw / 1_000_000;
    if (m < minM || m > maxM) return false;
    if (hideSold && l.status === 'sold') return false;
    if (query) {
      const name = (l[`name_${currentLang}`] || l.name_en || '').toLowerCase();
      const hay  = `${l.brand} ${l.model} ${name}`.toLowerCase();
      if (!hay.includes(query)) return false;
    }
    return true;
  });

  sortListings(sortBy);
  visibleCount = PAGE_SIZE;
  renderCards();
  updateCount();
}

function sortListings(sortBy) {
  switch (sortBy) {
    case 'price_asc':  filteredListings.sort((a, b) => a.price_krw - b.price_krw); break;
    case 'price_desc': filteredListings.sort((a, b) => b.price_krw - a.price_krw); break;
    case 'year_desc':  filteredListings.sort((a, b) => (b.year || 0) - (a.year || 0)); break;
    case 'year_asc':   filteredListings.sort((a, b) => (a.year || 9999) - (b.year || 9999)); break;
    default:           filteredListings.reverse(); // newest (last added in sheet) first
  }
}

function renderCards() {
  const grid         = document.getElementById('listings-grid');
  const noResults     = document.getElementById('no-results');
  const showMoreWrap = document.getElementById('show-more-wrap');

  if (!filteredListings.length) {
    grid.innerHTML = '';
    noResults.style.display = 'block';
    showMoreWrap.style.display = 'none';
    return;
  }

  noResults.style.display = 'none';
  grid.innerHTML = filteredListings.slice(0, visibleCount).map(cardHTML).join('');
  showMoreWrap.style.display = visibleCount < filteredListings.length ? 'block' : 'none';
}

function cardHTML(l) {
  return buildCardHTML(l, { asLink: false, showMeta: true, showDetailsButton: true, newIds });
}

function updateCount() {
  const el = document.getElementById('results-count');
  if (el) el.textContent = filteredListings.length;
}

function setupFilterListeners() {
  ['filter-category', 'filter-brand', 'filter-sort'].forEach(id => {
    document.getElementById(id).addEventListener('change', applyFilters);
  });
  ['filter-price-min', 'filter-price-max', 'filter-search'].forEach(id => {
    document.getElementById(id).addEventListener('input', applyFilters);
  });
  document.getElementById('filter-hide-sold').addEventListener('change', applyFilters);
  document.getElementById('show-more-btn').addEventListener('click', () => {
    visibleCount += PAGE_SIZE;
    renderCards();
  });
  document.getElementById('filter-reset').addEventListener('click', () => {
    ['filter-category', 'filter-brand'].forEach(id => {
      document.getElementById(id).value = '';
    });
    ['filter-price-min', 'filter-price-max', 'filter-search'].forEach(id => {
      document.getElementById(id).value = '';
    });
    document.getElementById('filter-sort').value = 'default';
    document.getElementById('filter-hide-sold').checked = false;
    applyFilters();
  });
}

document.addEventListener('langchange', () => {
  if (allListings.length > 0) renderCards();
});

document.addEventListener('DOMContentLoaded', initCatalog);
