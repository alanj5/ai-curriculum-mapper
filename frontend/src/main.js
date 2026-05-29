import { api } from './api.js';
import { initGraph, highlightNode, fitGraph, rerunLayout, applyGraphFilter, switchGraphView, setSelectedModuleForGraph } from './components/GraphView.js';
import { initModulePanel, selectModule, showModuleDetail } from './components/ModulePanel.js';
import { initAlignmentTable } from './components/AlignmentTable.js';
import { initValidationWidget } from './components/ValidationWidget.js';
import { initGapReport } from './components/GapReport.js';

// ── Health check ─────────────────────────────────────────────────
async function checkHealth() {
  const dot = document.querySelector('.dot');
  const text = document.getElementById('health-text');
  try {
    const h = await api.health();
    dot.classList.add('ok');
    text.textContent = `${h.modules} modules · ${h.concepts} concepts · ${h.alignments} alignments`;
  } catch {
    dot.classList.add('err');
    text.textContent = 'API unreachable';
  }
}

// ── Tab routing ──────────────────────────────────────────────────
let _activeTab = 'graph';
let _gapLoaded = false;
let _alignmentsLoaded = false;

function activateTab(tab) {
  _activeTab = tab;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', p.id === `tab-${tab}`));

  if (tab === 'gaps' && !_gapLoaded) {
    _gapLoaded = true;
    initGapReport();
  }
}

// ── Module selection callback ────────────────────────────────────
function onModuleSelect(code) {
  showModuleDetail(code);
  highlightNode(code);
  setSelectedModuleForGraph(code);
}

// ── KA list (shared between alignment table and validation widget) ─
async function getKaOptions() {
  const coverage = await api.coverage();
  return coverage.map(c => ({ code: c.ka_code, name: c.ka_name }));
}

// ── Bootstrap ────────────────────────────────────────────────────
async function main() {
  checkHealth();

  // Tab buttons
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => activateTab(btn.dataset.tab));
  });

  // Parallel init of module panel + KA data
  const [, kaOptions] = await Promise.all([
    initModulePanel(onModuleSelect),
    getKaOptions(),
  ]);

  // Validation widget (modal, shared by alignment table)
  initValidationWidget(kaOptions);

  // Graph tab
  const cyContainer = document.getElementById('cy');
  initGraph(cyContainer, (code) => {
    if (code) {
      selectModule(code);
      showModuleDetail(code);
    } else {
      showModuleDetail(null);
    }
  }).then(() => {
    // Wire up graph controls once graph is ready
    document.getElementById('graph-fit-btn').addEventListener('click', () => fitGraph());
    document.getElementById('graph-layout-btn').addEventListener('click', () => rerunLayout());

    const slider = document.getElementById('edge-threshold');
    const sliderVal = document.getElementById('edge-threshold-val');
    slider.addEventListener('input', () => {
      const v = parseFloat(slider.value);
      sliderVal.textContent = v.toFixed(2);
      applyGraphFilter(v);
    });

    const viewSelect = document.getElementById('graph-view-select');
    viewSelect.addEventListener('change', () => {
      switchGraphView(viewSelect.value, null);
    });
  }).catch(err => {
    cyContainer.innerHTML = `<p class="placeholder" style="color:#f87171">Graph unavailable: ${err.message}</p>`;
  });

  // Alignments tab (lazy — only load once on first tab switch)
  document.querySelector('[data-tab="alignments"]').addEventListener('click', () => {
    if (!_alignmentsLoaded) {
      _alignmentsLoaded = true;
      initAlignmentTable(kaOptions);
    }
  }, { once: true });
}

main().catch(console.error);
