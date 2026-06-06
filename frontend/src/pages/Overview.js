import { api } from '../api.js';

// Decorative little node–edge graph for the Map hero (purely illustrative).
const MAP_ART = `
  <svg width="190" height="140" viewBox="0 0 190 140" fill="none" xmlns="http://www.w3.org/2000/svg">
    <g stroke="rgba(255,255,255,.40)" stroke-width="2">
      <line x1="34" y1="46" x2="92" y2="26"/>
      <line x1="92" y1="26" x2="152" y2="44"/>
      <line x1="34" y1="46" x2="60" y2="100"/>
      <line x1="92" y1="26" x2="116" y2="106"/>
      <line x1="60" y1="100" x2="116" y2="106"/>
      <line x1="152" y1="44" x2="116" y2="106"/>
    </g>
    <g fill="#ffffff">
      <circle cx="34" cy="46" r="9"/>
      <circle cx="92" cy="26" r="12"/>
      <circle cx="152" cy="44" r="8"/>
      <circle cx="60" cy="100" r="7"/>
      <circle cx="116" cy="106" r="10"/>
    </g>
    <circle cx="152" cy="44" r="8" fill="#9fd0ff"/>
    <circle cx="60" cy="100" r="7" fill="#9fd0ff"/>
  </svg>`;

/** Overview — the welcoming landing page and home: headline numbers, a prominent
 *  Curriculum Map call-to-action, quick links, and an at-a-glance summary. */
export async function mountOverview(app) {
  app.innerHTML = `<div class="page"><p class="placeholder">Loading…</p></div>`;

  let summary, coverage, programmes;
  try {
    [summary, coverage, programmes] = await Promise.all([
      api.summary(),
      api.coverage(),
      api.programmes().catch(() => []),
    ]);
  } catch (e) {
    app.innerHTML = `<div class="page"><p class="placeholder error">Could not reach the API: ${e.message}</p></div>`;
    return;
  }

  const sorted = [...coverage].sort((a, b) => b.coverage - a.coverage);
  const best = sorted.slice(0, 4);
  const thin = sorted.slice(-3).reverse();
  const pct = (n) => `${Math.round(n * 100)}%`;
  const swatch = (sev) => sev === 'good' ? '#157f3d' : sev === 'warning' ? '#d99a00' : '#b42318';

  const hasMit = (programmes || []).some(p => /mit|opencourseware/i.test(p.id + ' ' + p.name));
  const sourcesPhrase = hasMit
    ? `Imperial Computing module descriptors — alongside a comparison set of MIT OpenCourseWare courses —`
    : `Imperial Computing module descriptors`;
  const progLine = (programmes && programmes.length)
    ? `Currently showing <strong>${programmes.map(p => esc(p.name)).join(' · ')}</strong>. Use the filters on the Curriculum Map to narrow by programme or year.`
    : `Imperial College Computing, Years 1–3.`;

  const card = (href, icon, title, desc) => `
    <a class="action-card" href="${href}">
      <div class="ac-icon">${icon}</div>
      <div class="ac-title">${title}</div>
      <div class="ac-desc">${desc}</div>
      <div class="ac-go">Open →</div>
    </a>`;

  const chip = (c) => `<span class="theme-chip"><span class="swatch" style="background:${swatch(c.severity)}"></span>${esc(c.ka_name)} <strong style="color:var(--muted);font-weight:600">${pct(c.coverage)}</strong></span>`;

  app.innerHTML = `
    <div class="page">
      <div class="hero">
        <div class="eyebrow">AI Curriculum Mapper</div>
        <h2>See how the <span class="accent">Computing curriculum</span> fits together</h2>
        <p>This tool reads ${sourcesPhrase} and maps them to the 18 ACM/IEEE CS2023 Knowledge Areas — so students and staff can explore what's taught, how topics build on each other, and where coverage is thin. Every mapping is a reviewable AI suggestion.</p>
        <div class="context-line">${progLine}</div>
      </div>

      <a class="map-hero" href="#/map">
        <div class="mh-text">
          <div class="mh-eyebrow">The curriculum, mapped</div>
          <h3>Open the Curriculum Map</h3>
          <p>The heart of the tool: an interactive graph of how modules relate and how concepts build on one another. Switch views, filter by programme or year, and trace any prerequisite chain.</p>
          <span class="mh-cta">Open the map →</span>
        </div>
        <div class="mh-art" aria-hidden="true">${MAP_ART}</div>
      </a>

      <div class="stat-row">
        <div class="stat"><div class="num">${summary.total_modules}</div><div class="lbl">Modules mapped</div></div>
        <div class="stat"><div class="num">${summary.total_concepts.toLocaleString()}</div><div class="lbl">Concepts extracted</div></div>
        <div class="stat"><div class="num">${summary.covered_kas}/${summary.total_kas}</div><div class="lbl">Knowledge Areas covered</div></div>
        <div class="stat"><div class="num">${summary.total_alignments.toLocaleString()}</div><div class="lbl">Concept → CS2023 mappings</div></div>
      </div>

      <div class="section-title">Or jump straight to…</div>
      <div class="action-grid">
        ${card('#/explore', '🔍', 'Explore modules &amp; concepts', "Search any module or concept and see its learning outcomes, key topics, and where each idea is taught across the years.")}
        ${card('#/coverage', '📊', 'Check coverage &amp; gaps', 'How well each CS2023 Knowledge Area and programme outcome is covered — with the thinnest areas highlighted.')}
        ${card('#/review', '✓', 'Review mappings <span style="font-weight:400;color:var(--muted)">(educators)</span>', "Validate the AI's suggestions: accept, reject or reassign any mapping. Every change is undoable.")}
      </div>

      <div class="section-title">Curriculum at a glance</div>
      <div class="glance-grid">
        <div class="card card-pad">
          <h3 style="font-size:13px;font-weight:700;color:var(--text);margin-bottom:10px">Best-covered Knowledge Areas</h3>
          <div class="theme-chips">${best.map(chip).join('')}</div>
        </div>
        <div class="card card-pad">
          <h3 style="font-size:13px;font-weight:700;color:var(--text);margin-bottom:10px">Where coverage is thinnest</h3>
          <div class="theme-chips">${thin.map(chip).join('')}</div>
          <p class="section-sub" style="margin:12px 0 0"><a href="#/coverage">See the full coverage report →</a></p>
        </div>
      </div>
    </div>
  `;
}

function esc(str) {
  return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
