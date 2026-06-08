import { Chart, BarController, BarElement, CategoryScale, LinearScale, Tooltip, Legend } from 'chart.js';
import { api } from '../api.js';
import { navigate } from '../router.js';

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip, Legend);

let _coverageChart = null;
let _comparisonChart = null;
let _matrix = null;     // last-loaded coverage matrix (for the grid + cohort filter)
let _allModules = [];   // full module set (for the "not covered" side of a drill-down)
let _coverage = [];     // last-loaded coverage rows (for KA names in the drill-down)

export async function initGapReport() {
  const container = document.getElementById('gap-report-container');
  container.innerHTML = '<p class="placeholder">Loading coverage…</p>';

  try {
    const [summary, coverage, gaps, redundancies, modules, ploCov, comparison, matrix] = await Promise.all([
      api.summary(),
      api.coverage(),
      api.gaps(),
      api.redundancies(),
      api.modules({ limit: 200 }),
      api.ploCoverage().catch(() => []),
      api.programmeComparison().catch(() => null),
      api.coverageMatrix().catch(() => null),
    ]);
    _allModules = modules;
    _coverage = coverage;
    _matrix = matrix;

    container.innerHTML = buildHTML(summary, coverage, gaps, redundancies, ploCov, comparison, matrix);
    renderCoverageChart(coverage, summary.total_modules);
    if (comparison && comparison.comparable) renderComparisonChart(comparison);
    if (matrix) renderMatrix('all');

    container.querySelectorAll('.gap-item[data-ka]').forEach(el =>
      el.addEventListener('click', () => showDrilldown(el.dataset.ka)));
    container.querySelectorAll('.gap-item[data-plo]').forEach(el =>
      el.addEventListener('click', () => showPloDrilldown(el.dataset.plo, el.dataset.title)));
    const cohortSel = document.getElementById('matrix-cohort');
    if (cohortSel) cohortSel.addEventListener('change', () => renderMatrix(cohortSel.value));
  } catch (e) {
    container.innerHTML = `<p class="placeholder error">Failed to load: ${e.message}</p>`;
  }
}

