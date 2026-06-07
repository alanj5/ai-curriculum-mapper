import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';
import { api } from '../api.js';
import { isLikelyFragment } from '../util/concepts.js';

cytoscape.use(fcose);

// Close the edge-evidence popover on Escape, or when the route changes (so it
// never lingers after navigating to another page). Registered once.
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideEdgeEvidence(); });
window.addEventListener('hashchange', () => hideEdgeEvidence());

const COMMUNITY_COLORS = [
  '#5b8dee', '#7c6af6', '#34d399', '#fbbf24', '#f87171',
  '#60a5fa', '#a78bfa', '#6ee7b7', '#fcd34d', '#fca5a5',
];

// Distinct colours for the level-progression view (indexed by level − 1).
const LEVEL_COLORS = ['#5b8dee', '#7c6af6', '#34d399', '#fbbf24'];

const LAYOUT_OPTS = {
  name: 'fcose',
  randomize: true,
  animate: true,
  animationDuration: 800,
  quality: 'proof',
  // Reserve space for the (now title-based) labels so nodes don't overlap them,
  // and push nodes further apart for a calmer, more legible layout.
  nodeDimensionsIncludeLabels: true,
  nodeRepulsion: 1700000,
  idealEdgeLength: 240,
  nodeSeparation: 320,
  edgeElasticity: 0.35,
  nestingFactor: 0.1,
  gravity: 0.08,
  gravityRange: 4.6,
  numIter: 5000,
  packComponents: true,
  tile: true,
  tilingPaddingVertical: 24,
  tilingPaddingHorizontal: 24,
};

// Word-safe label: prefer the human title, never cut mid-word. Used for graph
// node labels so people see "Robotics" not "IC60019", and full concept terms
// instead of "complexity classes p".
function nodeLabel(text, fallback = '', maxChars = 34) {
  const t = String(text || fallback || '').trim();
  if (t.length <= maxChars) return t;
  const cut = t.slice(0, maxChars);
  const sp = cut.lastIndexOf(' ');
  return (sp > Math.floor(maxChars * 0.45) ? cut.slice(0, sp) : cut).replace(/[\s,;:]+$/, '') + '…';
}

// Build a code→level lookup so prerequisite edges can be oriented from the
// earlier (lower-level) module to the later one, giving the dashed edge a
// meaningful arrow direction (prerequisite → dependent).
function levelByCode(nodes) {
  const m = {};
  for (const n of nodes) m[n.data.id] = n.data.level ?? 99;
  return m;
}
function orientPrereq(d, lv) {
  if (d.type === 'prerequisite' && (lv[d.source] ?? 99) > (lv[d.target] ?? 99)) {
    return { source: d.target, target: d.source };
  }
  return { source: d.source, target: d.target };
}

let _cy = null;
let _edgeThreshold = 0.0;
let _allEdgeData = [];   // original edge list, kept for filter resets
let _currentView = 'module-module';
let _selectedModule = null;
let _onNodeClick = null;
let _onConceptClick = null;   // opens a concept's detail in the map drawer
let _confMin = 0;        // confidence range of the current bipartite concept set
let _confMax = 1;
let _levelPositions = {}; // module-code → {x,y} for the level-progression preset layout
let _pinnedId = null;     // module pinned by click (focus persists on mouse-out)
const _conceptCache = {}; // module-code → concept list (for edge-evidence popover)
let _centerConcept = null;        // concept id at the centre of the concept-prereq view
let _conceptPrereqPositions = {};  // concept id → {x,y} for the concept-prereq preset layout
let _programmeCodes = null;       // Set of module codes to show (programme filter), or null = all
let _showSimilarity = true;       // edge-type toggles (module-module / by-year views)
let _showPrereq = true;

// Toggle whole edge types on/off so a user can see only shared-concept overlaps
// or only prerequisites. Persisted across view switches and re-applied on render.
export function setEdgeTypeVisibility(showSimilarity, showPrereq) {
  _showSimilarity = showSimilarity;
  _showPrereq = showPrereq;
  _applyEdgeTypeVisibility();
}

function _applyEdgeTypeVisibility() {
  if (!_cy) return;
  // Only the module-similarity and by-year views carry typed (similarity /
  // prerequisite) edges; the bipartite and concept-prereq views keep their own.
  const typed = _currentView === 'module-module' || _currentView === 'level';
  _cy.edges().forEach(e => {
    e.removeClass('as-sim as-pre as-both type-hidden');
    if (!typed) return;
    // Similarity and prerequisite are overlapping relationships, not exclusive
    // types: a pair can both share concepts (>=3) AND have a prerequisite
    // direction. Render each edge by which of its relationships are toggled on,
    // so a "both" edge keeps its concept-overlap (solid line) while also showing
    // the prerequisite direction (arrow) — and toggling one off reveals the
    // other rather than hiding the edge.
    const isSim = (e.data('sharedCount') || 0) >= 3 || e.data('type') === 'similarity';
    const isPre = e.data('type') === 'prerequisite';
    const s = isSim && _showSimilarity;
    const p = isPre && _showPrereq;
    if (s && p) e.addClass('as-both');   // concept overlap (solid) + prereq (arrow)
    else if (s) e.addClass('as-sim');    // concept overlap only (solid, no arrow)
    else if (p) e.addClass('as-pre');    // prerequisite only (dashed + arrow)
    else e.addClass('type-hidden');
  });
}

// Programme filter: hide module nodes (and their edges) not in `codes` (a Set);
// null shows everything. Persisted in `_programmeCodes` and re-applied on every
// view (re)render so it survives layout/view switches.
export function setVisibleModules(codes) {
  _programmeCodes = codes && codes.size ? codes : null;
  _applyProgrammeFilter();
}

function _applyProgrammeFilter() {
  if (!_cy) return;
  _cy.nodes().forEach(n => {
    if (n.data('nodeType') === 'concept') return;  // module views only
    n.toggleClass('prog-hidden', !!(_programmeCodes && !_programmeCodes.has(n.id())));
  });
  _cy.edges().forEach(e => {
    const hide = _programmeCodes &&
      (e.source().hasClass('prog-hidden') || e.target().hasClass('prog-hidden'));
    e.toggleClass('prog-hidden', !!hide);
  });
  // Keep the legend in step with what's actually on screen after a programme/year
  // filter: the by-year view re-packs its columns, the module-similarity view
  // re-derives its cluster names and counts from the visible modules only.
  if (_currentView === 'level') _recenterLevelLayout();
  else if (_currentView === 'module-module') _refreshModuleLegend();
}

