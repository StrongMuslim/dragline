const SUPPORTED_LANGS = ['kr', 'uz', 'ru', 'en'];
const DEFAULT_LANG = 'en';

let currentLang = DEFAULT_LANG;
let translations = {};

function detectLang() {
  const saved = localStorage.getItem('dragline_lang');
  if (saved && SUPPORTED_LANGS.includes(saved)) return saved;
  const browser = (navigator.language || '').slice(0, 2).toLowerCase();
  return SUPPORTED_LANGS.includes(browser) ? browser : DEFAULT_LANG;
}

async function loadTranslations(lang) {
  try {
    const res = await fetch(`locales/${lang}.json`);
    if (!res.ok) throw new Error('fetch failed');
    translations = await res.json();
    currentLang = lang;
    localStorage.setItem('dragline_lang', lang);
  } catch {
    if (lang !== DEFAULT_LANG) {
      return loadTranslations(DEFAULT_LANG);
    }
  }
  applyTranslations();
  updateLangSwitcher();
  document.dispatchEvent(new CustomEvent('langchange'));
}

function t(key) {
  return translations[key] || key;
}

function applyTranslations() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  document.documentElement.lang = currentLang;
}

function updateLangSwitcher() {
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.lang === currentLang);
  });
}

function showLangPicker() {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'lang-picker-overlay';
    overlay.innerHTML = `
      <div class="lang-picker">
        <div class="lang-picker__hint">
          언어 선택 &nbsp;·&nbsp; Tilni tanlang &nbsp;·&nbsp; Выберите язык &nbsp;·&nbsp; Choose language
        </div>
        <div class="lang-picker__grid">
          <button class="lang-picker__btn" data-lang="ko">
            <span class="lang-picker__flag">🇰🇷</span>
            <span class="lang-picker__name">한국어</span>
          </button>
          <button class="lang-picker__btn" data-lang="uz">
            <span class="lang-picker__flag">🇺🇿</span>
            <span class="lang-picker__name">O'zbekcha</span>
          </button>
          <button class="lang-picker__btn" data-lang="ru">
            <span class="lang-picker__flag">🇷🇺</span>
            <span class="lang-picker__name">Русский</span>
          </button>
          <button class="lang-picker__btn" data-lang="en">
            <span class="lang-picker__flag">🌍</span>
            <span class="lang-picker__name">English</span>
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    overlay.querySelectorAll('.lang-picker__btn').forEach(btn => {
      btn.addEventListener('click', () => {
        overlay.classList.add('lang-picker--out');
        setTimeout(() => overlay.remove(), 280);
        resolve(btn.dataset.lang);
      });
    });
  });
}

async function initI18n() {
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => loadTranslations(btn.dataset.lang));
  });
  const saved = localStorage.getItem('dragline_lang');
  const lang = saved ? saved : await showLangPicker();
  await loadTranslations(lang);
}
