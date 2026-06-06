import { api } from '../api.js';
import { isLikelyFragment } from '../util/concepts.js';
import { navigate } from '../router.js';

let _allModules = [];
let _selectedCode = null;
let _onSelect = null;
let _searchMode = 'modules';   // 'modules' | 'concepts'
let _kaNames = {};             // ka_code → full Knowledge-Area name

// Where detail views render. The Explore page uses #module-detail-content; the
// Map drawer passes its own element via the `target` argument.
function detailHost(target) {
  return target || document.getElementById('module-detail-content');
}

export async function initModulePanel(onSelect, kaOptions) {
  _onSelect = onSelect;
  _searchMode = 'modules';   // reset so the markup's default toggle stays consistent on re-mount
  _selectedCode = null;
  if (kaOptions) _kaNames = Object.fromEntries(kaOptions.map(k => [k.code, k.name]));
  _allModules = await api.modules({ limit: 100 });
  renderList(_allModules);

  const searchInput = document.getElementById('module-search');
  const levelFilter = document.getElementById('level-filter');
  const programmeFilter = document.getElementById('programme-filter');

  // Populate the programme facet (interim §3.2.4 "filter ... by programme").
  try {
    const programmes = await api.programmes();
    if (programmeFilter) {
      programmeFilter.innerHTML = '<option value="">All programmes</option>' +
        programmes.map(p => `<option value="${p.id}">${p.name} (${p.module_count})</option>`).join('');
    }
  } catch { /* programmes endpoint unavailable — leave the default option */ }

  let debounceTimer;
  searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => applyFilters(), 200);
  });
  levelFilter.addEventListener('change', () => applyFilters());
  if (programmeFilter) programmeFilter.addEventListener('change', () => applyFilters());

  // Modules ↔ Concepts search-mode toggle
  document.querySelectorAll('#search-mode .sm-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      _searchMode = btn.dataset.mode;
      document.querySelectorAll('#search-mode .sm-btn')
        .forEach(b => b.classList.toggle('active', b.dataset.mode === _searchMode));
      const concepts = _searchMode === 'concepts';
      searchInput.placeholder = concepts ? 'Search concepts…' : 'Search modules…';
      levelFilter.style.display = concepts ? 'none' : '';
      if (programmeFilter) programmeFilter.style.display = concepts ? 'none' : '';
      applyFilters();
    });
  });
}

function applyFilters() {
  if (_searchMode === 'concepts') return applyConceptSearch();

  const q = document.getElementById('module-search').value.toLowerCase().trim();
  const level = document.getElementById('level-filter').value;
  const programme = document.getElementById('programme-filter')?.value || '';

  let filtered = _allModules;
  if (level) filtered = filtered.filter(m => String(m.level) === level);
  if (programme) filtered = filtered.filter(m => (m.programmes || []).includes(programme));
  if (q) {
    filtered = filtered.filter(m =>
      m.code.toLowerCase().includes(q) ||
      m.title.toLowerCase().includes(q) ||
      (m.description || '').toLowerCase().includes(q)
    );
  }
  renderList(filtered);
}

async function applyConceptSearch() {
  const q = document.getElementById('module-search').value.trim();
  const el = document.getElementById('module-list');
  setListMeta('Searching…');
  el.innerHTML = '<p class="placeholder">Searching…</p>';
  try {
    const concepts = await api.concepts({ search: q, limit: 60 });
    renderConceptList(concepts);
  } catch (e) {
    el.innerHTML = `<p class="placeholder error">Search failed: ${e.message}</p>`;
  }
}

function setListMeta(text) {
  const m = document.getElementById('list-meta');
  if (m) m.textContent = text;
}

function renderConceptList(concepts) {
  const el = document.getElementById('module-list');
  concepts = _cleanConcepts(concepts);
  setListMeta(`${concepts.length} concept${concepts.length === 1 ? '' : 's'}`);
  if (concepts.length === 0) {
    el.innerHTML = '<p class="placeholder">No concepts match.</p>';
    return;
  }
  el.innerHTML = concepts.map(c => `
    <div class="module-card concept-result" data-concept-id="${c.id}">
      <div class="title">${esc(c.term)}</div>
      <div class="meta">${(c.confidence * 100).toFixed(0)}% confidence · ${c.module_codes.length} module${c.module_codes.length === 1 ? '' : 's'}</div>
    </div>
  `).join('');

  el.querySelectorAll('.concept-result').forEach(card => {
    card.addEventListener('click', () => showConceptDetail(card.dataset.conceptId));
  });
}

function renderList(modules) {
  const el = document.getElementById('module-list');
  setListMeta(`${modules.length} module${modules.length === 1 ? '' : 's'}`);
  if (modules.length === 0) {
    el.innerHTML = '<p class="placeholder">No modules match.</p>';
    return;
  }
  el.innerHTML = modules.map(m => `
    <div class="module-card ${m.code === _selectedCode ? 'selected' : ''}" data-code="${m.code}">
      <div class="title">${esc(m.title)}</div>
      <div class="meta"><span class="code">${m.code}</span> · Level ${m.level} · ${m.credits} credits</div>
    </div>
  `).join('');

  el.querySelectorAll('.module-card').forEach(card => {
    card.addEventListener('click', () => selectModule(card.dataset.code));
  });
}