// Rebuild the "Module clusters" legend from the currently-visible modules so its
// exemplar names and counts reflect the filtered cohort, not the whole corpus.
function _refreshModuleLegend() {
  if (!_cy || _currentView !== 'module-module') return;
  const visible = _cy.nodes()
    .filter(n => n.data('nodeType') !== 'concept' && !n.hasClass('prog-hidden'))
    .map(n => ({ data: n.data() }));
  buildLegend(visible);
}

// Normalise a confidence value to [0,1] over the current concept set so the
// size/colour encoding uses the full visual range even when scores cluster.
function _normConf(c) {
  if (_confMax <= _confMin) return 0.5;
  return Math.max(0, Math.min(1, ((c ?? 0) - _confMin) / (_confMax - _confMin)));
}

// Interpolate dim-grey (low confidence) → accent-blue (high confidence).
function _confColor(c) {
  const t = _normConf(c);
  const a = [71, 85, 105], b = [91, 141, 238];
  const ch = (i) => Math.round(a[i] + (b[i] - a[i]) * t);
  return `rgb(${ch(0)},${ch(1)},${ch(2)})`;
}

export async function initGraph(container, onNodeClick, onConceptClick) {
  _onNodeClick = onNodeClick;
  _onConceptClick = onConceptClick || null;
  _showSimilarity = true;   // fresh mount: both edge types on (matches the legend)
  _showPrereq = true;
  return _loadView(container, 'module-module', null);
}

async function _loadView(container, view, moduleCode) {
  _currentView = view;
  hideEdgeEvidence();   // never carry a click-evidence popover across a view switch
  const hint = document.getElementById('graph-hint');
  const thresholdLabel = document.getElementById('edge-threshold-label');
  const legend = document.getElementById('graph-legend');
  const edgeLegend = document.getElementById('edge-legend');

  let data, elements, style;

  if (view === 'bipartite') {
    if (!moduleCode) {
      if (hint) hint.textContent = 'Choose a module above to see its concepts';
      if (thresholdLabel) thresholdLabel.style.display = 'none';
      if (legend) legend.innerHTML = '';
      if (edgeLegend) edgeLegend.style.display = 'none';
      if (_cy) _cy.destroy();
      _cy = null;
      const cy = document.getElementById('cy');
      if (cy) cy.innerHTML = '<p class="placeholder">Pick a module from the “Choose a module…” dropdown above to see the concepts it teaches.</p>';
      return null;
    }
    data = await api.bipartiteGraph(moduleCode);
    // Confidence range of this module's concepts drives the size/colour scale.
    const confs = data.nodes
      .filter(n => (n.data.type || 'concept') === 'concept')
      .map(n => n.data.confidence ?? 0);
    _confMin = confs.length ? Math.min(...confs) : 0;
    _confMax = confs.length ? Math.max(...confs) : 1;
    elements = buildBipartiteElements(data);
    style = buildBipartiteStyle();
    if (hint) hint.textContent = `Showing concepts for ${moduleCode} — bigger, brighter = higher confidence`;
    if (thresholdLabel) thresholdLabel.style.display = '';
    _calibrateConfidenceSlider();
    if (legend) legend.innerHTML =
      '<div class="lg-title">This module’s concepts</div>' +
      '<div class="legend-item"><div class="legend-dot" style="background:#003e74"></div><span>The module</span></div>' +
      '<div class="legend-item"><div class="legend-dot" style="background:#47556b"></div><span>Lower confidence</span></div>' +
      '<div class="legend-item"><div class="legend-dot" style="background:#1565c0"></div><span>Higher confidence (bigger)</span></div>';
    // Bipartite edges mean "module teaches concept", so the similarity/prerequisite
    // edge legend does not apply here.
    if (edgeLegend) edgeLegend.style.display = 'none';
  } else if (view === 'level') {
    data = await api.moduleModuleGraph({ include_centrality: true, include_communities: true });
    _allEdgeData = data.edges;
    elements = buildLevelElements(data);
    style = buildStyle('level');
    if (hint) hint.textContent = 'Columns are Levels 1→3 left to right — prerequisite edges (dashed) flow forward through the degree. Raise slider to hide weak links.';
    if (thresholdLabel) thresholdLabel.style.display = '';
    _calibrateEdgeSlider(data.edges);
    buildLevelLegend(data.nodes);
    if (edgeLegend) edgeLegend.style.display = '';
  } else if (view === 'concept-prereq') {
    if (!_centerConcept) {
      if (hint) hint.textContent = 'Search a concept above to see what it builds on and what builds on it.';
      if (thresholdLabel) thresholdLabel.style.display = 'none';
      if (legend) legend.innerHTML = '';
      if (edgeLegend) edgeLegend.style.display = 'none';
      if (_cy) _cy.destroy();
      _cy = null;
      const cy = document.getElementById('cy');
      if (cy) cy.innerHTML = '<p class="placeholder">Search for a concept in the box above — for example “dynamic programming”, “recursion” or “machine learning” — to see its prerequisite concepts (what you need first) and the concepts that build on it.</p>';
      return null;
    }
    // Depth 1 keeps the view legible (immediate prerequisites + dependents);
    // clicking a neighbour recentres, so the chain is still fully walkable.
    data = await api.conceptNeighbourhood(_centerConcept, 1);
    if (!data.nodes || data.nodes.length === 0) {
      if (hint) hint.textContent = 'No prerequisite/subsequent concepts were inferred for this concept.';
      if (thresholdLabel) thresholdLabel.style.display = 'none';
      if (legend) legend.innerHTML = '';
      if (edgeLegend) edgeLegend.style.display = 'none';
      if (_cy) _cy.destroy();
      _cy = null;
      const cy = document.getElementById('cy');
      if (cy) cy.innerHTML = '<p class="placeholder">No prerequisite or subsequent concepts were inferred for this concept. Try a more central concept (e.g. from a module\'s top concepts).</p>';
      return null;
    }
    elements = buildConceptPrereqElements(data);
    style = buildConceptPrereqStyle();
    if (hint) hint.textContent = 'Prerequisite concepts (left) → this concept → subsequent concepts (right). Arrows point prerequisite → dependent; click a concept to recentre.';
    if (thresholdLabel) thresholdLabel.style.display = 'none';
    if (legend) legend.innerHTML =
      '<div class="lg-title">Prerequisite flow</div>' +
      '<div class="legend-item"><div class="legend-dot" style="background:#d99a00"></div><span>Prerequisite (need first)</span></div>' +
      '<div class="legend-item"><div class="legend-dot" style="background:#003e74"></div><span>This concept</span></div>' +
      '<div class="legend-item"><div class="legend-dot" style="background:#157f3d"></div><span>Builds on it (subsequent)</span></div>';
    if (edgeLegend) edgeLegend.style.display = 'none';
  } else {
    data = await api.moduleModuleGraph({ include_centrality: true, include_communities: true });
    _allEdgeData = data.edges;
    elements = buildElements(data);
    style = buildStyle();
    if (hint) hint.textContent = 'Raise slider to hide weak connections and reveal clusters';
    if (thresholdLabel) thresholdLabel.style.display = '';
    _calibrateEdgeSlider(data.edges);
    buildLegend(data.nodes);
    if (edgeLegend) edgeLegend.style.display = '';
  }

  if (_cy) _cy.destroy();
  // Clear any placeholder text in the container before Cytoscape takes over,
  // otherwise the "Select a module…" hint can remain visible behind the canvas.
  const cyEl = container || document.getElementById('cy');
  if (cyEl) cyEl.innerHTML = '';
  const layout = (view === 'level' || view === 'concept-prereq')
    ? { name: 'preset', positions: view === 'level' ? _levelPositions : _conceptPrereqPositions, fit: true, padding: 50, animate: false }
    : { ...LAYOUT_OPTS, randomize: true };
  _cy = cytoscape({
    container: cyEl,
    elements,
    style,
    layout,
    wheelSensitivity: 0.3,
    minZoom: 0.2,
    maxZoom: 4,
  });

  _setupTooltip();
  if (_onNodeClick) _setupInteractions(_onNodeClick);
  _applyProgrammeFilter();      // re-apply any active programme filter to the new view
  _applyEdgeTypeVisibility();   // re-apply any active edge-type toggles
  return _cy;
}

