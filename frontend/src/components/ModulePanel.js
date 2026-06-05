import { api } from '../api.js';
import { isLikelyFragment } from '../util/concepts.js';
import { reviewModuleAlignments } from './AlignmentTable.js';

let _allModules = [];
let _selectedCode = null;
let _onSelect = null;
let _searchMode = 'modules';   // 'modules' | 'concepts'
let _kaNames = {};             // ka_code → full Knowledge-Area name

export async function initModulePanel(onSelect, kaOptions) {
  _onSelect = onSelect;
  if (kaOptions) _kaNames = Object.fromEntries(kaOptions.map(k => [k.code, k.name]));
  _allModules = await api.modules({ limit: 100 });
  renderList(_allModules);

  const searchInput = document.getElementById('module-search');
  const levelFilter = document.getElementById('level-filter');

  let debounceTimer;
  searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => applyFilters(), 200);
  });
  levelFilter.addEventListener('change', () => applyFilters());

  // Modules ↔ Concepts search-mode toggle
  document.querySelectorAll('#search-mode .sm-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      _searchMode = btn.dataset.mode;
      document.querySelectorAll('#search-mode .sm-btn')
        .forEach(b => b.classList.toggle('active', b.dataset.mode === _searchMode));
      const concepts = _searchMode === 'concepts';
      searchInput.placeholder = concepts ? 'Search concepts…' : 'Search modules…';
      levelFilter.style.display = concepts ? 'none' : '';
      applyFilters();
    });
  });
}

function applyFilters() {
  if (_searchMode === 'concepts') return applyConceptSearch();

  const q = document.getElementById('module-search').value.toLowerCase().trim();
  const level = document.getElementById('level-filter').value;

  let filtered = _allModules;
  if (level) filtered = filtered.filter(m => String(m.level) === level);
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
  el.innerHTML = '<p class="placeholder">Searching…</p>';
  try {
    const concepts = await api.concepts({ search: q, limit: 60 });
    renderConceptList(concepts);
  } catch (e) {
    el.innerHTML = `<p class="placeholder" style="color:#f87171">Search failed: ${e.message}</p>`;
  }
}

function renderConceptList(concepts) {
  const el = document.getElementById('module-list');
  concepts = _cleanConcepts(concepts);
  if (concepts.length === 0) {
    el.innerHTML = '<p class="placeholder">No concepts match.</p>';
    return;
  }
  el.innerHTML = concepts.map(c => `
    <div class="module-card concept-result" data-concept-id="${c.id}">
      <div class="title">${esc(c.term)}</div>
      <div class="meta">conf ${(c.confidence * 100).toFixed(0)}% · ${c.module_codes.length} module${c.module_codes.length === 1 ? '' : 's'}</div>
    </div>
  `).join('');

  el.querySelectorAll('.concept-result').forEach(card => {
    card.addEventListener('click', () => showConceptDetail(card.dataset.conceptId));
  });
}

