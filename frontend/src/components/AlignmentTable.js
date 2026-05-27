import { api } from '../api.js';
import { acceptAlignment, rejectAlignment, openReassignModal } from './ValidationWidget.js';

let _sortCol = 'score';
let _sortDir = -1; // -1 = desc

export async function initAlignmentTable(kaOptions) {
  // Populate KA filter dropdown
  const kaFilter = document.getElementById('ka-filter');
  kaFilter.innerHTML = '<option value="">All KAs</option>' +
    kaOptions.map(ka => `<option value="${ka.code}">${ka.code} — ${ka.name}</option>`).join('');

  document.getElementById('ka-filter').addEventListener('change', () => loadTable());
  document.getElementById('ambiguous-filter').addEventListener('change', () => loadTable());
  document.getElementById('validated-filter').addEventListener('change', () => loadTable());

  await loadTable();
}

async function loadTable() {
  const ka = document.getElementById('ka-filter').value;
  const ambiguousVal = document.getElementById('ambiguous-filter').value;
  const validatedVal = document.getElementById('validated-filter').value;

  const params = { limit: 500, rank: 1 };
  if (ka) params.ka = ka;
  if (ambiguousVal) params.ambiguous = ambiguousVal;

  // validated filter: "null" means unvalidated (filter client-side)
  let alignments = await api.alignments(params);

  if (validatedVal === 'true') alignments = alignments.filter(a => a.validated === true);
  else if (validatedVal === 'false') alignments = alignments.filter(a => a.validated === false);
  else if (validatedVal === 'null') alignments = alignments.filter(a => a.validated === null);

  renderTable(alignments, ka, ambiguousVal, validatedVal);
}

function renderTable(alignments, ka, ambiguousVal, validatedVal) {
  const container = document.getElementById('alignment-table-container');

  if (alignments.length === 0) {
    container.innerHTML = '<p class="placeholder">No alignments match the current filters.</p>';
    return;
  }

  const sorted = [...alignments].sort((a, b) => {
    const av = a[_sortCol] ?? 0;
    const bv = b[_sortCol] ?? 0;
    if (typeof av === 'string') return _sortDir * av.localeCompare(bv);
    return _sortDir * (av - bv);
  });

  const colHeader = (col, label) => {
    const arrow = _sortCol === col ? (_sortDir === 1 ? ' ↑' : ' ↓') : '';
    return `<th data-col="${col}">${label}${arrow}</th>`;
  };

  container.innerHTML = `
    <table class="align-table">
      <thead>
        <tr>
          ${colHeader('concept_term', 'Concept')}
          ${colHeader('ka_code', 'KA')}
          <th>Topic</th>
          ${colHeader('method', 'Method')}
          ${colHeader('score', 'Score')}
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${sorted.map(a => renderRow(a)).join('')}
      </tbody>
    </table>
  `;

  // Sort click
  container.querySelectorAll('th[data-col]').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (_sortCol === col) _sortDir *= -1;
      else { _sortCol = col; _sortDir = -1; }
      renderTable(alignments, ka, ambiguousVal, validatedVal);
    });
  });

  // Action buttons
  container.querySelectorAll('.btn-accept').forEach(btn => {
    btn.addEventListener('click', () => {
      acceptAlignment(btn.dataset.id, () => loadTable());
    });
  });
  container.querySelectorAll('.btn-reject').forEach(btn => {
    btn.addEventListener('click', () => {
      rejectAlignment(btn.dataset.id, () => loadTable());
    });
  });
  container.querySelectorAll('.btn-reassign').forEach(btn => {
    btn.addEventListener('click', () => {
      openReassignModal(btn.dataset.id, () => loadTable());
    });
  });
}

function renderRow(a) {
  const barWidth = Math.round(a.score * 100);
  const ambBadge = a.is_ambiguous ? '<span class="badge badge-ambiguous">ambiguous</span>' : '';
  let valBadge;
  if (a.validated === true) valBadge = '<span class="badge badge-accepted">accepted</span>';
  else if (a.validated === false) valBadge = '<span class="badge badge-rejected">rejected</span>';
  else valBadge = '<span class="badge badge-pending">pending</span>';

  return `
    <tr>
      <td>${escHtml(a.concept_term)}</td>
      <td><strong>${a.ka_code}</strong></td>
      <td style="font-size:11px; color:#64748b; max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap"
          title="${escHtml(a.ka_topic || '')}">${escHtml(a.ka_topic || '—')}</td>
      <td style="font-size:11px">${a.method}</td>
      <td class="conf-bar-cell">
        <div class="conf-bar-wrap">
          <div class="conf-bar" style="width:${barWidth}px; max-width:100px"></div>
          <span class="conf-val">${a.score.toFixed(3)}</span>
        </div>
      </td>
      <td>${ambBadge} ${valBadge}</td>
      <td>
        <div class="action-btns">
          <button class="btn btn-accept" data-id="${a.id}" title="Accept">✓</button>
          <button class="btn btn-reject" data-id="${a.id}" title="Reject">✗</button>
          <button class="btn btn-reassign" data-id="${a.id}" title="Reassign">↩</button>
        </div>
      </td>
    </tr>
  `;
}

function escHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
