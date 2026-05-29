import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';
import { api } from '../api.js';

cytoscape.use(fcose);

const COMMUNITY_COLORS = [
  '#5b8dee', '#7c6af6', '#34d399', '#fbbf24', '#f87171',
  '#60a5fa', '#a78bfa', '#6ee7b7', '#fcd34d', '#fca5a5',
];

const LAYOUT_OPTS = {
  name: 'fcose',
  randomize: true,
  animate: true,
  animationDuration: 800,
  quality: 'proof',
  nodeRepulsion: 600000,
  idealEdgeLength: 120,
  edgeElasticity: 0.45,
  nestingFactor: 0.1,
  gravity: 0.15,
  gravityRange: 3.8,
  numIter: 3000,
  tile: false,
};

let _cy = null;
let _edgeThreshold = 0.0;
let _allEdgeData = [];   // original edge list, kept for filter resets
let _currentView = 'module-module';
let _selectedModule = null;
let _onNodeClick = null;
let _confMin = 0;        // confidence range of the current bipartite concept set
let _confMax = 1;

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

export async function initGraph(container, onNodeClick) {
  _onNodeClick = onNodeClick;
  return _loadView(container, 'module-module', null);
}

async function _loadView(container, view, moduleCode) {
  _currentView = view;
  const hint = document.getElementById('graph-hint');
  const thresholdLabel = document.getElementById('edge-threshold-label');
  const legend = document.getElementById('graph-legend');

  let data, elements, style;

  if (view === 'bipartite') {
    if (!moduleCode) {
      if (hint) hint.textContent = 'Select a module from the list to see its concepts';
      if (thresholdLabel) thresholdLabel.style.display = 'none';
      if (legend) legend.innerHTML = '';
      if (_cy) _cy.destroy();
      _cy = null;
      const cy = document.getElementById('cy');
      if (cy) cy.innerHTML = '<p class="placeholder">Select a module on the left to explore its concept graph.</p>';
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
      '<div class="legend-item"><div class="legend-dot" style="background:#5b8dee"></div><span>Module</span></div>' +
      '<div class="legend-item"><div class="legend-dot" style="background:#475569"></div><span>Low conf.</span></div>' +
      '<div class="legend-item"><div class="legend-dot" style="background:#5b8dee"></div><span>High conf.</span></div>';
  } else {
    data = await api.moduleModuleGraph({ include_centrality: true, include_communities: true });
    _allEdgeData = data.edges;
    elements = buildElements(data);
    style = buildStyle();
    if (hint) hint.textContent = 'Raise slider to hide weak connections and reveal clusters';
    if (thresholdLabel) thresholdLabel.style.display = '';
    _calibrateEdgeSlider(data.edges);
    buildLegend(data.nodes);
  }

  if (_cy) _cy.destroy();
  // Clear any placeholder text in the container before Cytoscape takes over,
  // otherwise the "Select a module…" hint can remain visible behind the canvas.
  const cyEl = container || document.getElementById('cy');
  if (cyEl) cyEl.innerHTML = '';
  _cy = cytoscape({
    container: cyEl,
    elements,
    style,
    layout: { ...LAYOUT_OPTS, randomize: true },
    wheelSensitivity: 0.3,
    minZoom: 0.2,
    maxZoom: 4,
  });

  _setupTooltip();
  if (_onNodeClick) _setupInteractions(_onNodeClick);
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

// ── Public controls ──────────────────────────────────────────────

export function fitGraph() {
  if (_cy) _cy.fit(undefined, 30);
}

export function rerunLayout() {
  if (!_cy) return;
  _cy.layout({ ...LAYOUT_OPTS, animate: true, animationDuration: 600 }).run();
}

export function applyEdgeFilter(threshold) {
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

export function highlightNode(moduleCode) {
  if (!_cy) return;
  _cy.nodes().removeClass('selected dimmed');
  _cy.edges().removeClass('highlighted dimmed');
  if (!moduleCode) return;

  const node = _cy.getElementById(moduleCode);
  if (node.length === 0) return;
  node.addClass('selected');

  const neighborNodes = node.neighborhood('node');
  const incidentEdges = node.connectedEdges();

  _cy.nodes().not(node).not(neighborNodes).addClass('dimmed');
  _cy.edges().not(incidentEdges).addClass('dimmed');
  incidentEdges.not('.filtered').addClass('highlighted');
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
  else applyEdgeFilter(threshold);
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
    // Concept nodes (bipartite view) are not modules — ignore clicks so we do
    // not fire a /modules/<concept-uuid> request (which 404s).
    if (node.data('nodeType') === 'concept') return;
    highlightNode(node.data('id'));
    onNodeClick(node.data('id'));
  });

  _cy.on('tap', (evt) => {
    if (evt.target === _cy) {
      _cy.nodes().removeClass('selected dimmed');
      _cy.edges().removeClass('highlighted dimmed');
      onNodeClick(null);
    }
  });
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
    const srcLabel = _cy.getElementById(d.source).data('label') || d.source;
    const tgtLabel = _cy.getElementById(d.target).data('label') || d.target;
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
  const nodes = data.nodes.map(n => ({
    data: {
      id: n.data.id,
      label: n.data.type === 'module' ? n.data.id : (n.data.term || n.data.id).slice(0, 22),
      nodeType: n.data.type || 'concept',
      title: n.data.title || n.data.term || '',
      level: n.data.level ?? null,
      confidence: n.data.confidence ?? null,
    },
  }));
  const edges = data.edges.map((e, i) => ({
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
        'background-color': '#5b8dee',
        'width': 48, 'height': 48,
        'label': 'data(label)',
        'font-size': '14px', 'font-weight': 700,
        'color': '#e2e8f0',
        'text-valign': 'center', 'text-halign': 'center',
        'text-outline-color': '#0f1117', 'text-outline-width': 2,
        'cursor': 'pointer',
        'z-index': 10,
      },
    },
    {
      selector: 'node[nodeType = "concept"]',
      style: {
        // Size and colour both encode extraction confidence (bigger/brighter = higher).
        'background-color': (ele) => _confColor(ele.data('confidence')),
        'border-width': 1, 'border-color': '#64748b',
        'width': (ele) => 12 + _normConf(ele.data('confidence')) * 26,
        'height': (ele) => 12 + _normConf(ele.data('confidence')) * 26,
        'label': 'data(label)',
        'font-size': '11px',
        'color': '#cbd5e1',
        'text-valign': 'bottom', 'text-halign': 'center',
        'text-margin-y': 4,
        'text-outline-color': '#0f1117', 'text-outline-width': 1,
        'cursor': 'default',
      },
    },
    {
      selector: 'edge',
      style: {
        'line-color': '#3a3f5c',
        'width': (ele) => 0.5 + (ele.data('weight') ?? 0) * 1.5,
        'opacity': 0.5,
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
      label: n.data.id,
      community: n.data.community ?? 0,
      degree: n.data.degree ?? 0,
      title: n.data.title ?? '',
      level: n.data.level ?? null,
      credits: n.data.credits ?? null,
      topConcepts: n.data.top_concepts ?? [],
    },
  }));

  const edges = data.edges.map(e => {
    const d = e.data;
    // prerequisite edges have weight=1.0 (not a similarity score);
    // use the 'similarity' attribute (Jaccard) if present, else null.
    // similarity edges have weight = Jaccard directly.
    const displaySim = d.type === 'prerequisite'
      ? (d.similarity ?? null)
      : (d.weight ?? 0);
    return {
      data: {
        id: d.id,
        source: d.source,
        target: d.target,
        weight: d.weight ?? 0,
        displaySim,
        type: d.type ?? 'similarity',
        sharedCount: d.shared_count ?? 0,
      },
    };
  });

  return [...nodes, ...edges];
}