export async function switchGraphView(view, moduleCode) {
  _currentView = view;
  _selectedModule = moduleCode || _selectedModule;
  const container = document.getElementById('cy');
  return _loadView(container, view, view === 'bipartite' ? (_selectedModule || moduleCode) : null);
}

export function setSelectedModuleForGraph(moduleCode) {
  _selectedModule = moduleCode;
  if (_currentView === 'bipartite') {
    const container = document.getElementById('cy');
    _loadView(container, 'bipartite', moduleCode);
  }
}

// One-click prerequisite-chain trace (interim §2.7.2): highlight a module's full
// transitive prerequisite chain (upstream) and dependents (downstream) in the
// graph, fading everything else. Uses the level view so prerequisite edges show.
export async function traceModuleChain(code) {
  if (_currentView !== 'level' && _currentView !== 'module-module') {
    await switchGraphView('level', null);
  }
  if (!_cy) return;
  let trace;
  try { trace = await api.traceModule(code); } catch { return; }
  const upstream = new Set(trace.upstream || []);
  const downstream = new Set(trace.downstream || []);
  const chain = new Set([trace.center, ...upstream, ...downstream]);
  _pinnedId = null;
  _cy.batch(() => {
    _cy.nodes().removeClass('selected dimmed');
    _cy.edges().removeClass('highlighted dimmed');
    _cy.nodes().forEach(n => n.addClass(chain.has(n.id()) ? 'selected' : 'dimmed'));
    _cy.edges().forEach(e => {
      const inChain = chain.has(e.source().id()) && chain.has(e.target().id());
      e.addClass(inChain ? 'highlighted' : 'dimmed');
    });
  });
  const sel = _cy.nodes('.selected');
  if (sel.length) _cy.fit(sel, 60);
  const hint = document.getElementById('graph-hint');
  if (hint) hint.textContent = `Prerequisite chain for ${code}: ${upstream.size} upstream (need first), ${downstream.size} downstream (build on it), depth ${trace.chain_depth}.`;
}

// Open the directed concept-prerequisite neighbourhood centred on a concept —
// the interim §3.2.4 "click a concept to reveal its neighbourhood of
// prerequisite/subsequent concepts".
export function showConceptNeighbourhood(conceptId) {
  _centerConcept = conceptId;
  _currentView = 'concept-prereq';
  const sel = document.getElementById('graph-view-select');
  if (sel) sel.value = 'concept-prereq';
  const container = document.getElementById('cy');
  return _loadView(container, 'concept-prereq', null);
}

// ── Public controls ──────────────────────────────────────────────

export function fitGraph() {
  if (_cy) _cy.fit(undefined, 30);
}

export function rerunLayout() {
  if (!_cy) return;
  if (_currentView === 'level') {
    // Restore the fixed level columns rather than re-running force-directed layout.
    _cy.layout({ name: 'preset', positions: _levelPositions, fit: true, padding: 50, animate: true, animationDuration: 400 }).run();
    return;
  }
  _cy.layout({ ...LAYOUT_OPTS, animate: true, animationDuration: 600 }).run();
}

export function applyEdgeFilter(threshold, relayout = true) {
  if (!_cy) return;
  _edgeThreshold = threshold;

  _cy.edges().forEach(edge => {
    const sim = edge.data('displaySim');
    const hide = sim !== null && sim < threshold;
    if (hide) {
      edge.addClass('filtered');
    } else {
      edge.removeClass('filtered');
    }
  });

  // The level view uses a fixed preset layout, so only hide edges there.
  if (!relayout) return;

  // Re-run a quick layout using only visible edges so clusters tighten
  const visibleElements = _cy.elements().not('.filtered');
  visibleElements.layout({
    ...LAYOUT_OPTS,
    randomize: false,
    animate: true,
    animationDuration: 500,
    numIter: 800,
  }).run();
}

