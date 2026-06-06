import { initGapReport } from '../components/GapReport.js';

/** Coverage — how well the curriculum covers the CS2023 Knowledge Areas and
 *  programme outcomes, with the gaps surfaced. */
export async function mountCoverage(app) {
  app.innerHTML = `
    <div class="page">
      <div class="page-head">
        <div class="eyebrow">Coverage</div>
        <h2>Curriculum coverage &amp; gaps</h2>
        <p class="lede">A bird's-eye view of how the curriculum maps onto the 18 ACM/IEEE CS2023 Knowledge Areas and the programme-level outcomes — and where coverage is thin.</p>
      </div>
      <div id="gap-report-container"><p class="placeholder">Loading coverage…</p></div>
    </div>
  `;
  await initGapReport();
}
