import { Chart, BarController, BarElement, CategoryScale, LinearScale, Tooltip, Legend } from 'chart.js';
import { api } from '../api.js';
import { selectModule } from './ModulePanel.js';

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip, Legend);

let _coverageChart = null;
let _allModules = [];   // full module set (for the "not covered" side of a drill-down)
let _coverage = [];     // last-loaded coverage rows (for KA names in the drill-down)

export async function initGapReport() {
  const container = document.getElementById('gap-report-container');
  container.innerHTML = '<p class="placeholder">Loading gap report…</p>';

  try {
    const [summary, coverage, gaps, redundancies, modules] = await Promise.all([
      api.summary(),
      api.coverage(),
      api.gaps(),
      api.redundancies(),
      api.modules({ limit: 100 }),
    ]);
    _allModules = modules;
    _coverage = coverage;

    container.innerHTML = buildHTML(summary, coverage, gaps, redundancies);
    renderCoverageChart(coverage, summary.total_modules);

    // Any KA (a chart bar or a gap row) drills down to which modules cover it.
    container.querySelectorAll('.gap-item[data-ka]').forEach(el =>
      el.addEventListener('click', () => showDrilldown(el.dataset.ka)));
  } catch (e) {
    container.innerHTML = `<p class="placeholder" style="color:#f87171">Failed to load: ${e.message}</p>`;
  }
}

function buildHTML(summary, coverage, gaps, redundancies) {
  const pct = (n) => `${(n * 100).toFixed(1)}%`;

  return `
    <div class="gap-summary-cards">
      <div class="summary-card">
        <div class="card-val">${summary.total_modules}</div>
        <div class="card-label">Modules</div>
      </div>
      <div class="summary-card">
        <div class="card-val">${summary.total_concepts.toLocaleString()}</div>
        <div class="card-label">Concepts extracted</div>
      </div>
      <div class="summary-card">
        <div class="card-val">${summary.total_alignments.toLocaleString()}</div>
        <div class="card-label">Alignments</div>
      </div>
      <div class="summary-card">
        <div class="card-val">${pct(summary.ka_coverage_fraction)}</div>
        <div class="card-label">KA coverage (${summary.covered_kas}/${summary.total_kas})</div>
      </div>
      <div class="summary-card">
        <div class="card-val" style="color:${summary.critical_gap_count > 0 ? '#f87171' : '#34d399'}">${summary.critical_gap_count}</div>
        <div class="card-label">Critical gaps</div>
      </div>
      <div class="summary-card">
        <div class="card-val">${summary.redundancy_count}</div>
        <div class="card-label">Redundancies</div>
      </div>
    </div>

    <div class="gap-section">
      <h2>Knowledge Area Coverage</h2>
      <p class="section-sub">
        For each of the 18 CS2023 Knowledge Areas, the share of the ${summary.total_modules} modules
        that teach at least one concept aligned to it (its <em>breadth</em> across the curriculum).
        <span class="cov-key"><span class="sev-dot sev-good"></span>≥50% well covered</span>
        <span class="cov-key"><span class="sev-dot sev-warning"></span>10–49% thin</span>
        <span class="cov-key"><span class="sev-dot sev-critical"></span>&lt;10% gap</span>
      </p>
      <div class="chart-container" style="max-height:420px; overflow:hidden">
        <canvas id="coverage-chart" height="400"></canvas>
      </div>
      <p class="section-sub" style="margin-top:6px">Click any bar to see which modules cover it.</p>
      <div id="ka-drilldown" class="ka-drilldown hidden"></div>
    </div>

    <div class="gap-section">
      <h2>Coverage Gaps (${gaps.length})</h2>
      <div class="gap-list">
        ${gaps.length === 0
          ? '<p class="placeholder">No gaps — great curriculum coverage!</p>'
          : gaps.map(g => `
            <div class="gap-item gap-item-click" data-ka="${g.ka_code}" title="See which modules cover ${g.ka_code}">
              <div class="sev sev-${g.severity}"></div>
              <span class="ka-code">${g.ka_code}</span>
              <span class="ka-name">${g.ka_name}</span>
              <span class="ka-cov">${pct(g.coverage)}</span>
            </div>
          `).join('')}
      </div>
    </div>

    <div class="gap-section">
      <h2>Concept Redundancies (${redundancies.length})</h2>
      <div class="gap-list">
        ${redundancies.length === 0
          ? '<p class="placeholder">No redundancies detected.</p>'
          : redundancies.slice(0, 20).map(r => `
            <div class="redundancy-item">
              <div class="r-term">${r.concept} <span style="color:#64748b; font-size:11px; font-weight:400">× ${r.module_count} modules</span></div>
              <div class="r-mods">${r.modules.join(', ')}</div>
            </div>
          `).join('')}
        ${redundancies.length > 20 ? `<p class="placeholder">… and ${redundancies.length - 20} more</p>` : ''}
      </div>
    </div>
  `;
}

