"""Disease scaffolding — bootstrap new disease modules from public knowledge bases.

The bottleneck to scaling the platform beyond its curated diseases is the
per-disease data files (genes/drugs/pathways/relationships + config.py).
This module automates the *first draft* of those files from free public
sources so a human only has to review and refine:

  * Genes     — Open Targets Platform (EFO association scores) + NHGRI-EBI
                GWAS Catalog (author-reported genes from trait studies)
  * Drugs     — Open Targets Platform known-drugs (approved + investigational,
                with clinical phase and mechanism of action)
  * Pathways  — Reactome ContentService disease-pathway search, merged with
                a built-in keyword -> pathway template so scaffolds are useful
                even when Reactome is unreachable
  * Relations — derived deterministically (drug TARGETS gene, gene
                PARTICIPATES_IN pathway, gene ASSOCIATED_WITH disease,
                drug TREATS disease for late-stage/approved agents)

Everything is emitted as plain JSON/Python matching the schemas in
``diseases/schemas.py`` so a scaffolded module works with the full pipeline
and the knowledge-graph builder immediately.

Usage:
    med-research disease add crohns --name "Crohn's disease"
    med-research disease add ra2 --name "Rheumatoid Arthritis" --efo EFO_0001370
    med-research disease validate crohns
    med-research disease refresh sle --prune          Re-merge + drop entities no source reports
    med-research disease restore sle --backup ...     Re-merge a pruned backup (undo --prune)
    med-research disease backups sle --purge --keep 5 List / prune old backups
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Union, cast

from med_research.cache import CacheManager
from med_research.logging_config import get_logger

logger = get_logger(__name__)

# ── External API endpoints ───────────────────────────────────────────────

OPENTARGETS_URL = "https://platform-api.opentargets.org/v4/graphql"
GWAS_API = "https://www.ebi.ac.uk/gwas/rest/api"
REACTOME_API = "https://reactome.org/ContentService"
USER_AGENT = "med-research-platform/2.0 (disease scaffold)"

# Open Targets query fragments
_OT_SEARCH_QUERY = """
query($q: String!) {
  search(queryString: $q, entityNames: ["disease"]) {
    hits { id name entity }
  }
}
"""
_OT_TARGETS_QUERY = """
query($efo: String!, $size: Int!) {
  disease(efoId: $efo) {
    id name synonyms description { value }
    associatedTargets(page: { index: 0, size: $size }) {
      count
      rows {
        score
        target { id approvedSymbol approvedName biotype }
      }
    }
  }
}
"""
_OT_DRUGS_QUERY = """
query($efo: String!, $size: Int!) {
  disease(efoId: $efo) {
    knownDrugs(size: $size) {
      count
      rows {
        drug { id name drugType }
        maximumClinicalTrialPhase
        target { approvedSymbol }
        mechanismsOfAction { rows { actionType mechanismOfAction target { approvedSymbol } } }
      }
    }
  }
}
"""


# ── HTTP helpers (module-level so tests can monkeypatch them) ────────────

def _http_get_json(url: str, params: Optional[dict] = None, timeout: int = 30) -> Optional[dict]:
    """GET a JSON endpoint; return None on any failure (scaffold degrades gracefully)."""
    import requests

    try:
        resp = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        return cast(dict, resp.json())
    except Exception as e:  # noqa: BLE001 — scaffold must degrade gracefully
        logger.warning("GET %s failed: %s", url, e)
        return None


def _http_post_json(url: str, payload: dict, timeout: int = 30) -> Optional[dict]:
    """POST a JSON payload (GraphQL); return None on any failure."""
    import requests

    try:
        resp = requests.post(
            url, json=payload, timeout=timeout, headers={"User-Agent": USER_AGENT}
        )
        resp.raise_for_status()
        return cast(dict, resp.json())
    except Exception as e:  # noqa: BLE001
        logger.warning("POST %s failed: %s", url, e)
        return None


# ── Identifiers & helpers ────────────────────────────────────────────────

def sanitize_id(name: str) -> str:
    """Turn a free-form name into a lowercase slug usable as a disease ID."""
    # Drop apostrophes/possessives, then collapse other separators to '_'
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower().replace("'", "")).strip("_")
    return slug or "disease"


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _first(items: list) -> Optional[str]:
    return items[0] if items else None


# ── Open Targets Platform ────────────────────────────────────────────────

def search_efo_id(name: str) -> Optional[str]:
    """Resolve a disease name to an Open Targets EFO id (e.g. EFO_0001370)."""
    if not name:
        return None
    data = _http_post_json(
        OPENTARGETS_URL,
        {"query": _OT_SEARCH_QUERY, "variables": {"q": name}},
    )
    if not data:
        return None
    hits = ((data.get("data") or {}).get("search") or {}).get("hits") or []
    for hit in hits:
        if hit.get("entity") == "disease" and hit.get("id", "").startswith("EFO_"):
            return cast(str, hit["id"])
    return None


def fetch_ot_disease_info(efo_id: str) -> dict:
    """Return {name, synonyms, description} for an EFO id (best-effort)."""
    data = _http_post_json(
        OPENTARGETS_URL,
        {"query": _OT_TARGETS_QUERY, "variables": {"efo": efo_id, "size": 1}},
    )
    if not data:
        return {}
    disease = (data.get("data") or {}).get("disease") or {}
    synonyms = disease.get("synonyms") or []
    name = disease.get("name") or ""
    # synonyms can be a list of strings or of {term} dicts in some responses
    cleaned = [
        s.get("term", s) if isinstance(s, dict) else s
        for s in synonyms
        if isinstance(s, (dict, str))
    ]
    description = ""
    raw_desc = disease.get("description")
    # OT v4 returns a single {value} object; some mirror/legacy shapes are lists
    if isinstance(raw_desc, dict):
        description = raw_desc.get("value", "")
    elif isinstance(raw_desc, list) and raw_desc:
        description = raw_desc[0].get("value", "") if isinstance(raw_desc[0], dict) else ""
    return {"name": name, "synonyms": cleaned[:5], "description": description}


def fetch_ot_associated_targets(efo_id: str, max_genes: int = 60) -> list[dict]:
    """Fetch disease-associated targets from Open Targets.

    Returns a list of ``{"symbol", "name", "score"}`` sorted by score desc,
    filtered to protein-coding targets.
    """
    data = _http_post_json(
        OPENTARGETS_URL,
        {"query": _OT_TARGETS_QUERY, "variables": {"efo": efo_id, "size": max_genes}},
    )
    if not data:
        return []
    disease = (data.get("data") or {}).get("disease") or {}
    rows = (disease.get("associatedTargets") or {}).get("rows") or []
    targets = []
    for row in rows:
        target = row.get("target") or {}
        symbol = target.get("approvedSymbol") or ""
        if not symbol:
            continue
        biotype = target.get("biotype", "")
        if biotype and biotype != "protein_coding":
            continue
        targets.append({
            "symbol": symbol,
            "name": target.get("approvedName") or symbol,
            "score": row.get("score"),
        })
    targets.sort(key=lambda t: t["score"] or 0, reverse=True)
    return targets[:max_genes]


def fetch_ot_known_drugs(efo_id: str, max_drugs: int = 60) -> list[dict]:
    """Fetch known drugs for a disease from Open Targets.

    Returns a list of dicts with id/name/type/phase/status/targets/mechanism.
    """
    data = _http_post_json(
        OPENTARGETS_URL,
        {"query": _OT_DRUGS_QUERY, "variables": {"efo": efo_id, "size": max_drugs}},
    )
    if not data:
        return []
    disease = (data.get("data") or {}).get("disease") or {}
    rows = (disease.get("knownDrugs") or {}).get("rows") or []
    drugs = []
    for row in rows:
        drug = row.get("drug") or {}
        drug_id = drug.get("id") or ""
        if not drug_id:
            continue
        # Targets from the row level and/or mechanism rows
        targets = []
        mechanism = ""
        mechanisms = ((row.get("mechanismsOfAction") or {}).get("rows")) or []
        for m in mechanisms:
            target = (m.get("target") or {}).get("approvedSymbol")
            if target and target not in targets:
                targets.append(target)
            moa = m.get("mechanismOfAction") or m.get("actionType") or ""
            if moa and not mechanism:
                mechanism = moa
        row_target = (row.get("target") or {}).get("approvedSymbol")
        if row_target and row_target not in targets:
            targets.append(row_target)

        drugs.append({
            "id": drug_id,
            "name": drug.get("name") or drug_id,
            "type": drug.get("drugType") or "",
            "phase": row.get("maximumClinicalTrialPhase"),
            "status": row.get("status") or "",
            "targets": targets,
            "mechanism": mechanism,
        })
    # Prefer drugs with a target and a phase; keep API order otherwise.
    drugs.sort(
        key=lambda d: (not d["targets"], d.get("phase") is None),
    )
    return drugs[:max_drugs]


# ── GWAS Catalog (reuses the proven parsing in bioinformatics/gwas.py) ───

def _gwas_genes_for_trait(trait: str, max_studies: int = 15) -> list[dict]:
    """Return author-reported genes for a trait via the GWAS Catalog.

    Returns a list of ``{"symbol", "n_studies", "best_p"}``. Uses the same
    parsing as the bioinformatics module but with SNP resolution disabled
    (fast: only author-reported genes are used).
    """
    from med_research.pipeline.bioinformatics.gwas import (
        extract_gene_associations,
        search_gwas_studies,
    )

    studies = search_gwas_studies(trait, max_results=max_studies)
    if not studies:
        return []
    results = extract_gene_associations(studies, max_studies=max_studies, resolve_snps=False)
    genes = []
    for symbol, info in results.get("gene_associations", {}).items():
        genes.append({
            "symbol": symbol,
            "n_studies": info.get("n_studies", 1),
            "best_p": info.get("best_p_value"),
        })
    genes.sort(key=lambda g: (g["n_studies"] or 0), reverse=True)
    return genes


# ── Reactome ─────────────────────────────────────────────────────────────

def fetch_reactome_pathways(name: str, max_pathways: int = 15) -> list[dict]:
    """Search Reactome for disease-relevant canonical pathways.

    Returns a list of ``{"id", "name", "description"}`` for pathway hits.
    """
    data = _http_get_json(
        f"{REACTOME_API}/data/query/search",
        params={"query": name, "types": "Pathway", "species": "Homo sapiens"},
        timeout=30,
    )
    if not data or not isinstance(data, list):
        return []
    pathways = []
    for hit in data:
        if hit.get("schemaClass") != "Pathway":
            continue
        pathways.append({
            "id": hit.get("stId") or "",
            "name": hit.get("displayName") or "",
            "description": (hit.get("description") or "").get("value", ""),
        })
    return [p for p in pathways if p["id"] and p["name"]][:max_pathways]


# ── Keyword -> pathway template (offline fallback / gene membership) ─────

KEYWORD_PATHWAYS: dict[str, dict] = {
    "jak-stat": {
        "name": "JAK-STAT Signaling",
        "description": "Cytokine receptor signaling through JAK kinases and STAT transcription factors; a hub for inflammatory and autoimmune disease pathways.",
        "keywords": ["JAK", "STAT", "TYK2", "SOCS", "PIAS"],
    },
    "nfkb": {
        "name": "NF-κB Pathway",
        "description": "Canonical and non-canonical NF-κB activation driving pro-inflammatory gene expression.",
        "keywords": ["NFKB", "TNFAIP3", "TNIP1", "REL", "IKB", "NFAT", "IKK", "CHUK", "CARD"],
    },
    "tnf-signaling": {
        "name": "TNF Signaling",
        "description": "Tumor necrosis factor receptor superfamily signaling; central to many autoimmune and inflammatory diseases.",
        "keywords": ["TNF", "TNFSF", "TNFR", "TRAF", "LTA", "LTB", "FAS", "TRADD"],
    },
    "type1-ifn": {
        "name": "Type I Interferon Pathway",
        "description": "IFN-α/β production and signaling through IFNAR; drives the interferon gene signature in autoimmune disease.",
        "keywords": ["IFN", "IRF", "MX1", "OAS", "ISG15", "STAT1", "ADAR", "IFIH1", "RIGI", "DDX58"],
    },
    "il6-signaling": {
        "name": "IL-6 Signaling",
        "description": "Interleukin-6 signaling via gp130 and STAT3; a key amplifier of systemic inflammation.",
        "keywords": ["IL6", "IL6R", "IL6ST", "GP130", "STAT3"],
    },
    "th17-il17": {
        "name": "Th17 / IL-17 Pathway",
        "description": "Th17 differentiation and IL-17 family cytokine signaling driving neutrophil recruitment and autoimmunity.",
        "keywords": ["IL17", "IL23", "RORC", "RORA", "CCR6", "IL21", "IL22", "IL12"],
    },
    "il1-inflammasome": {
        "name": "IL-1 / Inflammasome Pathway",
        "description": "NLRP3 inflammasome assembly and IL-1β/IL-18 maturation; a driver of sterile inflammation.",
        "keywords": ["IL1", "NLRP", "CASP1", "PYCARD", "IL18", "MEFV", "PSTPIP"],
    },
    "il4-il13": {
        "name": "IL-4 / IL-13 (Th2) Pathway",
        "description": "Type 2 cytokine signaling driving allergic and eosinophilic inflammation.",
        "keywords": ["IL4", "IL13", "IL4R", "STAT6", "GATA3", "IL5", "TSLP", "IL33"],
    },
    "bcr-signaling": {
        "name": "B Cell Receptor Signaling",
        "description": "BCR signal transduction controlling B cell survival, proliferation, and antibody production.",
        "keywords": ["CD19", "MS4A1", "CD20", "BLK", "BANK1", "BTK", "SYK", "LYN", "CD79", "PLCG2", "BCMA", "TNFRSF17", "CD22", "SIGLEC"],
    },
    "tcr-signaling": {
        "name": "T Cell Receptor Signaling",
        "description": "TCR signal transduction and T cell activation; a therapeutic hub in autoimmunity.",
        "keywords": ["CD3", "CD28", "CTLA4", "ICOS", "LAT", "ZAP70", "LCK", "PTPN22", "THEMIS", "CD8", "CD4"],
    },
    "complement": {
        "name": "Complement Cascade",
        "description": "Classical, lectin, and alternative complement pathways for opsonization, lysis, and immune complex clearance.",
        "keywords": ["C1Q", "C1QA", "C1QB", "C1QC", "C4A", "C4B", "C3AR1", "C5AR1", "CFH", "CFI", "MASP", "MBL", "ITGAM", "CR1", "CR2", "CD46", "SERPING1"],
    },
    "tlr-signaling": {
        "name": "TLR / Innate Sensing",
        "description": "Endosomal and surface Toll-like receptor signaling driving innate immune activation.",
        "keywords": ["TLR", "MYD88", "IRAK", "IRF7", "TICAM", "TRIF", "TRAF6", "UNC93B1"],
    },
    "apoptosis": {
        "name": "Apoptosis",
        "description": "Intrinsic and extrinsic programmed cell death; dysregulation contributes to autoimmunity and cancer.",
        "keywords": ["BCL2", "BAX", "BAD", "BIM", "BCL2L11", "CASP", "FADD", "RIPK", "MCL1", "XIAP", "BIRC"],
    },
    "autophagy": {
        "name": "Autophagy",
        "description": "Autophagosome formation and lysosomal degradation maintaining cellular and immune homeostasis.",
        "keywords": ["ATG", "BECN1", "ULK", "SQSTM1", "MAP1LC3", "LC3", "WIPI"],
    },
    "wnt-signaling": {
        "name": "Wnt Signaling",
        "description": "Canonical Wnt/β-catenin signaling controlling cell fate, proliferation, and tissue regeneration.",
        "keywords": ["WNT", "CTNNB1", "APC", "AXIN", "GSK3B", "LRP", "TCF7", "LEF1"],
    },
    "notch-signaling": {
        "name": "Notch Signaling",
        "description": "Notch receptor signaling regulating cell fate decisions and immune development.",
        "keywords": ["NOTCH", "DLL", "JAG", "RBPJ", "MAML", "ADAM10"],
    },
    "hedgehog": {
        "name": "Hedgehog Signaling",
        "description": "Hedgehog morphogen signaling governing embryonic patterning and stem cell maintenance.",
        "keywords": ["SHH", "IHH", "DHH", "GLI", "SMO", "PTCH"],
    },
    "mapk-erk": {
        "name": "MAPK / ERK Signaling",
        "description": "RAS-RAF-MEK-ERK cascade coupling growth factor receptors to proliferation and differentiation.",
        "keywords": ["MAPK", "ERK", "MEK", "MAP2K", "RAF", "RAS", "KRAS", "NRAS", "HRAS", "BRAF", "EGFR", "FGFR"],
    },
    "pi3k-akt-mtor": {
        "name": "PI3K / AKT / mTOR Signaling",
        "description": "Growth and survival signaling through PI3K-AKT-mTOR; a major oncology and immunology target hub.",
        "keywords": ["PI3K", "PIK3", "AKT", "MTOR", "PTEN", "TSC", "RHEB", "S6K", "RPS6KB1"],
    },
    "tgf-beta": {
        "name": "TGF-β Signaling",
        "description": "Transforming growth factor beta signaling controlling fibrosis, immune tolerance, and tumor suppression.",
        "keywords": ["TGFB", "TGFBR", "SMAD", "LTBP", "FBN"],
    },
    "vegf-angiogenesis": {
        "name": "VEGF / Angiogenesis",
        "description": "Vascular endothelial growth factor signaling driving angiogenesis and vascular permeability.",
        "keywords": ["VEGFA", "VEGFB", "VEGFC", "KDR", "VEGFR", "FLT1", "PGF", "HIF1A", "EPAS1"],
    },
    "cell-cycle": {
        "name": "Cell Cycle Regulation",
        "description": "Cyclin-CDK machinery controlling cell division; a backbone of oncology target discovery.",
        "keywords": ["CDK", "CCND", "CCNA", "CCNE", "RB1", "E2F", "MKI67", "CDC25", "WEE1", "AURK"],
    },
    "dna-repair": {
        "name": "DNA Repair",
        "description": "Homologous recombination, mismatch repair, and base excision pathways preserving genome integrity.",
        "keywords": ["BRCA", "ATM", "ATR", "PARP", "RAD51", "MLH", "MSH", "TP53", "CHEK", "FANCD"],
    },
    "immune-checkpoint": {
        "name": "Immune Checkpoint Signaling",
        "description": "Co-inhibitory receptor signaling (PD-1/CTLA-4/TIGIT/LAG-3) that restrains T cell responses.",
        "keywords": ["PDCD1", "CD274", "PDL1", "CTLA4", "LAG3", "HAVCR2", "TIGIT", "VSIR"],
    },
    "integrin-adhesion": {
        "name": "Integrin / Cell Adhesion",
        "description": "Integrin-mediated adhesion and leukocyte trafficking into inflamed tissue.",
        "keywords": ["ITGA", "ITGB", "VCAM", "ICAM", "SELE", "SELL", "SELP", "MADCAM"],
    },
    "chemokine-signaling": {
        "name": "Chemokine Signaling",
        "description": "Chemokine-receptor interactions directing leukocyte migration and lymphoid organization.",
        "keywords": ["CXCL", "CCL", "CXCR", "CCR", "ACKR", "XCL"],
    },
    "bone-remodeling": {
        "name": "Bone Remodeling",
        "description": "RANK-RANKL-OPG axis and osteoclast/osteoblast balance governing skeletal homeostasis.",
        "keywords": ["RANKL", "TNFSF11", "TNFRSF11A", "RANK", "OPG", "TNFRSF11B", "SOST", "RUNX2", "WNT1"],
    },
    "mast-cell": {
        "name": "Mast Cell / IgE Signaling",
        "description": "FcεRI-mediated mast cell activation and degranulation in allergic disease.",
        "keywords": ["KIT", "FCER1", "MRGPR", "TPSAB", "TPSB", "CPA3", "HDC"],
    },
    "coagulation": {
        "name": "Coagulation Cascade",
        "description": "Plasma coagulation factors and fibrinolysis; a hub for cardiovascular and thrombotic disease.",
        "keywords": ["F2", "F7", "F8", "F9", "F10", "VWF", "PLAT", "SERPINE1", "FGB", "FGG", "PROC"],
    },
    "lipid-metabolism": {
        "name": "Lipid Metabolism",
        "description": "Cholesterol and lipid homeostasis; the therapeutic hub of cardiovascular disease.",
        "keywords": ["LDLR", "PCSK9", "APOE", "APOB", "HMGCR", "CETP", "LPL", "FABP", "PPARG", "ANGPTL"],
    },
    "glucose-metabolism": {
        "name": "Glucose Metabolism / Insulin Secretion",
        "description": "Pancreatic β-cell function, insulin secretion, and glycemic control.",
        "keywords": ["SLC2A", "GCK", "G6PC", "HNF1", "HNF4", "PDX1", "ABCC8", "KCNJ11", "INS", "INSR", "IRS1", "GLP1R", "DPP4"],
    },
    "ecm-remodeling": {
        "name": "ECM Remodeling",
        "description": "Matrix metalloproteinases and extracellular matrix turnover in tissue remodeling and fibrosis.",
        "keywords": ["MMP", "TIMP", "COL", "ELN", "ADAM", "ADAMTS", "LOX", "PLOD"],
    },
    "thyroid-hormone": {
        "name": "Thyroid Hormone Signaling",
        "description": "Thyroid hormone synthesis, transport, and nuclear receptor signaling.",
        "keywords": ["TSHR", "THRB", "THRA", "TPO", "TG", "SLC5A5", "DIO"],
    },
    "gaba-glutamate": {
        "name": "GABA / Glutamate Signaling",
        "description": "Principal inhibitory and excitatory neurotransmitter signaling in the CNS.",
        "keywords": ["GABRA", "GABRB", "GRIA", "GRIN", "GRM", "SLC1A", "GAD", "GLUL"],
    },
    "serotonin-dopamine": {
        "name": "Serotonin / Dopamine Signaling",
        "description": "Monoamine neurotransmission; the pharmacological hub of psychiatry.",
        "keywords": ["HTR", "DRD", "SLC6A4", "SLC6A3", "MAOA", "COMT", "TH", "TPH"],
    },
    "opioid-signaling": {
        "name": "Opioid Signaling",
        "description": "Endogenous and exogenous opioid receptor signaling in pain and analgesia.",
        "keywords": ["OPRM", "OPRD", "OPRK", "PENK", "PDYN", "POMC", "OPN4"],
    },
    "cardiac-ion-channel": {
        "name": "Cardiac Ion Channel / Conduction",
        "description": "Voltage-gated sodium, potassium, and calcium channels governing cardiac excitability.",
        "keywords": ["SCN5A", "KCNQ", "KCNH", "KCNA", "CACNA", "HCN", "RYR2", "PLN"],
    },
    "renin-angiotensin": {
        "name": "Renin-Angiotensin System",
        "description": "Renin-angiotensin-aldosterone axis controlling blood pressure and fluid balance.",
        "keywords": ["ACE", "ACE2", "AGT", "AGTR1", "REN", "NR3C2", "CYP11B2"],
    },
    "xenobiotic-metabolism": {
        "name": "Xenobiotic Metabolism",
        "description": "Cytochrome P450 and conjugating enzymes governing drug metabolism and toxicity.",
        "keywords": ["CYP", "GST", "UGT", "NAT", "SULT", "ABCB", "ABCC", "SLCO"],
    },
    "hepcidin-iron": {
        "name": "Hepcidin / Iron Homeostasis",
        "description": "Hepcidin-ferroportin axis regulating systemic iron balance.",
        "keywords": ["HAMP", "HFE", "TFRC", "SLC40A1", "TFR2", "HJV", "BMP", "ERFE"],
    },
}


def keyword_pathways(genes: list[dict]) -> list[dict]:
    """Assign genes to built-in pathway templates by symbol keyword match.

    ``genes`` is a list of dicts with at least a "symbol" key. Returns a list
    of ``{"id", "name", "description", "key_components"}`` for every template
    that matched at least one gene.
    """
    matched: dict[str, set[str]] = {}
    for gene in genes:
        symbol_key = (gene.get("symbol") or gene.get("id") or "")
        symbol = symbol_key.upper()
        if not symbol:
            continue
        for pid, tmpl in KEYWORD_PATHWAYS.items():
            if any(kw.upper() in symbol for kw in tmpl["keywords"]):
                matched.setdefault(pid, set()).add(symbol_key)

    pathways = []
    for pid in sorted(matched):
        tmpl = KEYWORD_PATHWAYS[pid]
        pathways.append({
            "id": pid,
            "name": tmpl["name"],
            "description": tmpl["description"],
            "key_components": sorted(matched[pid]),
            "therapeutic_targets": sorted(matched[pid]),
            "references": [],
        })
    return pathways


# ── File builders ────────────────────────────────────────────────────────

def build_genes_json(
    ot_targets: list[dict],
    gwas_genes: list[dict],
    disease_id: str,
    max_genes: int = 60,
) -> dict:
    """Merge Open Targets + GWAS genes into genes.json (deduped by symbol)."""
    merged: dict[str, dict] = {}

    def _add(symbol: str, **updates: Any) -> None:
        key = symbol.upper()
        if key not in merged:
            merged[key] = {
                "id": symbol,
                "name": symbol,
                "chromosome": "",
                "function": "",
                "disease_evidence": "",
                "odds_ratio": None,
                "references": [],
                "category": "",
            }
        for k, v in updates.items():
            if not v:
                continue
            if k == "disease_evidence" and merged[key][k]:
                merged[key][k] = f"{merged[key][k]} | {v}"
            else:
                merged[key][k] = v

    for g in ot_targets:
        score = g.get("score")
        evidence = (
            f"Open Targets association score {score:.2f}" if score is not None
            else "Open Targets disease-associated target"
        )
        _add(g["symbol"], name=g.get("name") or g["symbol"], disease_evidence=evidence)

    for g in gwas_genes:
        p = g.get("best_p")
        p_text = f"{p:.1e}" if p is not None else "n/a"
        evidence = f"GWAS Catalog: {g['n_studies']} study(ies), best p={p_text}"
        _add(g["symbol"], disease_evidence=evidence)

    # Keep the merged list ordered by Open Targets score when available
    order = {g["symbol"].upper(): i for i, g in enumerate(ot_targets)}
    genes = sorted(
        merged.values(),
        key=lambda g: (order.get(g["id"].upper(), 10**6), g["id"].lower()),
    )
    return {"genes": genes[:max_genes]}


def _approval_text(phase: Any, status: str) -> str:
    status = (status or "").strip()
    if status and status.lower() not in ("unknown", "investigational"):
        return status
    if phase is None:
        return ""
    try:
        phase = int(phase)
    except (TypeError, ValueError):
        return ""
    if phase == 0:
        return "Approved"
    if phase >= 4:
        return "Phase 4 / marketed"
    return f"Phase {phase}"


def build_drugs_json(ot_drugs: list[dict]) -> dict:
    """Turn Open Targets known-drugs rows into drugs.json entries."""
    drugs = []
    for d in ot_drugs:
        if not d.get("id"):
            continue
        target = _first(d.get("targets") or []) or ""
        drugs.append({
            "id": d["id"],
            "name": d.get("name") or d["id"],
            "type": d.get("type") or "",
            "target": target,
            "mechanism": d.get("mechanism") or "",
            "approval": _approval_text(d.get("phase"), d.get("status") or ""),
            "route": "",
            "efficacy": "",
            "references": [],
            "category": "",
            "disease_evidence": f"Open Targets known-drug association (max phase {d.get('phase') or 'n/a'})",
        })
    return {"drugs": drugs}


def build_pathways_json(
    reactome: list[dict],
    genes: list[dict],
    max_pathways: int = 30,
) -> dict:
    """Merge Reactome disease pathways with keyword-template pathways.

    Reactome pathways win for the top slots; keyword templates provide
    gene-membership depth. ``genes`` is the list of gene dicts (with "symbol").
    """
    pathways = []
    gene_symbols: dict[str, str] = {
        (g.get("symbol") or g.get("id") or "").upper(): cast(
            str, g.get("symbol") or g.get("id")
        )
        for g in genes
        if (g.get("symbol") or g.get("id"))
    }

    # Prefer Reactome hits that match at least one scaffolded gene by keyword
    for rp in reactome:
        members = _match_pathway_genes(rp.get("name", ""), gene_symbols)
        pathways.append({
            "id": _slugify(rp.get("name", rp.get("id", ""))) or rp.get("id", ""),
            "name": rp.get("name") or rp.get("id", ""),
            "description": rp.get("description") or f"Reactome pathway implicated in {rp.get('name') or 'disease'}.",
            "key_components": members,
            "therapeutic_targets": members,
            "references": [
                f"https://reactome.org/content/detail/{rp.get('id', '')}"
            ] if rp.get("id") else [],
        })

    keyword = keyword_pathways(genes)
    pathways.extend(keyword)

    # Dedupe by name (case-insensitive), Reactome first
    seen, unique = set(), []
    for p in pathways:
        key = p["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    return {"pathways": unique[:max_pathways]}


def _match_pathway_genes(pathway_name: str, gene_symbols: dict[str, str]) -> list[str]:
    """Best-effort match of scaffolded genes to a Reactome pathway by keyword."""
    tokens = {w for w in re.findall(r"[A-Za-z0-9]+", pathway_name.lower()) if len(w) > 2}
    hits = []
    for upper, symbol in gene_symbols.items():
        if any(tok in upper.lower() for tok in tokens):
            hits.append(symbol)
    return sorted(hits)


def build_relationships_json(
    genes: list[dict],
    drugs: list[dict],
    pathways: list[dict],
    disease_label: str,
) -> dict:
    """Derive relationships deterministically from the scaffolded entities."""
    gene_ids = {g["id"] for g in genes}
    relationships = []

    # drug TARGETS gene
    for d in drugs:
        target = d.get("target") or ""
        if target and target in gene_ids:
            relationships.append({
                "source": d["id"],
                "target": target,
                "type": "TARGETS",
                "description": f"{d.get('name', d['id'])} targets {target}.",
            })

    # drug TREATS disease (approved / late-stage only)
    for d in drugs:
        approval = (d.get("approval") or "").lower()
        if any(token in approval for token in ("approv", "phase 3", "phase 4", "marketed", "launched")):
            relationships.append({
                "source": d["id"],
                "target": disease_label,
                "type": "TREATS",
                "description": (
                    f"{d.get('name', d['id'])} is {approval} for {disease_label}."
                ),
            })

    # gene PARTICIPATES_IN pathway
    for p in pathways:
        for comp in p.get("key_components") or []:
            if comp in gene_ids:
                relationships.append({
                    "source": comp,
                    "target": p["id"],
                    "type": "PARTICIPATES_IN",
                    "description": f"{comp} is a component of the {p['name']} pathway.",
                })

    # gene ASSOCIATED_WITH disease
    for g in genes:
        evidence = (g.get("disease_evidence") or "").strip()
        relationships.append({
            "source": g["id"],
            "target": disease_label,
            "type": "ASSOCIATED_WITH",
            "description": f"{g['id']} is associated with {disease_label}. {evidence}".strip(),
        })

    return {"relationships": relationships}


def build_profile(disease_id: str, name: str, description: str, key_pathways: list[str]) -> dict:
    return {
        "id": disease_id,
        "name": name,
        "description": description or f"{name} — auto-generated scaffold; review and refine.",
        "prevalence": "",
        "female_to_male_ratio": "",
        "peak_onset": "",
        "primary_tissue": "",
        "hallmark_markers": [],
        "key_pathways": key_pathways[:5],
        "kg_node_id": f"{name} ({disease_id.upper()})",
    }


def generate_config_py(disease_id: str, name: str) -> str:
    """Generate the disease config.py scaffold."""
    label = f"{name} ({disease_id.upper()})"
    acronym = name.split()[0] if name else disease_id
    return f'''"""{label} disease configuration.