function buildHTML(summary, coverage, gaps, redundancies, ploCov = [], comparison = null, matrix = null) {
  const pct = (n) => `${(n * 100).toFixed(1)}%`;

  // Side-by-side cohort comparison (interim §2.7 "browse two curricula … to
  // reveal differences in topic coverage"; realises the §3.5 MIT-OCW stretch
  // goal as a visible feature). Only meaningful on the combined corpus.
  const comparisonSection = (comparison && comparison.comparable) ? `
    <div class="gap-section">
      <h2>Cohort comparison</h2>
      <p class="section-sub">CS2023 Knowledge-Area breadth of each cohort, side by side —
        ${comparison.cohorts.map(c => `<strong>${esc(c.label)}</strong> (${c.n_modules} modules, ${c.kas_covered}/18 KAs)`).join(' vs. ')}.
        ${comparisonSummary(comparison)}</p>
      <div class="chart-container" style="max-height:520px; overflow:hidden">
        <canvas id="comparison-chart" height="500"></canvas>
      </div>
    </div>` : ((comparison && !comparison.comparable) ? `
    <div class="gap-section">
      <h2>Cohort comparison</h2>
      <p class="section-sub">A side-by-side comparison against the MIT OpenCourseWare cohort is available when viewing the combined corpus (<code>make serve-multi</code>).</p>
    </div>` : '');

  // Interactive module × KA grid (interim "adjacency matrix … to see coverage
  // across categories at once without crossing edges").
  const cohorts = matrix ? [...new Set(matrix.modules.map(m => m.cohort))] : [];
  const matrixSection = matrix ? `
    <div class="gap-section">
      <h2>Module × Knowledge-Area map</h2>
      <p class="section-sub">Each module's CS2023 footprint — how many of its concepts fall in each Knowledge Area (darker = more). Click a Knowledge-Area header to drill into it.
        ${cohorts.length > 1 ? `<select id="matrix-cohort" class="matrix-cohort">
          <option value="all">All cohorts</option>
          ${cohorts.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join('')}
        </select>` : ''}
      </p>
      <div id="matrix-grid" class="cov-matrix-wrap"><p class="placeholder">Rendering…</p></div>
    </div>` : '';

  const ploSection = (ploCov && ploCov.length) ? `
    <div class="gap-section">
      <h2>Programme outcomes</h2>
      <p class="section-sub">How many of the ${summary.total_modules} modules contribute to each BEng/MEng Computing programme-level outcome — the broader graduate competencies behind the curriculum. Click any one to see which courses address it.</p>
      <div class="gap-list">
        ${ploCov.map(p => `
          <div class="gap-item gap-item-click" data-plo="${esc(p.plo_id)}" data-title="${esc(p.code)} — ${esc(p.title)}" title="See which modules address ${esc(p.code)}">
            <span class="ka-code">${esc(p.code)}</span>
            <span class="ka-name">${esc(p.title)}</span>
            <span class="ka-cov">${p.module_count}/${summary.total_modules} modules</span>
          </div>`).join('')}
      </div>
      <div id="plo-drilldown" class="ka-drilldown hidden"></div>
    </div>` : '';

  return `
    <div class="cov-stack">
      <div class="gap-summary-cards">
        <div class="summary-card"><div class="card-val">${summary.total_modules}</div><div class="card-label">Modules</div></div>
        <div class="summary-card"><div class="card-val">${summary.total_concepts.toLocaleString()}</div><div class="card-label">Concepts extracted</div></div>
        <div class="summary-card"><div class="card-val">${summary.total_alignments.toLocaleString()}</div><div class="card-label">Mappings</div></div>
        <div class="summary-card"><div class="card-val">${pct(summary.ka_coverage_fraction)}</div><div class="card-label">KA coverage (${summary.covered_kas}/${summary.total_kas})</div></div>
        <div class="summary-card"><div class="card-val" style="color:${summary.critical_gap_count > 0 ? 'var(--danger)' : 'var(--success)'}">${summary.critical_gap_count}</div><div class="card-label">Critical gaps</div></div>
        <div class="summary-card"><div class="card-val">${summary.redundancy_count}</div><div class="card-label">Cross-cutting terms</div></div>
      </div>

      <div class="gap-section">
        <h2>Knowledge Area coverage</h2>
        <p class="section-sub">
          For each of the 18 CS2023 Knowledge Areas, the share of the ${summary.total_modules} modules that teach at least one concept aligned to it — its <em>breadth</em> across the curriculum.
          <span class="cov-key"><span class="sev-dot sev-good"></span>≥50% well covered</span>
          <span class="cov-key"><span class="sev-dot sev-warning"></span>10–49% thin</span>
          <span class="cov-key"><span class="sev-dot sev-critical"></span>&lt;10% gap</span>
        </p>
        <div class="chart-container" style="max-height:440px; overflow:hidden">
          <canvas id="coverage-chart" height="420"></canvas>
        </div>
        <p class="section-sub" style="margin:10px 0 0">Click any bar to see which modules cover that area — and which don't.</p>
        <div id="ka-drilldown" class="ka-drilldown hidden"></div>
      </div>

      ${comparisonSection}
      ${matrixSection}

      <div class="gap-section">
        <h2>Coverage gaps <span style="font-weight:400;color:var(--muted);font-size:14px">(${gaps.length})</span></h2>
        <p class="section-sub">Knowledge Areas taught by very few modules — the clearest opportunities to broaden the curriculum.</p>
        <div class="gap-list">
          ${gaps.length === 0
            ? '<p class="placeholder">No critical gaps — every Knowledge Area is taught by enough modules.</p>'
            : gaps.map(g => `
              <div class="gap-item gap-item-click" data-ka="${esc(g.ka_code)}" title="See which modules cover ${esc(g.ka_code)}">
                <div class="sev sev-${g.severity}"></div>
                <span class="ka-code">${esc(g.ka_code)}</span>
                <span class="ka-name">${esc(g.ka_name)}</span>
                <span class="ka-cov">${pct(g.coverage)}</span>
              </div>`).join('')}
        </div>
      </div>

      <div class="gap-section">
        <h2>Cross-cutting concepts <span style="font-weight:400;color:var(--muted);font-size:14px">(${redundancies.length})</span></h2>
        <p class="section-sub">Concepts that recur across many modules — foundational vocabulary that threads through the degree (not necessarily redundant).</p>
        <div class="gap-list">
          ${redundancies.length === 0
            ? '<p class="placeholder">No widely-recurring concepts detected.</p>'
            : redundancies.slice(0, 20).map(r => `
              <div class="redundancy-item">
                <div class="r-term">${esc(r.concept)} <span style="color:var(--muted);font-size:12px;font-weight:400">· in ${r.module_count} modules</span></div>
                <div class="r-mods">${esc(r.modules.join(', '))}</div>
              </div>`).join('')}
          ${redundancies.length > 20 ? `<p class="placeholder">… and ${redundancies.length - 20} more</p>` : ''}
        </div>
      </div>

      ${ploSection}
    </div>
  `;
}

