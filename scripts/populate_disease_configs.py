"""Derive disease config CAR-T rubrics and drug safety tiers from KG JSON.

Reads each disease module's ``genes.json`` and ``drugs.json``, applies a
documented scoring rubric, and optionally writes ``config.py`` sections or
prints a per-disease validation report.

Rubric (category-keyed CAR_T_SCORES for non-SLE diseases):
  - Group genes by the ``category`` field in genes.json.
  - Assign a category base score from pathway semantics (B-cell highest).
  - Adjust per gene with odds_ratio: score = min(10, base + min(1.5, (OR-1)*0.5)).

Drug safety tiers (DRUG_SAFETY_RISK):
  - Classify each drug from mechanism, category, type, and adverse_effects text.
  - high_risk: interferons, anti-TNF, checkpoint inhibitors, known inducers.
  - moderate_risk: broad immunomodulators / biologics with secondary-autoimmunity signal.
  - low_risk: established disease-standard therapies and supportive care.

Usage:
    python scripts/populate_disease_configs.py --all --report
    python scripts/populate_disease_configs.py ra --write
    python scripts/populate_disease_configs.py --all --check --strict
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
from med_research.diseases.base import Disease

DISEASE_IDS = tuple(Disease.list_all())

SLE_DIMENSION_KEYS = frozenset(
    {
        "B_CELL_DEPENDENCY",
        "AUTOANTIBODY_ASSOCIATION",
        "PLASMA_CELL_RELEVANCE",
        "CD19_TARGETING",
        "CAR_T_EVIDENCE",
    }
)

# Category keyword rules — first match wins (ordered highest relevance first).
_CATEGORY_RULES: list[tuple[tuple[str, ...], float]] = [
    (("b cell", "germinal", "plasma cell", "baff", "bcr", "b lymphocyte"), 9.0),
    (("autoantigen", "autoantibody", "citrullination", "beta cell", "myelin"), 8.5),
    (("treg", "il-2 pathway", "il-2 "), 8.0),
    (("il-23", "th17", "il-17"), 7.5),
    (("costimulation", "costimulatory", "cd28", "ctla4"), 7.0),
    (("mhc", "antigen presentation", "hla"), 6.5),
    (("jak-stat", "il-6"), 6.0),
    (("t cell signaling", "t cell "), 6.0),
    (("tnf", "nf-κb", "nf-kb"), 5.5),
    (("interferon", "ifn", "type i interferon"), 5.0),
    (("fibrosis", "tgf", "ecm", "erosion", "osteoclast", "barrier", "epithelial"), 4.0),
]

_HIGH_RISK_PATTERNS = re.compile(
    r"interferon|anti-tnf|tnf inhibitor|tnf-alpha|checkpoint|alemtuzumab|"
    r"natalizumab|bleomycin|procainamide|hydralazine|isoniazid|minocycline|"
    r"pentamidine|diazoxide|paclitaxel|gemcitabine|bromocriptine|"
    r"ustekinumab|infliximab|adalimumab|etanercept|certolizumab|golimumab",
    re.I,
)
_MODERATE_PATTERNS = re.compile(
    r"jak inhibitor|janus kinase|azathioprine|methotrexate|sulfasalazine|"
    r"teriflunomide|dimethyl fumarate|cladribine|penicillamine|mercaptopurine|"
    r"tofacitinib|belimumab|rituximab|fingolimod|hydroxychloroquine|"
    r"glucocorticoid|corticosteroid|prednisone|mycophenolate|cyclosporine|"
    r"thalidomide|levamisole|gold salt|budesonide|thiazide",
    re.I,
)
_LOW_PATTERNS = re.compile(
    r"nsaid|mesalamine|insulin|metformin|ace inhibitor|proton pump|"
    r"pilocarpine|cevimeline|iloprost|calcium channel|glatiramer|"
    r"hydroxychloroquine|statins|oral contraceptive",
    re.I,
)


def _category_base_score(category: str) -> float:
    lowered = (category or "").lower()
    for keywords, score in _CATEGORY_RULES:
        if any(kw in lowered for kw in keywords):
            return score
    return 4.0


def _gene_score(gene: dict, category: str) -> float:
    base = _category_base_score(category)
    or_val = gene.get("odds_ratio")
    if or_val is None:
        return base
    try:
        bump = min(1.5, max(0.0, (float(or_val) - 1.0) * 0.5))
    except (TypeError, ValueError):
        bump = 0.0
    return min(10.0, round(base + bump, 1))


def derive_car_t_scores(genes_payload: dict, disease_id: str) -> dict[str, dict[str, float]]:
    """Build category-keyed CAR_T_SCORES from genes.json."""
    if disease_id == "sle":
        return {}

    scores: dict[str, dict[str, float]] = {}
    for gene in genes_payload.get("genes", []):
        gene_id = gene.get("id")
        category = gene.get("category") or "Uncategorized"
        if not gene_id:
            continue
        bucket = scores.setdefault(category, {})
        bucket[gene_id] = _gene_score(gene, category)
    return scores


def _drug_text(drug: dict) -> str:
    parts = [
        drug.get("id", ""),
        drug.get("name", ""),
        drug.get("type", ""),
        drug.get("target", ""),
        drug.get("mechanism", ""),
        drug.get("category", ""),
        drug.get("adverse_effects", ""),
    ]
    return " ".join(str(p) for p in parts if p)


def classify_drug_tier(drug: dict) -> str | None:
    """Return high_risk, moderate_risk, low_risk, or None when unclassified."""
    text = _drug_text(drug)
    if _HIGH_RISK_PATTERNS.search(text):
        return "high_risk"
    if _LOW_PATTERNS.search(text):
        return "low_risk"
    if _MODERATE_PATTERNS.search(text):
        return "moderate_risk"
    if re.search(r"biologic|monoclonal|antibody|fusion protein", text, re.I):
        return "moderate_risk"
    if re.search(r"dmard|immunosuppress|small molecule", text, re.I):
        return "moderate_risk"
    return None


def derive_drug_safety_risk(drugs_payload: dict) -> dict[str, list[str]]:
    tiers: dict[str, list[str]] = {
        "high_risk": [],
        "moderate_risk": [],
        "low_risk": [],
    }
    for drug in drugs_payload.get("drugs", []):
        drug_id = drug.get("id")
        if not drug_id:
            continue
        label = drug.get("name", drug_id).split("(")[0].strip().lower()
        tier = classify_drug_tier(drug)
        if tier is None:
            continue
        entry = label if label else drug_id
        if entry not in tiers[tier]:
            tiers[tier].append(entry)
    for tier in tiers:
        tiers[tier] = sorted(tiers[tier])
    return tiers


def derive_screening_profile(
    pathways_payload: dict,
    drugs_payload: dict,
    disease_id: str,
) -> dict[str, Any]:
    """Build a minimal SCREENING_PROFILE stub from KG pathways and drugs."""
    pathway_keywords: list[str] = []
    for pathway in pathways_payload.get("pathways", [])[:10]:
        name = str(pathway.get("name", "")).lower()
        pathway_keywords.extend(
            token
            for token in name.replace("/", " ").replace("-", " ").split()
            if len(token) > 3
        )
    pathway_keywords = sorted(set(pathway_keywords))[:10] or ["immune", "inflammation"]

    reference_drug_ids = [
        drug_id
        for drug_id in (
            drug.get("id") for drug in drugs_payload.get("drugs", [])[:6] if drug.get("id")
        )
        if drug_id
    ]

    return {
        "strategy_id": f"{disease_id}-screening-v1",
        "pathway_keywords": pathway_keywords,
        "mechanism_keywords": pathway_keywords[:10],
        "reference_drug_ids": reference_drug_ids,
        "weights": {
            "binding_estimate": 0.25,
            "druglikeness": 0.15,
            "target_complementarity": 0.35,
            "similarity_score": 0.15,
            "novelty_score": 0.10,
        },
        "source": f"scaffold_{disease_id}_knowledge_graph",
        "curated_inputs": ["pathways", "drugs", "screening_strategy"],
        "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
        "limitations": [
            "Property scores are heuristic prioritization signals and do not establish "
            "clinical efficacy or safety."
        ],
    }


def _format_screening_block(profile: dict[str, Any]) -> str:
    lines = ["SCREENING_PROFILE = {"]
    for key, value in profile.items():
        if isinstance(value, str):
            lines.append(f'    "{key}": "{value}",')
        elif isinstance(value, list):
            lines.append(f'    "{key}": [')
            for item in value:
                lines.append(f'        "{item}",')
            lines.append("    ],")
        elif isinstance(value, dict):
            lines.append(f'    "{key}": {{')
            for sub_key, sub_value in value.items():
                lines.append(f'        "{sub_key}": {sub_value},')
            lines.append("    },")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _load_config_module(disease_id: str) -> dict[str, Any]:
    from med_research.diseases.base import Disease

    return Disease(disease_id).config


def _compare_car_t(existing: dict, derived: dict, strict: bool = False) -> list[str]:
    """Structural comparison; score drift is reported only in strict rubric mode."""
    issues: list[str] = []
    if not derived and not existing:
        return issues
    if strict:
        if set(existing.keys()) != set(derived.keys()):
            missing = set(derived.keys()) - set(existing.keys())
            if missing:
                issues.append(f"CAR_T missing categories: {sorted(missing)[:5]}")
        for category in set(existing.keys()) & set(derived.keys()):
            e_genes = existing.get(category) or {}
            d_genes = derived.get(category) or {}
            for gene_id, score in d_genes.items():
                if gene_id not in e_genes:
                    issues.append(f"CAR_T missing gene {gene_id} in {category}")
                elif abs(float(e_genes[gene_id]) - float(score)) > 0.6:
                    issues.append(
                        f"CAR_T score drift {gene_id}/{category}: "
                        f"config={e_genes[gene_id]} derived={score}"
                    )
    return issues


def _compare_risk(existing: dict, derived: dict, strict: bool = False) -> list[str]:
    issues: list[str] = []
    if strict:
        for tier in ("high_risk", "moderate_risk", "low_risk"):
            existing_set = {x.lower() for x in (existing.get(tier) or [])}
            derived_set = {x.lower() for x in (derived.get(tier) or [])}
            if not existing_set and derived_set:
                issues.append(f"{tier}: config empty but derived has {len(derived_set)} entries")
    return issues


def validate_disease(disease_id: str, rubric_strict: bool = False) -> dict[str, Any]:
    """Compare config.py against KG-derived rubric and structural checks."""
    data_dir = SRC / "med_research" / "diseases" / disease_id / "data"
    genes = _load_json(data_dir / "genes.json")
    drugs = _load_json(data_dir / "drugs.json")
    config = _load_config_module(disease_id)

    derived_car_t = derive_car_t_scores(genes, disease_id)
    derived_risk = derive_drug_safety_risk(drugs)
    existing_car_t = config.get("CAR_T_SCORES") or {}
    existing_risk = (
        config.get("DRUG_SAFETY_RISK")
        or config.get("DISEASE_SPECIFIC_RISK")
        or config.get("DRUG_INDUCED_LUPUS_RISK")
        or {}
    )

    issues: list[str] = []
    if disease_id != "sle":
        issues.extend(_compare_car_t(existing_car_t, derived_car_t, strict=rubric_strict))
    issues.extend(_compare_risk(existing_risk, derived_risk, strict=rubric_strict))

    car_t_categories = len(existing_car_t)
    if disease_id == "sle":
        car_t_categories = sum(1 for k in existing_car_t if k in SLE_DIMENSION_KEYS)
    if car_t_categories < 5:
        issues.append(f"CAR_T has only {car_t_categories} categories (need >=5)")

    pubmed = config.get("PUBMED_QUERIES") or []
    if not pubmed:
        issues.append("PUBMED_QUERIES empty")
    if disease_id != "sle":
        for query in pubmed:
            lower = query.lower()
            if "lupus" in lower or re.search(r"\bsle\b", lower):
                issues.append(f"PUBMED contains SLE term: {query[:60]}")

    if not existing_risk or not any(existing_risk.values()):
        issues.append("DRUG_SAFETY_RISK tiers empty")

    if not config.get("DRUG_SAFETY_RISK"):
        issues.append("DRUG_SAFETY_RISK missing")
    if not config.get("DISEASE_SPECIFIC_RISK"):
        issues.append("DISEASE_SPECIFIC_RISK alias missing")
    if not config.get("DRUG_INDUCED_LUPUS_RISK"):
        issues.append("DRUG_INDUCED_LUPUS_RISK compat alias missing")

    return {
        "disease_id": disease_id,
        "car_t_categories": car_t_categories,
        "car_t_genes": sum(len(v) for v in existing_car_t.values() if isinstance(v, dict)),
        "risk_tiers": {k: len(v or []) for k, v in existing_risk.items()},
        "pubmed_queries": len(pubmed),
        "derived_car_t_categories": len(derived_car_t),
        "issues": issues,
        "ok": not issues,
    }


def _format_car_t_block(scores: dict[str, dict[str, float]]) -> str:
    if not scores:
        return "CAR_T_SCORES = {}\n"
    lines = ["CAR_T_SCORES = {"]
    for category in sorted(scores.keys()):
        lines.append(f'    "{category}": {{')
        for gene_id, score in sorted(scores[category].items()):
            lines.append(f'        "{gene_id}": {score},')
        lines.append("    },")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _format_risk_block(risk: dict[str, list[str]]) -> str:
    lines = ["DRUG_SAFETY_RISK = {"]
    for tier in ("high_risk", "moderate_risk", "low_risk"):
        items = risk.get(tier) or []
        lines.append(f'    "{tier}": [')
        for item in items:
            lines.append(f'        "{item}",')
        lines.append("    ],")
    lines.append("}")
    lines.append("")
    lines.append("DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK")
    lines.append("DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK")
    return "\n".join(lines)


def write_config_sections(disease_id: str, dry_run: bool = False) -> Path:
    """Replace CAR_T_SCORES and risk blocks in config.py for non-SLE diseases."""
    if disease_id == "sle":
        raise ValueError("SLE config is manually curated; use --report only for sle")

    data_dir = SRC / "med_research" / "diseases" / disease_id / "data"
    config_path = SRC / "med_research" / "diseases" / disease_id / "config.py"
    genes = _load_json(data_dir / "genes.json")
    drugs = _load_json(data_dir / "drugs.json")
    pathways = _load_json(data_dir / "pathways.json")

    car_t = derive_car_t_scores(genes, disease_id)
    risk = derive_drug_safety_risk(drugs)
    screening = derive_screening_profile(pathways, drugs, disease_id)

    text = config_path.read_text(encoding="utf-8")
    car_t_block = _format_car_t_block(car_t)
    risk_block = _format_risk_block(risk)
    screening_block = _format_screening_block(screening)

    if "CAR_T_SCORES = {" in text:
        start = text.index("CAR_T_SCORES = {")
        end = text.index("\n\n", start)
        # Find end of CAR_T block (closing brace at start of line)
        depth = 0
        end = start
        for idx in range(start, len(text)):
            if text[idx] == "{":
                depth += 1
            elif text[idx] == "}":
                depth -= 1
                if depth == 0:
                    end = idx + 1
                    break
        text = text[:start] + car_t_block.rstrip() + text[end:]

    risk_markers = (
        "DRUG_SAFETY_RISK = {",
        "DRUG_INDUCED_LUPUS_RISK = {",
        "DISEASE_SPECIFIC_RISK = ",
    )
    risk_start = None
    for marker in risk_markers:
        if marker in text:
            risk_start = text.index(marker)
            break
    if risk_start is not None:
        section_end = len(text)
        for marker in ("SCREENING_PROFILE = {", "# ── Clinical trials", "TRIAL_QUERY"):
            pos = text.find(marker, risk_start + 1)
            if pos != -1:
                section_end = min(section_end, pos)
        text = text[:risk_start] + risk_block + "\n\n" + text[section_end:]

    if "SCREENING_PROFILE = {" in text:
        start = text.index("SCREENING_PROFILE = {")
        depth = 0
        end = start
        for idx in range(start, len(text)):
            if text[idx] == "{":
                depth += 1
            elif text[idx] == "}":
                depth -= 1
                if depth == 0:
                    end = idx + 1
                    break
        text = text[:start] + screening_block.rstrip() + text[end:]

    if not dry_run:
        config_path.write_text(text, encoding="utf-8")
    return config_path


def print_report(results: list[dict[str, Any]]) -> None:
    print("\n=== Disease config curation report ===")
    for row in results:
        status = "OK" if row["ok"] else "GAPS"
        print(
            f"\n{row['disease_id']:4s} [{status}] "
            f"CAR-T: {row['car_t_categories']} categories, {row['car_t_genes']} genes | "
            f"risk tiers: {row['risk_tiers']} | pubmed: {row['pubmed_queries']}"
        )
        for issue in row["issues"]:
            safe = issue.encode("ascii", errors="replace").decode("ascii")
            print(f"  - {safe}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Populate/validate disease config curation")
    parser.add_argument("disease_id", nargs="?", help="Disease id (e.g. ra)")
    parser.add_argument("--all", action="store_true", help="Process all seven diseases")
    parser.add_argument("--write", action="store_true", help="Write derived blocks to config.py")
    parser.add_argument("--report", action="store_true", help="Print validation report")
    parser.add_argument("--check", action="store_true", help="Validate config against rubric")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when validation issues exist")
    parser.add_argument("--json", action="store_true", help="Emit report as JSON")
    args = parser.parse_args(argv)

    disease_ids = list(DISEASE_IDS) if args.all else ([args.disease_id] if args.disease_id else [])
    if not disease_ids:
        parser.error("Provide disease_id or --all")

    rubric_strict = args.strict and args.check
    results = [validate_disease(did, rubric_strict=rubric_strict) for did in disease_ids]

    if args.write:
        for did in disease_ids:
            if did == "sle":
                print("Skipping write for sle (reference config)")
                continue
            path = write_config_sections(did)
            print(f"Updated {path}")
            results = [validate_disease(did, rubric_strict=rubric_strict) for did in disease_ids]

    if args.json:
        print(json.dumps(results, indent=2))
    elif args.report or args.check or not args.write:
        print_report(results)

    if args.strict and any(not r["ok"] for r in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