function renderList(modules) {
  const el = document.getElementById('module-list');
  if (modules.length === 0) {
    el.innerHTML = '<p class="placeholder">No modules match.</p>';
    return;
  }
  el.innerHTML = modules.map(m => `
    <div class="module-card ${m.code === _selectedCode ? 'selected' : ''}" data-code="${m.code}">
      <div class="code">${m.code}</div>
      <div class="title">${m.title}</div>
      <div class="meta">Level ${m.level} · ${m.credits} credits · ${m.ilo_count} ILOs</div>
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

export async function showModuleDetail(code) {
  const container = document.getElementById('module-detail-content');
  if (!code) {
    container.innerHTML = '<p class="placeholder">Select a module to see details.</p>';
    return;
  }
  container.innerHTML = '<p class="placeholder">Loading…</p>';

  try {
    const [detail, concepts, alignments] = await Promise.all([
      api.module(code),
      api.moduleConcepts(code),
      api.moduleAlignments(code),
    ]);

    const cleaned = _cleanConcepts(concepts);
    const topConcepts = cleaned.slice(0, 12);

    // CS2023 coverage profile: the Knowledge Areas this module's concepts map to
    // (primary, rank-1 alignments), most-covered first — the curriculum mapping
    // made concrete for this module.
    const kaCounts = {};
    for (const a of alignments) {
      if (a.rank === 1) kaCounts[a.ka_code] = (kaCounts[a.ka_code] || 0) + 1;
    }
    const kaList = Object.entries(kaCounts).sort((a, b) => b[1] - a[1]);
    const nMappings = alignments.filter(a => a.rank === 1).length;

    container.innerHTML = `
      <h2>${detail.code}</h2>
      <p style="font-size:12.5px; color:#94a3b8; margin-bottom:8px">${detail.title}</p>
      <div class="detail-stat">
        <span>Level ${detail.level}</span>·
        <span>${detail.credits} ECTS credits</span>
      </div>
      ${detail.description ? `<p style="font-size:12px; color:#64748b; margin-bottom:10px">${detail.description}</p>` : ''}

      ${kaList.length ? `
        <h3>CS2023 Coverage <span style="font-weight:400; color:#64748b; font-size:11px">(${kaList.length} Knowledge Area${kaList.length === 1 ? '' : 's'})</span></h3>
        <div class="ka-profile">
          ${kaList.map(([ka, n]) => `<span class="ka-chip" title="${esc(_kaNames[ka] || ka)} — ${n} concept${n === 1 ? '' : 's'} map here">${ka}<span class="ka-chip-n">${n}</span></span>`).join('')}
        </div>
      ` : ''}

      <h3>ILOs (${detail.ilos.length})</h3>
      <ul class="ilo-list">
        ${detail.ilos.map(ilo => `
          <li class="ilo-item">${ilo.text}</li>
        `).join('')}
      </ul>

      <h3>Top Concepts <span style="font-weight:400; color:#64748b; font-size:11px">(click to explore)</span></h3>
      <div style="margin-top:4px">
        ${topConcepts.map(c => `
          <span class="concept-chip concept-chip-clickable" data-concept-id="${c.id}" title="confidence: ${c.confidence.toFixed(3)} — click to explore">${esc(c.term)}</span>
        `).join('')}
        ${cleaned.length > 12 ? `<span class="concept-chip" style="color:#64748b">+${cleaned.length - 12} more</span>` : ''}
      </div>

      ${detail.prerequisites && detail.prerequisites.length > 0 ? `
        <h3>Prerequisites</h3>
        <div style="margin-top:4px">
          ${detail.prerequisites.map(p => `<span class="concept-chip prereq-chip" data-prereq="${esc(p)}" title="Go to ${esc(p)}">${esc(p)}</span>`).join('')}
        </div>
      ` : ''}

      ${nMappings ? `<button class="btn btn-review" id="review-aligns" data-code="${detail.code}">Review this module's ${nMappings} mappings →</button>` : ''}
    `;

    container.querySelectorAll('.concept-chip-clickable').forEach(chip => {
      chip.addEventListener('click', () => showConceptDetail(chip.dataset.conceptId, code));
    });
    container.querySelectorAll('.prereq-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const c = chip.dataset.prereq;
        if (_allModules.some(m => m.code === c)) selectModule(c);
      });
    });
    const reviewBtn = container.querySelector('#review-aligns');
    if (reviewBtn) reviewBtn.addEventListener('click', () => reviewModuleAlignments(reviewBtn.dataset.code));
  } catch (e) {
    container.innerHTML = `<p class="placeholder" style="color:#f87171">Failed to load: ${e.message}</p>`;
  }
}

// ── Concept detail (click a concept chip to explore its mapping) ──────
// Shows the concept's CS2023 alignment, synonym variants, and every module
// that teaches it, ordered by level so progression (introduced → reinforced)
// is visible — delivering the concept-centric exploration promised for
// students in the interim report.
export async function showConceptDetail(conceptId, fromModule = null) {
  const container = document.getElementById('module-detail-content');
  container.innerHTML = '<p class="placeholder">Loading…</p>';

  try {
    const [concept, alignments] = await Promise.all([
      api.concept(conceptId),
      api.conceptAlignments(conceptId),
    ]);

    // Resolve the modules that teach this concept, ordered by level.
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
      ? `<a class="back-link" data-back="${fromModule}">← Back to ${fromModule}</a>`
      : '';

    container.innerHTML = `
      ${backLink}
      <h2>${esc(concept.term)}</h2>
      <p style="font-size:12.5px; color:#94a3b8; margin-bottom:8px">Extracted concept</p>
      <div class="detail-stat">
        <span>confidence ${(concept.confidence * 100).toFixed(0)}%</span>·
        <span>${concept.module_codes.length} module${concept.module_codes.length === 1 ? '' : 's'}</span>
      </div>

      <h3>CS2023 Alignment</h3>
      ${top ? `
        <div class="concept-align-row">
          <span class="align-ka">${top.ka_code}</span>
          <span class="align-topic">${esc(top.ka_topic || '')}</span>
          <span class="align-score">${top.score.toFixed(3)}</span>
          ${statusBadge(top)}
        </div>
        <p style="font-size:11px; color:#64748b; margin-top:4px">Suggested mapping — review in the Alignments tab.</p>
      ` : '<p class="placeholder">No alignment recorded.</p>'}

      ${concept.variants && concept.variants.length > 1 ? `
        <h3>Variants merged</h3>
        <div style="margin-top:4px">
          ${concept.variants.map(v => `<span class="concept-chip">${esc(v)}</span>`).join('')}
        </div>
      ` : ''}

      <h3>Taught in ${teaching.length} module${teaching.length === 1 ? '' : 's'} <span style="font-weight:400; color:#64748b; font-size:11px">(by level)</span></h3>
      <div class="concept-modules">
        ${teaching.map(m => `
          <div class="concept-mod-card" data-code="${m.code}">
            <div><span class="code">${m.code}</span> <span class="cm-title">${esc(m.title || '')}</span></div>
            <div class="cm-meta">${m.level != null ? `Level ${m.level}` : ''}${m.level === introLevel && m.level != null ? ' · introduced here' : ''}</div>
          </div>
        `).join('')}
      </div>
    `;

    const back = container.querySelector('.back-link');
    if (back) back.addEventListener('click', () => showModuleDetail(back.dataset.back));
    container.querySelectorAll('.concept-mod-card').forEach(card => {
      card.addEventListener('click', () => selectModule(card.dataset.code));
    });
  } catch (e) {
    container.innerHTML = `<p class="placeholder" style="color:#f87171">Failed to load concept: ${e.message}</p>`;
  }
}

// ── Display-only concept cleanup ──────────────────────────────────────
// Suppress ILO sentence-fragments from the concept chips and search for
// readability only (shared heuristic, see util/concepts.js). Never blank the
// view: fall back to the original list if everything looks like a fragment.
function _cleanConcepts(list) {
  const filtered = list.filter(c => !isLikelyFragment(c.term));
  return filtered.length ? filtered : list;
}

function esc(str) {
  return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
