# Gold-Standard Annotation Guideline

This guideline defines how the gold concept→Knowledge-Area annotations in
`gold_concepts.json` are produced, so that (a) the set can be expanded
consistently and (b) a second annotator can replicate it for an inter-annotator
agreement (Cohen's κ) measurement.

## Unit of annotation
One **module** at a time. For each module, list the **key computing concepts** a
student should know after completing it, and tag each with its single best
**ACM/IEEE CS2023 Knowledge Area (KA)** code.

## Sources to read (and only these)
For each module, read its Imperial descriptor page — the **Module aims**,
**Learning outcomes**, and **Module syllabus** sections (the same fields the
pipeline ingests, plus the syllabus topics). Do **not** use outside knowledge of
how the module is "really" taught; annotate what the descriptor states, so the
gold set measures alignment to the *published* curriculum.

## What counts as a concept
- A concrete computing **topic / technique / artefact**: e.g. *dynamic
  programming*, *virtual memory*, *relational schema*, *gradient descent*.
- Prefer the **canonical name** of the concept over the descriptor's exact
  phrasing (matching uses SBERT partial credit ≥ 0.75, so *quicksort* ≈ *quick
  sort algorithm*).
- Aim for roughly **12–20 concepts per module** — the ones a knowledgeable peer
  would call the module's core content.

### What is NOT a concept (exclude)
- Generic academic/skills verbs and nouns: *analysis*, *design*, *evaluation*,
  *understanding*, *coursework*, *group work*, *report writing*.
- Assessment/logistics: *exam*, *50% coursework*, *lab*, *tutorial*.
- Whole sub-disciplines used as filler (*computer science*, *programming*) unless
  the module is genuinely an introduction to exactly that.

## Choosing the Knowledge Area
Assign the **one** KA that best matches the concept's primary home in CS2023
(the 18 KAs are listed in Appendix A.2 of the report / `data/raw/standards/cs2023_ka.json`).
- If a concept plausibly fits two KAs, pick the **more specific** one (e.g.
  *page replacement* → **OS**, not **SF**).
- Record genuinely cross-cutting cases in the notes; do not split one concept
  across two KAs.

## Module sampling (for expanding the set)
Choose modules to span **all four years** and the main **sub-areas** (theory,
systems, programming/SE, data/AI, HCI/graphics, security). Target a representative
subset of the 69 modules for the gold set (the committed reference set annotates 5).

## Inter-annotator agreement (Cohen's κ)
A **second annotator** independently labels the KA for a random subset of
already-listed concept terms (terms shared, KA blank). Agreement is computed on
the shared terms:

```bash
# 1. emit a blank sheet for the first N gold modules
python scripts/make_annotation_sheet.py --modules 4 --out second_annotator.csv
# 2. second annotator fills the KA column, then:
python scripts/make_annotation_sheet.py --score second_annotator.csv   # prints Cohen's κ
```

Report κ in the evaluation chapter (κ ≥ 0.6 substantial, ≥ 0.8 near-perfect).
Adjudicate disagreements into the reference set and note the adjudication rule.

## Recording
Append to `gold_concepts.json` in the existing format:

```json
"IC50005": {
  "module_title": "...",
  "concepts": [ {"term": "concept name", "ka": "KA"}, ... ]
}
```

Update `_metadata.modules_annotated` and re-run `python scripts/run_evaluation.py`
to refresh all gold-based metrics (F1@k, MAP, alignment Top-1/3, per-KA, error
analysis). Treat the committed run as the single reference run and reconcile the
report's numbers in one pass.
