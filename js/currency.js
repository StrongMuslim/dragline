const FALLBACK_RATE = 1350; // 1 USD = N KRW — update manually if needed
const RATE_CACHE_KEY = 'dragline_usd_rate';
const RATE_CACHE_TTL = 3600 * 1000; // 1 hour

let krwPerUsd = FALLBACK_RATE;

async function fetchRate() {
  const cached = localStorage.getItem(RATE_CACHE_KEY);
  if (cached) {
    try {
      const { rate, ts } = JSON.parse(cached);
      if (Date.now() - ts < RATE_CACHE_TTL && rate > 0) {
        krwPerUsd = rate;
        return;
      }
    } catch { /* ignore bad cache */ }
  }
  try {
    const res = await fetch('https://open.er-api.com/v6/latest/USD');
    const data = await res.json();
    if (data.result === 'success' && data.rates && data.rates.KRW > 0) {
      krwPerUsd = data.rates.KRW;
      localStorage.setItem(RATE_CACHE_KEY, JSON.stringify({ rate: krwPerUsd, ts: Date.now() }));
    }
  } catch {
    // use FALLBACK_RATE
  }
}

function krwToUsd(krw) {
  return Math.round(krw / krwPerUsd);
}

function formatKrw(krw) {
  return (krw / 1000000).toFixed(1) + ' млн ₩';
}

function formatUsd(usd) {
  return '≈ $' + usd.toLocaleString('en-US');
}
