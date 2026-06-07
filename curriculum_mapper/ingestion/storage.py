"""SQLite persistence layer.

Deliberately uses raw sqlite3 (no ORM) for simplicity and reproducibility —
the dataset (30–50 modules, ~5000 alignments) does not warrant ORM overhead.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from curriculum_mapper.config import DB_PATH
from curriculum_mapper.ingestion.schema import (
    ILO,
    AlignmentResult,
    Concept,
    ConceptPrerequisite,
    ModuleDescriptor,
    PLOAlignment,
    ProgrammeLearningOutcome,
)

# ── Schema DDL ─────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS modules (
    code            TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    level           INTEGER,
    credits         INTEGER,
    description     TEXT,
    description_clean TEXT,
    source          TEXT,
    programmes      TEXT,            -- JSON array of programme ids
    source_file     TEXT,
    ingested_at     TEXT
);

CREATE TABLE IF NOT EXISTS ilos (
    id              TEXT PRIMARY KEY,
    module_code     TEXT NOT NULL REFERENCES modules(code),
    text            TEXT,
    text_clean      TEXT,
    bloom_level     TEXT
);

CREATE TABLE IF NOT EXISTS prerequisites (
    module_code     TEXT NOT NULL REFERENCES modules(code),
    prereq_code     TEXT NOT NULL,
    PRIMARY KEY (module_code, prereq_code)
);

CREATE TABLE IF NOT EXISTS module_topics (
    module_code     TEXT NOT NULL REFERENCES modules(code),
    topic           TEXT NOT NULL,
    PRIMARY KEY (module_code, topic)
);

CREATE TABLE IF NOT EXISTS concepts (
    id              TEXT PRIMARY KEY,
    term            TEXT UNIQUE NOT NULL,
    confidence      REAL NOT NULL,
    extractors      TEXT NOT NULL,   -- JSON array
    module_codes    TEXT NOT NULL    -- JSON array
);

CREATE TABLE IF NOT EXISTS concept_variants (
    concept_id      TEXT NOT NULL REFERENCES concepts(id),
    variant         TEXT NOT NULL,
    PRIMARY KEY (concept_id, variant)
);

CREATE TABLE IF NOT EXISTS alignments (
    id              TEXT PRIMARY KEY,
    concept_id      TEXT NOT NULL REFERENCES concepts(id),
    ka_code         TEXT NOT NULL,
    ka_topic        TEXT NOT NULL,
    method          TEXT NOT NULL,
    score           REAL NOT NULL,
    rank            INTEGER NOT NULL,
    is_ambiguous    INTEGER DEFAULT 0,
    validated       INTEGER,          -- NULL / 0 / 1
    validated_by    TEXT,
    validated_at    TEXT
);

CREATE TABLE IF NOT EXISTS user_feedback (
    id              TEXT PRIMARY KEY,
    alignment_id    TEXT NOT NULL REFERENCES alignments(id),
    action          TEXT NOT NULL,    -- "accept" | "reject" | "reassign"
    new_ka_code     TEXT,
    comment         TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS concept_prerequisites (
    id              TEXT PRIMARY KEY,
    from_concept_id TEXT NOT NULL REFERENCES concepts(id),
    to_concept_id   TEXT NOT NULL REFERENCES concepts(id),
    confidence      REAL NOT NULL,
    method          TEXT NOT NULL,
    inferred        INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS programme_learning_outcomes (
    id              TEXT PRIMARY KEY,
    programme       TEXT NOT NULL,
    code            TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT
);

CREATE TABLE IF NOT EXISTS plo_alignments (
    id              TEXT PRIMARY KEY,
    module_code     TEXT NOT NULL REFERENCES modules(code),
    plo_id          TEXT NOT NULL REFERENCES programme_learning_outcomes(id),
    method          TEXT NOT NULL,
    score           REAL NOT NULL,
    rank            INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alignments_concept ON alignments(concept_id);
CREATE INDEX IF NOT EXISTS idx_alignments_ka      ON alignments(ka_code);
CREATE INDEX IF NOT EXISTS idx_concepts_term      ON concepts(term);
CREATE INDEX IF NOT EXISTS idx_ilos_module        ON ilos(module_code);
CREATE INDEX IF NOT EXISTS idx_cprereq_from       ON concept_prerequisites(from_concept_id);
CREATE INDEX IF NOT EXISTS idx_cprereq_to         ON concept_prerequisites(to_concept_id);
CREATE INDEX IF NOT EXISTS idx_plo_align_module   ON plo_alignments(module_code);
CREATE INDEX IF NOT EXISTS idx_plo_programme      ON programme_learning_outcomes(programme);
"""


