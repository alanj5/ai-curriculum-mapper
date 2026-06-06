import {
  initGraph, switchGraphView, setSelectedModuleForGraph, setVisibleModules,
  fitGraph, rerunLayout, applyGraphFilter, traceModuleChain, showConceptNeighbourhood,
} from '../components/GraphView.js';
import { showModuleDetail } from '../components/ModulePanel.js';
import { getModules } from '../state.js';
import { isLikelyFragment } from '../util/concepts.js';
import { api } from '../api.js';

const VIEWS = ['module-module', 'level', 'bipartite', 'concept-prereq'];

/** Curriculum Map — the centrepiece. Plain-language controls, programme/year
 *  filters, a concept picker for the prerequisite view (offering only concepts
 *  that actually have prerequisites), and a slide-over detail drawer. */
export async function mountMap(app, params = {}) {
  app.innerHTML = `
    <div class="map-wrap">
      <div class="map-controls">
        <div class="view-switch" id="view-switch">
          <button class="view-btn active" data-view="module-module">How modules relate</button>
          <button class="view-btn" data-view="level">By year</button>
          <button class="view-btn" data-view="bipartite">A module's concepts</button>
          <button class="view-btn" data-view="concept-prereq">Concept prerequisites</button>
        </div>

        <div class="map-ctrl-group" id="map-filters">
          <select id="map-programme" class="filter-select" title="Show only modules in this programme"><option value="">All programmes</option></select>
          <select id="map-level" class="filter-select" title="Show only modules at this level">
            <option value="">All years</option>
            <option value="1">Year 1</option>
            <option value="2">Year 2</option>
            <option value="3">Year 3</option>
          </select>
        </div>

        <div class="map-ctrl-group" id="bipartite-picker" style="display:none">
          <select id="bipartite-module" class="filter-select" title="Choose a module to see its concepts"></select>
        </div>

        <div class="map-ctrl-group" id="concept-picker" style="display:none">
          <input id="concept-search" class="filter-select" list="concept-options" placeholder="Search a concept…" autocomplete="off" style="min-width:300px" />
          <datalist id="concept-options"></datalist>
        </div>

        <label class="map-ctrl-group" id="edge-threshold-label">
          <span id="edge-threshold-text">Show only strong links</span>
          <input type="range" id="edge-threshold" min="0" max="0.2" step="0.01" value="0" />
          <span id="edge-threshold-val">0.00</span>
        </label>

        <button class="map-btn" id="reset-view" title="Re-arrange and zoom to fit">Reset view</button>
        <span class="ctrl-desc" id="graph-hint"></span>
      </div>

      <div class="graph-viewport">
        <div id="cy" class="cytoscape-container"></div>
        <div class="graph-legend" id="graph-legend"></div>
        <div class="edge-legend" id="edge-legend">
          <div class="legend-item"><div class="edge-sample edge-solid"></div><span>Concept overlap</span></div>
          <div class="legend-item"><div class="edge-sample edge-dashed-arrow"></div><span>Prerequisite (arrow → the later module)</span></div>
        </div>
        <div class="map-hint" id="map-firsthint">
          <button class="mh-close" id="mh-close" aria-label="Dismiss">✕</button>
          <strong>Tip:</strong> hover a node to spotlight its connections, click it to open details. Drag to pan, scroll to zoom.
        </div>
        <aside class="map-drawer" id="map-drawer">
          <button class="drawer-close" id="drawer-close" aria-label="Close">✕</button>
          <div id="map-detail"></div>
        </aside>
      </div>
    </div>
  `;

  const cy = document.getElementById('cy');
  const picker = document.getElementById('bipartite-module');
  const strengthText = document.getElementById('edge-threshold-text');
  const allModules = await getModules().catch(() => []);
  let centerConcept = null;

  const openDrawer = (code) => {
    document.getElementById('map-drawer').classList.add('open');
    showModuleDetail(code, document.getElementById('map-detail'));
  };
  const closeDrawer = () => document.getElementById('map-drawer')?.classList.remove('open');

  await initGraph(cy, (code) => {
    if (code) { setSelectedModuleForGraph(code); openDrawer(code); }
    else closeDrawer();
  });

  const applyStrengthText = (view) => {
    if (strengthText) strengthText.textContent = view === 'bipartite' ? 'Show only confident concepts' : 'Show only strong links';
  };
  applyStrengthText('module-module');

  // ── Programme + year filters (module views) ───────────────────────
  const progSel = document.getElementById('map-programme');
  try {
    const programmes = await api.programmes();
    progSel.innerHTML = '<option value="">All programmes</option>' +
      programmes.map(p => `<option value="${p.id}">${esc(p.name)} (${p.module_count})</option>`).join('');
  } catch { /* leave default */ }

  const applyMapFilters = () => {
    const prog = progSel.value;
    const lvl = document.getElementById('map-level').value;
    if (!prog && !lvl) { setVisibleModules(null); return; }
    const codes = new Set(allModules
      .filter(m => (!prog || (m.programmes || []).includes(prog)) && (!lvl || String(m.level) === lvl))
      .map(m => m.code));
    setVisibleModules(codes);
  };
  progSel.addEventListener('change', applyMapFilters);
  document.getElementById('map-level').addEventListener('change', applyMapFilters);

  // ── Bipartite module picker ───────────────────────────────────────
  const sortedModules = allModules.slice().sort((a, b) => a.code.localeCompare(b.code));
  picker.innerHTML = '<option value="">Choose a module…</option>' +
    sortedModules.map(m => `<option value="${m.code}">${m.code} — ${esc(m.title)}</option>`).join('');
  picker.addEventListener('change', () => { if (picker.value) setSelectedModuleForGraph(picker.value); });

  // ── Concept picker (only concepts that have prerequisites) ─────────
  const conceptInput = document.getElementById('concept-search');
  const conceptList = document.getElementById('concept-options');
  let conceptMap = {};          // term → id
  let conceptLoaded = false;
  let defaultConcept = null;    // most-connected concept (a good starting point)

  async function ensureConceptData() {
    if (conceptLoaded) return;
    conceptLoaded = true;
    let g;
    try { g = await api.conceptPrerequisites(); } catch { return; }
    // Edges are directed prerequisite → dependent: out = things that build on it,
    // in = its own prerequisites.
    const inDeg = {}, outDeg = {};
    for (const e of g.edges || []) {
      outDeg[e.data.source] = (outDeg[e.data.source] || 0) + 1;
      inDeg[e.data.target] = (inDeg[e.data.target] || 0) + 1;
    }
    const nodes = (g.nodes || []).filter(n => !isLikelyFragment(n.data.term || ''));
    // Datalist offers the readable concepts, most-confident first.
    const byConf = nodes.slice().sort((a, b) => (b.data.confidence || 0) - (a.data.confidence || 0));
    conceptMap = {};
    conceptList.innerHTML = byConf.map(n => { conceptMap[n.data.term] = n.data.id; return `<option value="${esc(n.data.term)}"></option>`; }).join('');
    // Best default landing: a BALANCED, moderate concept (has both prerequisites
    // and dependents, modest size) — not a hub that explodes the view.
    const score = (n) => {
      const i = inDeg[n.data.id] || 0, o = outDeg[n.data.id] || 0, tot = i + o;
      if (i > 0 && o > 0 && tot >= 4 && tot <= 12) return 200 + (n.data.confidence || 0);
      if (i > 0 && o > 0) return 100 + (n.data.confidence || 0) - tot * 0.1;
      return (n.data.confidence || 0);
    };
    defaultConcept = nodes.slice().sort((a, b) => score(b) - score(a))[0]?.data.id || null;
  }

  const loadConcept = (id) => { centerConcept = id; showConceptNeighbourhood(id); };
  conceptInput.addEventListener('change', () => {
    const id = conceptMap[conceptInput.value.trim()];
    if (id) loadConcept(id);
  });
  conceptInput.addEventListener('input', () => {        // fires when picking from the datalist
    const id = conceptMap[conceptInput.value.trim()];
    if (id) loadConcept(id);
  });

  // ── View switching + contextual controls ──────────────────────────
  const show = (id, on) => { const el = document.getElementById(id); if (el) el.style.display = on ? '' : 'none'; };
  const setActive = (view) => {
    document.querySelectorAll('.view-btn').forEach(b => b.classList.toggle('active', b.dataset.view === view));
    show('map-filters', view === 'module-module' || view === 'level');
    show('bipartite-picker', view === 'bipartite');
    show('concept-picker', view === 'concept-prereq');
  };

  async function goView(view) {
    setActive(view);
    closeDrawer();
    if (view === 'concept-prereq') {
      await ensureConceptData();
      if (centerConcept) showConceptNeighbourhood(centerConcept);
      else if (defaultConcept) loadConcept(defaultConcept);
      else await switchGraphView(view, null);
    } else {
      await switchGraphView(view, null);
    }
    applyStrengthText(view);
  }

  document.querySelectorAll('.view-btn').forEach(btn =>
    btn.addEventListener('click', () => goView(btn.dataset.view)));

  // Strength slider
  const slider = document.getElementById('edge-threshold');
  const sliderVal = document.getElementById('edge-threshold-val');
  slider.addEventListener('input', () => {
    const v = parseFloat(slider.value);
    sliderVal.textContent = v.toFixed(2);
    applyGraphFilter(v);
  });

  document.getElementById('reset-view').addEventListener('click', () => { rerunLayout(); setTimeout(fitGraph, 60); });
  document.getElementById('drawer-close').addEventListener('click', closeDrawer);
  document.getElementById('mh-close')?.addEventListener('click', () => document.getElementById('map-firsthint')?.remove());

  // ── Deep links ───────────────────────────────────────────────────
  if (params.concept) {
    setActive('concept-prereq');
    ensureConceptData();         // populate the picker in the background
    centerConcept = params.concept;
    await showConceptNeighbourhood(params.concept);
    applyStrengthText('concept-prereq');
  } else if (params.trace) {
    setActive('level');
    await traceModuleChain(params.trace);
    applyStrengthText('level');
  } else if (params.module) {
    setActive('bipartite');
    picker.value = params.module;
    setSelectedModuleForGraph(params.module);
    applyStrengthText('bipartite');
  } else if (params.view && VIEWS.includes(params.view)) {
    await goView(params.view);
  }
}

function esc(str) {
  return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