// Focus a module's neighbourhood: dim everything else and highlight its incident
// edges. `pinned` adds the white selection ring (click); hover-focus omits it.
function _applyFocus(id, pinned) {
  if (!_cy) return;
  _cy.nodes().removeClass('selected dimmed');
  _cy.edges().removeClass('highlighted dimmed');
  if (!id) return;
  const node = _cy.getElementById(id);
  if (node.length === 0) return;
  if (pinned) node.addClass('selected');

  const neighborNodes = node.neighborhood('node');
  const incidentEdges = node.connectedEdges();
  _cy.nodes().not(node).not(neighborNodes).addClass('dimmed');
  _cy.edges().not(incidentEdges).addClass('dimmed');
  incidentEdges.not('.filtered').addClass('highlighted');
}

export function highlightNode(moduleCode) {
  _pinnedId = moduleCode || null;
  _applyFocus(moduleCode, true);
}

// ── Internal ─────────────────────────────────────────────────────

// Set the edge-strength slider range to the actual data so it is not mostly
// dead space: module-module similarities are Jaccard values that rarely exceed
// ~0.1, whereas the default slider ran to 0.9.
function _calibrateEdgeSlider(edges) {
  const slider = document.getElementById('edge-threshold');
  const valLabel = document.getElementById('edge-threshold-val');
  const text = document.getElementById('edge-threshold-text');
  if (!slider) return;
  if (text) text.textContent = 'Min edge strength';
  const sims = (edges || [])
    .map(e => (e.data.type === 'prerequisite' ? (e.data.similarity ?? 0) : (e.data.weight ?? 0)))
    .filter(s => s != null);
  const maxSim = sims.length ? Math.max(...sims) : 0.1;
  // Round the ceiling up to a tidy step; keep a sensible minimum span.
  const ceil = Math.max(0.05, Math.ceil(maxSim * 20) / 20);
  slider.max = String(ceil);
  slider.step = String(Math.max(0.005, +(ceil / 20).toFixed(3)));
  slider.value = '0';
  if (valLabel) valLabel.textContent = '0.00';
  _edgeThreshold = 0;
}

// Calibrate the shared slider to act as a min-confidence filter in the
// bipartite (module ↔ concepts) view, spanning the concept confidence range.
function _calibrateConfidenceSlider() {
  const slider = document.getElementById('edge-threshold');
  const valLabel = document.getElementById('edge-threshold-val');
  const text = document.getElementById('edge-threshold-text');
  if (!slider) return;
  if (text) text.textContent = 'Min concept confidence';
  const ceil = Math.max(0.1, Math.ceil(_confMax * 20) / 20);
  slider.max = String(ceil);
  slider.step = '0.01';
  slider.value = '0';
  if (valLabel) valLabel.textContent = '0.00';
}

// View-aware slider handler: edge-strength filter in module-similarity view,
// concept-confidence filter in the bipartite view.
export function applyGraphFilter(threshold) {
  if (_currentView === 'bipartite') _applyConfidenceFilter(threshold);
  else applyEdgeFilter(threshold, _currentView !== 'level');
}

function _applyConfidenceFilter(threshold) {
  if (!_cy) return;
  _cy.nodes('[nodeType = "concept"]').forEach(node => {
    if ((node.data('confidence') ?? 0) < threshold) node.addClass('filtered');
    else node.removeClass('filtered');
  });
  // Hide edges whose concept endpoint is filtered out. Positions are left
  // stable (no re-layout) so the user can see which concepts drop away.
  _cy.edges().forEach(edge => {
    if (edge.target().hasClass('filtered') || edge.source().hasClass('filtered')) {
      edge.addClass('filtered');
    } else {
      edge.removeClass('filtered');
    }
  });
}

function _setupInteractions(onNodeClick) {
  _cy.on('tap', 'node', (evt) => {
    const node = evt.target;
    // In the concept-prerequisite view, clicking a concept recentres on it AND
    // opens its detail in the drawer (the same view Explore shows).
    if (_currentView === 'concept-prereq') {
      if (_onConceptClick) _onConceptClick(node.data('id'));
      showConceptNeighbourhood(node.data('id'));
      return;
    }
    // Concept nodes (bipartite view) are not modules — don't fire a
    // /modules/<concept-uuid> request (404); instead open the concept detail.
    if (node.data('nodeType') === 'concept') {
      if (_onConceptClick) _onConceptClick(node.data('id'));
      return;
    }
    _pinnedId = node.data('id');
    _applyFocus(_pinnedId, true);
    onNodeClick(node.data('id'));
  });

  // Hover-to-focus: spotlight a module's neighbourhood (dim the rest) as the
  // pointer moves, so a dense graph stays readable without committing a click.
  _cy.on('mouseover', 'node', (evt) => {
    const node = evt.target;
    if (node.data('nodeType') === 'concept') return;
    if (_pinnedId === node.data('id')) return;
    _applyFocus(node.data('id'), false);
  });
  _cy.on('mouseout', 'node', (evt) => {
    if (evt.target.data('nodeType') === 'concept') return;
    _applyFocus(_pinnedId, true);   // restore the pinned focus, or clear if none
  });

  // Click a module-module / level edge to reveal the concepts the two modules
  // share — the evidence behind the similarity (or prerequisite) link
  // (interim §2.7.2: "clicking an edge could display supporting evidence").
  _cy.on('tap', 'edge', (evt) => {
    if (_currentView === 'bipartite') return;  // bipartite edges are module→concept
    const d = evt.target.data();
    const src = _cy.getElementById(d.source).data('code') || _cy.getElementById(d.source).data('label') || d.source;
    const tgt = _cy.getElementById(d.target).data('code') || _cy.getElementById(d.target).data('label') || d.target;
    const e = evt.originalEvent;
    showEdgeEvidence(src, tgt, d.type, e ? e.clientX : 200, e ? e.clientY : 200);
  });

  _cy.on('tap', (evt) => {
    if (evt.target === _cy) {
      _pinnedId = null;
      _applyFocus(null);
      onNodeClick(null);
      hideEdgeEvidence();
    }
  });
}

async function _moduleConcepts(code) {
  if (!_conceptCache[code]) _conceptCache[code] = await api.moduleConcepts(code);
  return _conceptCache[code];
}

function hideEdgeEvidence() {
  document.getElementById('edge-evidence')?.classList.add('hidden');
}

