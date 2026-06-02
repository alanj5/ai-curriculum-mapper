import { api } from '../api.js';

let _allModules = [];
let _selectedCode = null;
let _onSelect = null;

export async function initModulePanel(onSelect) {
  _onSelect = onSelect;
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
}

function applyFilters() {
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
    const [detail, concepts] = await Promise.all([
      api.module(code),
      api.moduleConcepts(code),
    ]);

    const topConcepts = concepts.slice(0, 12);

    container.innerHTML = `
      <h2>${detail.code}</h2>
      <p style="font-size:12.5px; color:#94a3b8; margin-bottom:8px">${detail.title}</p>
      <div class="detail-stat">
        <span>Level ${detail.level}</span>·
        <span>${detail.credits} credits</span>·
        <span>${detail.ects_credits} ECTS</span>
      </div>
      ${detail.description ? `<p style="font-size:12px; color:#64748b; margin-bottom:10px">${detail.description}</p>` : ''}

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
        ${concepts.length > 12 ? `<span class="concept-chip" style="color:#64748b">+${concepts.length - 12} more</span>` : ''}
      </div>

      ${detail.prerequisites && detail.prerequisites.length > 0 ? `
        <h3>Prerequisites</h3>
        <div style="margin-top:4px">
          ${detail.prerequisites.map(p => `<span class="concept-chip">${p}</span>`).join('')}
        </div>
      ` : ''}
    `;

    container.querySelectorAll('.concept-chip-clickable').forEach(chip => {
      chip.addEventListener('click', () => showConceptDetail(chip.dataset.conceptId, code));
    });
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

function esc(str) {
  return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