export function selectModule(code) {
  _selectedCode = code;
  document.querySelectorAll('.module-card').forEach(c => {
    c.classList.toggle('selected', c.dataset.code === code);
  });
  if (_onSelect) _onSelect(code);
}

export async function showModuleDetail(code, target) {
  const container = detailHost(target);
  if (!container) return;
  if (!code) {
    container.innerHTML = `<div class="detail-empty"><div class="big">📘</div><div>Select a module to see its outcomes, topics and prerequisites.</div></div>`;
    return;
  }
  container.innerHTML = '<p class="placeholder">Loading…</p>';

  try {
    const [detail, concepts, alignments, plos] = await Promise.all([
      api.module(code),
      api.moduleConcepts(code),
      api.moduleAlignments(code),
      api.modulePlos(code).catch(() => []),
    ]);

    const cleaned = _cleanConcepts(concepts);
    const topConcepts = cleaned.slice(0, 14);

    // CS2023 coverage profile: the Knowledge Areas this module's concepts map to
    // (primary, rank-1 alignments), most-covered first.
    const kaCounts = {};
    for (const a of alignments) if (a.rank === 1) kaCounts[a.ka_code] = (kaCounts[a.ka_code] || 0) + 1;
    const kaList = Object.entries(kaCounts).sort((a, b) => b[1] - a[1]);
    const nMappings = alignments.filter(a => a.rank === 1).length;

    container.innerHTML = `
      <div class="detail-card">
        <div class="dc-code">${detail.code}</div>
        <h2 class="dc-title">${esc(detail.title)}</h2>
        <div class="detail-stat">
          <span class="pill">Level ${detail.level}</span>
          <span class="pill">${detail.credits} ECTS credits</span>
          <span class="pill">${detail.ilos.length} learning outcomes</span>
        </div>
        ${detail.description ? `<p class="dc-desc">${esc(detail.description)}</p>` : ''}

        ${kaList.length ? `
          <div class="dc-section">
            <h3>CS2023 coverage <span class="h-note">— Knowledge Areas this module teaches (${kaList.length})</span></h3>
            <div class="ka-profile">
              ${kaList.map(([ka, n]) => `<span class="ka-chip" title="${esc(_kaNames[ka] || ka)} — ${n} concept${n === 1 ? '' : 's'} map here">${ka}<span class="ka-chip-n">${n}</span></span>`).join('')}
            </div>
          </div>` : ''}

        ${plos && plos.length ? `
          <div class="dc-section">
            <h3>Programme outcomes fulfilled <span class="h-note">(${plos.length})</span></h3>
            <div class="ka-profile">
              ${plos.map(p => `<span class="ka-chip plo-chip" title="${esc(p.description)} (semantic match ${p.score.toFixed(2)})">${esc(p.code)} · ${esc(p.title)}</span>`).join('')}
            </div>
          </div>` : ''}

        <div class="dc-section">
          <h3>Learning outcomes <span class="h-note">(${detail.ilos.length})</span></h3>
          <ul class="ilo-list">
            ${detail.ilos.map(ilo => `<li class="ilo-item">${esc(ilo.text)}</li>`).join('')}
          </ul>
        </div>

        <div class="dc-section">
          <h3>Key concepts <span class="h-note">— click any to explore where it's taught</span></h3>
          <div class="chip-wrap">
            ${topConcepts.map(c => `<span class="concept-chip concept-chip-clickable" data-concept-id="${c.id}" title="confidence ${(c.confidence * 100).toFixed(0)}% — click to explore">${esc(c.term)}</span>`).join('')}
            ${cleaned.length > 14 ? `<span class="concept-chip" style="color:var(--muted)">+${cleaned.length - 14} more</span>` : ''}
          </div>
        </div>

        ${detail.prerequisites && detail.prerequisites.length > 0 ? `
          <div class="dc-section">
            <h3>Prerequisites</h3>
            <div class="chip-wrap">
              ${detail.prerequisites.map(p => `<span class="concept-chip prereq-chip" data-prereq="${esc(p)}" title="Go to ${esc(p)}">${esc(p)}</span>`).join('')}
            </div>
          </div>` : ''}

        <button class="btn-action" id="trace-prereq" data-code="${detail.code}">Trace prerequisite chain on the map →</button>
        ${nMappings ? `<button class="btn-action" id="review-aligns" data-code="${detail.code}">Review this module's ${nMappings} AI mappings →</button>` : ''}
      </div>
    `;

    container.querySelectorAll('.concept-chip-clickable').forEach(chip => {
      chip.addEventListener('click', () => showConceptDetail(chip.dataset.conceptId, code, target));
    });
    container.querySelectorAll('.prereq-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const c = chip.dataset.prereq;
        if (_allModules.some(m => m.code === c)) selectModule(c);
      });
    });
    container.querySelector('#review-aligns')?.addEventListener('click', e => navigate('review', { module: e.target.dataset.code }));
    container.querySelector('#trace-prereq')?.addEventListener('click', e => navigate('map', { view: 'level', trace: e.target.dataset.code }));
  } catch (e) {
    container.innerHTML = `<p class="placeholder error">Failed to load: ${e.message}</p>`;
  }
}

// ── Concept detail ────────────────────────────────────────────────────
// The concept's CS2023 alignment, merged variants, and every module that teaches
// it ordered by level so progression (introduced → reinforced) is visible.
export async function showConceptDetail(conceptId, fromModule = null, target) {
  const container = detailHost(target);
  if (!container) return;
  container.innerHTML = '<p class="placeholder">Loading…</p>';

  try {
    const [concept, alignments] = await Promise.all([
      api.concept(conceptId),
      api.conceptAlignments(conceptId),
    ]);

    const byCode = new Map(_allModules.map(m => [m.code, m]));
    const teaching = (concept.module_codes || [])
      .map(c => byCode.get(c) || { code: c, title: '', level: null })
      .sort((a, b) => (a.level ?? 99) - (b.level ?? 99) || a.code.localeCompare(b.code));
    const introLevel = teaching.length ? teaching[0].level : null;

    const top = alignments.find(a => a.rank === 1) || alignments[0];
    const statusBadge = (a) => {
      if (!a) return '';
      if (a.validated === true) return '<span class="badge badge-accepted">accepted</span>';
      if (a.validated === false) return '<span class="badge badge-rejected">rejected</span>';
      if (a.is_ambiguous) return '<span class="badge badge-ambiguous">ambiguous</span>';
      return '<span class="badge badge-pending">pending</span>';
    };

    const backLink = fromModule
      ? `<a class="back-link" data-back="${esc(fromModule)}">← Back to ${esc(fromModule)}</a>`
      : '';

    container.innerHTML = `
      <div class="detail-card">
        ${backLink}
        <div class="dc-code">Extracted concept</div>
        <h2 class="dc-title">${esc(concept.term)}</h2>
        <div class="detail-stat">
          <span class="pill">${(concept.confidence * 100).toFixed(0)}% confidence</span>
          <span class="pill">taught in ${concept.module_codes.length} module${concept.module_codes.length === 1 ? '' : 's'}</span>
        </div>

        <button class="btn-action" id="explore-prereq">Explore its prerequisites on the map →</button>

        <div class="dc-section">
          <h3>CS2023 alignment</h3>
          ${top ? `
            <div class="concept-align-row">
              <span class="align-ka">${top.ka_code}</span>
              <span class="align-topic">${esc(top.ka_topic || '')}</span>
              <span class="align-score">${top.score.toFixed(3)}</span>
              ${statusBadge(top)}
            </div>
            <p class="section-sub" style="margin:8px 0 0">Suggested mapping — review on the Review page.</p>
          ` : '<p class="placeholder">No alignment recorded.</p>'}
        </div>

        ${concept.variants && concept.variants.length > 1 ? `
          <div class="dc-section">
            <h3>Variants merged into this concept</h3>
            <div class="chip-wrap">${concept.variants.map(v => `<span class="concept-chip">${esc(v)}</span>`).join('')}</div>
          </div>` : ''}

        <div class="dc-section">
          <h3>Taught in ${teaching.length} module${teaching.length === 1 ? '' : 's'} <span class="h-note">— ordered by level</span></h3>
          <div class="concept-modules">
            ${teaching.map(m => `
              <div class="concept-mod-card" data-code="${m.code}">
                <div><span class="code">${m.code}</span> <span class="cm-title">${esc(m.title || '')}</span></div>
                <div class="cm-meta">${m.level != null ? `Level ${m.level}` : ''}${m.level === introLevel && m.level != null ? ' · introduced here' : ''}</div>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;

    container.querySelector('.back-link')?.addEventListener('click', e => showModuleDetail(e.target.dataset.back, target));
    container.querySelectorAll('.concept-mod-card').forEach(card => {
      card.addEventListener('click', () => selectModule(card.dataset.code));
    });
    container.querySelector('#explore-prereq')?.addEventListener('click', () => navigate('map', { view: 'concept-prereq', concept: conceptId }));
  } catch (e) {
    container.innerHTML = `<p class="placeholder error">Failed to load concept: ${e.message}</p>`;
  }
}

// ── Display-only concept cleanup (shared heuristic, see util/concepts.js) ──
function _cleanConcepts(list) {
  const filtered = list.filter(c => !isLikelyFragment(c.term));
  return filtered.length ? filtered : list;
}

function esc(str) {
  return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
