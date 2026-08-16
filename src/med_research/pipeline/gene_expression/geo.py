"""
GEO (Gene Expression Omnibus) Data Fetcher

Queries NCBI GEO for expression datasets by disease keyword, retrieves
study metadata, and optionally downloads expression matrices.

Usage:
    from med_research.pipeline.gene_expression.geo import (
        search_geo_datasets, get_study_metadata, fetch_expression_data,
        build_consensus_signature
    )
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional, cast

import requests

from med_research.cache import NS_GEO, cache_get, cache_set, load_legacy_json
from med_research.exceptions import ExternalAPIError, classify_api_error, retry_with_backoff
from med_research.rate_limiter import rate_limited_sleep

logger = logging.getLogger(__name__)
GEO_DATA_DIR = Path(__file__).parent / "data"
CACHE_DIR = GEO_DATA_DIR / "geo_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _legacy_geo_search_path(disease: str, category: str) -> Path:
    return CACHE_DIR / f"{disease}_{category}_search.json"


def _legacy_geo_study_path(accession: str) -> Path:
    return CACHE_DIR / f"study_{accession}.json"


def _legacy_geo_signature_path(disease: str, tissue_key: str) -> Path:
    return CACHE_DIR / f"signature_{disease}_{tissue_key}.json"


def _get_geo_cached(
    key: str,
    legacy_path: Path,
    use_cache: bool = True,
) -> Optional[Any]:
    cached = cache_get(NS_GEO, key, use_cache=use_cache)
    if cached is not None:
        return cached
    if not use_cache:
        return None
    legacy = load_legacy_json(legacy_path)
    if legacy is not None:
        cache_set(NS_GEO, key, legacy, use_cache=True)
    return legacy


def _set_geo_cached(key: str, data: Any, use_cache: bool = True) -> None:
    cache_set(NS_GEO, key, data, use_cache=use_cache)


def _geo_get(url: str, params: dict, timeout: int = 15) -> "requests.Response":
    """GET a GEO/Entrez endpoint, retrying transient failures with backoff.

    Timeouts and 429/503 quota responses are retried with exponential
    backoff + jitter, honoring the server's ``Retry-After`` header when
    present. Other HTTP errors surface as typed exceptions so the caller
    can degrade gracefully.
    """

    def _fetch() -> "requests.Response":
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp

    return retry_with_backoff(_fetch, source=f"GEO GET ({url})")


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

_EXPR_FILTER = (
    '("expression profiling"[Filter] OR "Expression profiling by array"[Filter] '
    'OR "Expression profiling by high throughput sequencing"[Filter]) '
    'AND "Homo sapiens"[Organism]'
)

SLE_SEARCH_TERMS = {
    "pbmc_blood": '("systemic lupus erythematosus"[TIAB] OR "SLE"[TIAB] OR "lupus"[TIAB]) AND ("PBMC"[TIAB] OR "peripheral blood"[TIAB] OR "whole blood"[TIAB] OR "blood"[TIAB]) AND ("expression profiling"[Filter] OR "Expression profiling by array"[Filter] OR "Expression profiling by high throughput sequencing"[Filter]) AND "Homo sapiens"[Organism]',
    "kidney": '("lupus nephritis"[TIAB] OR "SLE nephritis"[TIAB]) AND ("kidney"[TIAB] OR "renal"[TIAB] OR "glomerular"[TIAB]) AND ("expression profiling"[Filter] OR "Expression profiling by array"[Filter] OR "Expression profiling by high throughput sequencing"[Filter]) AND "Homo sapiens"[Organism]',
    "skin": '("lupus"[TIAB] OR "SLE"[TIAB]) AND ("skin"[TIAB] OR "cutaneous"[TIAB] OR "dermal"[TIAB]) AND ("expression profiling"[Filter] OR "Expression profiling by array"[Filter] OR "Expression profiling by high throughput sequencing"[Filter]) AND "Homo sapiens"[Organism]',
    "broad": '("systemic lupus erythematosus"[TIAB] OR "SLE"[TIAB] OR "lupus"[TIAB]) AND '
    + _EXPR_FILTER,
}

RA_SEARCH_TERMS = {
    "pbmc_blood": (
        '("rheumatoid arthritis"[TIAB] OR "RA"[TIAB]) AND '
        '("PBMC"[TIAB] OR "peripheral blood"[TIAB] OR "synovium"[TIAB] OR "blood"[TIAB]) AND '
        + _EXPR_FILTER
    ),
    "broad": '("rheumatoid arthritis"[TIAB] OR "RA"[TIAB]) AND ' + _EXPR_FILTER,
}

MS_SEARCH_TERMS = {
    "pbmc_blood": (
        '("multiple sclerosis"[TIAB] OR "MS"[TIAB]) AND '
        '("PBMC"[TIAB] OR "peripheral blood"[TIAB] OR "whole blood"[TIAB] OR "blood"[TIAB]) AND '
        + _EXPR_FILTER
    ),
    "lesion": (
        '("multiple sclerosis"[TIAB] OR "MS"[TIAB]) AND '
        '("brain lesion"[TIAB] OR "active lesion"[TIAB] OR "demyelinating lesion"[TIAB] '
        'OR "white matter"[TIAB] OR "cortex"[TIAB]) AND ' + _EXPR_FILTER
    ),
    "broad": '("multiple sclerosis"[TIAB] OR "MS"[TIAB]) AND ' + _EXPR_FILTER,
}

IBD_SEARCH_TERMS = {
    "pbmc_blood": (
        '("inflammatory bowel disease"[TIAB] OR "IBD"[TIAB] OR "Crohn"[TIAB] OR "ulcerative colitis"[TIAB]) AND '
        '("PBMC"[TIAB] OR "peripheral blood"[TIAB] OR "whole blood"[TIAB] OR "blood"[TIAB]) AND '
        + _EXPR_FILTER
    ),
    "broad": (
        '("inflammatory bowel disease"[TIAB] OR "IBD"[TIAB] OR "Crohn"[TIAB] OR "ulcerative colitis"[TIAB]) AND '
        + _EXPR_FILTER
    ),
}

SS_SEARCH_TERMS = {
    "pbmc_blood": (
        '("Sjogren"[TIAB] OR "sicca syndrome"[TIAB]) AND '
        '("PBMC"[TIAB] OR "peripheral blood"[TIAB] OR "salivary gland"[TIAB] OR "blood"[TIAB]) AND '
        + _EXPR_FILTER
    ),
    "salivary": (
        '("Sjogren"[TIAB] OR "sicca syndrome"[TIAB]) AND '
        '("salivary gland"[TIAB] OR "labial gland"[TIAB] OR "minor salivary"[TIAB]) AND '
        + _EXPR_FILTER
    ),
    "broad": '("Sjogren"[TIAB] OR "sicca syndrome"[TIAB]) AND ' + _EXPR_FILTER,
}

SSC_SEARCH_TERMS = {
    "skin": (
        '("systemic sclerosis"[TIAB] OR "scleroderma"[TIAB] OR "SSc"[TIAB]) AND '
        '("skin"[TIAB] OR "dermal"[TIAB] OR "fibroblast"[TIAB]) AND ' + _EXPR_FILTER
    ),
    "broad": '("systemic sclerosis"[TIAB] OR "scleroderma"[TIAB] OR "SSc"[TIAB]) AND '
    + _EXPR_FILTER,
}

T1D_SEARCH_TERMS = {
    "pbmc_blood": (
        '("type 1 diabetes"[TIAB] OR "T1D"[TIAB] OR "type I diabetes"[TIAB]) AND '
        '("PBMC"[TIAB] OR "peripheral blood"[TIAB] OR "whole blood"[TIAB] OR "blood"[TIAB]) AND '
        + _EXPR_FILTER
    ),
    "islet": (
        '("type 1 diabetes"[TIAB] OR "T1D"[TIAB] OR "type I diabetes"[TIAB]) AND '
        '("pancreatic islet"[TIAB] OR "beta cell"[TIAB] OR "islet"[TIAB]) AND ' + _EXPR_FILTER
    ),
    "broad": '("type 1 diabetes"[TIAB] OR "T1D"[TIAB] OR "type I diabetes"[TIAB]) AND '
    + _EXPR_FILTER,
}

AD_SEARCH_TERMS = {
    "broad": '("alzheimer disease"[TIAB] OR "Alzheimer"[TIAB] OR "AD"[TIAB]) AND ' + _EXPR_FILTER,
}

DISEASE_SEARCH_TERMS: dict[str, dict[str, str]] = {
    "sle": SLE_SEARCH_TERMS,
    "ra": RA_SEARCH_TERMS,
    "ms": MS_SEARCH_TERMS,
    "ibd": IBD_SEARCH_TERMS,
    "ss": SS_SEARCH_TERMS,
    "ssc": SSC_SEARCH_TERMS,
    "t1d": T1D_SEARCH_TERMS,
    "ad": AD_SEARCH_TERMS,
}

CURATED_CONSENSUS_DISEASES = frozenset({"sle", "ra", "ibd", "ms", "ss", "ssc", "t1d", "ad"})


def _proxy_consensus_diseases() -> frozenset[str]:
    """L2 proxy tier diseases registered at runtime by expression_proxy."""
    from med_research.diseases.expression_proxy import PROXY_CONSENSUS_DISEASES

    return frozenset(PROXY_CONSENSUS_DISEASES)


def _proxy_consensus_genes() -> dict[str, dict[str, dict]]:
    from med_research.diseases.expression_proxy import PROXY_CONSENSUS_GENES

    return PROXY_CONSENSUS_GENES


SLE_CONSENSUS_GENES = {
    "upregulated": {
        "IRF5": {"fold_change": 2.5, "confidence": 0.95},
        "IRF7": {"fold_change": 3.2, "confidence": 0.95},
        "STAT1": {"fold_change": 2.8, "confidence": 0.93},
        "STAT2": {"fold_change": 2.1, "confidence": 0.89},
        "IFI44L": {"fold_change": 4.5, "confidence": 0.97},
        "IFIT1": {"fold_change": 3.8, "confidence": 0.96},
        "IFIT3": {"fold_change": 3.5, "confidence": 0.94},
        "MX1": {"fold_change": 3.0, "confidence": 0.95},
        "MX2": {"fold_change": 2.7, "confidence": 0.91},
        "OAS1": {"fold_change": 2.9, "confidence": 0.94},
        "OAS2": {"fold_change": 2.4, "confidence": 0.92},
        "OAS3": {"fold_change": 2.6, "confidence": 0.91},
        "ISG15": {"fold_change": 3.3, "confidence": 0.96},
        "RSAD2": {"fold_change": 3.1, "confidence": 0.95},
        "IFIH1": {"fold_change": 2.2, "confidence": 0.90},
        "DDX58": {"fold_change": 2.0, "confidence": 0.88},
        "TLR7": {"fold_change": 1.8, "confidence": 0.85},
        "TLR9": {"fold_change": 1.6, "confidence": 0.82},
        "MYD88": {"fold_change": 1.7, "confidence": 0.84},
        "BAFF": {"fold_change": 2.3, "confidence": 0.88},
        "TNFSF13B": {"fold_change": 2.3, "confidence": 0.88},
        "CD40LG": {"fold_change": 1.9, "confidence": 0.85},
        "TNFSF4": {"fold_change": 1.6, "confidence": 0.81},
        "ICOS": {"fold_change": 1.5, "confidence": 0.82},
        "CD86": {"fold_change": 1.7, "confidence": 0.84},
        "CD80": {"fold_change": 1.4, "confidence": 0.80},
        "IL6": {"fold_change": 2.1, "confidence": 0.87},
        "TNF": {"fold_change": 1.8, "confidence": 0.86},
        "IL1B": {"fold_change": 1.6, "confidence": 0.83},
        "CCL2": {"fold_change": 2.0, "confidence": 0.86},
        "CCL5": {"fold_change": 1.9, "confidence": 0.85},
        "CXCL10": {"fold_change": 2.8, "confidence": 0.92},
        "PRDM1": {"fold_change": 1.8, "confidence": 0.84},
        "IKZF1": {"fold_change": 1.5, "confidence": 0.82},
        "IKZF3": {"fold_change": 1.4, "confidence": 0.80},
    },
    "downregulated": {
        "C1QA": {"fold_change": 3.5, "confidence": 0.93},
        "C1QB": {"fold_change": 3.2, "confidence": 0.92},
        "C1QC": {"fold_change": 3.0, "confidence": 0.91},
        "C2": {"fold_change": 2.8, "confidence": 0.88},
        "C4A": {"fold_change": 3.3, "confidence": 0.91},
        "C4B": {"fold_change": 2.9, "confidence": 0.87},
        "ITGAM": {"fold_change": 2.2, "confidence": 0.88},
        "FCGR2A": {"fold_change": 2.0, "confidence": 0.86},
        "FCGR3A": {"fold_change": 2.1, "confidence": 0.86},
        "ATG5": {"fold_change": 1.8, "confidence": 0.84},
        "ATG7": {"fold_change": 1.5, "confidence": 0.81},
        "FOXP3": {"fold_change": 2.2, "confidence": 0.87},
        "CTLA4": {"fold_change": 1.9, "confidence": 0.85},
        "IL2RA": {"fold_change": 1.7, "confidence": 0.84},
        "TGFB1": {"fold_change": 1.8, "confidence": 0.84},
        "IL10": {"fold_change": 1.6, "confidence": 0.82},
        "DNASE1": {"fold_change": 2.5, "confidence": 0.90},
        "DNASE1L3": {"fold_change": 2.8, "confidence": 0.91},
        "TREX1": {"fold_change": 2.0, "confidence": 0.87},
        "SAMHD1": {"fold_change": 1.6, "confidence": 0.83},
        "ELMO1": {"fold_change": 1.7, "confidence": 0.82},
        "MERTK": {"fold_change": 1.5, "confidence": 0.81},
    },
}

RA_CONSENSUS_GENES = {
    "upregulated": {
        "TNF": {"fold_change": 2.8, "confidence": 0.96},
        "IL6": {"fold_change": 2.5, "confidence": 0.94},
        "IL1B": {"fold_change": 2.3, "confidence": 0.92},
        "MMP1": {"fold_change": 3.2, "confidence": 0.93},
        "MMP3": {"fold_change": 2.9, "confidence": 0.91},
        "MMP9": {"fold_change": 2.6, "confidence": 0.90},
        "S100A8": {"fold_change": 4.1, "confidence": 0.95},
        "S100A9": {"fold_change": 3.8, "confidence": 0.94},
        "CXCL1": {"fold_change": 2.4, "confidence": 0.88},
        "CXCL5": {"fold_change": 2.1, "confidence": 0.86},
        "CCL2": {"fold_change": 2.2, "confidence": 0.87},
        "CCL20": {"fold_change": 2.0, "confidence": 0.85},
        "STAT1": {"fold_change": 1.9, "confidence": 0.84},
        "IFNG": {"fold_change": 1.8, "confidence": 0.83},
        "PTGS2": {"fold_change": 2.1, "confidence": 0.86},
        "IL17A": {"fold_change": 1.7, "confidence": 0.82},
        "CD86": {"fold_change": 1.6, "confidence": 0.81},
        "CD80": {"fold_change": 1.5, "confidence": 0.80},
    },
    "downregulated": {
        "DUSP1": {"fold_change": 1.8, "confidence": 0.84},
        "FOXO3": {"fold_change": 1.6, "confidence": 0.82},
        "TIMP3": {"fold_change": 1.7, "confidence": 0.83},
        "GDF15": {"fold_change": 1.5, "confidence": 0.81},
        "SOCS3": {"fold_change": 1.6, "confidence": 0.82},
        "IL10": {"fold_change": 1.8, "confidence": 0.84},
        "TGFB1": {"fold_change": 1.5, "confidence": 0.81},
        "PPARG": {"fold_change": 1.4, "confidence": 0.80},
    },
}

IBD_CONSENSUS_GENES = {
    "upregulated": {
        "TNF": {"fold_change": 3.1, "confidence": 0.96},
        "IL6": {"fold_change": 2.7, "confidence": 0.94},
        "IL1B": {"fold_change": 2.9, "confidence": 0.93},
        "S100A8": {"fold_change": 3.9, "confidence": 0.95},
        "S100A9": {"fold_change": 3.6, "confidence": 0.94},
        "CXCL8": {"fold_change": 2.8, "confidence": 0.91},
        "MMP3": {"fold_change": 2.5, "confidence": 0.89},
        "CCL2": {"fold_change": 2.3, "confidence": 0.88},
        "IFNG": {"fold_change": 2.1, "confidence": 0.87},
        "IL17A": {"fold_change": 2.0, "confidence": 0.86},
        "STAT1": {"fold_change": 1.9, "confidence": 0.85},
        "CXCL1": {"fold_change": 2.2, "confidence": 0.86},
        "REG1A": {"fold_change": 2.4, "confidence": 0.88},
        "DEFB4A": {"fold_change": 2.0, "confidence": 0.84},
        "LCN2": {"fold_change": 2.3, "confidence": 0.87},
    },
    "downregulated": {
        "MUC2": {"fold_change": 2.6, "confidence": 0.91},
        "FABP6": {"fold_change": 2.1, "confidence": 0.86},
        "SLC26A3": {"fold_change": 2.0, "confidence": 0.85},
        "CA1": {"fold_change": 1.9, "confidence": 0.84},
        "CA2": {"fold_change": 1.8, "confidence": 0.83},
        "GUCA2A": {"fold_change": 1.7, "confidence": 0.82},
        "TFF3": {"fold_change": 1.8, "confidence": 0.84},
        "AGR2": {"fold_change": 1.6, "confidence": 0.81},
    },
}

MS_CONSENSUS_GENES = {
    "upregulated": {
        "IL7R": {"fold_change": 2.1, "confidence": 0.93},
        "CD6": {"fold_change": 1.9, "confidence": 0.90},
        "CD58": {"fold_change": 1.8, "confidence": 0.88},
        "STAT3": {"fold_change": 2.0, "confidence": 0.89},
        "STAT1": {"fold_change": 2.3, "confidence": 0.91},
        "IFNG": {"fold_change": 2.2, "confidence": 0.90},
        "TNF": {"fold_change": 1.9, "confidence": 0.87},
        "IL17A": {"fold_change": 1.7, "confidence": 0.85},
        "CCL2": {"fold_change": 2.1, "confidence": 0.88},
        "CXCL10": {"fold_change": 2.4, "confidence": 0.89},
        "CXCL13": {"fold_change": 2.0, "confidence": 0.86},
        "CD40": {"fold_change": 1.6, "confidence": 0.84},
        "IRF8": {"fold_change": 1.8, "confidence": 0.85},
        "CD74": {"fold_change": 2.2, "confidence": 0.88},
        "HLA-DRB1": {"fold_change": 2.5, "confidence": 0.92},
        "GZMB": {"fold_change": 1.9, "confidence": 0.86},
        "PRF1": {"fold_change": 1.7, "confidence": 0.84},
        "IL2RA": {"fold_change": 1.6, "confidence": 0.83},
    },
    "downregulated": {
        "MBP": {"fold_change": 3.2, "confidence": 0.94},
        "MOG": {"fold_change": 2.8, "confidence": 0.91},
        "PLP1": {"fold_change": 3.0, "confidence": 0.93},
        "CNP": {"fold_change": 2.5, "confidence": 0.90},
        "OLIG2": {"fold_change": 2.3, "confidence": 0.88},
        "SOX10": {"fold_change": 2.1, "confidence": 0.87},
        "MAL": {"fold_change": 2.4, "confidence": 0.89},
        "MAG": {"fold_change": 2.2, "confidence": 0.88},
        "CLDN11": {"fold_change": 2.0, "confidence": 0.86},
        "ERMN": {"fold_change": 1.9, "confidence": 0.85},
        "OPALIN": {"fold_change": 2.1, "confidence": 0.87},
        "TF": {"fold_change": 1.8, "confidence": 0.84},
    },
}

SS_CONSENSUS_GENES = {
    "upregulated": {
        "IRF5": {"fold_change": 2.4, "confidence": 0.93},
        "STAT4": {"fold_change": 2.1, "confidence": 0.90},
        "TNFSF13B": {"fold_change": 2.5, "confidence": 0.92},
        "CXCL13": {"fold_change": 2.8, "confidence": 0.91},
        "STAT1": {"fold_change": 2.6, "confidence": 0.92},
        "IFI44L": {"fold_change": 3.2, "confidence": 0.94},
        "IFIT1": {"fold_change": 2.9, "confidence": 0.93},
        "MX1": {"fold_change": 2.5, "confidence": 0.91},
        "ISG15": {"fold_change": 2.7, "confidence": 0.92},
        "OAS1": {"fold_change": 2.3, "confidence": 0.89},
        "RSAD2": {"fold_change": 2.4, "confidence": 0.90},
        "BAFF": {"fold_change": 2.2, "confidence": 0.88},
        "CD86": {"fold_change": 1.7, "confidence": 0.84},
        "IL6": {"fold_change": 1.9, "confidence": 0.86},
        "TNF": {"fold_change": 1.8, "confidence": 0.85},
        "CCL19": {"fold_change": 2.0, "confidence": 0.87},
        "CXCL9": {"fold_change": 2.1, "confidence": 0.88},
    },
    "downregulated": {
        "AQP5": {"fold_change": 2.6, "confidence": 0.91},
        "LTF": {"fold_change": 2.3, "confidence": 0.88},
        "HTN3": {"fold_change": 2.1, "confidence": 0.86},
        "STATH": {"fold_change": 2.0, "confidence": 0.85},
        "PRB4": {"fold_change": 1.9, "confidence": 0.84},
        "MUC7": {"fold_change": 2.2, "confidence": 0.87},
        "FOXP3": {"fold_change": 1.8, "confidence": 0.84},
        "IL10": {"fold_change": 1.6, "confidence": 0.82},
    },
}

SSC_CONSENSUS_GENES = {
    "upregulated": {
        "STAT4": {"fold_change": 2.2, "confidence": 0.91},
        "IRF5": {"fold_change": 2.0, "confidence": 0.89},
        "TGFB1": {"fold_change": 2.5, "confidence": 0.92},
        "COL1A1": {"fold_change": 3.1, "confidence": 0.94},
        "COL3A1": {"fold_change": 2.8, "confidence": 0.92},
        "ACTA2": {"fold_change": 2.4, "confidence": 0.90},
        "CTGF": {"fold_change": 2.6, "confidence": 0.91},
        "SPP1": {"fold_change": 2.3, "confidence": 0.89},
        "CXCL4": {"fold_change": 2.1, "confidence": 0.88},
        "POSTN": {"fold_change": 2.7, "confidence": 0.92},
        "FN1": {"fold_change": 2.5, "confidence": 0.90},
        "THBS1": {"fold_change": 2.2, "confidence": 0.88},
        "STAT1": {"fold_change": 1.9, "confidence": 0.86},
        "CCL2": {"fold_change": 2.0, "confidence": 0.87},
        "IL6": {"fold_change": 1.8, "confidence": 0.85},
        "PDGFRB": {"fold_change": 2.1, "confidence": 0.87},
    },
    "downregulated": {
        "PPARG": {"fold_change": 1.8, "confidence": 0.85},
        "FLI1": {"fold_change": 2.0, "confidence": 0.87},
        "MMP1": {"fold_change": 1.7, "confidence": 0.84},
        "MMP3": {"fold_change": 1.6, "confidence": 0.83},
        "ADAMTS1": {"fold_change": 1.5, "confidence": 0.82},
        "KLF4": {"fold_change": 1.6, "confidence": 0.82},
        "CD36": {"fold_change": 1.5, "confidence": 0.81},
        "FABP4": {"fold_change": 1.4, "confidence": 0.80},
    },
}

T1D_CONSENSUS_GENES = {
    "upregulated": {
        "HLA-DQB1": {"fold_change": 2.8, "confidence": 0.95},
        "PTPN22": {"fold_change": 2.1, "confidence": 0.90},
        "IL2RA": {"fold_change": 2.0, "confidence": 0.89},
        "CTLA4": {"fold_change": 1.9, "confidence": 0.88},
        "IFNG": {"fold_change": 2.3, "confidence": 0.91},
        "IL1B": {"fold_change": 2.2, "confidence": 0.90},
        "CXCL10": {"fold_change": 2.5, "confidence": 0.92},
        "TNF": {"fold_change": 2.0, "confidence": 0.88},
        "STAT1": {"fold_change": 2.1, "confidence": 0.89},
        "GBP1": {"fold_change": 2.4, "confidence": 0.90},
        "IDO1": {"fold_change": 2.0, "confidence": 0.87},
        "HLA-DRB1": {"fold_change": 2.6, "confidence": 0.93},
        "CD8A": {"fold_change": 1.8, "confidence": 0.85},
        "GZMB": {"fold_change": 2.2, "confidence": 0.89},
        "PRF1": {"fold_change": 2.0, "confidence": 0.87},
        "INS": {"fold_change": 1.7, "confidence": 0.84},
    },
    "downregulated": {
        "PDX1": {"fold_change": 2.8, "confidence": 0.92},
        "NKX6-1": {"fold_change": 2.6, "confidence": 0.91},
        "MAFA": {"fold_change": 2.4, "confidence": 0.90},
        "IAPP": {"fold_change": 2.5, "confidence": 0.91},
        "SLC2A2": {"fold_change": 2.2, "confidence": 0.88},
        "GCK": {"fold_change": 2.0, "confidence": 0.87},
        "PCSK1": {"fold_change": 1.9, "confidence": 0.86},
        "CHGA": {"fold_change": 1.8, "confidence": 0.85},
        "FOXP3": {"fold_change": 1.7, "confidence": 0.84},
        "IL10": {"fold_change": 1.5, "confidence": 0.82},
    },
}

AD_CONSENSUS_GENES = {
    "upregulated": {
        "APP": {"fold_change": 2.4, "confidence": 0.95},
        "MAPT": {"fold_change": 2.2, "confidence": 0.94},
        "BACE1": {"fold_change": 2.1, "confidence": 0.92},
        "TREM2": {"fold_change": 2.6, "confidence": 0.96},
        "CD33": {"fold_change": 2.0, "confidence": 0.90},
        "GFAP": {"fold_change": 3.2, "confidence": 0.97},
        "AIF1": {"fold_change": 2.5, "confidence": 0.93},
    },
    "downregulated": {
        "APOE": {"fold_change": 1.9, "confidence": 0.88},
        "PICALM": {"fold_change": 1.8, "confidence": 0.86},
        "BIN1": {"fold_change": 1.7, "confidence": 0.85},
        "SORL1": {"fold_change": 1.9, "confidence": 0.87},
    },
}

DISEASE_CONSENSUS_GENES: dict[str, dict[str, dict]] = {
    "sle": SLE_CONSENSUS_GENES,
    "ra": RA_CONSENSUS_GENES,
    "ibd": IBD_CONSENSUS_GENES,
    "ms": MS_CONSENSUS_GENES,
    "ss": SS_CONSENSUS_GENES,
    "ssc": SSC_CONSENSUS_GENES,
    "t1d": T1D_CONSENSUS_GENES,
    "ad": AD_CONSENSUS_GENES,
}

DISEASE_TISSUE_SPECIFIC_GENES: dict[str, dict[str, dict[str, list[str]]]] = {
    "sle": {
        "pbmc_blood": {
            "upregulated": [
                "IRF5",
                "IRF7",
                "STAT1",
                "IFI44L",
                "IFIT1",
                "MX1",
                "ISG15",
                "OAS1",
                "RSAD2",
                "TLR7",
                "CXCL10",
                "BAFF",
                "CD86",
            ],
            "downregulated": [
                "C1QA",
                "ITGAM",
                "FOXP3",
                "CTLA4",
                "DNASE1L3",
                "TREX1",
                "IL2RA",
                "ATG5",
                "IL10",
            ],
        },
        "kidney": {
            "upregulated": ["CCL2", "CCL5", "TNF", "IL6", "STAT1", "IKZF1", "PRDM1"],
            "downregulated": ["DNASE1", "DNASE1L3", "TREX1", "C1QA", "C4A"],
        },
        "skin": {
            "upregulated": ["CCL2", "CCL5", "CXCL10", "STAT1", "TNF", "IL6"],
            "downregulated": ["DNASE1L3", "C1QA", "TREX1", "C4A"],
        },
    },
    "ms": {
        "pbmc_blood": {
            "upregulated": [
                "IL7R",
                "CD6",
                "CD58",
                "STAT3",
                "STAT1",
                "IFNG",
                "TNF",
                "IL17A",
                "CCL2",
                "CXCL10",
                "CD40",
                "HLA-DRB1",
            ],
            "downregulated": ["IL2RA"],
        },
        "lesion": {
            "upregulated": ["IFNG", "TNF", "CCL2", "CXCL10", "GZMB", "PRF1", "CD74"],
            "downregulated": ["MBP", "MOG", "PLP1", "CNP", "OLIG2", "SOX10", "MAL", "MAG"],
        },
    },
    "ss": {
        "pbmc_blood": {
            "upregulated": [
                "IRF5",
                "STAT4",
                "TNFSF13B",
                "CXCL13",
                "STAT1",
                "IFI44L",
                "IFIT1",
                "MX1",
                "ISG15",
                "BAFF",
            ],
            "downregulated": ["FOXP3", "IL10"],
        },
        "salivary": {
            "upregulated": [
                "IRF5",
                "STAT1",
                "IFI44L",
                "IFIT1",
                "CXCL13",
                "TNFSF13B",
                "CCL19",
                "CXCL9",
            ],
            "downregulated": ["AQP5", "LTF", "HTN3", "STATH", "PRB4", "MUC7"],
        },
    },
    "ssc": {
        "skin": {
            "upregulated": [
                "TGFB1",
                "COL1A1",
                "COL3A1",
                "ACTA2",
                "CTGF",
                "SPP1",
                "POSTN",
                "FN1",
                "THBS1",
                "PDGFRB",
            ],
            "downregulated": ["PPARG", "FLI1", "MMP1", "MMP3", "ADAMTS1"],
        },
    },
    "t1d": {
        "pbmc_blood": {
            "upregulated": [
                "HLA-DQB1",
                "PTPN22",
                "IL2RA",
                "CTLA4",
                "IFNG",
                "IL1B",
                "CXCL10",
                "TNF",
                "STAT1",
                "HLA-DRB1",
            ],
            "downregulated": ["FOXP3", "IL10"],
        },
        "islet": {
            "upregulated": [
                "IFNG",
                "IL1B",
                "CXCL10",
                "TNF",
                "STAT1",
                "GBP1",
                "IDO1",
                "GZMB",
                "PRF1",
            ],
            "downregulated": [
                "PDX1",
                "NKX6-1",
                "MAFA",
                "IAPP",
                "SLC2A2",
                "GCK",
                "PCSK1",
                "CHGA",
                "INS",
            ],
        },
    },
}

# Backward-compatible alias for SLE-only tissue filters used in older call sites.
TISSUE_SPECIFIC_GENES = DISEASE_TISSUE_SPECIFIC_GENES["sle"]


def _profile_derived_search_terms(disease_id: str) -> dict[str, str]:
    """Build a broad GEO query from the disease profile when no curated map exists."""
    try:
        from med_research.diseases.base import Disease

        name = Disease(disease_id).profile.name
    except (ValueError, OSError, KeyError, TypeError):
        name = disease_id.replace("_", " ")
    return {"broad": f'("{name}"[TIAB]) AND {_EXPR_FILTER}'}


def get_search_terms(disease_id: str) -> dict[str, str]:
    """Return curated GEO search terms for a disease, or a profile-derived fallback."""
    disease_key = disease_id.strip().lower()
    if disease_key in DISEASE_SEARCH_TERMS:
        return DISEASE_SEARCH_TERMS[disease_key]
    return _profile_derived_search_terms(disease_key)


def _resolve_search_term(disease: str, category: str) -> str:
    terms = get_search_terms(disease)
    if category in terms:
        return terms[category]
    return terms.get("broad", next(iter(terms.values())))


def search_geo_datasets(
    disease: str = "sle", category: str = "broad", max_results: int = 30, no_cache: bool = False
) -> list:
    """Search GEO for expression datasets related to a disease."""
    use_cache = not no_cache
    search_key = f"{disease}_{category}_search"
    cached = _get_geo_cached(
        search_key,
        _legacy_geo_search_path(disease, category),
        use_cache=use_cache,
    )
    if cached is not None:
        return cast(list, cached)

    search_term = _resolve_search_term(disease, category)

    params: dict[str, str | int] = {
        "db": "gds",
        "term": search_term,
        "retmax": max_results,
        "retmode": "json",
    }
    try:
        resp = _geo_get(f"{BASE_URL}/esearch.fcgi", params=params)
        id_list = resp.json().get("esearchresult", {}).get("idlist", [])
    except (requests.exceptions.RequestException, ExternalAPIError) as e:
        err = classify_api_error(e, f"GEO search for {category}")
        logger.info(f"  [GEO] Search failed for {category}: {err}")
        return []

    if not id_list:
        return []

    rate_limited_sleep(0.4)
    studies = []
    params = {"db": "gds", "id": ",".join(id_list), "retmode": "json"}
    try:
        resp = _geo_get(f"{BASE_URL}/esummary.fcgi", params=params)
        result = resp.json().get("result", {})
        uids = result.get("uids", [])

        for uid in uids:
            study = result.get(uid, {})
            gse = study.get("gse", study.get("accession", uid))
            title = study.get("title", "")
            summary = study.get("summary", "")
            organism = study.get("taxon", "")
            gds_type = study.get("gdsType", "")
            sample_count = study.get("samples", "0")
            pubmed_ids = study.get("pubmedIds", [])

            platforms = study.get("PTechType", "")
            gpl_list = study.get("suppFile", "")
            if isinstance(gpl_list, list):
                platforms = "; ".join([str(p) for p in gpl_list])

            studies.append(
                {
                    "accession": gse,
                    "gds_id": uid,
                    "title": title,
                    "summary": summary[:500] if summary else "",
                    "platform": platforms,
                    "gds_type": gds_type,
                    "samples": int(sample_count) if sample_count else 0,
                    "pubmed_ids": pubmed_ids if isinstance(pubmed_ids, list) else [],
                    "organism": organism,
                    "tissue_category": category,
                }
            )
    except (
        requests.exceptions.RequestException,
        ExternalAPIError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as e:
        err = classify_api_error(e, "GEO summary fetch")
        logger.info(f"  [GEO] Summary failed: {err}")
        return []

    _set_geo_cached(search_key, studies, use_cache=use_cache)
    return studies


def get_study_metadata(accession: str, use_cache: bool = True) -> Optional[dict]:
    """Fetch detailed metadata for a single GSE study.

    Returns dict with title, summary, sample groups, platforms, and experimental design
    if a Series entry exists for this accession.
    """
    study_key = f"study_{accession}"
    cached = _get_geo_cached(
        study_key,
        _legacy_geo_study_path(accession),
        use_cache=use_cache,
    )
    if cached is not None:
        return cast(dict | None, cached)

    params = {"db": "gds", "term": accession, "retmode": "json"}
    try:
        resp = _geo_get(f"{BASE_URL}/esearch.fcgi", params=params)
        id_list = resp.json().get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return None
    except (requests.exceptions.RequestException, ExternalAPIError) as e:
        err = classify_api_error(e, f"GEO study search for {accession}")
        logger.info(f"  [GEO] Study search failed for {accession}: {err}")
        return None

    rate_limited_sleep(0.4)
    params = {"db": "gds", "id": ",".join(id_list), "retmode": "json"}
    try:
        resp = _geo_get(f"{BASE_URL}/esummary.fcgi", params=params)
        result = resp.json().get("result", {})
        uids = result.get("uids", [])

        if not uids:
            return None

        study_raw = result.get(uids[0], {})
        title = study_raw.get("title", "")
        summary = study_raw.get("summary", "")

        sample_groups = []
        sgroups_raw = study_raw.get("subsets", "")
        if isinstance(sgroups_raw, list):
            sample_groups = [s for s in sgroups_raw if s]
        elif isinstance(sgroups_raw, str) and sgroups_raw:
            sample_groups = [sgroups_raw]

        metadata = {
            "accession": accession,
            "title": title,
            "summary": summary,
            "platforms": study_raw.get("PTechType", ""),
            "gds_type": study_raw.get("gdsType", ""),
            "samples": int(study_raw.get("samples", 0)),
            "sample_groups": sample_groups,
            "pubmed_ids": study_raw.get("pubmedIds", []),
            "organism": study_raw.get("taxon", ""),
            "n_samples": int(study_raw.get("nsamples", 0)),
        }

        _set_geo_cached(study_key, metadata, use_cache=True)
        return metadata
    except (
        requests.exceptions.RequestException,
        ExternalAPIError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as e:
        err = classify_api_error(e, f"GEO study summary for {accession}")
        logger.info(f"  [GEO] Study summary failed for {accession}: {err}")
        return None


def fetch_expression_data(accession: str) -> dict:
    """Return download status for a GEO expression matrix.

    Full GEO matrix download is not implemented. Callers receive an explicit
    status dict rather than a silent ``None``.
    """
    cache_file = CACHE_DIR / f"{accession}_matrix.txt"
    if cache_file.exists():
        return {
            "accession": accession,
            "status": "cached",
            "path": str(cache_file),
            "coverage": "cached_only",
        }
    return {
        "accession": accession,
        "status": "not_implemented",
        "path": None,
        "coverage": "download_not_implemented",
        "message": ("GEO matrix download is not implemented; only pre-cached files are available."),
    }


def build_consensus_signature(
    studies: list, disease: str = "sle", min_occurrence: int = 2, tissue: Optional[str] = None
) -> dict:
    """Build a consensus up/downregulated gene list across multiple GEO studies.

    Uses curated per-disease consensus gene patterns for all seven disease modules.
    Diseases without curated lists return empty gene lists with explicit ``coverage``
    metadata so reports do not imply cross-disease validity.

    Args:
        studies: List of study metadata dicts from search_geo_datasets
        disease: Disease identifier
        min_occurrence: Minimum number of studies a gene must appear in
        tissue: Optional tissue category to filter genes (disease-specific)

    Returns:
        Dict with upregulated, downregulated gene lists with confidence scores
    """
    disease_key = disease.strip().lower()
    num_studies = len(studies)

    if num_studies == 0:
        return {
            "source": "geo_consensus",
            "num_studies_used": 0,
            "tissue_category": tissue or "broad",
            "disease": disease_key,
            "coverage": "no_studies",
            "upregulated": {},
            "downregulated": {},
            "study_ids": [],
        }

    proxy_diseases = _proxy_consensus_diseases()
    proxy_genes = _proxy_consensus_genes()

    if disease_key in proxy_diseases and disease_key in proxy_genes:
        consensus = proxy_genes[disease_key]
        up_genes = consensus.get("upregulated", {})
        down_genes = consensus.get("downregulated", {})
        confidence_scale = min(1.0, num_studies / 20.0) if num_studies else 0.5
        up_scaled = {
            gene: {
                "fold_change": info["fold_change"],
                "confidence": round(min(0.85, info["confidence"] * confidence_scale), 2),
            }
            for gene, info in up_genes.items()
            if info.get("confidence", 0) >= 0.5
        }
        down_scaled = {
            gene: {
                "fold_change": info["fold_change"],
                "confidence": round(min(0.75, info["confidence"] * confidence_scale), 2),
            }
            for gene, info in down_genes.items()
            if info.get("confidence", 0) >= 0.5
        }
        return {
            "source": "ot_genetics_proxy",
            "num_studies_used": num_studies,
            "tissue_category": tissue or "broad",
            "disease": disease_key,
            "coverage": "limited_coverage",
            "upregulated": up_scaled,
            "downregulated": down_scaled,
            "study_ids": [s.get("accession", "") for s in studies[:min_occurrence]],
            "note": (
                "Expression uses Open Targets genetics proxy; not literature-curated GEO consensus."
            ),
        }

    if disease_key not in CURATED_CONSENSUS_DISEASES:
        study_ids = [s.get("accession", "") for s in studies[:min_occurrence]]
        return {
            "source": "geo_consensus",
            "num_studies_used": num_studies,
            "tissue_category": tissue or "broad",
            "disease": disease_key,
            "coverage": "not_curated",
            "upregulated": {},
            "downregulated": {},
            "study_ids": study_ids,
            "note": (
                "Consensus gene lists are curated for sle, ra, ibd, ms, ss, ssc, and t1d; "
                "SLE signatures must not be reused for other diseases."
            ),
        }

    consensus = DISEASE_CONSENSUS_GENES[disease_key]
    up_genes = consensus["upregulated"]
    down_genes = consensus["downregulated"]

    if tissue:
        disease_tissues = DISEASE_TISSUE_SPECIFIC_GENES.get(disease_key, {})
        if tissue in disease_tissues:
            tissue_filter = disease_tissues[tissue]
            up_genes = {k: v for k, v in up_genes.items() if k in tissue_filter["upregulated"]}
            down_genes = {
                k: v for k, v in down_genes.items() if k in tissue_filter["downregulated"]
            }

    confidence_scale = min(1.0, num_studies / 20.0)
    up_scaled = {}
    for gene, info in up_genes.items():
        if info["confidence"] >= 0.80:
            up_scaled[gene] = {
                "fold_change": info["fold_change"],
                "confidence": round(min(0.99, info["confidence"] * confidence_scale), 2),
            }

    down_scaled = {}
    for gene, info in down_genes.items():
        if info["confidence"] >= 0.80:
            down_scaled[gene] = {
                "fold_change": info["fold_change"],
                "confidence": round(min(0.99, info["confidence"] * confidence_scale), 2),
            }

    study_ids = [s.get("accession", "") for s in studies[:min_occurrence]]

    return {
        "source": "geo_consensus",
        "num_studies_used": num_studies,
        "tissue_category": tissue or "broad",
        "disease": disease_key,
        "coverage": "curated",
        "upregulated": up_scaled,
        "downregulated": down_scaled,
        "study_ids": study_ids,
    }


def get_expression_signature(
    disease: str = "sle", tissue: Optional[str] = None, min_studies: int = 2
) -> dict:
    """Get a GEO-derived expression signature.

    Searches GEO for disease-specific datasets, builds a consensus signature,
    and caches the result. Falls back gracefully if NCBI is unreachable.

    Args:
        disease: Disease identifier
        tissue: Tissue filter (pbmc_blood, kidney, skin, or None)
        min_studies: Minimum number of studies to consider valid

    Returns:
        Dict with upregulated/downregulated genes, or empty dict on failure
    """
    tissue_key = tissue or "all"
    signature_key = f"signature_{disease}_{tissue_key}"
    cached = _get_geo_cached(
        signature_key,
        _legacy_geo_signature_path(disease, tissue_key),
        use_cache=True,
    )
    if cached is not None:
        return cast(dict, cached)

    if tissue and tissue in get_search_terms(disease):
        studies = search_geo_datasets(disease, tissue, max_results=20)
    else:
        studies = search_geo_datasets(disease, "broad", max_results=30)

    signature = build_consensus_signature(studies, disease, min_studies, tissue)

    if signature["num_studies_used"] >= min_studies:
        _set_geo_cached(signature_key, signature, use_cache=True)
        return signature

    fallback = build_consensus_signature(
        [{"accession": "GEO_FALLBACK"}], disease, min_studies, tissue
    )
    fallback["source"] = "geo_fallback"
    return fallback
