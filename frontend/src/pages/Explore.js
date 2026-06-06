import { initModulePanel, showModuleDetail, showConceptDetail, selectModule } from '../components/ModulePanel.js';
import { getKaOptions } from '../state.js';

/** Explore — the student's home: a master-detail browser for modules & concepts. */
export async function mountExplore(app, params = {}) {
  app.innerHTML = `
    <div class="page">
      <div class="page-head">
        <div class="eyebrow">Explore</div>
        <h2>Browse modules &amp; concepts</h2>
        <p class="lede">Search the curriculum, then open any module or concept to see its learning outcomes, the CS2023 areas it covers, its key topics, and where each concept is taught across the years.</p>
      </div>
      <div class="explore">
        <div class="browse-col">
          <div class="search-bar">
            <div class="search-mode" id="search-mode">
              <button type="button" class="sm-btn active" data-mode="modules">Modules</button>
              <button type="button" class="sm-btn" data-mode="concepts">Concepts</button>
            </div>
            <input type="text" id="module-search" placeholder="Search modules…" autocomplete="off" />
            <div class="filter-row">
              <select id="level-filter" class="filter-select" title="Filter by year/level">
                <option value="">All levels</option>
                <option value="1">Level 1</option>
                <option value="2">Level 2</option>
                <option value="3">Level 3</option>
              </select>
              <select id="programme-filter" class="filter-select" title="Filter by degree programme">
                <option value="">All programmes</option>
              </select>
            </div>
          </div>
          <div class="list-meta" id="list-meta"></div>
          <div class="module-list" id="module-list"><p class="placeholder">Loading…</p></div>
        </div>
        <div class="detail-col">
          <div id="module-detail-content">
            <div class="detail-empty">
              <div class="big">📘</div>
              <div>Select a module or concept on the left to see its details here.</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  const kaOptions = await getKaOptions().catch(() => []);
  await initModulePanel((code) => showModuleDetail(code), kaOptions);

  // Deep links: #/explore?module=IC50001  or  #/explore?concept=<id>
  if (params.module) selectModule(params.module);
  else if (params.concept) showConceptDetail(params.concept);
}
