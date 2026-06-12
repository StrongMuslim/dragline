// Replace with your Google Sheet ID from the URL:
// https://docs.google.com/spreadsheets/d/SHEET_ID/edit
const SHEET_ID = '1izy_C-QA3Pm6SKSpjDkGTgGmcBouEvu2cU4JmWyAdy0';
const GVIZ_URL = `https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:json&sheet=Sheet1`;

async function _fetchAllListings() {
  const res  = await fetch(GVIZ_URL);
  const text = await res.text();
  const data = JSON.parse(text.slice(text.indexOf('{'), text.lastIndexOf('}') + 1));

  return (data.table.rows || []).map(row => {
    const c = row.c || [];
    const v = (i, def = '') => {
      try { const cell = c[i]; return (cell && cell.v !== null && cell.v !== undefined) ? cell.v : def; }
      catch { return def; }
    };
    const s = i => {
      const val = v(i);
      if (val === '' || val == null) return '';
      if (typeof val === 'number' && Number.isInteger(val)) return String(val);
      return String(val).trim();
    };

    const rawId = v(0);
    if (rawId === '' || rawId == null) return null;

    return {
      id:                s(0),
      category:          s(1),
      brand:             s(2),
      model:             s(3),
      year:              v(4) != null && v(4) !== '' ? Number(v(4)) : null,
      hours:             v(5) != null && v(5) !== '' ? Number(v(5)) : null,
      condition:         s(6),
      compatible_models: s(7),
      price_krw:         Number(v(8)) || 0,
      location_kr:       s(9),
      status:            s(10) || 'available',
      name_kr:           s(11),
      name_uz:           s(12),
      name_ru:           s(13),
      name_en:           s(14),
      desc_kr:           s(15),
      desc_uz:           s(16),
      desc_ru:           s(17),
      desc_en:           s(18),
      photos:            s(19),
    };
  }).filter(Boolean);
}

async function getListing(id) {
  const listings = await _fetchAllListings();
  return listings.find(l => l.id === id) || null;
}

let currentListing = null;
let galleryPhotos = [];
let activeThumb = 0;

async function initListing() {
  const params = new URLSearchParams(location.search);
  const id = params.get('id');
  if (!id) { location.href = 'index.html'; return; }

  await Promise.all([fetchRate(), initI18n()]);

  currentListing = await getListing(id);
  if (!currentListing) { location.href = 'index.html'; return; }

  renderListing(currentListing);
}

function renderListing(l) {
  const lang  = currentLang;
  const name  = l[`name_${lang}`] || l.name_en;
  const desc  = l[`desc_${lang}`]  || l.desc_en;

  document.title = `${name} — Dragline`;

  galleryPhotos = l.photos.split(',').map(s => s.trim()).filter(Boolean);
  renderGallery();

  document.getElementById('listing-title').textContent = name;
  const pill = document.getElementById('listing-status');
  pill.textContent = t('card_' + l.status);
  pill.className = `status-pill status-pill--${l.status}`;

  const usd = krwToUsd(l.price_krw);
  document.getElementById('listing-price-krw').textContent = formatKrw(l.price_krw);
  document.getElementById('listing-price-usd').textContent = formatUsd(usd);

  const rows = [
    ['listing_brand',     l.brand],
    ['listing_model',     l.model],
    ['listing_year',      l.year  ? String(l.year)                        : null],
    ['listing_hours',     l.hours ? `${l.hours.toLocaleString()} ${t('card_hours')}` : null],
    ['listing_condition', l.condition],
    ['listing_location',  l.location_kr],
    ['listing_compatible', l.compatible_models || null],
  ];

  document.getElementById('specs-body').innerHTML = rows
    .filter(([, v]) => v)
    .map(([key, val]) => `
      <tr>
        <th>${t(key)}</th>
        <td>${val}</td>
      </tr>`)
    .join('');

  const descEl = document.getElementById('listing-desc');
  if (desc) {
    descEl.textContent = desc;
    descEl.closest('.listing-desc-wrap').style.display = 'block';
  } else {
    descEl.closest('.listing-desc-wrap').style.display = 'none';
  }
}

function renderGallery() {
  const mainImg  = document.getElementById('gallery-main-img');
  const thumbsEl = document.getElementById('gallery-thumbs');

  mainImg.src = galleryPhotos[activeThumb] || '';
  mainImg.alt = currentListing ? (currentListing[`name_${currentLang}`] || '') : '';

  thumbsEl.innerHTML = galleryPhotos.map((src, i) => `
    <button class="gallery__thumb${i === activeThumb ? ' active' : ''}"
            onclick="setThumb(${i})" aria-label="Photo ${i + 1}">
      <img src="${src}" alt="Photo ${i + 1}" loading="lazy">
    </button>`).join('');
}

function setThumb(i) {
  activeThumb = i;
  renderGallery();
}

document.addEventListener('langchange', () => {
  if (currentListing) renderListing(currentListing);
});

document.addEventListener('DOMContentLoaded', initListing);
