"""Evidence graph projection for saved Workspace dossiers."""

from __future__ import annotations

from typing import Any

from med_research.web.identity import DEFAULT_RESEARCHER_ID


def _key(value: Any) -> str:
    return str(value or "").strip().lower()


def _node_id(kind: str, value: Any) -> str:
    return f"{kind}:{value}"


def build_workspace_graph(
    run: dict[str, Any],
    reviews: list[dict[str, Any]] | None = None,
    researcher_id: str = DEFAULT_RESEARCHER_ID,
) -> dict[str, Any]:
    """Project one saved dossier into a compact graph for interactive exploration."""
    dossier = run.get("dossier") or {}
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    edge_index = 0
    review_by_candidate = {
        (item["candidate_type"], item["candidate_id"]): item for item in (reviews or [])
    }

    def add_node(
        node_id: str,
        node_type: str,
        label: str,
        *,
        subtitle: str = "",
        description: str = "",
        url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if node_id in nodes:
            return
        nodes[node_id] = {
            "id": node_id,
            "type": node_type,
            "label": label or node_id,
            "subtitle": subtitle,
            "description": description,
            "url": url,
            "metadata": metadata or {},
        }

    def add_edge(source: str, target: str, edge_type: str, label: str = "") -> None:
        nonlocal edge_index
        if source not in nodes or target not in nodes:
            return
        edge_index += 1
        edges.append(
            {
                "id": f"edge:{edge_index}",
                "source": source,
                "target": target,
                "type": edge_type,
                "label": label or edge_type.replace("_", " ").title(),
            }
        )

    evidence_by_id: dict[str, dict[str, Any]] = {
        item.get("evidence_id", ""): item for item in dossier.get("evidence", []) if item.get("evidence_id")
    }
    citation_lookup: dict[str, str] = {}

    def citation_node(
        *,
        source: str,
        native_id: str = "",
        doi: str = "",
        title: str = "",
        url: str = "",
        evidence_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        identity = native_id or doi or evidence_id or url or title or "unknown"
        node_id = _node_id("citation", f"{source}:{identity}")
        add_node(
            node_id,
            "citation",
            title or native_id or doi or evidence_id or "Citation",
            subtitle=f"{source} · {native_id or doi or evidence_id or 'source record'}",
            url=url or None,
            metadata={"source": source, "native_id": native_id, "doi": doi, **(metadata or {})},
        )
        for alias in (evidence_id, native_id, doi, url):
            if alias:
                citation_lookup[_key(alias)] = node_id
        return node_id

    for evidence_id, evidence in evidence_by_id.items():
        citation_node(
            source=evidence.get("source", "unknown"),
            native_id=evidence.get("native_id", ""),
            doi=evidence.get("doi", "") or "",
            title=evidence.get("title", ""),
            url=evidence.get("url", ""),
            evidence_id=evidence_id,
            metadata={
                "evidence_id": evidence_id,
                "quality_tier": evidence.get("quality_tier", ""),
                "quality_score": evidence.get("quality_score"),
                "published_date": evidence.get("published_date"),
            },
        )

    claim_by_id: dict[str, dict[str, Any]] = {}
    for claim in dossier.get("claims", []):
        claim_id = claim.get("claim_id", "")
        if not claim_id:
            continue
        claim_by_id[claim_id] = claim
        claim_node = _node_id("claim", claim_id)
        add_node(
            claim_node,
            "claim",
            claim.get("text", "Claim"),
            subtitle=f"{claim.get('relationship', 'claim')} · confidence {float(claim.get('confidence', 0)):.0%}",
            description=claim.get("supporting_snippet", ""),
            metadata={
                "claim_id": claim_id,
                "subject_id": claim.get("subject_id", ""),
                "subject_name": claim.get("subject_name", ""),
                "relationship": claim.get("relationship", ""),
                "confidence": claim.get("confidence", 0),
                "evidence_ids": claim.get("evidence_ids", []),
            },
        )
        for evidence_id in claim.get("evidence_ids", []):
            citation = citation_lookup.get(_key(evidence_id))
            if citation:
                add_edge(claim_node, citation, "evidence", "Supported by evidence")
        for citation in claim.get("citations", []):
            citation_id = citation_node(
                source=citation.get("source", "unknown"),
                native_id=citation.get("native_id", ""),
                doi=citation.get("doi", "") or "",
                title=citation.get("title", ""),
                url=citation.get("url", ""),
            )
            add_edge(claim_node, citation_id, "citation", "Cites")

        if claim.get("subject_type") == "pathway" and claim.get("subject_id"):
            pathway_node = _node_id("pathway", claim["subject_id"])
            add_node(
                pathway_node,
                "pathway",
                claim.get("subject_name", claim["subject_id"]),
                subtitle="Claim-associated pathway",
                metadata={"pathway_id": claim["subject_id"], "source": "evidence claim"},
            )
            add_edge(claim_node, pathway_node, claim.get("relationship", "associated_with"))

    candidate_nodes: dict[tuple[str, str], str] = {}
    for candidate_type, ranking_key in (("drug", "drug_rankings"), ("target", "target_rankings")):
        for candidate in dossier.get(ranking_key, []):
            candidate_id = candidate.get("candidate_id", "")
            if not candidate_id:
                continue
            candidate_node = _node_id("candidate", f"{candidate_type}:{candidate_id}")
            candidate_nodes[(candidate_type, candidate_id)] = candidate_node
            review = review_by_candidate.get((candidate_type, candidate_id), {})
            decision = review.get("decision", "unreviewed")
            add_node(
                candidate_node,
                "candidate",
                candidate.get("name", candidate_id),
                subtitle=f"{candidate_type} · score {float(candidate.get('score', 0)):.1f} · {decision}",
                description=candidate.get("explanation", ""),
                metadata={
                    "candidate_id": candidate_id,
                    "candidate_type": candidate_type,
                    "score": candidate.get("score"),
                    "confidence_band": candidate.get("confidence_band", ""),
                    "decision": decision,
                    "tags": review.get("tags", []),
                    "rationale": review.get("rationale", ""),
                    "notes": review.get("notes", ""),
                    "changed_my_mind": review.get("changed_my_mind", ""),
                    "provenance_fingerprint": review.get("provenance_fingerprint", ""),
                },
            )
            for claim_id in candidate.get("supporting_claim_ids", []):
                claim_node = _node_id("claim", claim_id)
                add_edge(claim_node, candidate_node, "supports", "Supports candidate")
            for claim_id in candidate.get("contradicting_claim_ids", []):
                claim_node = _node_id("claim", claim_id)
                add_edge(claim_node, candidate_node, "contradicts", "Contradicts candidate")
            for citation_id in candidate.get("citation_ids", []):
                citation = citation_lookup.get(_key(citation_id))
                if citation:
                    add_edge(candidate_node, citation, "citation", "Candidate citation")

            if review and decision != "unreviewed":
                decision_node = _node_id("decision", f"{candidate_type}:{candidate_id}:{researcher_id}")
                add_node(
                    decision_node,
                    "decision",
                    decision.title(),
                    subtitle=f"Researcher decision · {researcher_id}",
                    description=review.get("rationale", ""),
                    metadata={
                        "researcher_id": researcher_id,
                        "decision": decision,
                        "rationale": review.get("rationale", ""),
                        "notes": review.get("notes", ""),
                        "changed_my_mind": review.get("changed_my_mind", ""),
                        "tags": review.get("tags", []),
                        "provenance_fingerprint": review.get("provenance_fingerprint", ""),
                        "updated_at": review.get("updated_at", ""),
                    },
                )
                add_edge(decision_node, candidate_node, "decision", "Researcher decision")

    # Add explicit candidate-to-claim links when the claim subject is the candidate,
    # even if extraction did not include the claim ID in ranking components.
    for claim_id, claim in claim_by_id.items():
        subject_id = claim.get("subject_id", "")
        for candidate_type in ("drug", "target"):
            claim_candidate_node = candidate_nodes.get((candidate_type, subject_id))
            if claim_candidate_node:
                add_edge(
                    _node_id("claim", claim_id),
                    claim_candidate_node,
                    claim.get("relationship", "associated_with"),
                    "Claim relationship",
                )

    # Reuse the existing KG path explanations, preserving pathway node types when
    # the disease pathway catalog identifies an intermediate node.
    pathway_by_id: dict[str, dict[str, Any]] = {}
    pathway_by_name: dict[str, dict[str, Any]] = {}
    try:
        from med_research.pipeline.knowledge_graph.config import load_pathways

        for pathway in load_pathways(dossier.get("request", {}).get("disease_id", "sle")).get(
            "pathways", []
        ):
            pathway_by_id[_key(pathway.get("id"))] = pathway
            pathway_by_name[_key(pathway.get("name"))] = pathway
    except (FileNotFoundError, KeyError, TypeError, ValueError):
        pass

    for explanation in dossier.get("graph_explanations", []):
        candidate_id = explanation.get("candidate_id", "")
        path_candidate_node = next(
            (
                node_id
                for (candidate_type, ranked_id), node_id in candidate_nodes.items()
                if ranked_id == candidate_id
            ),
            None,
        )
        if not path_candidate_node or explanation.get("status") != "found":
            continue
        path_ids = explanation.get("path_node_ids", [])
        path_labels = explanation.get("path_labels", [])
        previous = path_candidate_node
        for index, path_id in enumerate(path_ids[1:], start=1):
            label = path_labels[index] if index < len(path_labels) else str(path_id)
            pathway = pathway_by_id.get(_key(path_id)) or pathway_by_name.get(_key(label))
            node_type = "pathway" if pathway or "pathway" in label.lower() else "knowledge_graph"
            graph_node = _node_id(node_type, path_id)
            add_node(
                graph_node,
                node_type,
                pathway.get("name", label) if pathway else label,
                subtitle="Knowledge-graph pathway" if node_type == "pathway" else "Knowledge-graph node",
                description=pathway.get("description", "") if pathway else "",
                metadata={"node_id": path_id, "path_position": index, "source": "knowledge graph"},
            )
            relationships = explanation.get("relationship_labels", [])
            relationship = relationships[index - 1] if index - 1 < len(relationships) else "RELATED_TO"
            add_edge(previous, graph_node, "knowledge_graph", relationship)
            previous = graph_node

    return {
        "run_id": run.get("run_id", ""),
        "researcher_id": researcher_id,
        "nodes": list(nodes.values()),
        "edges": edges,
    }