function renderCoverageChart(coverage, nModules) {
  const canvas = document.getElementById('coverage-chart');
  if (!canvas) return;

  const labels = coverage.map(c => c.ka_code);
  const values = coverage.map(c => Math.round(c.coverage * 100));
  const colors = coverage.map(c =>
    c.severity === 'good' ? '#157f3d' : c.severity === 'warning' ? '#d99a00' : '#b42318'
  );

  if (_coverageChart) _coverageChart.destroy();

  _coverageChart = new Chart(canvas, {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Coverage (%)', data: values, backgroundColor: colors, borderRadius: 4, borderSkipped: false }] },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      onClick: (_evt, elements) => { if (elements.length) showDrilldown(coverage[elements[0].index].ka_code); },
      onHover: (evt, elements) => { if (evt.native) evt.native.target.style.cursor = elements.length ? 'pointer' : 'default'; },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => { const it = coverage[items[0].dataIndex]; return `${it.ka_code} — ${it.ka_name}`; },
            label: (ctx) => {
              const it = coverage[ctx.dataIndex];
              const mc = it.module_count ?? Math.round((it.coverage || 0) * (nModules || 0));
              return ` ${ctx.raw}% of modules (${mc}/${nModules})`;
            },
          },
        },
      },
      scales: {
        x: {
          min: 0, max: 100,
          title: { display: true, text: '% of modules covering the Knowledge Area', color: '#475467', font: { size: 11 } },
          ticks: { color: '#475467', callback: v => `${v}%` },
          grid: { color: '#e3e8ef' },
        },
        y: { ticks: { color: '#1b2430', font: { size: 11 } }, grid: { display: false } },
      },
    },
  });
}

// One-line summary of where two cohorts diverge most in KA breadth.
function comparisonSummary(comparison) {
  const [a, b] = comparison.cohorts;
  if (!a || !b) return '';
  const diffs = comparison.kas.map(k => ({
    code: k.code,
    d: (a.ka_coverage[k.code] || 0) - (b.ka_coverage[k.code] || 0),
  }));
  const aLeads = diffs.filter(x => x.d > 0.15).sort((x, y) => y.d - x.d).slice(0, 3).map(x => x.code);
  const bLeads = diffs.filter(x => x.d < -0.15).sort((x, y) => x.d - y.d).slice(0, 3).map(x => x.code);
  const parts = [];
  if (aLeads.length) parts.push(`${esc(a.label)} leans further into ${aLeads.join(', ')}`);
  if (bLeads.length) parts.push(`${esc(b.label)} into ${bLeads.join(', ')}`);
  return parts.length ? parts.join('; ') + '.' : 'Both cohorts cover a similar spread.';
}