AUTO-GENERATED by `med-research disease add`. Review and fill in the
disease-specific parameters below before running the pipeline.
"""

PIPELINE_LABEL = "{label}"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
# TODO: add the clinical symptoms of {name}
SYMPTOMS = []

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    '({name}[Title/Abstract]) AND (treatment[Title/Abstract])',
    '({name}[Title/Abstract]) AND (genetics[Title/Abstract] OR genomics[Title/Abstract])',
    '({name}[Title/Abstract]) AND (clinical trial[Title/Abstract])',
    '({name}[Title/Abstract]) AND (biomarker[Title/Abstract])',
]

# ── Clinical trials / GWAS search terms (consumed by the web + bio modules) ─
TRIAL_QUERY = "{name} OR {acronym}"
GWAS_SEARCH_TERMS = ["{name}", "{acronym}"]

# ── CAR-T Scoring Tables (used by car_t_predictor/predictor.py) ──────────
# TODO: derive with scripts/populate_disease_configs.py after curating genes
CAR_T_SCORES = {{}}

# ── Drug-Induced Disease Risk (legacy key name; used by adverse_events) ──
# TODO: fill in drugs that can induce or exacerbate {name}
DRUG_INDUCED_LUPUS_RISK = {{
    "high_risk": [],
    "moderate_risk": [],
    "low_risk": [],
}}
'''


# ── Orchestration ────────────────────────────────────────────────────────

def _diseases_root() -> Path:
    import med_research.diseases as diseases_pkg

    return Path(diseases_pkg.__file__).parent


def _collect_sources(
    disease_id: str,
    name: str,
    efo_id: Optional[str] = None,
    max_genes: int = 60,
    max_drugs: int = 60,
    max_pathways: int = 30,
    use_gwas: bool = True,
    use_opentargets: bool = True,
    use_reactome: bool = True,
    use_cache: bool = True,
) -> dict:
    """Fetch every scaffold source and build the fresh entity payloads.

    Shared by ``scaffold_disease`` and ``refresh_disease`` so both commands
    hit exactly the same sources. Returns a dict with the resolved EFO id,
    the display name, and the freshly-built genes/drugs/pathways JSON.
    """
    cache = CacheManager() if use_cache else None
    resolved_efo = efo_id
    ot_info: dict = {}
    if use_opentargets:
        if not resolved_efo:
            if cache:
                resolved_efo = cache.get("scaffold", f"efo:{name}")
            if not resolved_efo:
                logger.info("🔍 Searching Open Targets for '%s'...", name)
                resolved_efo = search_efo_id(name)
                if cache and resolved_efo:
                    cache.set("scaffold", f"efo:{name}", resolved_efo)
        if resolved_efo:
            ot_info = fetch_ot_disease_info(resolved_efo)

    display_name = ot_info.get("name") or name

    ot_targets: list[dict] = []
    if use_opentargets and resolved_efo:
        logger.info("🧬 Fetching Open Targets genes (EFO %s)...", resolved_efo)
        ot_targets = fetch_ot_associated_targets(resolved_efo, max_genes)

    gwas_genes: list[dict] = []
    if use_gwas:
        logger.info("🧬 Fetching GWAS Catalog genes for '%s'...", display_name)
        gwas_genes = _gwas_genes_for_trait(display_name, max_studies=15)

    genes_json = build_genes_json(ot_targets, gwas_genes, disease_id, max_genes)

    drugs_json: dict[str, Any] = {"drugs": []}
    if use_opentargets and resolved_efo:
        logger.info("💊 Fetching Open Targets known drugs...")
        ot_drugs = fetch_ot_known_drugs(resolved_efo, max_drugs)
        drugs_json = build_drugs_json(ot_drugs)

    reactome: list[dict] = []
    if use_reactome:
        logger.info("🗺️  Searching Reactome for '%s'...", display_name)
        reactome = fetch_reactome_pathways(display_name, max_pathways)
    pathways_json = build_pathways_json(reactome, genes_json["genes"], max_pathways)

    return {
        "efo_id": resolved_efo,
        "name": display_name,
        "description": ot_info.get("description", ""),
        "genes": genes_json,
        "drugs": drugs_json,
        "pathways": pathways_json,
        "reactome_hits": reactome,
        "ot_targets": ot_targets,
        "gwas_genes": gwas_genes,
    }


def scaffold_disease(
    disease_id: str,
    name: Optional[str] = None,
    efo_id: Optional[str] = None,
    max_genes: int = 60,
    max_drugs: int = 60,
    max_pathways: int = 30,
    use_gwas: bool = True,
    use_opentargets: bool = True,
    use_reactome: bool = True,
    target_dir: Optional[Path] = None,
    overwrite: bool = False,
    use_cache: bool = True,
) -> dict:
    """Scaffold a disease module from public knowledge bases.

    Writes ``__init__.py``, ``config.py``, and ``data/{genes,drugs,pathways,
    relationships,profile}.json`` into ``target_dir`` (defaults to the real
    ``diseases/<id>/`` directory). Returns a summary dict for reporting.

    Every external source degrades gracefully: if a source fails or is
    disabled, the others still produce a usable scaffold.
    """
    disease_id = sanitize_id(disease_id or "")
    name = (name or disease_id).strip()
    if not disease_id or not name:
        raise ValueError("disease_id and name are required")

    root = target_dir or (_diseases_root() / disease_id)
    data_dir = root / "data"
    if root.exists() and any(root.iterdir()) and not overwrite:
        raise FileExistsError(
            f"Disease module '{disease_id}' already exists at {root}. "
            "Use --overwrite to regenerate it."
        )

    sources = _collect_sources(
        disease_id=disease_id,
        name=name,
        efo_id=efo_id,
        max_genes=max_genes,
        max_drugs=max_drugs,
        max_pathways=max_pathways,
        use_gwas=use_gwas,
        use_opentargets=use_opentargets,
        use_reactome=use_reactome,
        use_cache=use_cache,
    )
    resolved_efo = sources["efo_id"]
    display_name = sources["name"]
    genes_json = sources["genes"]
    drugs_json = sources["drugs"]
    pathways_json = sources["pathways"]

    # ── Relationships / profile / config ──────────────────────────────
    disease_label = f"{display_name} ({disease_id.upper()})"
    relationships_json = build_relationships_json(
        genes_json["genes"], drugs_json["drugs"], pathways_json["pathways"], disease_label
    )
    key_pathways = [p["name"] for p in pathways_json["pathways"][:5]]
    profile_json = build_profile(disease_id, display_name, sources.get("description") or "", key_pathways)

    # ── Write files ───────────────────────────────────────────────────
    root.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "config.py").write_text(generate_config_py(disease_id, display_name), encoding="utf-8")
    for fname, payload in (
        ("genes.json", genes_json),
        ("drugs.json", drugs_json),
        ("pathways.json", pathways_json),
        ("relationships.json", relationships_json),
        ("profile.json", profile_json),
    ):
        (data_dir / fname).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    return {
        "disease_id": disease_id,
        "name": display_name,
        "efo_id": resolved_efo,
        "root": str(root),
        "sources": {
            "opentargets": bool(sources["ot_targets"] or drugs_json["drugs"]),
            "gwas": bool(sources["gwas_genes"]),
            "reactome": bool(sources["reactome_hits"]),
            "keyword_pathways": len(pathways_json["pathways"]) > len(sources["reactome_hits"]),
        },
        "counts": {
            "genes": len(genes_json["genes"]),
            "drugs": len(drugs_json["drugs"]),
            "pathways": len(pathways_json["pathways"]),
            "relationships": len(relationships_json["relationships"]),
        },
        "files": [
            str(root / "__init__.py"),
            str(root / "config.py"),
            *(str(data_dir / f) for f in ("genes.json", "drugs.json", "pathways.json", "relationships.json", "profile.json")),
        ],
    }

# ── Refresh (merge into an existing module) ─────────────────────────────

# Fields that are treated as human-curated and must never be overwritten by
# a refresh. Source-derived fields (e.g. a drug's approval phase) update;
# curated fields (category, function, evidence text, references) are kept
# verbatim when a matching entity already exists — though an *empty* curated
# value is backfilled when a fresh source provides one.
GENE_CURATED_FIELDS = frozenset({
    "id", "name", "chromosome", "function", "lupus_evidence",
    "sle_evidence", "odds_ratio", "references", "category",
})
GENE_EVIDENCE_FIELD = "disease_evidence"  # appended, never replaced

DRUG_CURATED_FIELDS = frozenset({
    "id", "name", "category", "route", "efficacy",
    "adverse_effects", "references", "mechanism",
})
DRUG_EVIDENCE_FIELD = "disease_evidence"  # appended, never replaced

PATHWAY_CURATED_FIELDS = frozenset({"id", "name", "description", "references"})
PATHWAY_LIST_FIELDS = frozenset({"key_components", "therapeutic_targets"})

# Prefixes of auto-generated source evidence fragments (see build_genes_json /
# build_drugs_json). On refresh these fragments are *replaced* rather than
# accumulated, so repeated refreshes don't grow an evidence trail; any other
# (human-written) text is preserved.
_SOURCE_EVIDENCE_PREFIXES = ("Open Targets", "GWAS Catalog")


def _is_empty(value: Any) -> bool:
    """True for None, '', or an empty list (used for curated backfill)."""
    return value is None or value == "" or value == []


def _append_evidence(existing: str, fresh: str) -> str:
    """Merge fresh source evidence into curated evidence.

    Source-generated fragments (starting with "Open Targets" or "GWAS
    Catalog") in the existing text are *replaced* by the fresh fragment, so
    repeated refreshes with updated study counts don't accumulate stale
    lines. Human-written text is preserved, and identical evidence is never
    duplicated.
    """
    if not fresh:
        return existing
    if not existing:
        return fresh
    # Preserve human-written fragments only.
    curated_parts = [
        part.strip()
        for part in existing.split("|")
        if part.strip() and not part.strip().startswith(_SOURCE_EVIDENCE_PREFIXES)
    ]
    combined = [*curated_parts, fresh.strip()]
    return " | ".join(dict.fromkeys(p for p in combined if p))


def merge_genes(existing: list[dict], fresh: list[dict]) -> dict:
    """Merge freshly-scaffolded genes into the existing curated gene list.

    For genes already present (matched by id), curated fields are preserved
    verbatim and new source evidence is *appended* to disease_evidence — the
    curated text is never replaced. Brand-new genes are added with the full
    scaffold values. Returns ``{"genes": [...], "added": [...],
    "updated": [...], "kept": [...]}``.
    """
    existing_by_id = {g["id"]: g for g in existing}
    merged: list[dict] = []
    added: list[str] = []
    updated: list[str] = []
    kept: list[str] = []

    for gene in fresh:
        gid = gene["id"]
        if gid not in existing_by_id:
            merged.append(gene)
            added.append(gid)
            continue
        old = existing_by_id[gid]
        merged.append(_merge_entity(old, gene, GENE_CURATED_FIELDS, GENE_EVIDENCE_FIELD, updated, gid))

    # Any existing genes the sources no longer report are retained as-is.
    fresh_ids = {g["id"] for g in fresh}
    for gid, gene in existing_by_id.items():
        if gid not in fresh_ids:
            merged.append(gene)

    kept = [gid for gid in existing_by_id if gid not in updated]
    return {"genes": merged, "added": added, "updated": updated, "kept": kept}


def merge_drugs(existing: list[dict], fresh: list[dict]) -> dict:
    """Merge freshly-scaffolded drugs into the existing curated drug list.

    Curated fields (category, mechanism, efficacy, adverse effects, …) are
    preserved; the source-derived approval/type/target fields update; new
    source evidence is appended. Returns ``{"drugs": [...], "added": [...],
    "updated": [...], "kept": [...]}``.
    """
    existing_by_id = {d["id"]: d for d in existing}
    merged: list[dict] = []
    added: list[str] = []
    updated: list[str] = []
    kept: list[str] = []

    for drug in fresh:
        did = drug["id"]
        if did not in existing_by_id:
            merged.append(drug)
            added.append(did)
            continue
        old = existing_by_id[did]
        merged.append(_merge_entity(old, drug, DRUG_CURATED_FIELDS, DRUG_EVIDENCE_FIELD, updated, did))

    fresh_ids = {d["id"] for d in fresh}
    for did, drug in existing_by_id.items():
        if did not in fresh_ids:
            merged.append(drug)

    kept = [did for did in existing_by_id if did not in updated]
    return {"drugs": merged, "added": added, "updated": updated, "kept": kept}


def merge_pathways(existing: list[dict], fresh: list[dict]) -> dict:
    """Merge freshly-derived pathways into the existing curated pathway list.

    Pathway lists (key_components / therapeutic_targets) are unioned so new
    gene memberships appear; curated text fields are preserved. Returns
    ``{"pathways": [...], "added": [...], "updated": [...], "kept": [...]}``.
    """
    existing_by_id = {p["id"]: p for p in existing}
    merged: list[dict] = []
    added: list[str] = []
    updated: list[str] = []
    kept: list[str] = []

    for pathway in fresh:
        pid = pathway["id"]
        if pid not in existing_by_id:
            merged.append(pathway)
            added.append(pid)
            continue
        old = existing_by_id[pid]
        merged.append(_merge_entity(old, pathway, PATHWAY_CURATED_FIELDS, None, updated, pid, PATHWAY_LIST_FIELDS))

    fresh_ids = {p["id"] for p in fresh}
    for pid, pathway in existing_by_id.items():
        if pid not in fresh_ids:
            merged.append(pathway)

    kept = [pid for pid in existing_by_id if pid not in updated]
    return {"pathways": merged, "added": added, "updated": updated, "kept": kept}


def _merge_entity(
    old: dict,
    fresh: dict,
    curated_fields: frozenset,
    evidence_field: Optional[str],
    updated: list[str],
    eid: str,
    list_fields: frozenset = frozenset(),
) -> dict:
    """Merge a fresh entity into its existing curated counterpart.

    * curated scalar fields -> keep existing value verbatim; backfill with
        the fresh value only when the existing value is empty
    * list fields           -> union existing + fresh
    * evidence field        -> replace stale source fragments, append fresh,
        preserve human-written text
    * anything else (source-derived scalars) -> take the fresh value when
      present, else keep existing
    Any change beyond the existing record marks the entity as updated.
    """
    out = dict(old)
    changed = False
    for key, fresh_val in fresh.items():
        if key in curated_fields:
            # Never overwrite a curated value, but fill an empty one.
            if _is_empty(out.get(key)) and not _is_empty(fresh_val) and fresh_val != out.get(key):
                changed = True
                out[key] = fresh_val
            continue
        if evidence_field and key == evidence_field:
            new_val = _append_evidence(out.get(key, ""), fresh_val)
            if new_val != out.get(key, ""):
                changed = True
                out[key] = new_val
            continue
        if key in list_fields:
            union = list(dict.fromkeys([*(out.get(key) or []), *(fresh_val or [])]))
            if union != (out.get(key) or []):
                changed = True
                out[key] = union
            continue
        if (fresh_val or not out.get(key)) and fresh_val != out.get(key):
            changed = True
            out[key] = fresh_val
    if changed:
        updated.append(eid)
    return out


def _load_json_list(path: Path, key: str) -> list[dict]:
    """Load a data file's list (empty on any failure) for merging."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get(key, []) if isinstance(data, dict) else []
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not read %s — treating as empty for merge.", path)
        return []


def _existing_disease_label(root: Path, display_name: str, disease_id: str) -> str:
    """Reuse the disease label already used in relationships.json if present."""
    rel_path = root / "data" / "relationships.json"
    rels = _load_json_list(rel_path, "relationships")
    for rel in rels:
        target = rel.get("target") or ""
        if rel.get("type") in ("ASSOCIATED_WITH", "TREATS") and target:
            return target
    return f"{display_name} ({disease_id.upper()})"


def refresh_disease(
    disease_id: str,
    efo_id: Optional[str] = None,
    max_genes: int = 60,
    max_drugs: int = 60,
    max_pathways: int = 30,
    use_gwas: bool = True,
    use_opentargets: bool = True,
    use_reactome: bool = True,
    use_cache: bool = True,
    target_dir: Optional[Path] = None,
    dry_run: bool = False,
    prune: bool = False,
    confirm: Optional[Callable[[dict], bool]] = None,
) -> dict:
    """Re-run the scaffold sources and merge new entities into an existing module.

    Only ``data/genes.json``, ``data/drugs.json``, ``data/pathways.json`` and
    ``data/relationships.json`` are touched; ``profile.json``, ``config.py``
    and ``__init__.py`` are left alone. Curated fields (category, function,
    evidence text, references, …) on existing entities are preserved; brand-new
    genes/drugs/pathways are added with scaffold values; relationships are
    fully rebuilt from the merged entities.

    With ``dry_run=True`` nothing is written — the returned summary reports
    what *would* change.

    With ``prune=True``, genes/drugs that *no* source reports on this run are
    removed. When ``confirm`` is provided it is called with a plan dict
    (name/disease_id/genes/drugs) and may veto the prune by returning False;
    a declined prune aborts with nothing changed. Removed entities are backed
    up to ``data/backups/pruned_<id>_<timestamp>.json`` and their ids are
    scrubbed from pathway component lists so the rebuilt relationships stay
    consistent. Returns a summary dict for reporting.
    """
    disease_id = sanitize_id(disease_id or "")
    if not disease_id:
        raise ValueError("disease_id is required")

    root = target_dir or (_diseases_root() / disease_id)
    data_dir = root / "data"
    if not (root / "__init__.py").exists() or not (data_dir / "profile.json").exists():
        raise FileNotFoundError(
            f"No disease module '{disease_id}' found at {root}. "
            "Run 'med-research disease add <id>' first."
        )

    # Use the module's own display name (curated profile wins over sources)
    name = disease_id
    try:
        profile = json.loads((data_dir / "profile.json").read_text(encoding="utf-8"))
        name = profile.get("name") or name
    except (json.JSONDecodeError, OSError):
        pass

    sources = _collect_sources(
        disease_id=disease_id,
        name=name,
        efo_id=efo_id,
        max_genes=max_genes,
        max_drugs=max_drugs,
        max_pathways=max_pathways,
        use_gwas=use_gwas,
        use_opentargets=use_opentargets,
        use_reactome=use_reactome,
        use_cache=use_cache,
    )
    display_name = sources["name"]

    existing_genes = _load_json_list(data_dir / "genes.json", "genes")
    existing_drugs = _load_json_list(data_dir / "drugs.json", "drugs")
    existing_pathways = _load_json_list(data_dir / "pathways.json", "pathways")

    gene_merge = merge_genes(existing_genes, sources["genes"]["genes"])
    drug_merge = merge_drugs(existing_drugs, sources["drugs"]["drugs"])
    pathway_merge = merge_pathways(existing_pathways, sources["pathways"]["pathways"])

    # ── Prune: remove entities no source reports any more ───────────────
    apply_write = not dry_run
    prune_info: dict = {
        "enabled": prune,
        "aborted": False,
        "genes": [],
        "drugs": [],
        "scrubbed_pathways": [],
        "backup": None,
    }
    if prune:
        fresh_gene_ids = {g["id"] for g in sources["genes"]["genes"]}
        fresh_drug_ids = {d["id"] for d in sources["drugs"]["drugs"]}
        prune_info["genes"] = sorted(g["id"] for g in existing_genes if g["id"] not in fresh_gene_ids)
        prune_info["drugs"] = sorted(d["id"] for d in existing_drugs if d["id"] not in fresh_drug_ids)

        # Confirmation gate: only for a real (non dry-run) prune with work to do.
        # Declining aborts the *entire* write — nothing on disk changes.
        if not dry_run and (prune_info["genes"] or prune_info["drugs"]) and confirm is not None:
            plan = {
                "name": display_name,
                "disease_id": disease_id,
                "genes": prune_info["genes"],
                "drugs": prune_info["drugs"],
            }
            if not confirm(plan):
                prune_info["aborted"] = True
                apply_write = False
                prune = False

        if prune and apply_write and (prune_info["genes"] or prune_info["drugs"]):
            pruned_gene_ids = set(prune_info["genes"])
            pruned_drug_ids = set(prune_info["drugs"])
            gene_merge["genes"] = [g for g in gene_merge["genes"] if g["id"] not in pruned_gene_ids]
            gene_merge["kept"] = [gid for gid in gene_merge["kept"] if gid not in pruned_gene_ids]
            drug_merge["drugs"] = [d for d in drug_merge["drugs"] if d["id"] not in pruned_drug_ids]
            drug_merge["kept"] = [did for did in drug_merge["kept"] if did not in pruned_drug_ids]
            prune_info["scrubbed_pathways"] = _scrub_pathway_components(
                pathway_merge["pathways"], pruned_gene_ids, pathway_merge["updated"]
            )
            prune_info["backup"] = str(
                _write_prune_backup(
                    data_dir, disease_id, existing_genes, existing_drugs,
                    existing_pathways, pruned_gene_ids, pruned_drug_ids,
                )
            )

    disease_label = _existing_disease_label(root, display_name, disease_id)
    relationships = build_relationships_json(
        gene_merge["genes"], drug_merge["drugs"], pathway_merge["pathways"], disease_label
    )

    if apply_write:
        for fname, payload in (
            ("genes.json", {"genes": gene_merge["genes"]}),
            ("drugs.json", {"drugs": drug_merge["drugs"]}),
            ("pathways.json", {"pathways": pathway_merge["pathways"]}),
            ("relationships.json", relationships),
        ):
            (data_dir / fname).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    summary = {
        "disease_id": disease_id,
        "name": display_name,
        "efo_id": sources["efo_id"],
        "root": str(root),
        "dry_run": dry_run,
        "prune": prune_info,
        "sources": {
            "opentargets": bool(sources["ot_targets"] or sources["drugs"]["drugs"]),
            "gwas": bool(sources["gwas_genes"]),
            "reactome": bool(sources["reactome_hits"]),
        },
        "merge": {
            "genes": {"added": gene_merge["added"], "updated": gene_merge["updated"], "kept": gene_merge["kept"]},
            "drugs": {"added": drug_merge["added"], "updated": drug_merge["updated"], "kept": drug_merge["kept"]},
            "pathways": {"added": pathway_merge["added"], "updated": pathway_merge["updated"], "kept": pathway_merge["kept"]},
        },
        "counts": {
            "genes": len(gene_merge["genes"]),
            "drugs": len(drug_merge["drugs"]),
            "pathways": len(pathway_merge["pathways"]),
            "relationships": len(relationships["relationships"]),
        },
        "files": [
            str(data_dir / f) for f in ("genes.json", "drugs.json", "pathways.json", "relationships.json")
        ],
    }

    # Trace the mutation: a prune that actually wrote files is audited (a
    # declined prune or dry-run never reaches here). Recording is best-effort.
    if apply_write and prune_info["enabled"] and not prune_info["aborted"]:
        from med_research.diseases import audit

        audit.append_audit(disease_id, audit.prune_entry(summary), target_dir=root)

    return summary


def _scrub_pathway_components(
    pathways: list[dict],
    pruned_gene_ids: set[str],
    updated: list[str],
) -> list[str]:
    """Remove pruned gene ids from pathway component lists.

    Mutates each pathway's ``key_components``/``therapeutic_targets`` in place
    so the rebuilt relationships don't reference removed genes, and marks
    every affected pathway as updated. Returns the ids of scrubbed pathways.
    """
    pruned_upper = {gid.upper() for gid in pruned_gene_ids}
    scrubbed: list[str] = []
    for p in pathways:
        changed = False
        for field in ("key_components", "therapeutic_targets"):
            comps = p.get(field) or []
            filtered = [c for c in comps if c.upper() not in pruned_upper]
            if len(filtered) != len(comps):
                p[field] = filtered
                changed = True
        if changed:
            if p["id"] not in updated:
                updated.append(p["id"])
            if p["id"] not in scrubbed:
                scrubbed.append(p["id"])
    return scrubbed


def _write_prune_backup(
    data_dir: Path,
    disease_id: str,
    existing_genes: list[dict],
    existing_drugs: list[dict],
    existing_pathways: list[dict],
    pruned_gene_ids: set[str],
    pruned_drug_ids: set[str],
) -> Path:
    """Snapshot pruned entities to ``data/backups/pruned_<id>_<ts>.json``.

    Records each pruned gene's pre-prune pathway membership so ``restore`` can
    re-attach it exactly — the prune's pathway scrub is fully reversible.
    """
    backup_dir = data_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    # Microseconds so two prunes in the same second never clobber each other's backup.
    backup_path = backup_dir / f"pruned_{disease_id}_{datetime.now():%Y%m%d_%H%M%S_%f}.json"
    pathway_memberships = {
        gid: [p["id"] for p in existing_pathways if gid in (p.get("key_components") or [])]
        for gid in sorted(pruned_gene_ids)
    }
    payload = {
        "disease_id": disease_id,
        "pruned_at": datetime.now().isoformat(timespec="seconds"),
        "note": (
            "Entities removed by `med-research disease refresh --prune` because no "
            "source reported them on this run. Restore with "
            "`med-research disease restore <id> --backup <this file>`."
        ),
        "genes": [g for g in existing_genes if g["id"] in pruned_gene_ids],
        "drugs": [d for d in existing_drugs if d["id"] in pruned_drug_ids],
        "pathway_memberships": pathway_memberships,
    }
    backup_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return backup_path


# ── Restore (re-merge a pruned backup) ──────────────────────────────────

def _load_backup(data_dir: Path, disease_id: str, explicit: Optional[Union[str, Path]]) -> dict:
    """Locate + parse a prune backup (explicit path, else newest for the disease)."""
    if explicit is not None:
        path = Path(explicit)
        if not path.exists():
            raise FileNotFoundError(f"Backup file not found: {path}")
    else:
        backup_dir = data_dir / "backups"
        candidates = (
            sorted(backup_dir.glob(f"pruned_{disease_id}_*.json"))
            if backup_dir.exists()
            else []
        )
        if not candidates:
            raise FileNotFoundError(
                f"No pruned backups for '{disease_id}' in {backup_dir}. "
                "Pass --backup <file> to restore a specific backup."
            )
        path = candidates[-1]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Could not parse backup {path}: {e}") from e
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("genes"), list)
        or not isinstance(data.get("drugs"), list)
    ):
        raise ValueError(f"{path} is not a prune backup (expected 'genes' and 'drugs' lists).")
    data["_path"] = str(path)
    return data