function renderCoverageChart(coverage, nModules) {
  const canvas = document.getElementById('coverage-chart');
  if (!canvas) return;

  // Sort by coverage descending (already sorted from API)
  const labels = coverage.map(c => c.ka_code);
  const values = coverage.map(c => Math.round(c.coverage * 100));
  const colors = coverage.map(c =>
    c.severity === 'good' ? '#34d399' :
    c.severity === 'warning' ? '#fbbf24' : '#f87171'
  );

  if (_coverageChart) _coverageChart.destroy();

  _coverageChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Coverage (%)',
        data: values,
        backgroundColor: colors,
        borderRadius: 3,
        borderSkipped: false,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      onClick: (_evt, elements) => {
        if (elements.length) showDrilldown(coverage[elements[0].index].ka_code);
      },
      onHover: (evt, elements) => {
        if (evt.native) evt.native.target.style.cursor = elements.length ? 'pointer' : 'default';
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => {
              const item = coverage[items[0].dataIndex];
              return `${item.ka_code} — ${item.ka_name}`;
            },
            label: (ctx) => {
              const item = coverage[ctx.dataIndex];
              const mc = item.module_count ?? Math.round((item.coverage || 0) * (nModules || 0));
              return ` ${ctx.raw}% of modules (${mc}/${nModules})`;
            },
          },
        },
      },
      scales: {
        x: {
          min: 0, max: 100,
          title: { display: true, text: '% of modules covering the Knowledge Area', color: '#64748b', font: { size: 11 } },
          ticks: { color: '#64748b', callback: v => `${v}%` },
          grid: { color: '#2e3350' },
        },
        y: {
          ticks: { color: '#94a3b8', font: { size: 11 } },
          grid: { display: false },
        },
      },
    },
  });
}

// Drill-down: for one Knowledge Area, list the modules that cover it (a concept
// primarily aligned to it) vs the modules that do not — turning the coverage bar
// into an actionable "where is this taught / where is it missing" view. Module
// chips are clickable and open that module in the persistent detail panel.
async function showDrilldown(kaCode) {
  const panel = document.getElementById('ka-drilldown');
  if (!panel) return;
  panel.classList.remove('hidden');
  panel.innerHTML = `<p class="placeholder">Loading ${escAttr(kaCode)}…</p>`;

  const cov = _coverage.find(c => c.ka_code === kaCode);
  const kaName = cov ? cov.ka_name : kaCode;

  let aligns;
  try {
    aligns = await api.alignments({ ka: kaCode, rank: 1, limit: 500 });
  } catch (e) {
    panel.innerHTML = `<p class="placeholder" style="color:#f87171">Failed to load ${escAttr(kaCode)}: ${e.message}</p>`;
    return;
  }

  const covering = new Set();
  for (const a of aligns) (a.source_modules || []).forEach(m => covering.add(m));
  const titleOf = Object.fromEntries(_allModules.map(m => [m.code, m.title]));
  const allCodes = _allModules.map(m => m.code);
  const covered = allCodes.filter(c => covering.has(c)).sort();
  const missing = allCodes.filter(c => !covering.has(c)).sort();

  const chip = (c) => `<span class="dd-mod" data-code="${escAttr(c)}" title="${escAttr(titleOf[c] || c)} — open">${escAttr(c)}</span>`;

  panel.innerHTML = `
    <div class="dd-head">
      <span><strong>${escAttr(kaCode)}</strong> — ${escAttr(kaName)}</span>
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
    el.addEventListener('click', () => selectModule(el.dataset.code)));
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function escAttr(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