# ── Connection helper ──────────────────────────────────────────────────────────


@contextmanager
def get_connection(db_path: Path = DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Storage Manager ────────────────────────────────────────────────────────────


class StorageManager:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with get_connection(self.db_path) as conn:
            conn.executescript(_DDL)
            # Additive migration: add the programmes column to pre-existing DBs
            # (CREATE TABLE IF NOT EXISTS will not alter an existing table).
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(modules)")}
            if "programmes" not in cols:
                conn.execute("ALTER TABLE modules ADD COLUMN programmes TEXT")

    # ── Modules ────────────────────────────────────────────────────────────────

    def insert_module(self, module: ModuleDescriptor) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO modules
                   (code, title, level, credits, description, description_clean,
                    source, programmes, source_file, ingested_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    module.code,
                    module.title,
                    module.level,
                    module.credits,
                    module.description,
                    module.description_clean,
                    module.source,
                    json.dumps(module.programmes),
                    module.source_file,
                    module.ingested_at.isoformat(),
                ),
            )
            # ILOs
            conn.execute("DELETE FROM ilos WHERE module_code=?", (module.code,))
            for ilo in module.ilos:
                conn.execute(
                    "INSERT OR REPLACE INTO ilos (id, module_code, text, text_clean, bloom_level) VALUES (?,?,?,?,?)",
                    (ilo.id, module.code, ilo.text, ilo.text_clean, ilo.bloom_level),
                )
            # Prerequisites
            conn.execute(
                "DELETE FROM prerequisites WHERE module_code=?", (module.code,)
            )
            for prereq in module.prerequisites:
                conn.execute(
                    "INSERT OR IGNORE INTO prerequisites (module_code, prereq_code) VALUES (?,?)",
                    (module.code, prereq),
                )
            # Topics
            conn.execute(
                "DELETE FROM module_topics WHERE module_code=?", (module.code,)
            )
            for topic in module.topics:
                conn.execute(
                    "INSERT OR IGNORE INTO module_topics (module_code, topic) VALUES (?,?)",
                    (module.code, topic),
                )

    def get_all_modules(self) -> list[ModuleDescriptor]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM modules ORDER BY level, code").fetchall()
            modules = []
            for row in rows:
                ilos = self._get_ilos(conn, row["code"])
                prereqs = self._get_prerequisites(conn, row["code"])
                topics = self._get_topics(conn, row["code"])
                modules.append(
                    ModuleDescriptor(
                        code=row["code"],
                        title=row["title"],
                        level=row["level"] or 1,
                        credits=row["credits"] or 0,
                        prerequisites=prereqs,
                        description=row["description"] or "",
                        description_clean=row["description_clean"] or "",
                        ilos=ilos,
                        topics=topics,
                        source=row["source"] or "",
                        programmes=json.loads(row["programmes"]) if row["programmes"] else ["beng_computing"],
                        source_file=row["source_file"] or "",
                        ingested_at=datetime.fromisoformat(
                            row["ingested_at"] or datetime.utcnow().isoformat()
                        ),
                    )
                )
            return modules

    def get_module(self, code: str) -> Optional[ModuleDescriptor]:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM modules WHERE code=?", (code,)
            ).fetchone()
            if not row:
                return None
            ilos = self._get_ilos(conn, code)
            prereqs = self._get_prerequisites(conn, code)
            topics = self._get_topics(conn, code)
            return ModuleDescriptor(
                code=row["code"],
                title=row["title"],
                level=row["level"] or 1,
                credits=row["credits"] or 0,
                prerequisites=prereqs,
                description=row["description"] or "",
                description_clean=row["description_clean"] or "",
                ilos=ilos,
                topics=topics,
                source=row["source"] or "",
                programmes=json.loads(row["programmes"]) if row["programmes"] else ["beng_computing"],
                source_file=row["source_file"] or "",
                ingested_at=datetime.fromisoformat(
                    row["ingested_at"] or datetime.utcnow().isoformat()
                ),
            )

    def count_modules(self) -> int:
        with get_connection(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0]

    def _get_ilos(self, conn: sqlite3.Connection, module_code: str) -> list[ILO]:
        rows = conn.execute(
            "SELECT * FROM ilos WHERE module_code=? ORDER BY id", (module_code,)
        ).fetchall()
        return [
            ILO(
                id=r["id"],
                text=r["text"] or "",
                text_clean=r["text_clean"] or "",
                bloom_level=r["bloom_level"],
            )
            for r in rows
        ]

    def _get_prerequisites(self, conn: sqlite3.Connection, module_code: str) -> list[str]:
        rows = conn.execute(
            "SELECT prereq_code FROM prerequisites WHERE module_code=?", (module_code,)
        ).fetchall()
        return [r["prereq_code"] for r in rows]

    def _get_topics(self, conn: sqlite3.Connection, module_code: str) -> list[str]:
        rows = conn.execute(
            "SELECT topic FROM module_topics WHERE module_code=?", (module_code,)
        ).fetchall()
        return [r["topic"] for r in rows]

    # ── Concepts ───────────────────────────────────────────────────────────────

    def insert_concept(self, concept: Concept) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO concepts
                   (id, term, confidence, extractors, module_codes)
                   VALUES (?,?,?,?,?)""",
                (
                    concept.id,
                    concept.term,
                    concept.confidence,
                    json.dumps(concept.extractors),
                    json.dumps(concept.module_codes),
                ),
            )
            for variant in concept.variants:
                conn.execute(
                    "INSERT OR IGNORE INTO concept_variants (concept_id, variant) VALUES (?,?)",
                    (concept.id, variant),
                )

    def get_all_concepts(self) -> list[Concept]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT c.*, GROUP_CONCAT(cv.variant) as vars FROM concepts c "
                "LEFT JOIN concept_variants cv ON c.id=cv.concept_id "
                "GROUP BY c.id ORDER BY c.confidence DESC"
            ).fetchall()
            return [
                Concept(
                    id=r["id"],
                    term=r["term"],
                    confidence=r["confidence"],
                    extractors=json.loads(r["extractors"]),
                    module_codes=json.loads(r["module_codes"]),
                    variants=r["vars"].split(",") if r["vars"] else [],
                )
                for r in rows
            ]

    def count_concepts(self) -> int:
        with get_connection(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]

    # ── Alignments ─────────────────────────────────────────────────────────────

    def insert_alignment(self, alignment: AlignmentResult) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO alignments
                   (id, concept_id, ka_code, ka_topic, method, score, rank,
                    is_ambiguous, validated, validated_by, validated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    alignment.id,
                    alignment.concept_id,
                    alignment.ka_code,
                    alignment.ka_topic,
                    alignment.method,
                    alignment.score,
                    alignment.rank,
                    int(alignment.is_ambiguous),
                    None if alignment.validated is None else int(alignment.validated),
                    alignment.validated_by,
                    alignment.validated_at.isoformat() if alignment.validated_at else None,
                ),
            )

    def count_alignments(self) -> int:
        with get_connection(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM alignments").fetchone()[0]

    def get_all_alignments(self) -> list[AlignmentResult]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM alignments ORDER BY concept_id, rank"
            ).fetchall()
            return [
                AlignmentResult(
                    id=r["id"],
                    concept_id=r["concept_id"],
                    ka_code=r["ka_code"],
                    ka_topic=r["ka_topic"],
                    method=r["method"],
                    score=r["score"],
                    rank=r["rank"],
                    is_ambiguous=bool(r["is_ambiguous"]),
                    validated=None if r["validated"] is None else bool(r["validated"]),
                    validated_by=r["validated_by"],
                )
                for r in rows
            ]

    def get_best_alignments_per_concept(self) -> dict[str, AlignmentResult]:
        """Return {concept_id: AlignmentResult} for rank-1 alignments only."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM alignments WHERE rank=1 ORDER BY score DESC"
            ).fetchall()
            return {
                r["concept_id"]: AlignmentResult(
                    id=r["id"],
                    concept_id=r["concept_id"],
                    ka_code=r["ka_code"],
                    ka_topic=r["ka_topic"],
                    method=r["method"],
                    score=r["score"],
                    rank=r["rank"],
                    is_ambiguous=bool(r["is_ambiguous"]),
                    validated=None if r["validated"] is None else bool(r["validated"]),
                    validated_by=r["validated_by"],
                )
                for r in rows
            }

    def clear_concepts(self) -> None:
        """Remove all concepts and alignments (re-run pipeline without re-ingesting)."""
        with get_connection(self.db_path) as conn:
            conn.execute("DELETE FROM user_feedback")
            conn.execute("DELETE FROM alignments")
            conn.execute("DELETE FROM concept_variants")
            # concept_prerequisites also FK-references concepts; clear it before
            # the concepts themselves so a re-run doesn't hit a FK constraint.
            conn.execute("DELETE FROM concept_prerequisites")
            conn.execute("DELETE FROM concepts")

    def replace_prerequisites(self, edges: list[tuple[str, str]]) -> None:
        """Replace all module prerequisite rows. ``edges`` = [(prereq_code, module_code)].

        Used to persist the algorithmically-inferred module prerequisites (the
        Department publishes none) so the trace, by-year and graph views use them.
        """
        with get_connection(self.db_path) as conn:
            conn.execute("DELETE FROM prerequisites")
            conn.executemany(
                "INSERT OR IGNORE INTO prerequisites (module_code, prereq_code) VALUES (?, ?)",
                [(module, prereq) for prereq, module in edges],
            )

    def clear_alignments(self) -> None:
        """Remove all alignments (so re-running alignment alone is idempotent)."""
        with get_connection(self.db_path) as conn:
            conn.execute("DELETE FROM user_feedback")
            conn.execute("DELETE FROM alignments")

    # ── Concept prerequisites (directed concept graph) ──────────────────────────

    def insert_concept_prerequisite(self, edge: ConceptPrerequisite) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO concept_prerequisites
                   (id, from_concept_id, to_concept_id, confidence, method, inferred)
                   VALUES (?,?,?,?,?,?)""",
                (edge.id, edge.from_concept_id, edge.to_concept_id,
                 edge.confidence, edge.method, int(edge.inferred)),
            )

    def get_concept_prerequisites(self) -> list[ConceptPrerequisite]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM concept_prerequisites").fetchall()
            return [
                ConceptPrerequisite(
                    id=r["id"],
                    from_concept_id=r["from_concept_id"],
                    to_concept_id=r["to_concept_id"],
                    confidence=r["confidence"],
                    method=r["method"],
                    inferred=bool(r["inferred"]),
                )
                for r in rows
            ]

    def clear_concept_prerequisites(self) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute("DELETE FROM concept_prerequisites")

    # ── Programme-level outcomes (PLOs) ────────────────────────────────────────

    def insert_plo(self, plo: ProgrammeLearningOutcome) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO programme_learning_outcomes
                   (id, programme, code, title, description) VALUES (?,?,?,?,?)""",
                (plo.id, plo.programme, plo.code, plo.title, plo.description),
            )

    def get_plos(self, programme: str | None = None) -> list[ProgrammeLearningOutcome]:
        with get_connection(self.db_path) as conn:
            if programme:
                rows = conn.execute(
                    "SELECT * FROM programme_learning_outcomes WHERE programme=? ORDER BY code",
                    (programme,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM programme_learning_outcomes ORDER BY programme, code"
                ).fetchall()
            return [
                ProgrammeLearningOutcome(
                    id=r["id"], programme=r["programme"], code=r["code"],
                    title=r["title"], description=r["description"] or "",
                )
                for r in rows
            ]

    def insert_plo_alignment(self, alignment: PLOAlignment) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO plo_alignments
                   (id, module_code, plo_id, method, score, rank) VALUES (?,?,?,?,?,?)""",
                (alignment.id, alignment.module_code, alignment.plo_id,
                 alignment.method, alignment.score, alignment.rank),
            )

    def get_plo_alignments(self) -> list[PLOAlignment]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM plo_alignments ORDER BY module_code, rank"
            ).fetchall()
            return [
                PLOAlignment(
                    id=r["id"], module_code=r["module_code"], plo_id=r["plo_id"],
                    method=r["method"], score=r["score"], rank=r["rank"],
                )
                for r in rows
            ]

    def clear_plos(self) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute("DELETE FROM plo_alignments")
            conn.execute("DELETE FROM programme_learning_outcomes")