// Show the concepts shared by two modules in a small pinned popover near the
// click. Shared concepts are canonical, so a concept of module A whose
// module_codes also include B is taught by both.
async function showEdgeEvidence(srcCode, tgtCode, type, clientX, clientY) {
  const panel = document.getElementById('edge-evidence');
  if (!panel) return;
  const rel = type === 'prerequisite' ? 'prerequisite link' : 'concept overlap';
  panel.classList.remove('hidden');
  panel.innerHTML = `<div class="ee-head"><span class="ee-title">${srcCode} ↔ ${tgtCode}</span>
    <button class="ee-close" title="Close">✕</button></div><p class="ee-empty">Loading shared concepts…</p>`;
  _placePopover(panel, clientX, clientY);
  panel.querySelector('.ee-close').addEventListener('click', hideEdgeEvidence);

  let shared = [];
  try {
    const concepts = await _moduleConcepts(srcCode);
    shared = concepts
      .filter(c => (c.module_codes || []).includes(tgtCode))
      .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0));
  } catch {
    panel.querySelector('.ee-empty')?.replaceChildren(document.createTextNode('Could not load concepts.'));
    return;
  }

  const body = shared.length
    ? `<div class="ee-chips">${shared.slice(0, 30)
        .map(c => `<span class="ee-chip">${_esc(c.term)}</span>`).join('')}</div>`
    : '<p class="ee-empty">No directly shared concepts — this link reflects a prerequisite or weak overlap.</p>';
  panel.innerHTML = `<div class="ee-head">
      <span class="ee-title">${_esc(srcCode)} ↔ ${_esc(tgtCode)}</span>
      <button class="ee-close" title="Close">✕</button></div>
    <p class="ee-meta" style="font-size:11px;color:#94a3b8;margin-bottom:6px">${shared.length} shared concept${shared.length === 1 ? '' : 's'} · ${rel}</p>
    ${body}`;
  panel.querySelector('.ee-close').addEventListener('click', hideEdgeEvidence);
  _placePopover(panel, clientX, clientY);
}

function _placePopover(panel, x, y) {
  const pad = 14;
  const w = panel.offsetWidth || 280, h = panel.offsetHeight || 120;
  let left = x + pad, top = y + pad;
  if (left + w > window.innerWidth - 8) left = x - w - pad;
  if (top + h > window.innerHeight - 8) top = Math.max(8, y - h - pad);
  panel.style.left = `${left}px`;
  panel.style.top = `${top}px`;
}

function _esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function _setupTooltip() {
  const tooltip = document.getElementById('graph-tooltip');
  if (!tooltip || !_cy) return;

  _cy.on('mouseover', 'node', (evt) => {
    const d = evt.target.data();
    if (d.nodeType === 'concept') {
      // Concept node: show the term and extraction confidence, not module fields.
      const conf = d.confidence != null ? `${(d.confidence * 100).toFixed(0)}%` : '—';
      tooltip.innerHTML = `
        <div class="tt-title">${d.title || d.label || 'concept'}</div>
        <div class="tt-meta">Extracted concept · confidence ${conf}</div>
      `;
    } else {
      tooltip.innerHTML = `
        <div class="tt-code">${d.id}</div>
        <div class="tt-title">${d.title || ''}</div>
        <div class="tt-meta">Level ${d.level ?? '?'}${d.credits != null ? ` · ${d.credits} credits` : ''}</div>
        ${d.topConcepts && d.topConcepts.length
          ? `<div class="tt-concepts"><strong>Top concepts:</strong> ${d.topConcepts.join(', ')}</div>`
          : ''}
      `;
    }
    tooltip.classList.remove('hidden');
    _positionTooltip(evt.originalEvent, tooltip);
  });

  _cy.on('mousemove', 'node', (evt) => {
    _positionTooltip(evt.originalEvent, tooltip);
  });

  _cy.on('mouseout', 'node', () => {
    tooltip.classList.add('hidden');
  });

  _cy.on('mouseover', 'edge', (evt) => {
    const d = evt.target.data();
    // Resolve endpoint labels (module code or concept term) so we never show
    // raw concept UUIDs in the bipartite view.
    const srcLabel = _cy.getElementById(d.source).data('code') || _cy.getElementById(d.source).data('label') || d.source;
    const tgtLabel = _cy.getElementById(d.target).data('code') || _cy.getElementById(d.target).data('label') || d.target;
    if (_currentView === 'bipartite') {
      tooltip.innerHTML = `
        <div class="tt-meta"><strong>${srcLabel}</strong> teaches</div>
        <div class="tt-title">${tgtLabel}</div>
      `;
    } else {
      const isPre = d.type === 'prerequisite';
      const simLine = d.displaySim != null
        ? `<div class="tt-meta">Concept overlap: <strong>${d.displaySim.toFixed(3)}</strong>${d.sharedCount ? ` (${d.sharedCount} shared)` : ''}</div>`
        : '';
      tooltip.innerHTML = `
        <div class="tt-meta">${srcLabel} ↔ ${tgtLabel}</div>
        <div class="tt-meta">${isPre ? '🔗 Prerequisite' : '~ Similarity'}</div>
        ${simLine}
      `;
    }
    tooltip.classList.remove('hidden');
    _positionTooltip(evt.originalEvent, tooltip);
  });

  _cy.on('mousemove', 'edge', (evt) => {
    _positionTooltip(evt.originalEvent, tooltip);
  });

  _cy.on('mouseout', 'edge', () => {
    tooltip.classList.add('hidden');
  });
}

function _positionTooltip(mouseEvent, tooltip) {
  const pad = 14;
  const tw = tooltip.offsetWidth || 220;
  const th = tooltip.offsetHeight || 80;
  let x = mouseEvent.clientX + pad;
  let y = mouseEvent.clientY + pad;
  if (x + tw > window.innerWidth - 8) x = mouseEvent.clientX - tw - pad;
  if (y + th > window.innerHeight - 8) y = mouseEvent.clientY - th - pad;
  tooltip.style.left = `${x}px`;
  tooltip.style.top  = `${y}px`;
}

