# Contributing

This is an academic project (Imperial College London BEng Final Year Project) so
external contributions are not actively sought, but the codebase is structured to
make extension straightforward should anyone wish to fork it.

## Development setup

```bash
make setup       # Python venv + spaCy + NLTK + npm install
make pipeline    # End-to-end NLP + alignment + graph build
make test        # All 343 tests
make lint        # Ruff + Black checks
```

## Code style

- Python: Black (line length 88) + Ruff (rules `E,F,W,I`). `make format` autofixes.
- Type hints required on public functions. Pydantic v2 models at API boundaries.
- Tests required for any new logic — aim to keep total line coverage at or above 80%.

## Adding a new concept extractor

1. Create `curriculum_mapper/nlp/extractors/your_extractor.py` implementing the
   interface in `base_extractor.py` (a `extract(text: str) -> list[Concept]` method).
2. Register it in `curriculum_mapper/nlp/pipeline.py` and add a weight in
   `EXTRACTOR_WEIGHTS` in `config.py`.
3. Add unit tests in `tests/unit/test_<your_extractor>.py`.
4. Re-run `make pipeline && make evaluate` to refresh metrics.

## Adding a new aligner

1. Subclass / mirror `curriculum_mapper/alignment/lexical.py` or `semantic.py`.
2. Update `hybrid.py` to combine the new score, or register a new aligner class.
3. Add comparison data to the aligner benchmark in
   `curriculum_mapper/evaluation/benchmarks.py`.

## Reporting issues

Open a GitHub issue with: the command run, the error message, the Python version,
and (if relevant) the contents of `data/curriculum.db` schema (`sqlite3 data/curriculum.db .schema`).