// Grouped horizontal bars: per-cohort KA coverage, one colour per cohort.
function renderComparisonChart(comparison) {
  const canvas = document.getElementById('comparison-chart');
  if (!canvas) return;
  const kas = comparison.kas.map(k => k.code);
  const palette = ['#003e74', '#8a1538'];   // Imperial blue, MIT crimson
  const datasets = comparison.cohorts.map((c, i) => ({
    label: c.label,
    data: kas.map(k => Math.round((c.ka_coverage[k] || 0) * 100)),
    backgroundColor: palette[i % palette.length],
    borderRadius: 3,
    borderSkipped: false,
  }));
  if (_comparisonChart) _comparisonChart.destroy();
  _comparisonChart = new Chart(canvas, {
    type: 'bar',
    data: { labels: kas, datasets },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      onClick: (_e, els) => { if (els.length) showDrilldown(kas[els[0].index]); },
      onHover: (e, els) => { if (e.native) e.native.target.style.cursor = els.length ? 'pointer' : 'default'; },
      plugins: {
        legend: { display: true, position: 'top' },
        tooltip: { callbacks: {
          title: (items) => { const k = comparison.kas.find(x => x.code === items[0].label); return k ? `${k.code} — ${k.name}` : items[0].label; },
          label: (ctx) => ` ${ctx.dataset.label}: ${ctx.raw}% of its modules`,
        } },
      },
      scales: {
        x: { min: 0, max: 100, title: { display: true, text: "% of the cohort's modules", color: '#475467', font: { size: 11 } }, ticks: { color: '#475467', callback: v => `${v}%` }, grid: { color: '#e3e8ef' } },
        y: { ticks: { color: '#1b2430', font: { size: 11 } }, grid: { display: false } },
      },
    },
  });
}

// Module × KA heatmap grid; cell shade encodes #concepts, header/cell click
// drills into the KA. Re-rendered when the cohort filter changes.
function renderMatrix(cohortFilter) {
  const wrap = document.getElementById('matrix-grid');
  if (!wrap || !_matrix) return;
  const kas = _matrix.kas;
  const cells = _matrix.cells || {};
  let modules = _matrix.modules;
  if (cohortFilter && cohortFilter !== 'all') modules = modules.filter(m => m.cohort === cohortFilter);

  let maxC = 1;
  for (const m of modules) for (const k of kas) maxC = Math.max(maxC, (cells[m.code] || {})[k.code] || 0);

  const cell = (mcode, kcode) => {
    const v = (cells[mcode] || {})[kcode] || 0;
    const op = v ? (0.15 + 0.85 * Math.min(1, v / maxC)) : 0;
    const bg = v ? `rgba(0,62,116,${op.toFixed(2)})` : 'transparent';
    return `<div class="cm-cell" style="background:${bg}" title="${esc(mcode)} · ${esc(kcode)}: ${v} concept${v === 1 ? '' : 's'}" data-ka="${esc(kcode)}"></div>`;
  };
  const header = `<div class="cm-corner"></div>` +
    kas.map(k => `<div class="cm-kahead" data-ka="${esc(k.code)}" title="${esc(k.name)} — click to drill in">${esc(k.code)}</div>`).join('');
  const rows = modules.map(m =>
    `<div class="cm-rowlabel" title="${esc(m.title)} (Level ${m.level ?? '?'}, ${esc(m.cohort)})">${esc(m.code)}</div>` +
    kas.map(k => cell(m.code, k.code)).join('')).join('');

  wrap.innerHTML = `<div class="cov-matrix" style="grid-template-columns: 88px repeat(${kas.length}, minmax(0,1fr))">${header}${rows}</div>`;
  wrap.querySelectorAll('.cm-kahead, .cm-cell').forEach(el =>
    el.addEventListener('click', () => { if (el.dataset.ka) showDrilldown(el.dataset.ka); }));
}