def _pathway_matches_gene(pathway: dict, gene_upper: str) -> bool:
    """Keyword-template or name-token match of a gene symbol against a pathway."""
    template = KEYWORD_PATHWAYS.get(pathway.get("id", ""))
    if template and any(kw.upper() in gene_upper for kw in template["keywords"]):
        return True
    return bool(_match_pathway_genes(pathway.get("name", ""), {gene_upper: gene_upper}))


def _restore_pathway_membership(
    pathways: list[dict],
    restored_genes: list[dict],
    memberships: Optional[dict],
) -> list[str]:
    """Re-attach restored genes to their pre-prune pathways.

    Uses the backup's ``pathway_memberships`` map when present (lossless);
    otherwise falls back to keyword-matching gene symbols against pathway
    names/templates (best-effort for legacy backups). Returns changed ids.
    """
    by_id = {p["id"]: p for p in pathways}
    changed: list[str] = []
    for gene in restored_genes:
        gid = gene.get("id") or ""
        if not gid:
            continue
        if memberships is None:
            # Legacy backup without a membership map: best-effort keyword match.
            upper = gid.upper()
            target_ids = [
                pid for pid, p in by_id.items() if _pathway_matches_gene(p, upper)
            ]
        else:
            # The recorded map is authoritative: absent key = was in no pathway.
            target_ids = memberships.get(gid) or []
        for pid in target_ids:
            p = by_id.get(pid)
            if p is None:
                continue
            for field in ("key_components", "therapeutic_targets"):
                comps = p.get(field) or []
                if gid not in comps:
                    p[field] = [*comps, gid]
            if pid not in changed:
                changed.append(pid)
    return changed


