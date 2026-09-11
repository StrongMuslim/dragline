let currentListing = null;
let galleryPhotos = [];
let activeThumb = 0;
let lightboxOpen = false;
let newIds = new Set();

async function initListing() {
  const params = new URLSearchParams(location.search);
  const id = params.get('id');
  if (!id) { location.href = 'index.html'; return; }

  let listings;
  try {
    await Promise.all([fetchRate(), initI18n()]);
    listings = await fetchListings();
  } catch (err) {
    showErrorState('listing-status-box');
    return;
  }

  newIds = computeNewIds(listings);
  currentListing = listings.find(l => l.id === id) || null;
  if (!currentListing) { location.href = 'index.html'; return; }

  try {
    renderListing(currentListing);
    renderSimilar(listings, currentListing);
    setupShareButton();
    setupLightbox();
    showListingContent();
  } catch (err) {
    console.error('Dragline: failed to render listing', err);
    showErrorState('listing-status-box', 'error_render');
  }
}

function showListingContent() {
  document.getElementById('listing-status-box').style.display = 'none';
  document.getElementById('listing-layout').style.display = '';
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
  if (lightboxOpen) updateLightboxImg();
}

let cachedListings = [];

function renderSimilar(listings, current) {
  cachedListings = listings;
  const section = document.getElementById('similar-section');
  const grid    = document.getElementById('similar-grid');

  const pool = listings.filter(l => l.id !== current.id && l.status === 'available');
  let similar = pool.filter(l => l.category === current.category && l.brand === current.brand);
  if (similar.length < 4) {
    const more = pool.filter(l => l.category === current.category && !similar.includes(l));
    similar = similar.concat(more);
  }
  similar = similar.slice(0, 4);

  if (!similar.length) { section.style.display = 'none'; return; }

  grid.innerHTML = similar.map(similarCardHTML).join('');
  section.style.display = 'block';
}

function similarCardHTML(l) {
  return buildCardHTML(l, { asLink: true, showMeta: false, showDetailsButton: false, newIds });
}

function setupShareButton() {
  document.getElementById('share-btn').addEventListener('click', async () => {
    const name = currentListing[`name_${currentLang}`] || currentListing.name_en;
    const shareData = { title: `${name} — Dragline`, url: location.href };
    if (navigator.share) {
      try { await navigator.share(shareData); } catch { /* user cancelled */ }
    } else {
      try {
        await navigator.clipboard.writeText(location.href);
        showToast(t('share_copied'));
      } catch {
        showToast(t('share_failed'));
      }
    }
  });
}

function showToast(msg) {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add('toast--show');
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => toast.classList.remove('toast--show'), 2200);
}

function setupLightbox() {
  const overlay = document.getElementById('lightbox');
  document.getElementById('gallery-main-img').addEventListener('click', openLightbox);
  document.getElementById('lightbox-close').addEventListener('click', closeLightbox);
  document.getElementById('lightbox-prev').addEventListener('click', () => navLightbox(-1));
  document.getElementById('lightbox-next').addEventListener('click', () => navLightbox(1));
  overlay.addEventListener('click', e => { if (e.target === overlay) closeLightbox(); });
  document.addEventListener('keydown', e => {
    if (!lightboxOpen) return;
    if (e.key === 'Escape')    closeLightbox();
    if (e.key === 'ArrowLeft')  navLightbox(-1);
    if (e.key === 'ArrowRight') navLightbox(1);
  });
}

function openLightbox() {
  if (!galleryPhotos.length) return;
  lightboxOpen = true;
  document.getElementById('lightbox').classList.add('active');
  const multi = galleryPhotos.length > 1;
  document.getElementById('lightbox-prev').style.display = multi ? 'flex' : 'none';
  document.getElementById('lightbox-next').style.display = multi ? 'flex' : 'none';
  updateLightboxImg();
}

function closeLightbox() {
  lightboxOpen = false;
  document.getElementById('lightbox').classList.remove('active');
}

function navLightbox(dir) {
  activeThumb = (activeThumb + dir + galleryPhotos.length) % galleryPhotos.length;
  renderGallery();
  updateLightboxImg();
}

function updateLightboxImg() {
  document.getElementById('lightbox-img').src = galleryPhotos[activeThumb] || '';
}

document.addEventListener('langchange', () => {
  if (currentListing) {
    renderListing(currentListing);
    renderSimilar(cachedListings, currentListing);
  }
});

document.addEventListener('DOMContentLoaded', initListing);