// Drill-down: for one Knowledge Area, list the modules that cover it vs not —
// turning a coverage bar into an actionable "where is this taught / missing" view.
async function showDrilldown(kaCode) {
  const panel = document.getElementById('ka-drilldown');
  if (!panel) return;
  panel.classList.remove('hidden');
  panel.innerHTML = `<p class="placeholder">Loading ${esc(kaCode)}…</p>`;

  const cov = _coverage.find(c => c.ka_code === kaCode);
  const kaName = cov ? cov.ka_name : kaCode;

  let aligns;
  try {
    aligns = await api.alignments({ ka: kaCode, rank: 1, limit: 500 });
  } catch (e) {
    panel.innerHTML = `<p class="placeholder error">Failed to load ${esc(kaCode)}: ${e.message}</p>`;
    return;
  }

  const covering = new Set();
  for (const a of aligns) (a.source_modules || []).forEach(m => covering.add(m));
  const titleOf = Object.fromEntries(_allModules.map(m => [m.code, m.title]));
  const allCodes = _allModules.map(m => m.code);
  const covered = allCodes.filter(c => covering.has(c)).sort();
  const missing = allCodes.filter(c => !covering.has(c)).sort();

  const chip = (c) => `<span class="dd-mod" data-code="${esc(c)}" title="${esc(titleOf[c] || c)} — open in Explore">${esc(c)}</span>`;

  panel.innerHTML = `
    <div class="dd-head">
      <span><strong>${esc(kaCode)}</strong> — ${esc(kaName)}</span>
      <span class="dd-count">${covered.length}/${allCodes.length} modules</span>
      <button class="dd-close" id="dd-close" title="Close">✕</button>
    </div>
    <div class="dd-cols">
      <div class="dd-col">
        <h4 class="dd-col-h dd-cover">Covered by ${covered.length}</h4>
        <div class="dd-chips">${covered.length ? covered.map(chip).join('') : '<span class="dd-empty">— none —</span>'}</div>
      </div>
      <div class="dd-col">
        <h4 class="dd-col-h dd-miss">Not covered (${missing.length})</h4>
        <div class="dd-chips">${missing.length ? missing.map(chip).join('') : '<span class="dd-empty">— every module covers this —</span>'}</div>
      </div>
    </div>
  `;
  panel.querySelector('#dd-close').addEventListener('click', () => panel.classList.add('hidden'));
  panel.querySelectorAll('.dd-mod').forEach(el =>
    el.addEventListener('click', () => navigate('explore', { module: el.dataset.code })));
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Programme-outcome drill-down: list the modules that address one PLO — the
// interim §2.7.1 "clicking a programme-level outcome links to all courses that
// address it". Module chips open that module in Explore.
async function showPloDrilldown(ploId, title) {
  const panel = document.getElementById('plo-drilldown');
  if (!panel) return;
  panel.classList.remove('hidden');
  panel.innerHTML = `<p class="placeholder">Loading…</p>`;

  let mods;
  try { mods = await api.ploModules(ploId); }
  catch (e) { panel.innerHTML = `<p class="placeholder error">Failed to load: ${e.message}</p>`; return; }

  const sorted = mods.slice().sort((a, b) => String(a.code).localeCompare(String(b.code)));
  const chip = (m) => `<span class="dd-mod" data-code="${esc(m.code)}" title="${esc(m.title || m.code)} — open in Explore">${esc(m.code)}</span>`;

  panel.innerHTML = `
    <div class="dd-head">
      <span><strong>${esc(title)}</strong></span>
      <span class="dd-count">${sorted.length} module${sorted.length === 1 ? '' : 's'} address this</span>
      <button class="dd-close" id="plo-dd-close" title="Close">✕</button>
    </div>
    <div class="dd-chips">${sorted.length ? sorted.map(chip).join('') : '<span class="dd-empty">— none —</span>'}</div>
  `;
  panel.querySelector('#plo-dd-close').addEventListener('click', () => panel.classList.add('hidden'));
  panel.querySelectorAll('.dd-mod').forEach(el =>
    el.addEventListener('click', () => navigate('explore', { module: el.dataset.code })));
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function esc(str) {
  return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
