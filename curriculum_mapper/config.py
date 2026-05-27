"""Central configuration — all thresholds and paths in one place for reproducibility.

Most values are fixed (hyperparameters, thresholds) so that the pipeline produces
identical results across runs. A small set of deployment-related values
(API_HOST, API_PORT, CORS_ORIGINS, DB_PATH) may be overridden via environment
variables to support containerised deployment without code changes.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.environ.get("CURRICULUM_DB_PATH", DATA_DIR / "curriculum.db"))
STANDARDS_DIR = DATA_DIR / "raw" / "standards"
MODULES_DIR = DATA_DIR / "raw" / "modules"
CACHE_DIR = DATA_DIR / "cache"
EMBEDDING_CACHE = CACHE_DIR / "embeddings"
GRAPH_CACHE = CACHE_DIR / "graphs"
PROCESSED_DIR = DATA_DIR / "processed"
ANNOTATIONS_DIR = DATA_DIR / "annotations"
FIGURES_DIR = PROCESSED_DIR / "figures"

# Ensure critical dirs exist at import time
for _d in [DATA_DIR, CACHE_DIR, EMBEDDING_CACHE, GRAPH_CACHE, PROCESSED_DIR,
           ANNOTATIONS_DIR, FIGURES_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ── NLP Model Selection ────────────────────────────────────────────────────────
# all-MiniLM-L6-v2: 80 MB, 384-dim, 6× faster than all-mpnet-base-v2.
# Chosen per Green AI principle (Wang et al., 2020); quality gap ~5% on STS.
SBERT_MODEL = "all-MiniLM-L6-v2"
SPACY_MODEL = "en_core_web_sm"

# ── NLP Hyperparameters ────────────────────────────────────────────────────────
MAX_CONCEPTS_PER_MODULE = 50
TFIDF_TOP_N = 20
TFIDF_NGRAM_RANGE = (1, 3)
TFIDF_MIN_DF = 2
TFIDF_MAX_DF = 0.85
RAKE_MIN_WORDS = 1
RAKE_MAX_WORDS = 4
TEXTRANK_TOP_N = 20
KEYBERT_TOP_N = 15
KEYBERT_DIVERSITY = 0.7  # MMR diversity — balances relevance vs coverage

# Synonym deduplication (canonicalizer, Week 2)
SYNONYM_SIM_THRESHOLD = 0.92  # SBERT cosine above which two terms are merged
WORDNET_SIM_THRESHOLD = 0.85  # WordNet path_similarity threshold
SBERT_MATCH_THRESHOLD = 0.75  # partial-credit cosine threshold for evaluation metrics

# Extractor confidence weights (sum to 1.0; KeyBERT highest = contextual)
EXTRACTOR_WEIGHTS: dict[str, float] = {
    "tfidf": 0.15,
    "rake": 0.15,
    "textrank": 0.20,
    "keybert": 0.30,
    "bertopic": 0.20,
}

# ── Alignment Hyperparameters ──────────────────────────────────────────────────
LEXICAL_WEIGHT = 0.35
SEMANTIC_WEIGHT = 0.65
SIMILARITY_THRESHOLD = 0.35
TOP_K_ALIGNMENTS = 3
AMBIGUITY_MARGIN = 0.08  # top-2 score diff below which concept is flagged ambiguous
LEXICAL_THRESHOLD = 0.30

# ── Graph Hyperparameters ──────────────────────────────────────────────────────
SHARED_CONCEPT_EDGE_MIN = 2   # minimum shared concepts for module-module edge
REDUNDANCY_THRESHOLD = 5      # concepts appearing in >N modules flagged redundant
GAP_COVERAGE_THRESHOLD = 0.10  # KA coverage below 10% = gap

# ── API ────────────────────────────────────────────────────────────────────────
API_HOST = os.environ.get("API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("API_PORT", "8000"))

# Comma-separated list of allowed origins for CORS. Default allows local dev only.
_default_cors = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:8000,http://127.0.0.1:8000"
)
CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", _default_cors).split(",")
    if origin.strip()
]

# ── Computing-specific acronym expansion ──────────────────────────────────────
# Applied before tokenisation to prevent splitting of common abbreviations.
ACRONYM_MAP: dict[str, str] = {
    "OS": "operating system",
    "DB": "database",
    "ML": "machine learning",
    "NLP": "natural language processing",
    "AI": "artificial intelligence",
    "OOP": "object oriented programming",
    "FP": "functional programming",
    "DP": "dynamic programming",
    "BFS": "breadth first search",
    "DFS": "depth first search",
    "CPU": "central processing unit",
    "GPU": "graphics processing unit",
    "API": "application programming interface",
    "REST": "representational state transfer",
    "SQL": "structured query language",
    "TCP": "transmission control protocol",
    "UDP": "user datagram protocol",
    "IP": "internet protocol",
    "HTTP": "hypertext transfer protocol",
    "RAM": "random access memory",
    "ROM": "read only memory",
    "LRU": "least recently used",
    "MVC": "model view controller",
    "UML": "unified modelling language",
    "GCD": "greatest common divisor",
    "LCM": "least common multiple",
    "RPC": "remote procedure call",
    "IPC": "inter process communication",
    "POSIX": "portable operating system interface",
    "CISC": "complex instruction set computer",
    "RISC": "reduced instruction set computer",
    "ACM": "association for computing machinery",
    "IEEE": "institute of electrical and electronics engineers",
}

# Domain-specific stop words (supplement NLTK English stop words)
DOMAIN_STOP_WORDS: list[str] = [
    "module", "student", "students", "learning", "understand", "understanding",
    "able", "demonstrate", "knowledge", "skill", "skills", "week", "weeks",
    "lecture", "lectures", "lab", "labs", "laboratory", "course", "courses",
    "tutorial", "tutorials", "assessment", "exam", "exams", "objective",
    "objectives", "outcome", "outcomes", "aim", "aims", "introduce", "overview",
    "topic", "topics", "section", "chapter", "unit", "taught", "cover",
    "covering", "including", "included", "will", "shall", "describe",
    "explain", "apply", "analyse", "analyze", "evaluate", "create", "design",
    "implement", "use", "using", "basic", "advanced", "introduction",
    "fundamental", "fundamentals", "concept", "concepts", "theory",
    "practice", "method", "methods", "technique", "techniques",
    # Bloom's-taxonomy verbs and academic meta-words missing from original list
    "compare", "contrast", "identify", "recall", "discuss", "state",
    "outline", "list", "summarise", "summarize", "review", "present",
    "justify", "show", "prove", "verify", "select", "solve", "define",
    "produce", "extend", "modify", "trace", "construct", "write",
    "explore", "illustrate", "perform", "derive", "compute", "calculate",
    "appropriate", "suitable", "various", "required", "given", "written",
    "context", "perspective", "relationship", "relationships", "role",
    "roles", "example", "examples", "case", "cases", "process",
    "processes", "step", "steps", "result", "results", "value", "values",
]
