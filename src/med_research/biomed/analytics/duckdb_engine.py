"""DuckDB-accelerated analytical queries over the canonical biomedical store."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PathResult:
    source: str
    predicate: str
    target: str
    evidence_count: int


@dataclass(frozen=True)
class TargetAnalyticsScore:
    target_curie: str
    target_name: str
    target_type: str
    supporting_count: int
    contradictory_count: int
    evidence_score: float
    pathway_count: int
    phenotype_count: int


@dataclass(frozen=True)
class SharedMechanismResult:
    condition_a: str
    condition_b: str
    shared_pathways: list[str]
    shared_genes: list[str]
    jaccard_similarity: float


class DuckDBBiomedicalEngine:
    """Vectorized, high-throughput analytical query engine powered by DuckDB."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path).resolve()
        self._con: duckdb.DuckDBPyConnection | None = None

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        if self._con is None:
            self._con = duckdb.connect(":memory:")
            # Attach SQLite database in read-only mode for zero-copy vectorized execution
            if self.db_path.exists():
                sqlite_path_str = str(self.db_path).replace("\\", "/")
                self._con.execute(f"ATTACH '{sqlite_path_str}' AS bio (TYPE sqlite, READ_ONLY)")
        return self._con

    def close(self) -> None:
        if self._con is not None:
            self._con.close()
            self._con = None

    def get_summary_statistics(self) -> dict[str, Any]:
        """Compute aggregate counts and distributions across the biomedical knowledge graph."""
        con = self._get_connection()
        try:
            r_ent = con.execute("SELECT COUNT(*) FROM bio.entities").fetchone()
            entity_count = int(r_ent[0]) if r_ent else 0
            r_claim = con.execute("SELECT COUNT(*) FROM bio.claims").fetchone()
            claim_count = int(r_claim[0]) if r_claim else 0
            r_ev = con.execute("SELECT COUNT(*) FROM bio.claim_evidence").fetchone()
            evidence_count = int(r_ev[0]) if r_ev else 0
            r_snap = con.execute("SELECT COUNT(*) FROM bio.resource_snapshots").fetchone()
            snapshot_count = int(r_snap[0]) if r_snap else 0

            entity_type_dist = dict(
                con.execute(
                    "SELECT entity_type, COUNT(*) FROM bio.entities GROUP BY entity_type ORDER BY 2 DESC"
                ).fetchall()
            )
            predicate_dist = dict(
                con.execute(
                    "SELECT predicate, COUNT(*) FROM bio.claims GROUP BY predicate ORDER BY 2 DESC"
                ).fetchall()
            )

            return {
                "total_entities": entity_count,
                "total_claims": claim_count,
                "total_evidence": evidence_count,
                "total_snapshots": snapshot_count,
                "entity_type_distribution": entity_type_dist,
                "predicate_distribution": predicate_dist,
            }
        except Exception as err:
            logger.warning("DuckDB get_summary_statistics error: %s", err)
            return {"error": str(err)}

    def prioritize_targets_vectorized(
        self,
        disease_curie: str,
        *,
        top_k: int = 50,
    ) -> list[TargetAnalyticsScore]:
        """Vectorized target prioritization combining claims, direction of evidence, and pathway involvement."""
        con = self._get_connection()
        query = """
        WITH disease_claims AS (
            SELECT
                c.id AS claim_id,
                c.predicate,
                CASE
                    WHEN c.subject_curie = ? THEN c.object_curie
                    ELSE c.subject_curie
                END AS target_curie
            FROM bio.claims c
            WHERE c.subject_curie = ? OR c.object_curie = ?
        ),
        target_entities AS (
            SELECT
                e.primary_curie,
                COALESCE(er.label, e.primary_curie) AS canonical_name,
                e.entity_type
            FROM bio.entities e
            LEFT JOIN bio.entity_revisions er ON e.id = er.entity_id
        ),
        evidence_agg AS (
            SELECT
                dc.target_curie,
                COUNT(CASE WHEN ce.direction = 'supporting' THEN 1 END) AS supporting_count,
                COUNT(CASE WHEN ce.direction = 'contradictory' THEN 1 END) AS contradictory_count,
                COALESCE(AVG(CAST(json_extract(ce.evidence_json, '$.confidence_score') AS DOUBLE)), 1.0) AS avg_conf
            FROM disease_claims dc
            LEFT JOIN bio.claim_evidence ce ON dc.claim_id = ce.claim_id
            GROUP BY dc.target_curie
        ),
        pathway_counts AS (
            SELECT subject_curie AS target_curie, COUNT(DISTINCT object_curie) AS pathway_cnt
            FROM bio.claims
            WHERE predicate = 'INVOLVES_PATHWAY'
            GROUP BY subject_curie
        ),
        phenotype_counts AS (
            SELECT subject_curie AS target_curie, COUNT(DISTINCT object_curie) AS pheno_cnt
            FROM bio.claims
            WHERE predicate = 'HAS_PHENOTYPE'
            GROUP BY subject_curie
        )
        SELECT
            ea.target_curie,
            COALESCE(te.canonical_name, ea.target_curie) AS target_name,
            COALESCE(te.entity_type, 'gene') AS target_type,
            ea.supporting_count,
            ea.contradictory_count,
            (ea.supporting_count * ea.avg_conf - (ea.contradictory_count * 1.5)) AS evidence_score,
            COALESCE(pc.pathway_cnt, 0) AS pathway_count,
            COALESCE(phc.pheno_cnt, 0) AS phenotype_count
        FROM evidence_agg ea
        LEFT JOIN target_entities te ON ea.target_curie = te.primary_curie
        LEFT JOIN pathway_counts pc ON ea.target_curie = pc.target_curie
        LEFT JOIN phenotype_counts phc ON ea.target_curie = phc.target_curie
        ORDER BY evidence_score DESC, supporting_count DESC
        LIMIT ?
        """
        try:
            rows = con.execute(
                query, [disease_curie, disease_curie, disease_curie, top_k]
            ).fetchall()
            return [
                TargetAnalyticsScore(
                    target_curie=r[0],
                    target_name=r[1],
                    target_type=r[2],
                    supporting_count=int(r[3]),
                    contradictory_count=int(r[4]),
                    evidence_score=float(r[5]),
                    pathway_count=int(r[6]),
                    phenotype_count=int(r[7]),
                )
                for r in rows
            ]
        except Exception as err:
            logger.warning("DuckDB prioritize_targets_vectorized error: %s", err)
            return []

    def compute_shared_mechanisms(
        self,
        curie_a: str,
        curie_b: str,
    ) -> SharedMechanismResult:
        """Compute shared pathways and genes between two biomedical conditions using vectorized joins."""
        con = self._get_connection()
        query = """
        WITH cond_a_pathways AS (
            SELECT object_curie AS pathway
            FROM bio.claims
            WHERE subject_curie = ? AND predicate IN ('INVOLVES_PATHWAY', 'HAS_PHENOTYPE')
            UNION
            SELECT c2.object_curie AS pathway
            FROM bio.claims c1
            JOIN bio.claims c2 ON c1.object_curie = c2.subject_curie
            WHERE c1.subject_curie = ? AND c2.predicate = 'INVOLVES_PATHWAY'
        ),
        cond_b_pathways AS (
            SELECT object_curie AS pathway
            FROM bio.claims
            WHERE subject_curie = ? AND predicate IN ('INVOLVES_PATHWAY', 'HAS_PHENOTYPE')
            UNION
            SELECT c2.object_curie AS pathway
            FROM bio.claims c1
            JOIN bio.claims c2 ON c1.object_curie = c2.subject_curie
            WHERE c1.subject_curie = ? AND c2.predicate = 'INVOLVES_PATHWAY'
        ),
        cond_a_genes AS (
            SELECT object_curie AS gene
            FROM bio.claims
            WHERE subject_curie = ? AND predicate IN ('ASSOCIATED_WITH_GENE', 'TREATED_BY')
        ),
        cond_b_genes AS (
            SELECT object_curie AS gene
            FROM bio.claims
            WHERE subject_curie = ? AND predicate IN ('ASSOCIATED_WITH_GENE', 'TREATED_BY')
        )
        SELECT
            (SELECT list(pathway) FROM (SELECT pathway FROM cond_a_pathways INTERSECT SELECT pathway FROM cond_b_pathways)) AS shared_p,
            (SELECT list(gene) FROM (SELECT gene FROM cond_a_genes INTERSECT SELECT gene FROM cond_b_genes)) AS shared_g,
            (SELECT COUNT(*) FROM (SELECT pathway FROM cond_a_pathways UNION SELECT pathway FROM cond_b_pathways)) AS total_p,
            (SELECT COUNT(*) FROM (SELECT pathway FROM cond_a_pathways INTERSECT SELECT pathway FROM cond_b_pathways)) AS inter_p
        """
        try:
            row = con.execute(
                query, [curie_a, curie_a, curie_b, curie_b, curie_a, curie_b]
            ).fetchone()
            if not row:
                return SharedMechanismResult(curie_a, curie_b, [], [], 0.0)

            shared_pathways = row[0] or []
            shared_genes = row[1] or []
            total_p = row[2] or 1
            inter_p = row[3] or 0
            jaccard = float(inter_p) / float(total_p) if total_p > 0 else 0.0

            return SharedMechanismResult(
                condition_a=curie_a,
                condition_b=curie_b,
                shared_pathways=list(shared_pathways),
                shared_genes=list(shared_genes),
                jaccard_similarity=jaccard,
            )
        except Exception as err:
            logger.warning("DuckDB compute_shared_mechanisms error: %s", err)
            return SharedMechanismResult(curie_a, curie_b, [], [], 0.0)

    def find_multi_hop_subgraph(
        self,
        start_curie: str,
        max_hops: int = 2,
        limit: int = 100,
    ) -> list[PathResult]:
        """Extract multi-hop neighborhood subgraph around start_curie."""
        con = self._get_connection()
        query = """
        WITH RECURSIVE graph_hops(src, pred, tgt, depth) AS (
            SELECT subject_curie, predicate, object_curie, 1
            FROM bio.claims
            WHERE subject_curie = ?
            UNION ALL
            SELECT c.subject_curie, c.predicate, c.object_curie, gh.depth + 1
            FROM bio.claims c
            JOIN graph_hops gh ON c.subject_curie = gh.tgt
            WHERE gh.depth < ?
        ),
        claim_ev_counts AS (
            SELECT c.subject_curie AS src, c.object_curie AS tgt, COUNT(ce.id) AS ev_count
            FROM bio.claims c
            LEFT JOIN bio.claim_evidence ce ON c.id = ce.claim_id
            GROUP BY c.subject_curie, c.object_curie
        )
        SELECT
            gh.src,
            gh.pred,
            gh.tgt,
            COALESCE(cec.ev_count, 0) AS ev_count
        FROM graph_hops gh
        LEFT JOIN claim_ev_counts cec ON gh.src = cec.src AND gh.tgt = cec.tgt
        LIMIT ?
        """
        try:
            rows = con.execute(query, [start_curie, max_hops, limit]).fetchall()
            return [
                PathResult(
                    source=r[0],
                    predicate=r[1],
                    target=r[2],
                    evidence_count=int(r[3]),
                )
                for r in rows
            ]
        except Exception as err:
            logger.warning("DuckDB find_multi_hop_subgraph error: %s", err)
            return []

    def compute_cross_disease_matrix(
        self,
        disease_curies: list[str],
    ) -> dict[str, Any]:
        """Compute an N x N cross-disease biological similarity matrix using DuckDB."""
        if not disease_curies:
            return {"conditions": [], "matrix": [], "details": {}}

        matrix: list[list[float]] = []
        details: dict[str, dict[str, Any]] = {}

        for i, curie_a in enumerate(disease_curies):
            row: list[float] = []
            for j, curie_b in enumerate(disease_curies):
                if i == j:
                    row.append(1.0)
                    pair_key = f"{curie_a}___{curie_b}"
                    details[pair_key] = {
                        "condition_a": curie_a,
                        "condition_b": curie_b,
                        "jaccard_similarity": 1.0,
                        "shared_pathways": [],
                        "shared_genes": [],
                    }
                elif j < i:
                    # Symmetric matrix reuse
                    sym_val = matrix[j][i]
                    row.append(sym_val)
                    pair_key = f"{curie_a}___{curie_b}"
                    sym_key = f"{curie_b}___{curie_a}"
                    details[pair_key] = details.get(
                        sym_key,
                        {
                            "condition_a": curie_a,
                            "condition_b": curie_b,
                            "jaccard_similarity": sym_val,
                            "shared_pathways": [],
                            "shared_genes": [],
                        },
                    )
                else:
                    res = self.compute_shared_mechanisms(curie_a, curie_b)
                    sim = round(res.jaccard_similarity, 4)
                    row.append(sim)
                    pair_key = f"{curie_a}___{curie_b}"
                    details[pair_key] = {
                        "condition_a": curie_a,
                        "condition_b": curie_b,
                        "jaccard_similarity": sim,
                        "shared_pathways": res.shared_pathways,
                        "shared_genes": res.shared_genes,
                    }
            matrix.append(row)

        return {
            "conditions": disease_curies,
            "matrix": matrix,
            "details": details,
        }

    def get_druggability_distribution(
        self,
        disease_curie: str | None = None,
    ) -> dict[str, Any]:
        """Compute target druggability tiers and evidence counts using DuckDB."""
        con = self._get_connection()
        try:
            if disease_curie:
                query = """
                WITH target_claims AS (
                    SELECT DISTINCT
                        CASE WHEN subject_curie = ? THEN object_curie ELSE subject_curie END AS target_curie,
                        predicate
                    FROM bio.claims
                    WHERE subject_curie = ? OR object_curie = ?
                )
                SELECT
                    tc.predicate,
                    COUNT(DISTINCT tc.target_curie) AS target_count
                FROM target_claims tc
                GROUP BY tc.predicate
                ORDER BY 2 DESC
                """
                rows = con.execute(query, [disease_curie, disease_curie, disease_curie]).fetchall()
            else:
                query = """
                SELECT
                    predicate,
                    COUNT(DISTINCT subject_curie) AS count_subject,
                    COUNT(DISTINCT object_curie) AS count_object
                FROM bio.claims
                GROUP BY predicate
                ORDER BY 2 DESC
                """
                rows = con.execute(query).fetchall()

            dist = {r[0]: int(r[1]) for r in rows}
            return {
                "disease_curie": disease_curie or "global",
                "distribution": dist,
                "total_categories": len(dist),
            }
        except Exception as err:
            logger.warning("DuckDB get_druggability_distribution error: %s", err)
            return {
                "disease_curie": disease_curie or "global",
                "distribution": {},
                "error": str(err),
            }
