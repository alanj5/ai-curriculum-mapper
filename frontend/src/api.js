/** Thin API wrapper — all fetch calls go through here. */

const BASE = '/api/v1';

async function _get(path, params = {}) {
  const url = new URL(BASE + path, location.origin);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

async function _patch(path, body) {
  const res = await fetch(BASE + path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  health: () => fetch('/health').then(r => r.json()),

  // Modules
  modules: (params = {}) => _get('/modules/', params),
  module: (code) => _get(`/modules/${code}`),
  moduleConcepts: (code) => _get(`/modules/${code}/concepts`),
  moduleAlignments: (code) => _get(`/modules/${code}/alignments`),
  moduleNeighbors: (code) => _get(`/modules/${code}/neighbors`),

  // Concepts
  concepts: (params = {}) => _get('/concepts/', params),
  concept: (id) => _get(`/concepts/${id}`),
  conceptAlignments: (id) => _get(`/concepts/${id}/alignments`),

  // Alignments
  alignments: (params = {}) => _get('/alignments/', params),
  alignmentStats: () => _get('/alignments/stats'),
  validate: (id, body) => _patch(`/alignments/${id}/validate`, body),

  // Graph
  moduleModuleGraph: (params = {}) => _get('/graph/module-module', params),
  bipartiteGraph: (module = null) => _get('/graph/module-concept', module ? { module } : {}),
  communities: () => _get('/graph/communities'),
  centrality: () => _get('/graph/centrality'),

  // Reports
  coverage: () => _get('/reports/coverage'),
  gaps: () => _get('/reports/gaps'),
  redundancies: () => _get('/reports/redundancies'),
  summary: () => _get('/reports/summary'),
};
