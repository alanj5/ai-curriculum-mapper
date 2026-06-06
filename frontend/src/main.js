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

// ── Help / onboarding modal ──────────────────────────────────────
function initHelpModal() {
  const modal = document.getElementById('help-modal');
  if (!modal) return;
  const open = () => modal.classList.remove('hidden');
  const close = () => modal.classList.add('hidden');

  document.getElementById('help-btn')?.addEventListener('click', open);
  document.getElementById('help-close')?.addEventListener('click', close);
  document.getElementById('help-got-it')?.addEventListener('click', close);
  modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) close();
  });

  // Auto-open once for first-time visitors so the tool is never a blank slate.
  try {
    if (!localStorage.getItem('cm_seen_help')) { open(); localStorage.setItem('cm_seen_help', '1'); }
  } catch { /* localStorage unavailable — skip */ }
}

// ── Bootstrap ────────────────────────────────────────────────────
function main() {
  registerRoute('overview', mountOverview);
  registerRoute('explore',  mountExplore);
  registerRoute('map',      mountMap);
  registerRoute('coverage', mountCoverage);
  registerRoute('review',   mountReview);

  initHelpModal();
  checkHealth();
  initRouter();   // renders the first page immediately

  // Wire the shared reassign modal once, in the background.
  getKaOptions().then(ka => initValidationWidget(ka)).catch(() => { /* table still usable */ });
}

main();
