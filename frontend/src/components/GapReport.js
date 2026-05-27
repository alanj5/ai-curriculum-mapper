import { Chart, BarController, BarElement, CategoryScale, LinearScale, Tooltip, Legend } from 'chart.js';
import { api } from '../api.js';

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip, Legend);

let _coverageChart = null;

export async function initGapReport() {
  const container = document.getElementById('gap-report-container');
  container.innerHTML = '<p class="placeholder">Loading gap report…</p>';

  try {
    const [summary, coverage, gaps, redundancies] = await Promise.all([
      api.summary(),
      api.coverage(),
      api.gaps(),
      api.redundancies(),
    ]);

    container.innerHTML = buildHTML(summary, coverage, gaps, redundancies);
    renderCoverageChart(coverage);
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
      <h2>KA Coverage Heatmap</h2>
      <div class="chart-container" style="max-height:400px; overflow:hidden">
        <canvas id="coverage-chart" height="380"></canvas>
      </div>
    </div>

    <div class="gap-section">
      <h2>Coverage Gaps (${gaps.length})</h2>
      <div class="gap-list">
        ${gaps.length === 0
          ? '<p class="placeholder">No gaps — great curriculum coverage!</p>'
          : gaps.map(g => `
            <div class="gap-item">
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

function renderCoverageChart(coverage) {
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
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const item = coverage[ctx.dataIndex];
              return ` ${ctx.raw}% — ${item.ka_name}`;
            },
          },
        },
      },
      scales: {
        x: {
          min: 0, max: 100,
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