function buildBipartiteElements(data) {
  // Hide obvious ILO-fragment "concepts" (shared heuristic, see util/concepts.js)
  // so the star graph stays readable; keep the module node and all clean
  // concepts. Never blank the view: if everything looks like a fragment, keep
  // the original set.
  const moduleNode = data.nodes.find(n => n.data.type === 'module');
  let conceptNodes = data.nodes.filter(n => (n.data.type || 'concept') === 'concept');
  const cleaned = conceptNodes.filter(n => !isLikelyFragment(n.data.term || ''));
  if (cleaned.length) conceptNodes = cleaned;
  const keep = new Set([
    ...(moduleNode ? [moduleNode.data.id] : []),
    ...conceptNodes.map(n => n.data.id),
  ]);

  const nodes = [...(moduleNode ? [moduleNode] : []), ...conceptNodes].map(n => ({
    data: {
      id: n.data.id,
      code: n.data.type === 'module' ? n.data.id : undefined,
      label: n.data.type === 'module'
        ? (n.data.title ? `${n.data.id} — ${n.data.title}` : n.data.id)
        : nodeLabel(n.data.term || n.data.id, '', 30),
      nodeType: n.data.type || 'concept',
      title: n.data.title || n.data.term || '',
      level: n.data.level ?? null,
      confidence: n.data.confidence ?? null,
    },
  }));
  const edges = data.edges
    .filter(e => keep.has(e.data.source) && keep.has(e.data.target))
    .map((e, i) => ({
      data: {
        id: `e${i}`,
        source: e.data.source,
        target: e.data.target,
        weight: e.data.weight ?? 1,
      },
    }));
  return [...nodes, ...edges];
}

function buildBipartiteStyle() {
  return [
    {
      selector: 'node[nodeType = "module"]',
      style: {
        'background-color': '#003e74',
        'width': 56, 'height': 56,
        'label': 'data(label)',
        'font-size': '15px', 'font-weight': 700,
        'color': '#1b2430',
        'text-valign': 'bottom', 'text-halign': 'center', 'text-margin-y': 6,
        'text-wrap': 'wrap', 'text-max-width': '160px',
        'text-outline-color': '#ffffff', 'text-outline-width': 3,
        'cursor': 'pointer',
        'z-index': 10,
      },
    },
    {
      selector: 'node[nodeType = "concept"]',
      style: {
        // Size and colour both encode extraction confidence (bigger/brighter = higher).
        'background-color': (ele) => _confColor(ele.data('confidence')),
        'border-width': 1, 'border-color': '#94a3b8',
        'width': (ele) => 12 + _normConf(ele.data('confidence')) * 28,
        'height': (ele) => 12 + _normConf(ele.data('confidence')) * 28,
        'label': 'data(label)',
        'font-size': '11px', 'font-weight': 600,
        'color': '#1b2430',
        'text-valign': 'bottom', 'text-halign': 'center',
        'text-margin-y': 4,
        'text-wrap': 'wrap', 'text-max-width': '100px',
        'text-outline-color': '#ffffff', 'text-outline-width': 2,
        'cursor': 'default',
      },
    },
    {
      selector: 'edge',
      style: {
        'line-color': '#94a3b8',
        'width': (ele) => 1 + (ele.data('weight') ?? 0) * 1.8,
        'opacity': 0.8,
        'curve-style': 'haystack',
      },
    },
    {
      selector: '.filtered',
      style: { 'display': 'none' },
    },
  ];
}

function buildElements(data) {
  // Fetch module title/level/credits from the node metadata if present
  const nodes = data.nodes.map(n => ({
    data: {
      id: n.data.id,
      code: n.data.id,
      label: n.data.title || n.data.id,   // full module name (not truncated)
      community: n.data.community ?? 0,
      degree: n.data.degree ?? 0,
      title: n.data.title ?? '',
      level: n.data.level ?? null,
      credits: n.data.credits ?? null,
      topConcepts: n.data.top_concepts ?? [],
    },
  }));

  const lv = levelByCode(data.nodes);
  const edges = data.edges.map(e => {
    const d = e.data;
    // prerequisite edges have weight=1.0 (not a similarity score);
    // use the 'similarity' attribute (Jaccard) if present, else null.
    // similarity edges have weight = Jaccard directly.
    const displaySim = d.type === 'prerequisite'
      ? (d.similarity ?? null)
      : (d.weight ?? 0);
    const { source, target } = orientPrereq(d, lv);   // arrow points prerequisite → dependent
    return {
      data: {
        id: d.id,
        source,
        target,
        weight: d.weight ?? 0,
        displaySim,
        type: d.type ?? 'similarity',
        sharedCount: d.shared_count ?? 0,
      },
    };
  });

  return [...nodes, ...edges];
}

// Build module nodes laid out in columns by level (year), so the graph reads as
// a left-to-right progression through the degree. Edges are unchanged from the
// module-module view; positions are stored in _levelPositions for the preset layout.
function buildLevelElements(data) {
  const byLevel = new Map();
  for (const n of data.nodes) {
    const lvl = n.data.level ?? 0;
    if (!byLevel.has(lvl)) byLevel.set(lvl, []);
    byLevel.get(lvl).push(n);
  }
  const levels = [...byLevel.keys()].sort((a, b) => a - b);
  // Wide columns (clear Level 1→3 separation) but compact rows so all modules
  // fit on screen without shrinking labels to illegibility.
  const COL_W = 480, ROW_H = 66;
  _levelPositions = {};
  levels.forEach((lvl, ci) => {
    const group = byLevel.get(lvl).sort((a, b) => String(a.data.id).localeCompare(String(b.data.id)));
    group.forEach((node, ri) => {
      _levelPositions[node.data.id] = { x: ci * COL_W, y: (ri - (group.length - 1) / 2) * ROW_H };
    });
  });

  const nodes = data.nodes.map(n => ({
    data: {
      id: n.data.id,
      code: n.data.id,
      label: `${n.data.id} · ${nodeLabel(n.data.title, n.data.id, 30)}`,
      level: n.data.level ?? null,
      degree: n.data.degree ?? 0,
      title: n.data.title ?? '',
      credits: n.data.credits ?? null,
      topConcepts: n.data.top_concepts ?? [],
    },
  }));

  const lv = levelByCode(data.nodes);
  const edges = data.edges.map(e => {
    const d = e.data;
    const displaySim = d.type === 'prerequisite' ? (d.similarity ?? null) : (d.weight ?? 0);
    const { source, target } = orientPrereq(d, lv);
    return {
      data: {
        id: d.id,
        source,
        target,
        weight: d.weight ?? 0,
        displaySim,
        type: d.type ?? 'similarity',
        sharedCount: d.shared_count ?? 0,
      },
    };
  });

  return [...nodes, ...edges];
}