function buildStyle() {
  return [
    {
      selector: 'node',
      style: {
        'background-color': (ele) => COMMUNITY_COLORS[ele.data('community') % COMMUNITY_COLORS.length],
        'width':  (ele) => 18 + ele.data('degree') * 38,
        'height': (ele) => 18 + ele.data('degree') * 38,
        'label': 'data(label)',
        'font-size': '9px',
        'color': '#e2e8f0',
        'text-valign': 'center',
        'text-halign': 'center',
        'text-outline-color': '#0f1117',
        'text-outline-width': 2,
        'border-width': 0,
        'cursor': 'pointer',
        'transition-property': 'opacity border-width width height',
        'transition-duration': '0.15s',
      },
    },
    {
      selector: 'node.selected',
      style: {
        'border-width': 3,
        'border-color': '#ffffff',
        'z-index': 999,
      },
    },
    {
      selector: 'node.dimmed',
      style: { 'opacity': 0.2 },
    },
    {
      selector: 'edge',
      style: {
        'line-color': '#3a3f5c',
        'width': (ele) => {
          const s = ele.data('displaySim');
          return s != null ? 0.8 + s * 4 : 1.2;
        },
        'opacity': 0.45,
        'curve-style': 'bezier',
        'transition-property': 'opacity line-color width',
        'transition-duration': '0.12s',
      },
    },
    {
      selector: 'edge[type = "prerequisite"]',
      style: {
        'line-style': 'dashed',
        'line-dash-pattern': [6, 4],
        'line-color': '#7c6af6',
        'opacity': 0.55,
      },
    },
    {
      selector: 'edge.highlighted',
      style: {
        'line-color': '#5b8dee',
        'opacity': 0.9,
        'width': (ele) => {
          const s = ele.data('displaySim');
          return s != null ? 2 + s * 5 : 2;
        },
        'z-index': 100,
      },
    },
    {
      selector: 'edge.dimmed',
      style: { 'opacity': 0.04 },
    },
    {
      selector: 'edge.filtered',
      style: { 'display': 'none' },
    },
  ];
}

function buildLegend(nodes) {
  const legendEl = document.getElementById('graph-legend');
  if (!legendEl) return;

  const communities = new Map();
  for (const n of nodes) {
    const c = n.data.community ?? 0;
    if (!communities.has(c)) communities.set(c, []);
    communities.get(c).push(n.data.id);
  }

  legendEl.innerHTML = [...communities.entries()]
    .sort(([a], [b]) => a - b)
    .map(([c, mods]) => {
      const color = COMMUNITY_COLORS[c % COMMUNITY_COLORS.length];
      return `<div class="legend-item">
        <div class="legend-dot" style="background:${color}"></div>
        <span>Cluster ${c + 1} (${mods.length})</span>
      </div>`;
    })
    .join('');
}
