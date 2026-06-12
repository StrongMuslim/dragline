// ── To switch to SheetDB: replace getListing() body with:
//    const res = await fetch(`https://sheetdb.io/api/v1/YOUR_ID/search?id=${id}`);
//    const arr = await res.json();
//    return arr[0] || null;

async function getListing(id) {
  return PLACEHOLDER_LISTINGS.find(l => l.id === id) || null;
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

  // Title & status
  document.getElementById('listing-title').textContent = name;
  const pill = document.getElementById('listing-status');
  pill.textContent = t('card_' + l.status);
  pill.className = `status-pill status-pill--${l.status}`;

  // Price
  const usd = krwToUsd(l.price_krw);
  document.getElementById('listing-price-krw').textContent = formatKrw(l.price_krw);
  document.getElementById('listing-price-usd').textContent = formatUsd(usd);

  // Specs table — only show rows with values
  const rows = [
    ['listing_brand',    l.brand],
    ['listing_model',    l.model],
    ['listing_year',     l.year  ? String(l.year)                        : null],
    ['listing_hours',    l.hours ? `${l.hours.toLocaleString()} ${t('card_hours')}` : null],
    ['listing_condition',l.condition],
    ['listing_location', l.location_kr],
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

  // Description
  const descEl = document.getElementById('listing-desc');
  if (desc) {
    descEl.textContent = desc;
    descEl.closest('.listing-desc-wrap').style.display = 'block';
  } else {
    descEl.closest('.listing-desc-wrap').style.display = 'none';
  }

  // Contact block static strings (already handled by applyTranslations via data-i18n)
}

function renderGallery() {
  const mainImg   = document.getElementById('gallery-main-img');
  const thumbsEl  = document.getElementById('gallery-thumbs');

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

// Re-render when language changes
document.addEventListener('langchange', () => {
  if (currentListing) renderListing(currentListing);
});

document.addEventListener('DOMContentLoaded', initListing);
