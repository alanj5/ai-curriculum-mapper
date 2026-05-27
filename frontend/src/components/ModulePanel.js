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

      <h3>Top Concepts</h3>
      <div style="margin-top:4px">
        ${topConcepts.map(c => `
          <span class="concept-chip" title="confidence: ${c.confidence.toFixed(3)}">${c.term}</span>
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
  } catch (e) {
    container.innerHTML = `<p class="placeholder" style="color:#f87171">Failed to load: ${e.message}</p>`;
  }
}
