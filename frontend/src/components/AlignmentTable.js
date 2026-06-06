import { api } from '../api.js';
import { acceptAlignment, rejectAlignment, resetAlignment, openReassignModal } from './ValidationWidget.js';
import { showUndoToast } from './Toast.js';

let _sortCol = 'score';
let _sortDir = -1; // -1 = desc
let _moduleFilter = null;  // when set, only show alignments whose concept came from this module
let _initialised = false;

export async function initAlignmentTable(kaOptions) {
  _initialised = true;
  // Populate KA filter dropdown
  const kaFilter = document.getElementById('ka-filter');
  kaFilter.innerHTML = '<option value="">All KAs</option>' +
    kaOptions.map(ka => `<option value="${ka.code}">${ka.code} — ${ka.name}</option>`).join('');

  document.getElementById('ka-filter').addEventListener('change', () => loadTable());
  document.getElementById('ambiguous-filter').addEventListener('change', () => loadTable());
  document.getElementById('validated-filter').addEventListener('change', () => loadTable());

  await loadTable();
}

// Scope the review table to a single module — the natural unit of curriculum
// review (an educator validates a whole course's mappings at once). Pass null to
// clear the scope. Routing to the Review page is handled by the caller.
export function reviewModuleAlignments(code) {
  _moduleFilter = code || null;
  if (_initialised) loadTable();
}

function clearModuleFilter() {
  _moduleFilter = null;
  loadTable();
}

async function loadTable() {
  const ka = document.getElementById('ka-filter').value;
  const ambiguousVal = document.getElementById('ambiguous-filter').value;
  const validatedVal = document.getElementById('validated-filter').value;

  let alignments;
  if (_moduleFilter) {
    // module scope: pull exactly this module's primary mappings straight from the
    // module endpoint — no global 500-row cap, so the count matches the "Review N
    // mappings" button — then apply the KA / ambiguity filters client-side.
    alignments = (await api.moduleAlignments(_moduleFilter)).filter(a => a.rank === 1);
    if (ka) alignments = alignments.filter(a => a.ka_code === ka);
    if (ambiguousVal === 'true') alignments = alignments.filter(a => a.is_ambiguous === true);
    else if (ambiguousVal === 'false') alignments = alignments.filter(a => a.is_ambiguous === false);
  } else {
    const params = { limit: 500, rank: 1 };
    if (ka) params.ka = ka;
    if (ambiguousVal) params.ambiguous = ambiguousVal;
    alignments = await api.alignments(params);
  }

  // validated filter: "null" means unvalidated (filter client-side)
  if (validatedVal === 'true') alignments = alignments.filter(a => a.validated === true);
  else if (validatedVal === 'false') alignments = alignments.filter(a => a.validated === false);
  else if (validatedVal === 'null') alignments = alignments.filter(a => a.validated === null);

  renderTable(alignments, ka, ambiguousVal, validatedVal);
}

function renderTable(alignments, ka, ambiguousVal, validatedVal) {
  const container = document.getElementById('alignment-table-container');

  const scopeBanner = _moduleFilter
    ? `<div class="scope-banner">Reviewing <strong>${escHtml(_moduleFilter)}</strong> — ${alignments.length} mapping${alignments.length === 1 ? '' : 's'}<button class="scope-clear" id="scope-clear">Show all ✕</button></div>`
    : '';
  const wireClear = () => {
    const b = container.querySelector('#scope-clear');
    if (b) b.addEventListener('click', clearModuleFilter);
  };

  if (alignments.length === 0) {
    container.innerHTML = scopeBanner + '<p class="placeholder">No alignments match the current filters.</p>';
    wireClear();
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

  container.innerHTML = scopeBanner + `
    <p class="table-caption">
      Each row is the top-ranked CS2023 Knowledge-Area alignment for one extracted concept,
      scored by the hybrid lexical+semantic aligner.
      <strong>Status:</strong>
      <span class="badge badge-pending">pending</span> not yet reviewed ·
      <span class="badge badge-accepted">accepted</span> confirmed correct ·
      <span class="badge badge-rejected">rejected</span> marked incorrect ·
      <span class="badge badge-ambiguous">ambiguous</span> top-two KA scores within 0.08 (needs a human decision).
      Use <strong>✓ / ✗ / ↩</strong> to accept, reject, or reassign.
    </p>
    <table class="align-table">
      <thead>
        <tr>
          ${colHeader('concept_term', 'Concept')}
          <th title="Module(s) the concept was extracted from — trace each suggestion to its source">Source</th>
          ${colHeader('ka_code', 'KA')}
          <th>Topic</th>
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

  wireClear();

  // Sort click
  container.querySelectorAll('th[data-col]').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (_sortCol === col) _sortDir *= -1;
      else { _sortCol = col; _sortDir = -1; }
      renderTable(alignments, ka, ambiguousVal, validatedVal);
    });
  });

  // Action buttons. Accept/reject show a 5-second Undo toast so an accidental
  // click is recoverable without manual DB intervention.
  container.querySelectorAll('.btn-accept').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.id;
      if (await acceptAlignment(id, () => loadTable()))
        showUndoToast('Marked as accepted', () => resetAlignment(id, () => loadTable()));
    });
  });
  container.querySelectorAll('.btn-reject').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.id;
      if (await rejectAlignment(id, () => loadTable()))
        showUndoToast('Marked as rejected', () => resetAlignment(id, () => loadTable()));
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

  const mods = a.source_modules || [];
  const srcCell = mods.length
    ? `<span class="src-mod" title="Extracted from: ${escHtml(mods.join(', '))}">${escHtml(mods[0])}${mods.length > 1 ? ` +${mods.length - 1}` : ''}</span>`
    : '<span style="color:#475569">—</span>';

  return `
    <tr>
      <td>${escHtml(a.concept_term)}</td>
      <td style="font-size:11px; color:#94a3b8">${srcCell}</td>
      <td><strong>${a.ka_code}</strong></td>
      <td style="font-size:11px; color:#64748b; max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap"
          title="${escHtml(a.ka_topic || '')}">${escHtml(a.ka_topic || '—')}</td>
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
