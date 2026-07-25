"""
Literature → Knowledge Graph Cross-Reference Engine

Matches entities extracted from PubMed abstracts against:
  1. Knowledge Graph genes, drugs, and pathways (dictionary-based, always on)
  2. Optional spaCy biomedical NER for novel entities not in the KG
  3. Drug repurposing candidates (drug-gene pairs)

Scores each article by how many KG entities it references and
identifies literature-supported repurposing candidates.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DR_DATA_DIR = PROJECT_ROOT / "drug_repurposing" / "data"

from knowledge_graph.config import load_genes, load_drugs, load_pathways

# ── Optional spaCy NER ──────────────────────────────────────────────────
_biomedical_ner = None

def _get_ner():
    """Lazy-load the biomedical NER module."""
    global _biomedical_ner
    if _biomedical_ner is None:
        from literature_mining.ner import BiomedicalNER
        _biomedical_ner = BiomedicalNER()
    return _biomedical_ner


def load_kg_entities():
    """Load all named entities from the knowledge graph data files."""
    entities = {
        "genes": {},
        "drugs": {},
        "pathways": {},
    }

    # Load genes
    genes_data = load_genes()
    for g in genes_data["genes"]:
        entities["genes"][g["id"]] = {
            "name": g["name"],
            "id": g["id"],
            "category": g.get("category", ""),
            "synonyms": _generate_gene_synonyms(g),
        }

    # Load drugs
    drugs_data = load_drugs()
    for d in drugs_data["drugs"]:
        entities["drugs"][d["id"]] = {
            "name": d["name"],
            "id": d["id"],
            "category": d.get("category", ""),
            "target": d.get("target", ""),
            "synonyms": _generate_drug_synonyms(d),
        }

    # Load pathways
    pathways_data = load_pathways()
    for p in pathways_data["pathways"]:
        entities["pathways"][p["id"]] = {
            "name": p["name"],
            "id": p["id"],
            "description": p.get("description", ""),
        }

    return entities


def load_repurposing_candidates():
    """Load drug repurposing candidates for cross-reference."""
    candidates_data = json.loads(
        (DR_DATA_DIR / "candidates.json").read_text(encoding="utf-8")
    )
    return candidates_data["repurposing_candidates"]


def _generate_gene_synonyms(gene: dict) -> list:
    """Generate search synonyms for a gene."""
    synonyms = [gene["name"].lower()]
    if "function" in gene and gene["function"]:
        # Extract key functional terms
        func = gene["function"].lower()
        for term in ["transcription factor", "kinase", "receptor", "phosphatase",
                     "scaffold", "ligand", "integrin", "sensor"]:
            if term in func:
                synonyms.append(term)
    if gene.get("id"):
        synonyms.append(gene["id"].lower())
    return list(set(synonyms))


def _generate_drug_synonyms(drug: dict) -> list:
    """Generate search synonyms for a drug including brand and generic names."""
    synonyms = [drug["name"].lower()]
    # Extract brand name from "Generic (Brand)" format
    name = drug["name"]
    if "(" in name and ")" in name:
        brand = name.split("(")[1].split(")")[0].strip().lower()
        generic = name.split("(")[0].strip().lower()
        synonyms.append(brand)
        synonyms.append(generic)
    if drug.get("id"):
        synonyms.append(drug["id"].lower())
    return list(set(synonyms))


def cross_reference_articles(articles: list, entities: dict, candidates: list) -> dict:
    """
    Cross-reference extracted article entities against the knowledge graph.

    For each article, matches found entities to KG genes/drugs/pathways,
    and identifies which repurposing candidates have literature support.

    Returns a dict with:
      - article_matches: per-article entity matches and scores
      - candidate_support: which candidates are supported by which articles
      - gene_coverage: which genes have literature mentions
      - stats: summary statistics
    """
    article_matches = []
    candidate_support = {}
    gene_article_counts = {}
    drug_article_counts = {}

    for article in articles:
        matches = _match_article_entities(article, entities)
        article["kg_matches"] = matches
        article["relevance_score"] = _compute_relevance(matches)
        article_matches.append(article)

        # Track gene/drug mention counts
        for gene_id in matches["genes_found"]:
            gene_article_counts.setdefault(gene_id, []).append(article["pmid"])
        for drug_id in matches["drugs_found"]:
            drug_article_counts.setdefault(drug_id, []).append(article["pmid"])

        # Check which repurposing candidates this article supports
        for candidate in candidates:
            gene_id = candidate["gene_id"]
            drug_name = candidate["drug_name"].lower()
            if gene_id in matches["genes_found"]:
                # Check if drug is mentioned
                drug_found = any(
                    drug_name in d["name"].lower()
                    or any(s in drug_name for s in d["synonyms"])
                    for d in matches["drugs_found"].values()
                    if isinstance(d, dict)
                )
                # Also check raw drug mentions
                for raw_drug in matches.get("raw_drug_mentions", []):
                    if any(s in drug_name for s in [raw_drug.lower()]):
                        drug_found = True
                        break

                if drug_found:
                    cid = candidate["id"]
                    candidate_support.setdefault(cid, []).append(
                        {
                            "pmid": article["pmid"],
                            "title": article["title"],
                            "year": article.get("year", ""),
                        }
                    )

    # Sort articles by relevance score
    article_matches.sort(key=lambda a: a["relevance_score"], reverse=True)

    # Aggregate novel entities across all articles
    all_novel = {"chemicals": set(), "diseases": set(), "genes": set()}
    all_variants = set()
    all_clinical = set()
    all_statistics = set()
    all_dosage = set()
    for a in article_matches:
        for key in all_novel:
            for entity in a.get("kg_matches", {}).get("novel_entities", {}).get(key, []):
                all_novel[key].add(entity)
        for v in a.get("kg_matches", {}).get("variants", []):
            all_variants.add(v)
        for v in a.get("kg_matches", {}).get("clinical", []):
            all_clinical.add(v)
        for v in a.get("kg_matches", {}).get("statistics", []):
            all_statistics.add(v)
        for v in a.get("kg_matches", {}).get("dosage", []):
            all_dosage.add(v)
    novel_summary = {k: sorted(list(v)) for k, v in all_novel.items() if v}
    variant_summary = sorted(list(all_variants))
    clinical_summary = sorted(list(all_clinical))
    statistics_summary = sorted(list(all_statistics))
    dosage_summary = sorted(list(all_dosage))

    ner = _get_ner()
    if ner.spacy_available:
        from literature_mining.ner import _spacy_is_biomedical
        if _spacy_is_biomedical:
            spacy_status = "active (biomedical model)"
        else:
            spacy_status = "regex-based (generic spaCy loaded)"
    else:
        spacy_status = "regex-based (no spaCy)"

    return {
        "article_matches": article_matches,
        "candidate_support": candidate_support,
        "gene_coverage": {
            gid: {"articles": len(pmids), "pmids": pmids[:5]}
            for gid, pmids in gene_article_counts.items()
        },
        "drug_coverage": {
            did: {"articles": len(pmids), "pmids": pmids[:5]}
            for did, pmids in drug_article_counts.items()
        },
        "novel_entities": novel_summary,
        "variant_entities": variant_summary,
        "clinical_entities": clinical_summary,
        "statistics_entities": statistics_summary,
        "dosage_entities": dosage_summary,
        "stats": {
            "total_articles": len(article_matches),
            "articles_with_matches": sum(
                1 for a in article_matches if a["relevance_score"] > 0
            ),
            "genes_found": len(gene_article_counts),
            "drugs_found": len(drug_article_counts),
            "candidates_supported": len(candidate_support),
            "unique_pmids_with_matches": len(
                set(a["pmid"] for a in article_matches if a["relevance_score"] > 0)
            ),
            "spacy_ner": spacy_status,
            "novel_entities_found": sum(len(v) for v in novel_summary.values()),
            "variant_mentions": len(variant_summary),
            "clinical_mentions": len(clinical_summary),
            "statistics_mentions": len(statistics_summary),
            "dosage_mentions": len(dosage_summary),
        },
    }


def _match_article_entities(article: dict, entities: dict) -> dict:
    """Match a single article's entities against the knowledge graph.

    First pass: dictionary matching against KG genes, drugs, pathways.
    Second pass (optional): spaCy biomedical NER for novel entities.
    Third pass (optional): scispacy validation of KG dictionary matches.
    """
    text = article.get("abstract", "") + " " + article.get("title", "")
    text_lower = text.lower()

    genes_found = {}
    drugs_found = {}
    pathways_found = {}
    known_lower = set()  # Track matched entities to avoid spaCy duplicates

    # ── Pass 1: Dictionary matching ──────────────────────────────────

    ner = _get_ner()

    # Match genes by synonyms
    for gene_id, gene_info in entities["genes"].items():
        for synonym in gene_info["synonyms"]:
            if len(synonym) > 3 and synonym in text_lower:
                # Validate with scispacy if available
                validation = ner.validate_kg_match(text, gene_info["name"], "gene")
                genes_found[gene_id] = {
                    **gene_info,
                    "match_confidence": validation["confidence"],
                    "match_validated": validation["validated"],
                }
                known_lower.add(gene_info["name"].lower())
                known_lower.add(synonym)
                break

    # Match drugs by synonyms
    for drug_id, drug_info in entities["drugs"].items():
        for synonym in drug_info["synonyms"]:
            if len(synonym) > 3 and synonym in text_lower:
                validation = ner.validate_kg_match(text, drug_info["name"], "drug")
                drugs_found[drug_id] = {
                    **drug_info,
                    "match_confidence": validation["confidence"],
                    "match_validated": validation["validated"],
                }
                known_lower.add(drug_info["name"].lower())
                known_lower.add(synonym)
                break

    # Match pathways by name keywords
    for path_id, path_info in entities["pathways"].items():
        path_name = path_info["name"].lower()
        keywords = [w for w in path_name.split() if len(w) > 3]
        if keywords and all(kw in text_lower for kw in keywords[:3]):
            pathways_found[path_id] = path_info

    # ── Pass 2: Optional spaCy biomedical NER ────────────────────────

    novel_entities = {}
    extended_entities = {}
    ner = _get_ner()
    if ner.spacy_available:
        novel_entities = ner.extract_novel_entities(text, known_lower)

    # Always extract variants, clinical, statistics, dosage (regex-based)
    extended_entities = ner.extract_all_entities(text, known_lower)

    return {
        "genes_found": genes_found,
        "drugs_found": drugs_found,
        "pathways_found": pathways_found,
        "gene_count": len(genes_found),
        "drug_count": len(drugs_found),
        "pathway_count": len(pathways_found),
        "total_matches": len(genes_found) + len(drugs_found) + len(pathways_found),
        "novel_entities": novel_entities,
        "novel_count": sum(len(v) for v in novel_entities.values()),
        "variants": extended_entities.get("variants", []),
        "clinical": extended_entities.get("clinical", []),
        "statistics": extended_entities.get("statistics", []),
        "dosage": extended_entities.get("dosage", []),
    }


def _compute_relevance(matches: dict) -> float:
    """Compute a relevance score for an article based on KG entity matches.

    Genes and drugs both weighted equally. Having both a gene AND drug match
    (potential drug-target relationship) scores highest.
    Novel entities (from spaCy) provide a small bonus for discovery potential.
    """
    score = 0.0
    score += matches["gene_count"] * 2.0
    score += matches["drug_count"] * 2.0
    score += matches["pathway_count"] * 1.5

    # Bonus for co-mentioning a gene and drug (potential relationship)
    if matches["gene_count"] > 0 and matches["drug_count"] > 0:
        score += 5.0

    # Small bonus for novel entities discovered by spaCy
    score += matches.get("novel_count", 0) * 0.5

    return round(score, 1)
