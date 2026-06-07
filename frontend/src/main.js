import { initRouter, registerRoute } from './router.js';
import { api } from './api.js';
import { getKaOptions } from './state.js';
import { initValidationWidget } from './components/ValidationWidget.js';
import { mountOverview } from './pages/Overview.js';
import { mountExplore } from './pages/Explore.js';
import { mountMap } from './pages/Map.js';
import { mountCoverage } from './pages/Coverage.js';
import { mountReview } from './pages/Review.js';

// ── Health badge ─────────────────────────────────────────────────
async function checkHealth() {
  const dot = document.querySelector('.dot');
  const text = document.getElementById('health-text');
  try {
    const h = await api.health();
    dot.classList.add('ok');
    text.textContent = `${h.modules} modules · ${h.concepts.toLocaleString()} concepts · ${h.alignments.toLocaleString()} alignments`;
  } catch {
    dot.classList.add('err');
    text.textContent = 'API unreachable';
  }
}

// ── Bootstrap ────────────────────────────────────────────────────
// No global help modal: every page documents itself in context (the Overview is
// the index; each page has a lede; the map carries its own legends + hover tip;
// the review table and coverage chart carry their own keys).
function main() {
  registerRoute('overview', mountOverview);
  registerRoute('explore',  mountExplore);
  registerRoute('map',      mountMap);
  registerRoute('coverage', mountCoverage);
  registerRoute('review',   mountReview);

  checkHealth();
  initRouter();   // renders the first page immediately

  // Wire the shared reassign modal once, in the background.
  getKaOptions().then(ka => initValidationWidget(ka)).catch(() => { /* table still usable */ });
}

main();
