"""Graph analytics and pathfinding utilities for the canonical biomedical store."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from med_research.biomed.repository import BiomedicalRepository


@dataclass(frozen=True)
class GraphPath:
    nodes: list[str]
    predicates: list[str]
    score: float


@dataclass(frozen=True)
class TargetPrioritizationScore:
    target_curie: str
    target_label: str
    supporting_evidence_count: int
    contradictory_evidence_count: int
    centrality_score: float
    combined_vulnerability_score: float


class BiomedicalGraphAnalytics:
    """Provides pathfinding and target prioritization analytics over BiomedicalRepository."""

    def __init__(self, repo: BiomedicalRepository) -> None:
        self.repo = repo

    def find_shortest_paths(
        self,
        start_curie: str,
        target_curie: str,
        max_depth: int = 3,
        limit: int = 10,
    ) -> list[GraphPath]:
        """Find claim paths connecting start_curie to target_curie using BFS."""
        if start_curie == target_curie:
            return [GraphPath(nodes=[start_curie], predicates=[], score=1.0)]

        paths: list[GraphPath] = []
        queue: deque[tuple[str, list[str], list[str]]] = deque([
            (start_curie, [start_curie], [])
        ])
        visited: set[str] = {start_curie}

        with self.repo.database.connect() as conn:

            cursor = conn.cursor()
            while queue and len(paths) < limit:
                curr, curr_nodes, curr_preds = queue.popleft()

                if len(curr_nodes) - 1 >= max_depth:
                    continue

                cursor.execute(
                    """
                    SELECT object_curie, predicate FROM claims WHERE subject_curie = ?
                    UNION
                    SELECT subject_curie, predicate FROM claims WHERE object_curie = ?
                    """,
                    (curr, curr),
                )
                neighbors = cursor.fetchall()

                for nxt_node, pred in neighbors:
                    if nxt_node == target_curie:
                        path_score = 1.0 / (len(curr_nodes))
                        paths.append(
                            GraphPath(
                                nodes=curr_nodes + [nxt_node],
                                predicates=curr_preds + [pred],
                                score=path_score,
                            )
                        )
                        if len(paths) >= limit:
                            break
                    elif nxt_node not in visited and len(curr_nodes) < max_depth:
                        visited.add(nxt_node)
                        queue.append((
                            nxt_node,
                            curr_nodes + [nxt_node],
                            curr_preds + [pred],
                        ))

        return sorted(paths, key=lambda p: p.score, reverse=True)

    def prioritize_disease_targets(
        self,
        disease_curie: str,
        top_k: int = 10,
    ) -> list[TargetPrioritizationScore]:
        """Rank disease targets based on claim evidence support and graph degree centrality."""
        results: list[TargetPrioritizationScore] = []

        with self.repo.database.connect() as conn:

            cursor = conn.cursor()

            # Fetch all targets linked to disease_curie via claims
            cursor.execute(
                """
                SELECT 
                    c.object_curie as target_curie,
                    COUNT(CASE WHEN ce.direction = 'supporting' THEN 1 END) as supporting_cnt,
                    COUNT(CASE WHEN ce.direction = 'contradictory' THEN 1 END) as contradictory_cnt
                FROM claims c
                LEFT JOIN claim_evidence ce ON c.id = ce.claim_id
                WHERE c.subject_curie = ?
                GROUP BY c.object_curie
                ORDER BY supporting_cnt DESC
                LIMIT ?
                """,
                (disease_curie, top_k),
            )
            rows = cursor.fetchall()

            for target_curie, sup, con in rows:
                sup_cnt = sup or 0
                con_cnt = con or 0
                # Calculate simple degree centrality
                cursor.execute(
                    "SELECT COUNT(*) FROM claims WHERE subject_curie = ? OR object_curie = ?",
                    (target_curie, target_curie),
                )
                degree = cursor.fetchone()[0]
                centrality = min(1.0, degree / 50.0)

                # Vulnerability score: net positive evidence support weighted by connectivity
                net_evidence = max(0, sup_cnt - con_cnt)
                vuln_score = round(min(1.0, (net_evidence * 0.2) + (centrality * 0.3)), 4)

                # Fetch label if available
                summary = self.repo.get_entity(target_curie)
                label = summary.revision.label if (summary and summary.revision) else target_curie

                results.append(
                    TargetPrioritizationScore(
                        target_curie=target_curie,
                        target_label=label,
                        supporting_evidence_count=sup_cnt,
                        contradictory_evidence_count=con_cnt,
                        centrality_score=round(centrality, 4),
                        combined_vulnerability_score=vuln_score,
                    )
                )

        return sorted(results, key=lambda x: x.combined_vulnerability_score, reverse=True)