def restore_disease(
    disease_id: str,
    backup_path: Optional[Union[str, Path]] = None,
    target_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> dict:
    """Re-merge a pruned backup back into a disease module.

    Restores every backed-up gene/drug *verbatim* — the exact entity dicts
    from before the prune, curated fields included. Entities whose id is
    already in the module are skipped (the current version wins). Pre-prune
    pathway membership is re-attached when the backup recorded it, and
    relationships.json is rebuilt, returning the module to its pre-prune shape.

    Without ``backup_path`` the newest ``data/backups/pruned_<id>_*.json`` is
    used. With ``dry_run=True`` nothing is written. Returns a summary dict.
    """
    disease_id = sanitize_id(disease_id or "")
    if not disease_id:
        raise ValueError("disease_id is required")

    root = target_dir or (_diseases_root() / disease_id)
    data_dir = root / "data"
    if not (root / "__init__.py").exists() or not (data_dir / "profile.json").exists():
        raise FileNotFoundError(
            f"No disease module '{disease_id}' found at {root}. "
            "Run 'med-research disease add <id>' first."
        )

    backup = _load_backup(data_dir, disease_id, backup_path)
    if backup.get("disease_id") and backup["disease_id"] != disease_id:
        logger.warning(
            "Backup was created for '%s' but restoring into '%s'.",
            backup["disease_id"], disease_id,
        )

    # Use the module's own display name for relationships (profile wins).
    name = disease_id
    try:
        profile = json.loads((data_dir / "profile.json").read_text(encoding="utf-8"))
        name = profile.get("name") or name
    except (json.JSONDecodeError, OSError):
        pass

    existing_genes = _load_json_list(data_dir / "genes.json", "genes")
    existing_drugs = _load_json_list(data_dir / "drugs.json", "drugs")
    existing_pathways = _load_json_list(data_dir / "pathways.json", "pathways")

    backup_genes = backup.get("genes") or []
    backup_drugs = backup.get("drugs") or []
    existing_gene_ids = {g["id"] for g in existing_genes}
    existing_drug_ids = {d["id"] for d in existing_drugs}

    restored_genes = [g for g in backup_genes if g.get("id") and g["id"] not in existing_gene_ids]
    restored_drugs = [d for d in backup_drugs if d.get("id") and d["id"] not in existing_drug_ids]
    skipped_genes = [g["id"] for g in backup_genes if g.get("id") in existing_gene_ids]
    skipped_drugs = [d["id"] for d in backup_drugs if d.get("id") in existing_drug_ids]

    genes_out = [*existing_genes, *restored_genes]
    drugs_out = [*existing_drugs, *restored_drugs]
    pathways_out = list(existing_pathways)
    updated_pathways = _restore_pathway_membership(
        pathways_out, restored_genes, backup.get("pathway_memberships")
    )

    disease_label = _existing_disease_label(root, name, disease_id)
    relationships = build_relationships_json(genes_out, drugs_out, pathways_out, disease_label)

    if not dry_run:
        for fname, payload in (
            ("genes.json", {"genes": genes_out}),
            ("drugs.json", {"drugs": drugs_out}),
            ("pathways.json", {"pathways": pathways_out}),
            ("relationships.json", relationships),
        ):
            (data_dir / fname).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    summary = {
        "disease_id": disease_id,
        "backup": backup["_path"],
        "backup_disease_id": backup.get("disease_id"),
        "root": str(root),
        "dry_run": dry_run,
        "restored": {
            "genes": [g["id"] for g in restored_genes],
            "drugs": [d["id"] for d in restored_drugs],
        },
        "skipped": {"genes": skipped_genes, "drugs": skipped_drugs},
        "updated_pathways": updated_pathways,
        "counts": {
            "genes": len(genes_out),
            "drugs": len(drugs_out),
            "pathways": len(pathways_out),
            "relationships": len(relationships["relationships"]),
        },
        "files": [
            str(data_dir / f) for f in ("genes.json", "drugs.json", "pathways.json", "relationships.json")
        ],
    }

    if not dry_run:
        from med_research.diseases import audit

        audit.append_audit(disease_id, audit.restore_entry(summary), target_dir=root)

    return summary


def print_restore_summary(summary: dict) -> None:
    """Print a human-readable summary of a backup restore."""
    s = summary
    mode = "DRY-RUN — no files written" if s["dry_run"] else "files updated"
    logger.info("\n" + "=" * 70)
    logger.info(f"♻️  DISEASE RESTORED: {s['disease_id']}")
    logger.info("=" * 70)
    logger.info(f"  Backup:       {s['backup']}")
    logger.info(f"  Backup was:   {s['backup_disease_id'] or '—'}")
    logger.info(f"  Module dir:   {s['root']}")
    logger.info(f"  Mode:         {mode}")
    logger.info(f"\n  Restored: {len(s['restored']['genes'])} genes, {len(s['restored']['drugs'])} drugs")
    for gid in s["restored"]["genes"]:
        logger.info(f"    gene  {gid}")
    for did in s["restored"]["drugs"]:
        logger.info(f"    drug  {did}")
    if s["skipped"]["genes"] or s["skipped"]["drugs"]:
        logger.info(
            f"\n  Skipped (already present): {len(s['skipped']['genes'])} genes, "
            f"{len(s['skipped']['drugs'])} drugs"
        )
    if s["updated_pathways"]:
        logger.info(f"\n  Pathway membership re-attached: {len(s['updated_pathways'])} pathways")
    logger.info("\n  Counts (after restore):")
    for k, v in s["counts"].items():
        logger.info(f"    {k:<14} {v}")
    written = not s["dry_run"]
    logger.info(f"\n  {'Files written:' if written else 'Files (would be written):'}")
    for f in s["files"]:
        logger.info(f"    {f}")
    if not written:
        logger.info("\n  Re-run without --dry-run to apply these changes.")
    logger.info("=" * 70)


# ── Backup housekeeping (list / purge) ──────────────────────────────────

def list_backups(disease_id: str, target_dir: Optional[Path] = None) -> dict:
    """Inventory the pruned backups for a disease (newest first).

    Each entry carries the file path, size, mtime, and — when parseable — the
    gene/drug ids the backup would restore. Returns ``{"disease_id",
    "backups": [...], "count", "total_size_bytes"}``.
    """
    disease_id = sanitize_id(disease_id or "")
    if not disease_id:
        raise ValueError("disease_id is required")

    root = target_dir or (_diseases_root() / disease_id)
    if not (root / "__init__.py").exists():
        raise FileNotFoundError(
            f"No disease module '{disease_id}' found at {root}. "
            "Run 'med-research disease add <id>' first."
        )
    backup_dir = root / "data" / "backups"
    if not backup_dir.exists():
        return {"disease_id": disease_id, "backups": [], "count": 0, "total_size_bytes": 0}

    entries = []
    # Filenames embed %Y%m%d_%H%M%S_%f timestamps → lexicographic == chronological.
    for path in sorted(backup_dir.glob(f"pruned_{disease_id}_*.json"), reverse=True):
        entry = {
            "path": str(path),
            "size_bytes": 0,
            "modified": "",
            "genes": [],
            "drugs": [],
            "backup_disease_id": None,
            "readable": True,
        }
        try:
            entry["size_bytes"] = path.stat().st_size
            entry["modified"] = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
            data = json.loads(path.read_text(encoding="utf-8"))
            entry["backup_disease_id"] = data.get("disease_id")
            entry["genes"] = [g.get("id", "?") for g in data.get("genes") or [] if isinstance(g, dict)]
            entry["drugs"] = [d.get("id", "?") for d in data.get("drugs") or [] if isinstance(d, dict)]
        except (json.JSONDecodeError, OSError):
            # Unreadable or deleted-while-listing (race): flag it, don't crash.
            entry["readable"] = False
        entries.append(entry)

    return {
        "disease_id": disease_id,
        "backups": entries,
        "count": len(entries),
        "total_size_bytes": sum(e["size_bytes"] for e in entries),
    }


def purge_backups(
    disease_id: str,
    keep: int = 5,
    target_dir: Optional[Path] = None,
    dry_run: bool = False,
    confirm: Optional[Callable[[list[dict]], bool]] = None,
) -> dict:
    """Delete all but the ``keep`` newest pruned backups for a disease.

    ``keep`` is clamped to >= 0 (0 deletes every backup). When ``confirm`` is
    provided it is called with the deletion candidates and may veto the purge
    by returning False — a declined purge deletes nothing. With
    ``dry_run=True`` nothing is deleted; the summary previews the purge.
    """
    inventory = list_backups(disease_id, target_dir=target_dir)
    backups = inventory["backups"]  # newest first
    keep = max(0, keep)
    delete_candidates = backups[keep:]
    keep_entries = backups[:keep]

    if delete_candidates and confirm is not None and not confirm(delete_candidates):
        return {
            **inventory,
            "purge": {
                "enabled": True, "aborted": True, "keep": keep, "dry_run": dry_run,
                "deleted": [], "freed_bytes": 0,
                "kept": [e["path"] for e in keep_entries],
            },
        }

    if dry_run:
        deleted = [e["path"] for e in delete_candidates]
        freed = sum(e["size_bytes"] for e in delete_candidates)
    else:
        deleted, freed = [], 0
        for entry in delete_candidates:
            try:
                path = Path(entry["path"])
                freed += path.stat().st_size
                path.unlink()
                deleted.append(entry["path"])
            except OSError as e:
                logger.warning("Could not delete %s: %s", entry["path"], e)

    return {
        **inventory,
        "purge": {
            "enabled": True, "aborted": False, "keep": keep, "dry_run": dry_run,
            "deleted": deleted, "freed_bytes": freed,
            "kept": [e["path"] for e in keep_entries],
        },
    }


def print_backups_summary(summary: dict) -> None:
    """Print a backup inventory or purge summary."""
    s = summary
    purge = s.get("purge")
    if purge and purge["aborted"]:
        head = "⚠️  PURGE ABORTED — nothing deleted"
    elif purge and purge["dry_run"]:
        head = "🗑️  PURGE PREVIEW (dry-run — nothing deleted)"
    elif purge:
        head = "🗑️  BACKUPS PURGED"
    else:
        head = "💾 BACKUP INVENTORY"
    logger.info("\n" + "=" * 70)
    logger.info(f"{head}: {s['disease_id']}")
    logger.info("=" * 70)

    if not s["backups"]:
        logger.info("  No pruned backups found.")
        logger.info("=" * 70)
        return

    for e in s["backups"]:
        name = Path(e["path"]).name
        logger.info(f"\n  {name}")
        logger.info(f"    Size: {e['size_bytes']:,} bytes   Modified: {e['modified']}")
        if not e["readable"]:
            logger.info("    (unreadable — cannot show contents)")
            continue
        gene_ids = e["genes"]
        drug_ids = e["drugs"]
        logger.info(f"    Restores: {len(gene_ids)} gene(s), {len(drug_ids)} drug(s)")
        if gene_ids:
            shown = ", ".join(gene_ids[:8]) + (f" … and {len(gene_ids) - 8} more" if len(gene_ids) > 8 else "")
            logger.info(f"      Genes: {shown}")
        if drug_ids:
            shown = ", ".join(drug_ids[:8]) + (f" … and {len(drug_ids) - 8} more" if len(drug_ids) > 8 else "")
            logger.info(f"      Drugs: {shown}")

    logger.info("\n  " + "-" * 66)
    logger.info(f"  Total: {s['count']} backup(s), {s['total_size_bytes']:,} bytes")

    if purge:
        p = purge
        logger.info(f"\n  Keep newest: {p['keep']}")
        if p["aborted"]:
            logger.warning("  ⚠️  Deletion cancelled by user — no files removed.")
        else:
            verb = "would delete" if p["dry_run"] else "deleted"
            logger.info(f"  {verb.capitalize()}: {len(p['deleted'])} backup(s), {p['freed_bytes']:,} bytes freed")
            for path in p["deleted"]:
                logger.info(f"    - {Path(path).name}")
            logger.info(f"  Kept: {len(p['kept'])} backup(s)")
            for path in p["kept"]:
                logger.info(f"    + {Path(path).name}")
        if p["dry_run"]:
            logger.info("\n  Re-run without --dry-run to delete.")
    logger.info("=" * 70)


def print_refresh_summary(summary: dict) -> None:
    """Print a human-readable summary of a refresh merge."""
    s = summary
    if s["dry_run"]:
        mode = "DRY-RUN — no files written"
    elif s.get("prune", {}).get("aborted"):
        mode = "ABORTED by user — no files written"
    else:
        mode = "files updated"
    logger.info("\n" + "=" * 70)
    logger.info(f"🔄 DISEASE REFRESHED: {s['name']} ({s['disease_id']})")
    logger.info("=" * 70)
    logger.info(f"  EFO id:      {s['efo_id'] or '—'}")
    logger.info(f"  Module dir:  {s['root']}")
    logger.info(f"  Mode:        {mode}")
    logger.info("\n  Sources used:")
    for src, ok in s["sources"].items():
        logger.warning(f"    {'✅' if ok else '⚠️  '} {src}")
    logger.info("\n  Merge results:")
    for kind in ("genes", "drugs", "pathways"):
        m = s["merge"][kind]
        logger.info(f"    {kind:<9} +{len(m['added'])} added, ~{len(m['updated'])} updated, {len(m['kept'])} unchanged")
    p = s.get("prune") or {}
    if p.get("enabled"):
        if p.get("aborted"):
            logger.warning("\n  Prune: ⚠️  aborted by user — no entities removed")
        else:
            verb = "would remove" if s["dry_run"] else "removed"
            logger.info(f"\n  Prune: {verb} {len(p['genes'])} genes, {len(p['drugs'])} drugs")
            for gid in p["genes"][:10]:
                logger.info(f"    gene  {gid}")
            for did in p["drugs"][:10]:
                logger.info(f"    drug  {did}")
            if p.get("scrubbed_pathways"):
                logger.info(f"    {len(p['scrubbed_pathways'])} pathways scrubbed of pruned genes")
            if not s["dry_run"] and p.get("backup"):
                logger.info(f"    Backup: {p['backup']}")
    logger.info("\n  Added:")
    for kind in ("genes", "drugs", "pathways"):
        for eid in s["merge"][kind]["added"][:10]:
            logger.info(f"    {kind:<9} {eid}")
    logger.info("\n  Counts (after merge):")
    for k, v in s["counts"].items():
        logger.info(f"    {k:<14} {v}")
    written = not s["dry_run"] and not s.get("prune", {}).get("aborted")
    logger.info(f"\n  {'Files written:' if written else 'Files (would be written):'}")
    for f in s["files"]:
        logger.info(f"    {f}")
    if not written:
        logger.info("\n  Nothing was written — re-run to apply these changes.")
    logger.info("=" * 70)


def print_scaffold_summary(summary: dict) -> None:
    """Print a human-readable review summary for a scaffold."""
    s = summary
    logger.info("\n" + "=" * 70)
    logger.info(f"✅ DISEASE SCAFFOLDED: {s['name']} ({s['disease_id']})")
    logger.info("=" * 70)
    logger.info(f"  EFO id:      {s['efo_id'] or '— (not resolved; genes/drugs limited)'}")
    logger.info(f"  Target dir:  {s['root']}")
    logger.info("\n  Sources used:")
    for src, ok in s["sources"].items():
        logger.warning(f"    {'✅' if ok else '⚠️  '} {src}")
    logger.info("\n  Counts:")
    for k, v in s["counts"].items():
        logger.info(f"    {k:<14} {v}")
    logger.info("\n  Files written:")
    for f in s["files"]:
        logger.info(f"    {f}")
    logger.info("\n  Next steps:")
    logger.info("    1. Review data/*.json — refine gene categories & evidence")
    logger.info("    2. Fill SYMPTOMS, CAR_T_SCORES in config.py")
    logger.info("    3. Run: med-research disease validate " + s["disease_id"])
    logger.info("    4. Run: med-research kg --disease " + s["disease_id"])
    logger.info("=" * 70)
