// Shared between index.html (main.js) and listing.html (listing.js):
// gviz fetch/parse, "NEW" badge detection, card markup, error-state UI.

const SHEET_ID = '1izy_C-QA3Pm6SKSpjDkGTgGmcBouEvu2cU4JmWyAdy0';
const GVIZ_URL = `https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:json&sheet=Sheet1`;

async function fetchListings() {
  const res  = await fetch(GVIZ_URL, { cache: 'no-store' });
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

function computeNewIds(listings, count = 3) {
  return new Set(listings.slice(-count).map(l => l.id));
}

// opts: asLink (render <a href> instead of <article onclick>), showMeta
// (year/hours row), showDetailsButton, newIds (Set of ids to badge "NEW")
function buildCardHTML(l, opts = {}) {
  const { asLink = false, showMeta = true, showDetailsButton = true, newIds = new Set() } = opts;

  const name  = l[`name_${currentLang}`] || l.name_en;
  const photo = (l.photos.split(',')[0] || '').trim();
  const usd   = krwToUsd(l.price_krw);
  const isNew = l.status === 'available' && newIds.has(l.id);

  const catKey = l.category === 'excavator' ? 'filter_excavators'
               : l.category === 'parts'     ? 'filter_parts'
               :                              'filter_other';

  const statusBadge = l.status !== 'available'
    ? `<span class="badge badge--${l.status}">${t('card_' + l.status)}</span>`
    : '';

  const meta = [];
  if (showMeta) {
    if (l.year)  meta.push(`${l.year} ${t('card_year')}`);
    if (l.hours) meta.push(`${l.hours.toLocaleString()} ${t('card_hours')}`);
  }

  const body = `
  <div class="card__img-wrap">
    <img class="card__img" src="${photo}" alt="${name}" loading="lazy">
    <span class="card__cat">${t(catKey)}</span>
    ${statusBadge}
  </div>
  <div class="card__body">
    <div class="card__brand">${l.brand} · ${l.model}${isNew ? ` <span class="badge-new">${t('badge_new')}</span>` : ''}</div>
    <h3 class="card__name">${name}</h3>
    ${meta.length ? `<div class="card__meta">${meta.join(' · ')}</div>` : ''}
    <div class="card__price">
      <span class="card__price-main">${formatKrw(l.price_krw)}</span>
      <span class="card__price-usd">${formatUsd(usd)}</span>
    </div>
    ${showDetailsButton ? `<div class="btn btn--outline">${t('card_details')}</div>` : ''}
  </div>`;

  if (asLink) {
    return `<a href="listing.html?id=${l.id}" class="card${l.status !== 'available' ? ' card--inactive' : ''}">${body}</a>`;
  }

  return `
<article class="card${l.status !== 'available' ? ' card--inactive' : ''}"
         onclick="location.href='listing.html?id=${l.id}'"
         role="link" tabindex="0"
         onkeydown="if(event.key==='Enter')location.href='listing.html?id=${l.id}'">${body}</article>`;
}

function showErrorState(elementId, messageKey = 'error_loading') {
  const box = document.getElementById(elementId);
  const retryId = `${elementId}-retry`;
  box.innerHTML = `
    <p>${t(messageKey)}</p>
    <button class="btn--retry" id="${retryId}">${t('retry')}</button>`;
  box.style.display = 'block';
  document.getElementById(retryId).addEventListener('click', () => location.reload());
}
