import { initAlignmentTable, reviewModuleAlignments } from '../components/AlignmentTable.js';
import { getKaOptions } from '../state.js';

/** Review — the educator workspace for validating the AI's suggested mappings.
 *  Kept separate from Explore so students get a clean, read-only experience. */
export async function mountReview(app, params = {}) {
  app.innerHTML = `
    <div class="page page-wide">
      <div class="page-head">
        <div class="eyebrow">Review · for educators</div>
        <h2>Validate the AI's mappings</h2>
        <p class="lede">Each row is the system's top CS2023 suggestion for one extracted concept. Confirm, correct or reassign any of them — you have the final say, and every change is undoable.</p>
      </div>

      <div class="review-intro">
        <span class="ri-icon">🧑‍🏫</span>
        <div>These are <strong>decision-support suggestions</strong>, never automatic decisions. Use <strong>✓ accept</strong>, <strong>✗ reject</strong> or <strong>↩ reassign</strong> on any row; an accept/reject can be undone for five seconds, and reassignments are logged with an optional comment.</div>
      </div>

      <div class="alignment-controls">
        <select id="ka-filter"><option value="">All Knowledge Areas</option></select>
        <select id="ambiguous-filter">
          <option value="">All confidence levels</option>
          <option value="true">Ambiguous only</option>
          <option value="false">Unambiguous only</option>
        </select>
        <select id="validated-filter">
          <option value="">Any review status</option>
          <option value="true">Accepted</option>
          <option value="false">Rejected</option>
          <option value="null">Not yet reviewed</option>
        </select>
      </div>

      <div id="alignment-table-container"><p class="placeholder">Loading mappings…</p></div>
    </div>
  `;

  const kaOptions = await getKaOptions().catch(() => []);
  // Set the (module) scope before init so the first render is already correct;
  // passing null clears any scope left over from a previous visit.
  reviewModuleAlignments(params.module || null);
  await initAlignmentTable(kaOptions);
}