// Lay the concept neighbourhood out left→right by signed distance from the
// centre: prerequisites on the left, the concept in the middle, subsequents on
// the right (a preset layout, like the level view).
function buildConceptPrereqElements(data) {
  const COL_W = 300, ROW_H = 64;
  const MAX_PER_SIDE = 14;   // cap each column so a hub concept stays legible
  // Keep the centre, then the most-confident prerequisites and dependents only.
  const byConf = (a, b) => (b.data.confidence ?? 0) - (a.data.confidence ?? 0);
  const self = data.nodes.filter(n => (n.data.direction || 'subsequent') === 'self');
  const pre = data.nodes.filter(n => n.data.direction === 'prerequisite').sort(byConf).slice(0, MAX_PER_SIDE);
  const sub = data.nodes.filter(n => n.data.direction !== 'self' && n.data.direction !== 'prerequisite').sort(byConf).slice(0, MAX_PER_SIDE);
  const kept = [...self, ...pre, ...sub];
  const keep = new Set(kept.map(n => n.data.id));

  const byCol = new Map();
  const nodes = kept.map(n => {
    const dir = n.data.direction || 'subsequent';
    const dist = n.data.dist ?? 1;
    const col = dir === 'self' ? 0 : (dir === 'prerequisite' ? -dist : dist);
    if (!byCol.has(col)) byCol.set(col, []);
    byCol.get(col).push(n.data.id);
    return {
      data: {
        id: n.data.id,
        label: nodeLabel(n.data.term || n.data.id, '', 30),
        term: n.data.term || '',
        nodeType: 'concept',
        direction: dir,
        confidence: n.data.confidence ?? null,
      },
    };
  });
  _conceptPrereqPositions = {};
  for (const [col, ids] of byCol.entries()) {
    ids.forEach((id, i) => {
      _conceptPrereqPositions[id] = { x: col * COL_W, y: (i - (ids.length - 1) / 2) * ROW_H };
    });
  }
  const edges = data.edges
    .filter(e => keep.has(e.data.source) && keep.has(e.data.target))
    .map((e, i) => ({
      data: {
        id: e.data.id || `cp${i}`,
        source: e.data.source,
        target: e.data.target,
        method: e.data.method || '',
        weight: e.data.weight ?? 0.5,
      },
    }));
  return [...nodes, ...edges];
}

function buildConceptPrereqStyle() {
  const colour = (ele) => {
    const d = ele.data('direction');
    return d === 'self' ? '#003e74' : d === 'prerequisite' ? '#d99a00' : '#157f3d';
  };
  return [
    {
      selector: 'node',
      style: {
        'background-color': colour,
        'width': (ele) => (ele.data('direction') === 'self' ? 34 : 22),
        'height': (ele) => (ele.data('direction') === 'self' ? 34 : 22),
        'label': 'data(label)',
        'font-size': '11px', 'font-weight': 600,
        'color': '#1b2430',
        'text-valign': 'bottom', 'text-halign': 'center', 'text-margin-y': 4,
        'text-wrap': 'wrap', 'text-max-width': '110px',
        'text-outline-color': '#ffffff', 'text-outline-width': 2,
        'cursor': 'pointer',
      },
    },
    {
      selector: 'node[direction = "self"]',
      style: { 'border-width': 3, 'border-color': '#003e74', 'font-size': '12.5px', 'z-index': 10 },
    },
    {
      selector: 'edge',
      style: {
        'line-color': '#9a7fd8',
        'width': (ele) => 1 + (ele.data('weight') ?? 0.5) * 2.5,
        'opacity': 0.85,
        'curve-style': 'bezier',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': '#6941c6',
        'arrow-scale': 1,
      },
    },
    { selector: '.filtered', style: { 'display': 'none' } },
  ];
}

