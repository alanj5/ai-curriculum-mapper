"""Graph-structure validation (interim §4.4).

Three diagnostics on the module-module curriculum graph, beyond the headline
counts already reported:

  * **Community ↔ level agreement** — do the Louvain communities track the year
    structure (and thus curriculum sub-areas)? Measured with normalised mutual
    information and the adjusted Rand index between the community partition and
    the module-level partition, plus the per-community level mix.
  * **Prerequisite DAG check** — a curriculum's prerequisite relation should be
    acyclic; this verifies the inferred/encoded prerequisites form a DAG.
  * **Edge-threshold sweep** — how the minimum shared-concept count changes edge
    count, community count and modularity, justifying the chosen threshold.

The graph is rebuilt inline (mirroring ``graph.builder.build_module_module_graph``
and ``evaluation.robustness``) so nothing on disk is clobbered.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict

import networkx as nx

from curriculum_mapper.config import SHARED_CONCEPT_EDGE_MIN
from curriculum_mapper.graph.analytics import detect_communities

logger = logging.getLogger(__name__)


def _build_mm_graph(modules, concepts, min_shared: int) -> nx.Graph:
    """Module-module graph at a given minimum shared-concept threshold.

    With ``min_shared == SHARED_CONCEPT_EDGE_MIN`` this reproduces the live graph.
    """
    G = nx.Graph()
    module_set = {m.code for m in modules}
    for m in modules:
        G.add_node(m.code, level=m.level)
    for m in modules:
        for prereq in m.prerequisites:
            if prereq in module_set and prereq != m.code and not G.has_edge(prereq, m.code):
                G.add_edge(prereq, m.code, type="prerequisite", weight=1.0)

    concept_sets: dict[str, set[str]] = {m.code: set() for m in modules}
    for c in concepts:
        for mc in c.module_codes:
            if mc in concept_sets:
                concept_sets[mc].add(c.id)

    codes = list(concept_sets.keys())
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            a, b = codes[i], codes[j]
            shared = concept_sets[a] & concept_sets[b]
            if len(shared) >= min_shared:
                union = concept_sets[a] | concept_sets[b]
                jaccard = len(shared) / len(union) if union else 0.0
                if G.has_edge(a, b):
                    G[a][b]["similarity"] = round(jaccard, 4)
                else:
                    G.add_edge(a, b, type="similarity", weight=round(jaccard, 4))
    return G


def validate_communities_vs_level(modules, communities: dict[str, int]) -> dict:
    """Agreement between Louvain communities and module year-levels."""
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

    level_of = {m.code: m.level for m in modules}
    codes = [c for c in communities if c in level_of]
    if not codes:
        return {}
    comm_labels = [communities[c] for c in codes]
    level_labels = [level_of[c] for c in codes]

    dist: dict[int, Counter] = defaultdict(Counter)
    for c in codes:
        dist[communities[c]][level_of[c]] += 1

    return {
        "n_communities": len(set(comm_labels)),
        "nmi_community_vs_level": round(
            float(normalized_mutual_info_score(level_labels, comm_labels)), 4),
        "ari_community_vs_level": round(
            float(adjusted_rand_score(level_labels, comm_labels)), 4),
        "per_community_level_distribution": {
            int(k): dict(sorted(v.items())) for k, v in sorted(dist.items())
        },
    }


def check_prerequisite_dag(G: nx.Graph) -> dict:
    """Verify the prerequisite edges form a directed acyclic graph."""
    DG = nx.DiGraph()
    for u, v, d in G.edges(data=True):
        if d.get("type") == "prerequisite":
            DG.add_edge(u, v)
    has_edges = DG.number_of_edges() > 0
    is_dag = nx.is_directed_acyclic_graph(DG) if has_edges else True
    cycles = [] if is_dag else [list(c) for c in nx.simple_cycles(DG)]
    return {
        "n_prerequisite_edges": DG.number_of_edges(),
        "is_acyclic": bool(is_dag),
        "cycles": cycles,
    }


def edge_threshold_sweep(modules, concepts, thresholds: list[int] | None = None) -> dict:
    """Edge/community/modularity sensitivity to the shared-concept threshold."""
    import community as community_louvain

    if thresholds is None:
        thresholds = [1, 2, 3, 4, 5]
    out: dict[int, dict] = {}
    for t in thresholds:
        G = _build_mm_graph(modules, concepts, t)
        sim_edges = sum(1 for _, _, d in G.edges(data=True) if d.get("type") == "similarity")
        partition = detect_communities(G)
        try:
            mod = round(float(community_louvain.modularity(partition, G.to_undirected(), weight="weight")), 4)
        except Exception:
            mod = 0.0
        out[t] = {
            "min_shared_concepts": t,
            "n_edges": G.number_of_edges(),
            "n_similarity_edges": sim_edges,
            "n_communities": len(set(partition.values())),
            "modularity": mod,
        }
        logger.info(f"  min_shared={t}: edges={out[t]['n_edges']}, "
                    f"communities={out[t]['n_communities']}, Q={mod:.3f}")
    return out


def run_graph_validation(storage) -> dict:
    """Run all three graph-validation diagnostics against the committed data."""
    modules = storage.get_all_modules()
    concepts = storage.get_all_concepts()
    if not modules or not concepts:
        logger.warning("No modules/concepts — run the pipeline first.")
        return {}

    G = _build_mm_graph(modules, concepts, SHARED_CONCEPT_EDGE_MIN)
    communities = detect_communities(G)
    result = {
        "community_vs_level": validate_communities_vs_level(modules, communities),
        "prerequisite_dag": check_prerequisite_dag(G),
        "edge_threshold_sweep": edge_threshold_sweep(modules, concepts),
    }
    cl = result["community_vs_level"]
    dag = result["prerequisite_dag"]
    logger.info(
        f"Graph validation: NMI(community,level)={cl.get('nmi_community_vs_level')}, "
        f"ARI={cl.get('ari_community_vs_level')}; "
        f"prerequisites acyclic={dag.get('is_acyclic')} ({dag.get('n_prerequisite_edges')} edges)"
    )
    return result


_KAS = ["AL", "AR", "CN", "DS", "GV", "HCI", "IAS", "IM", "IS",
        "NC", "OS", "PBD", "PD", "PL", "SDF", "SE", "SF", "SP"]


def evaluate_concept_prerequisites(storage, sample_size: int = 12) -> dict:
    """Evaluate the directed concept-prerequisite edges (interim §4.4).

    The relation is acyclic by construction; we report that property and its
    scaffolding depth, the method breakdown, and a *KA-coherence* precision proxy
    (the share of edges whose two endpoints fall in the same CS2023 Knowledge
    Area — a structural plausibility signal), plus a sample of edges (term→term)
    for expert validation. Returns a dict of metrics.
    """
    edges = storage.get_concept_prerequisites()
    if not edges:
        return {"n_edges": 0}
    concepts = {c.id: c for c in storage.get_all_concepts()}
    best = storage.get_best_alignments_per_concept()
    level_of = {m.code: m.level for m in storage.get_all_modules()}

    def intro(cid: str) -> int | None:
        c = concepts.get(cid)
        if not c:
            return None
        lv = [level_of[mc] for mc in c.module_codes if mc in level_of]
        return min(lv) if lv else None

    G = nx.DiGraph()
    for e in edges:
        G.add_edge(e.from_concept_id, e.to_concept_id)
    acyclic = nx.is_directed_acyclic_graph(G)
    depth = nx.dag_longest_path_length(G) if acyclic and G.number_of_edges() else 0

    same_ka = 0
    for e in edges:
        fka = best.get(e.from_concept_id)
        tka = best.get(e.to_concept_id)
        if fka and tka and fka.ka_code == tka.ka_code:
            same_ka += 1

    sample = []
    for e in sorted(edges, key=lambda x: -x.confidence)[:sample_size]:
        f, t = concepts.get(e.from_concept_id), concepts.get(e.to_concept_id)
        if f and t:
            sample.append({
                "from": f.term, "from_level": intro(e.from_concept_id),
                "to": t.term, "to_level": intro(e.to_concept_id),
                "method": e.method, "confidence": e.confidence,
            })

    out = {
        "n_edges": len(edges),
        "n_concepts": G.number_of_nodes(),
        "acyclic": bool(acyclic),
        "longest_chain": depth,
        "method_breakdown": dict(Counter(e.method for e in edges)),
        "same_ka_fraction": round(same_ka / len(edges), 4),
        "sample": sample,
    }
    logger.info(
        "Concept-prerequisites: %d edges / %d concepts, acyclic=%s, depth=%d, "
        "same-KA coherence=%.0f%%",
        out["n_edges"], out["n_concepts"], out["acyclic"], out["longest_chain"],
        out["same_ka_fraction"] * 100,
    )
    return out


def compare_programmes(storage) -> dict:
    """Cross-institution comparison by source cohort (Imperial vs MIT OCW).

    Realises the interim §3.5 "contrasting concept maps between degree
    programmes" / §4.2 external-dataset comparison. For each cohort it reports
    module/concept counts and CS2023 KA coverage. Meaningful on the combined
    ``curriculum_multi.db`` (a single-cohort DB returns one entry).
    """
    modules = storage.get_all_modules()
    concepts = storage.get_all_concepts()
    aligns = storage.get_all_alignments()
    cohort_of = {m.code: ("mit_ocw" if m.source == "mit_ocw" else "imperial") for m in modules}
    best = {a.concept_id: a for a in aligns if a.rank == 1}
    cid_modules = {c.id: c.module_codes for c in concepts}

    out: dict[str, dict] = {}
    for cohort in sorted(set(cohort_of.values())):
        cset = {code for code, c in cohort_of.items() if c == cohort}
        n = len(cset)
        cohort_concepts = {c.id for c in concepts if any(mc in cset for mc in c.module_codes)}
        ka_modules: dict[str, set] = defaultdict(set)
        for cid, a in best.items():
            for mc in cid_modules.get(cid, []):
                if mc in cset:
                    ka_modules[a.ka_code].add(mc)
        out[cohort] = {
            "n_modules": n,
            "n_concepts": len(cohort_concepts),
            "kas_covered": sum(1 for ka in _KAS if ka_modules.get(ka)),
            "ka_coverage": {ka: round(len(ka_modules.get(ka, set())) / n, 4) for ka in _KAS} if n else {},
        }
        logger.info("Programme cohort %-9s: %d modules, %d concepts, %d/18 KAs",
                    cohort, n, len(cohort_concepts), out[cohort]["kas_covered"])
    return out
