// Shared display-only heuristic for suppressing ILO sentence-fragments that
// survive extraction (e.g. "processing unit using", "problems formulate
// algorithmic abstractions"). Used by both the concept panel and the bipartite
// graph so they stay consistent. The underlying extracted data, the database,
// and all reported figures are unchanged — this only affects what is shown.
//
// A term is treated as a fragment only when it has 3+ words AND contains a clear
// ILO action-verb, so noun-phrase concepts ("design patterns", "abstract data
// types", "dynamic programming", "machine learning") are always kept.
const FRAGMENT_VERBS = new Set([
  'study', 'studying', 'formulate', 'formulating', 'formalise', 'formalize',
  'formalising', 'formalizing', 'develop', 'developing', 'connect', 'connecting',
  'evaluate', 'evaluating', 'demonstrate', 'demonstrating', 'apply', 'applying',
  'implement', 'implementing', 'describe', 'describing', 'explain', 'explaining',
  'understand', 'understanding', 'identify', 'identifying', 'construct', 'constructing',
  'derive', 'deriving', 'illustrate', 'illustrating', 'compare', 'comparing',
  'assess', 'assessing', 'discuss', 'discussing', 'examine', 'examining',
  'investigate', 'investigating', 'produce', 'producing', 'enable', 'enabling',
  'provide', 'providing', 'recognise', 'recognize', 'perform', 'performing',
  'analyse', 'analyze', 'create', 'creating', 'characterise', 'characterize',
  'manipulate', 'calculate', 'calculating', 'solve', 'solving', 'determine',
  'select', 'selecting', 'choose', 'summarise', 'summarize', 'interpret',
  'modify', 'classify', 'explore', 'exploring', 'prove', 'simulate', 'write',
  'present', 'outline', 'predict', 'estimate', 'validate', 'verify', 'define',
  'defining', 'distinguish', 'employ', 'utilise', 'utilize', 'justify',
  'critique', 'synthesise', 'synthesize', 'generalise', 'generalize',
  'deduce', 'infer', 'acquire', 'master', 'appreciate', 'gain',
  'use', 'using', 'uses',
]);

export function isLikelyFragment(term) {
  const tokens = String(term).toLowerCase().split(/\s+/).filter(Boolean);
  if (tokens.length < 3) return false;
  return tokens.some(t => FRAGMENT_VERBS.has(t));
}