function buildStyle(colorBy = 'community') {
  const isLevel = colorBy === 'level';
  const nodeColor = isLevel
    ? (ele) => LEVEL_COLORS[(((ele.data('level') ?? 1) - 1) % LEVEL_COLORS.length + LEVEL_COLORS.length) % LEVEL_COLORS.length]
    : (ele) => COMMUNITY_COLORS[ele.data('community') % COMMUNITY_COLORS.length];

  // Level view uses fixed, readable nodes (the columns are dense); module
  // similarity sizes by degree centrality so hubs stand out. The multiplier is
  // large because degree-centrality values are small on the sparser real-corpus
  // graph — without it every node would look the same size.
  const nodeSize = isLevel ? 30 : (ele) => 16 + (ele.data('degree') || 0) * 110;

  // Resting edge opacity. Module similarity: scale by Jaccard so strong links
  // stay visible while the weak long tail recedes — a calmer default hairball
  // that the hover-focus then makes fully legible. Level view: similarity edges
  // are kept but faded right back so the prerequisite progression dominates.
  const simOpacity = isLevel
    ? 0.32
    : (ele) => { const s = ele.data('displaySim'); return s != null ? Math.min(0.75, 0.48 + s * 3) : 0.48; };

  return [
    {
      selector: 'node',
      style: {
        'background-color': nodeColor,
        'width': nodeSize,
        'height': nodeSize,
        'label': 'data(label)',
        // Readable floor (14px) that grows a little with the node's degree, so
        // hub labels are larger but every label stays legible.
        'font-size': isLevel ? '12px' : (ele) => 14 + (ele.data('degree') || 0) * 26,
        'font-weight': 600,
        'color': '#1b2430',
        'text-valign': isLevel ? 'center' : 'bottom',
        'text-halign': isLevel ? 'right' : 'center',
        'text-margin-x': isLevel ? 8 : 0,
        'text-margin-y': isLevel ? 0 : 5,
        'text-wrap': 'wrap',
        'text-max-width': isLevel ? '200px' : '150px',
        'text-outline-color': '#ffffff',
        'text-outline-width': 3,
        'border-width': 1.5,
        'border-color': 'rgba(27,36,48,.18)',
        'cursor': 'pointer',
        'transition-property': 'opacity border-width width height',
        'transition-duration': '0.15s',
      },
    },
    {
      selector: 'node.selected',
      style: {
        'border-width': 3,
        'border-color': '#003e74',
        'z-index': 999,
      },
    },
    {
      selector: 'node.dimmed',
      style: { 'opacity': 0.18 },
    },
    {
      selector: 'edge',
      style: {
        'line-color': '#8593a6',
        'width': (ele) => {
          const s = ele.data('displaySim');
          return s != null ? 1.1 + s * 4 : 1.4;
        },
        'opacity': simOpacity,
        'curve-style': 'bezier',
        'transition-property': 'opacity line-color width',
        'transition-duration': '0.12s',
      },
    },
    {
      // Prerequisite WITHOUT much concept overlap: a dashed directed link.
      selector: 'edge.as-pre',
      style: {
        'line-style': 'dashed',
        'line-dash-pattern': [6, 4],
        'line-color': '#6941c6',
        'opacity': isLevel ? 0.85 : 0.65,
        'width': isLevel ? 2.4 : 1.8,
        // Arrow points from the earlier (prerequisite) module to the later one.
        'target-arrow-shape': 'triangle',
        'target-arrow-color': '#6941c6',
        'arrow-scale': 1.1,
        'curve-style': 'bezier',
      },
    },
    {
      // BOTH relationships: the modules share concepts (solid line, inherited
      // from the base edge style) AND one precedes the other (arrow). Keeping
      // the line solid stops genuine concept overlap from being hidden behind
      // the prerequisite — the case that made BEng look prerequisite-heavy.
      selector: 'edge.as-both',
      style: {
        'target-arrow-shape': 'triangle',
        'target-arrow-color': '#6941c6',
        'arrow-scale': 1.1,
        'opacity': isLevel ? 0.7 : 0.62,
        'curve-style': 'bezier',
      },
    },
    {
      selector: 'edge.highlighted',
      style: {
        'line-color': '#003e74',
        'opacity': 0.95,
        'width': (ele) => {
          const s = ele.data('displaySim');
          return s != null ? 2 + s * 5 : 2.8;
        },
        'z-index': 100,
      },
    },
    {
      selector: 'edge.dimmed',
      style: { 'opacity': 0.03 },
    },
    {
      selector: 'edge.filtered',
      style: { 'display': 'none' },
    },
    {
      selector: 'edge.type-hidden',
      style: { 'display': 'none' },
    },
    {
      selector: '.prog-hidden',
      style: { 'display': 'none' },
    },
  ];
}

// Colour = a thematic cluster of related modules (Louvain community). Name each
// by its most-connected module so the colours mean something at a glance.
function buildLegend(nodes) {
  const legendEl = document.getElementById('graph-legend');
  if (!legendEl) return;

  const byComm = new Map();
  for (const n of nodes) {
    const c = n.data.community ?? 0;
    if (!byComm.has(c)) byComm.set(c, []);
    byComm.get(c).push(n.data);
  }

  const rows = [...byComm.entries()]
    .sort(([a], [b]) => a - b)
    .map(([c, list]) => {
      const color = COMMUNITY_COLORS[c % COMMUNITY_COLORS.length];
      // Name each cluster by its single most-connected module (its exemplar) plus
      // a count — compact enough to read at a glance without dominating the canvas.
      const top = list.slice().sort((a, b) => (b.degree ?? 0) - (a.degree ?? 0))[0];
      const name = nodeLabel(top?.title || top?.id || '', '', 30);
      return `<div class="legend-item">
        <div class="legend-dot" style="background:${color}"></div>
        <span>${_esc(name)} <span style="color:var(--muted)">· ${list.length}</span></span>
      </div>`;
    })
    .join('');
  legendEl.innerHTML = `<div class="lg-title">Module clusters <span style="font-weight:400;text-transform:none;letter-spacing:0">— shared-concept groups</span></div>${rows}`;
}

function buildLevelLegend(nodes) {
  const counts = new Map();
  for (const n of nodes) {
    const l = n.data.level ?? 0;
    counts.set(l, (counts.get(l) || 0) + 1);
  }
  _renderLevelLegend(counts);
}

// Render the year/level legend from a level→count map. Only the levels actually
// present are shown, so it tracks the programme/year filter (fix: BEng shows
// Levels 1–3, MEng adds Level 4).
function _renderLevelLegend(counts) {
  const legendEl = document.getElementById('graph-legend');
  if (!legendEl) return;
  const rows = [...counts.entries()]
    .filter(([, n]) => n > 0)
    .sort(([a], [b]) => a - b)
    .map(([l, n]) => {
      const color = LEVEL_COLORS[(l - 1 + LEVEL_COLORS.length) % LEVEL_COLORS.length];
      return `<div class="legend-item">
        <div class="legend-dot" style="background:${color}"></div>
        <span>Level ${l} <strong>(${n})</strong></span>
      </div>`;
    })
    .join('');
  legendEl.innerHTML = `<div class="lg-title">Year / level</div>${rows}`;
}

// Re-pack the level columns using only the currently-visible modules, so each
// column stays vertically centred (and the legend counts match) after a
// programme/year filter hides part of the cohort.
function _recenterLevelLayout() {
  if (!_cy || _currentView !== 'level') return;
  const COL_W = 480, ROW_H = 66;
  const visible = _cy.nodes().filter(n => n.data('nodeType') !== 'concept' && !n.hasClass('prog-hidden'));
  const byLevel = new Map();
  visible.forEach(n => {
    const lvl = n.data('level') ?? 0;
    if (!byLevel.has(lvl)) byLevel.set(lvl, []);
    byLevel.get(lvl).push(n);
  });
  const levels = [...byLevel.keys()].sort((a, b) => a - b);
  const positions = {};
  levels.forEach((lvl, ci) => {
    const group = byLevel.get(lvl).sort((a, b) => String(a.id()).localeCompare(String(b.id())));
    group.forEach((node, ri) => {
      positions[node.id()] = { x: ci * COL_W, y: (ri - (group.length - 1) / 2) * ROW_H };
    });
  });
  _levelPositions = positions;   // so "Re-arrange & fit" keeps the filtered layout
  _cy.layout({ name: 'preset', positions, fit: true, padding: 50, animate: true, animationDuration: 350 }).run();
  _renderLevelLegend(new Map(levels.map(l => [l, byLevel.get(l).length])));
}
