import json
from pathlib import Path
from typing import Any, cast

# Load allele definitions (compact JSON) relative to this file
_ALLELE_DEF_PATH = Path(__file__).parent / "allele_definitions.json"


def _load_definitions() -> dict[str, Any]:
    if not _ALLELE_DEF_PATH.is_file():
        raise FileNotFoundError(f"Allele definitions not found at {_ALLELE_DEF_PATH}")
    with open(_ALLELE_DEF_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Allele definitions must be a JSON object")
    return cast(dict[str, Any], data)


DEFINITIONS = _load_definitions()


def parse_star_allele(gene: str, allele_str: str) -> dict[str, str | list[str]]:
    """Parse a star‑allele string for a given gene.
    Example inputs::
        gene = "CYP2D6"
        allele_str = "*1/*4"
    Returns a dict with gene and a list of allele identifiers.
    Raises ValueError for unknown alleles.
    """
    gene = gene.upper()
    if gene not in DEFINITIONS:
        raise ValueError(f"Gene {gene} is not supported for PGx parsing.")
    # Split on '/' and strip whitespace
    alleles = [a.strip() for a in allele_str.split("/") if a]
    for a in alleles:
        if a not in DEFINITIONS[gene]["alleles"]:
            raise ValueError(f"Allele {a} not recognized for gene {gene}.")
    return {"gene": gene, "alleles": alleles}
