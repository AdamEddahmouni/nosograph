"""
Lupus GWAS Catalog Annotation

Queries the NHGRI-EBI GWAS Catalog REST API for lupus-associated
(SLE) variants, maps them to genes, and cross-references findings
with the Lupus Knowledge Graph.

API: https://www.ebi.ac.uk/gwas/rest/api
No API key required. Rate-limited to ~1 request/second.

Usage:
    python gwas.py                      # Full analysis
    python gwas.py --max-studies 50     # Max studies to fetch
"""

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

from med_research.cache import (
    NS_GWAS,
    cache_get,
    cache_set,
    load_legacy_json,
)
from med_research.exceptions import (
    ConfigurationError,
    ExternalAPIError,
    classify_api_error,
    retry_with_backoff,
)
from med_research.pipeline.knowledge_graph.config import load_genes as config_load_genes
from med_research.pipeline.progress import StandardProgress, _tick
from med_research.rate_limiter import rate_limited_sleep

logger = logging.getLogger(__name__)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

DATA_DIR = Path(__file__).parent / "data"

GWAS_API = "https://www.ebi.ac.uk/gwas/rest/api"


def _gwas_http_get(url: str, params: dict, timeout: int = 30):
    """Perform a GWAS Catalog GET request, raising on HTTP failure."""
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp


# EFO term for systemic lupus erythematosus
SLE_EFO_TERMS = [
    "EFO_0002690",  # systemic lupus erythematosus
    "EFO_0005757",  # lupus nephritis
    "EFO_1000654",  # systemic lupus erythematosus (child term)
]

# Common SLE search terms
SLE_SEARCH_TERMS = [
    "systemic lupus erythematosus",
    "lupus erythematosus",
    "lupus nephritis",
    "SLE",
]


def disease_search_terms(disease_id: str = "sle") -> list:
    """Resolve GWAS Catalog search terms for a disease.

    Prefers the disease module's ``GWAS_SEARCH_TERMS`` config (see
    ``diseases/<id>/config.py``), falls back to the disease's display name,
    and finally to the disease profile name. Returns a list of trait strings.
    """
    try:
        from med_research.diseases.base import Disease
        terms = Disease(disease_id).get_gwas_search_terms()
    except ValueError:
        # Unknown diseases are invalid input, never an excuse to query SLE.
        return []
    except ConfigurationError as exc:
        logger.info(f"   ⚠️  Disease config error for {disease_id}: {exc}")
        terms = []
    except (AttributeError, KeyError, TypeError, OSError) as exc:
        logger.info(f"   ⚠️  Disease config error for {disease_id}: {exc}")
        terms = []
    if terms:
        return list(terms)
    return []


def gwas_cache_path(disease_id: str = "sle") -> Path:
    """Per-disease GWAS cache path, honoring the legacy SLE cache file."""
    path = DATA_DIR / f"gwas_cache_{disease_id}.json"
    if disease_id == "sle" and not path.exists():
        legacy = DATA_DIR / "gwas_cache.json"
        if legacy.exists():
            return legacy
    return path


def search_gwas_studies(
    query: str | None = None,
    max_results: int = 100,
    disease_id: str = "sle",
    progress_callback: StandardProgress | None = None,
) -> list:
    """
    Search the GWAS Catalog for disease-associated studies.

    When ``query`` is omitted, uses the first term from
    :func:`disease_search_terms` for ``disease_id``.
    """
    if query is None:
        terms = disease_search_terms(disease_id)
        query = terms[0] if terms else ""
    if not query:
        logger.info("   ⚠️  No GWAS search terms configured; skipping catalog query")
        return []
    if not REQUESTS_AVAILABLE:
        logger.info("❌ requests required. Install: pip install requests")
        return []

    studies = []
    page = 0

    logger.info(f"\n🔄 Searching GWAS Catalog for: {query}")

    while len(studies) < max_results:
        params = {
            "q": query,
            "size": 50,
            "page": page,
        }

        try:
            resp = retry_with_backoff(
                lambda p=params: _gwas_http_get(
                    f"{GWAS_API}/studies/search/findByDiseaseTrait",
                    {"diseaseTrait": p["q"], "size": p["size"]},
                    timeout=30,
                ),
                source="GWAS search",
            )
            data = resp.json()

            page_studies = data.get("_embedded", {}).get("studies", [])
            if not page_studies:
                break

            studies.extend(page_studies)
            page += 1
            _tick(progress_callback, "fetching GWAS studies", min(len(studies), max_results), max_results)

            # Rate limiting
            rate_limited_sleep(0.5)

        except ExternalAPIError as e:
            logger.info(f"   ⚠️  {e}")
            break
        except json.JSONDecodeError as e:
            err = classify_api_error(e, "GWAS search")
            logger.info(f"   ⚠️  {err}")
            break
        except requests.exceptions.RequestException as e:
            err = classify_api_error(e, "GWAS search")
            logger.info(f"   ⚠️  {err}")
            break

    logger.info(f"   Found {len(studies)} studies")
    return studies


def fetch_study_associations(study_accession: str) -> list:
    """Fetch raw SNP-trait associations for a GWAS study.

    Returns raw association dicts with loci containing SNP rsIDs.
    Gene resolution happens later via _resolve_snp_genes().
    """
    associations = []

    try:
        resp = retry_with_backoff(
            lambda: _gwas_http_get(
                f"{GWAS_API}/studies/{study_accession}/associations",
                {"size": 100},
                timeout=30,
            ),
            source=f"GWAS associations for {study_accession}",
        )
        data = resp.json()
        return data.get("_embedded", {}).get("associations", [])

    except ExternalAPIError as e:
        logger.info(f"   ⚠️  {e}")
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            logger.info(f"   ⚠️  No associations found for study {study_accession} (404)")
        else:
            err = classify_api_error(e, f"GWAS associations for {study_accession}")
            logger.info(f"   ⚠️  {err}")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        err = classify_api_error(e, f"GWAS associations for {study_accession}")
        logger.info(f"   ⚠️  {err}")
    except json.JSONDecodeError as e:
        err = classify_api_error(e, f"GWAS associations for {study_accession}")
        logger.info(f"   ⚠️  {err}")
    except requests.exceptions.RequestException as e:
        err = classify_api_error(e, f"GWAS associations for {study_accession}")
        logger.info(f"   ⚠️  {err}")

    rate_limited_sleep(0.5)
    return associations


def _resolve_snp_details(
    rsids: set,
    progress_callback: StandardProgress | None = None,
) -> dict:
    """
    Resolve SNP rsIDs to gene names + genomic locations.

    Each SNP's genomicContexts provides gene names (gene.geneName)
    and location info (location.chromosomeName, location.chromosomePosition).

    Returns dict: {rsid: {"genes": [...], "chromosome": str, "position": int}}
    """
    snp_cache = {}

    unresolved = [r for r in rsids if r and r not in snp_cache]

    if not unresolved:
        return {r: snp_cache.get(r, {"genes": [], "chromosome": "", "position": 0}) for r in rsids}

    logger.info(f"   🔬 Resolving {len(unresolved)} unique SNPs to genes + locations...")
    resolved = 0

    for i, rsid in enumerate(unresolved):
        try:
            resp = retry_with_backoff(
                lambda rsid=rsid: _gwas_http_get(
                    f"{GWAS_API}/singleNucleotidePolymorphisms/{rsid}",
                    {},
                    timeout=15,
                ),
                source=f"SNP resolution for {rsid}",
            )
            if resp.ok:
                data = resp.json()
                genes = []
                chromosome = ""
                position = 0

                for ctx in data.get("genomicContexts", []):
                    gene_info = ctx.get("gene")
                    if gene_info and gene_info.get("geneName"):
                        genes.append(gene_info["geneName"])
                    # Capture location from first context with position data
                    loc = ctx.get("location", {})
                    if not chromosome and loc.get("chromosomeName"):
                        chromosome = str(loc["chromosomeName"])
                        position = int(loc.get("chromosomePosition", 0))

                snp_cache[rsid] = {
                    "genes": genes,
                    "chromosome": chromosome,
                    "position": position,
                }
                if genes:
                    resolved += 1
            else:
                snp_cache[rsid] = {"genes": [], "chromosome": "", "position": 0}
        except ExternalAPIError as e:
            logger.info(f"   ⚠️  {e}")
            snp_cache[rsid] = {"genes": [], "chromosome": "", "position": 0}
        except json.JSONDecodeError as e:
            err = classify_api_error(e, f"SNP resolution for {rsid}")
            logger.info(f"   ⚠️  {err}")
            snp_cache[rsid] = {"genes": [], "chromosome": "", "position": 0}
        except requests.exceptions.RequestException as e:
            err = classify_api_error(e, f"SNP resolution for {rsid}")
            logger.info(f"   ⚠️  {err}")
            snp_cache[rsid] = {"genes": [], "chromosome": "", "position": 0}

        if (i + 1) % 20 == 0 or i == len(unresolved) - 1:
            logger.info(f"      [{i+1}/{len(unresolved)}] {resolved} SNPs mapped")
        _tick(progress_callback, "resolving SNPs", i + 1, len(unresolved))

        rate_limited_sleep(0.3)

    logger.info(f"   ✅ Resolved {resolved}/{len(unresolved)} SNPs")
    return {r: snp_cache.get(r, {"genes": [], "chromosome": "", "position": 0}) for r in rsids}


def extract_gene_associations(
    studies: list,
    max_studies: int = 30,
    resolve_snps: bool = True,
    progress_callback: StandardProgress | None = None,
) -> dict:
    """
    Extract gene-level associations from GWAS studies.

    For each study, fetch SNP associations and map to genes.
    When resolve_snps=True, follows SNP links to resolve rsIDs to genes
    via the singleNucleotidePolymorphisms endpoint.

    Returns:
        {
            "gene_associations": {gene_name: {studies: [...], best_p: ...}},
            "total_studies": n,
            "total_associations": n,
            "study_details": [...],
        }
    """
    gene_map = defaultdict(lambda: {"studies": [], "best_p": 1.0})
    study_details = []
    total_associations = 0
    all_rsids = set()
    # Store (accession, title, pubmed_id, p_val, rsids) per association
    assoc_records = []

    study_limit = min(len(studies), max_studies)
    for i, study in enumerate(studies[:max_studies]):
        _tick(progress_callback, "extracting associations", i + 1, study_limit)
        accession = study.get("accessionId", "")
        title = study.get("title", "Unknown")
        pubmed_id = study.get("publicationInfo", {}).get("pubmedId", "")

        logger.info(f"   [{i+1}/{min(len(studies), max_studies)}] {title[:80]}...")

        raw_associations = fetch_study_associations(accession)
        if raw_associations:
            study_detail = {
                "accession": accession,
                "title": title,
                "pubmed_id": pubmed_id,
                "n_associations": len(raw_associations),
                "genes": set(),
            }

            for assoc in raw_associations:
                # Compute p-value from mantissa + exponent
                p_val = None
                mantissa = assoc.get("pvalueMantissa")
                exponent = assoc.get("pvalueExponent")
                if mantissa is not None and exponent is not None:
                    try:
                        p_val = float(mantissa) * (10 ** int(exponent))
                    except (ValueError, TypeError):
                        logger.info(f"   ⚠️  Could not parse p-value for association: mantissa={mantissa}, exponent={exponent}")

                # Collect rsIDs from all loci
                rsids = []
                for locus in assoc.get("loci", []):
                    # Author-reported genes (immediate, no API call needed)
                    reported = locus.get("authorReportedGenes", [])
                    if isinstance(reported, list):
                        for gene in reported:
                            gene_name = gene.get("geneName", gene) if isinstance(gene, dict) else gene
                            if gene_name:
                                study_detail["genes"].add(str(gene_name))
                                gene_map[str(gene_name)]["studies"].append({
                                    "accession": accession,
                                    "title": title[:120],
                                    "pubmed_id": pubmed_id,
                                    "p_value": p_val,
                                })
                                if p_val is not None:
                                    gene_map[str(gene_name)]["best_p"] = min(
                                        gene_map[str(gene_name)]["best_p"], float(p_val)
                                    )

                    # Collect SNP rsIDs for later resolution
                    for allele in locus.get("strongestRiskAlleles", []):
                        rs_name = allele.get("riskAlleleName", "")
                        rsid = rs_name.split("-")[0] if "-" in rs_name else rs_name
                        if rsid.startswith("rs"):
                            rsids.append(rsid)
                            all_rsids.add(rsid)

                assoc_records.append({
                    "accession": accession,
                    "title": title[:120],
                    "pubmed_id": pubmed_id,
                    "p_val": p_val,
                    "rsids": rsids,
                })

            study_details.append(study_detail)
            total_associations += len(raw_associations)
            rate_limited_sleep(0.5)  # Rate limiting between studies

    # ── Resolve SNPs to genes + locations ────────────────────────────
    snp_details = {}
    if resolve_snps and all_rsids:
        logger.info(f"\n   🧬 Collected {len(all_rsids)} unique SNP rsIDs across all studies")
        snp_details = _resolve_snp_details(all_rsids, progress_callback=progress_callback)

        # Map resolved genes back to study/gene tracking
        for record in assoc_records:
            for rsid in record["rsids"]:
                details = snp_details.get(rsid, {})
                genes = details.get("genes", [])
                for gene in genes:
                    if gene:
                        gene_map[gene]["studies"].append({
                            "accession": record["accession"],
                            "title": record["title"],
                            "pubmed_id": record["pubmed_id"],
                            "p_value": record["p_val"],
                        })
                        if record["p_val"] is not None:
                            gene_map[gene]["best_p"] = min(
                                gene_map[gene]["best_p"], float(record["p_val"])
                            )

        # Update study_details with SNP-resolved genes
        resolved_genes_by_study = defaultdict(set)
        for record in assoc_records:
            for rsid in record["rsids"]:
                for gene in snp_details.get(rsid, {}).get("genes", []):
                    if gene:
                        resolved_genes_by_study[record["accession"]].add(gene)

        for sd in study_details:
            extra = resolved_genes_by_study.get(sd["accession"], set())
            sd["genes"] = sorted(set(sd["genes"]) | extra)

    # Sort genes by study count
    gene_associations = {}
    for gene, info in sorted(
        gene_map.items(), key=lambda x: len(x[1]["studies"]), reverse=True
    ):
        gene_associations[gene] = {
            "n_studies": len(info["studies"]),
            "best_p_value": info["best_p"],
            "studies": info["studies"][:5],
        }

    # Build SNP-level data for Manhattan plot
    snp_data = []
    for record in assoc_records:
        if record["p_val"] is not None and record["p_val"] > 0:
            for rsid in record["rsids"]:
                details = snp_details.get(rsid, {})
                if details.get("chromosome") and details.get("position"):
                    snp_data.append({
                        "rsid": rsid,
                        "chromosome": details["chromosome"],
                        "position": details["position"],
                        "p_value": record["p_val"],
                    })

    return {
        "gene_associations": gene_associations,
        "total_studies_analyzed": min(len(studies), max_studies),
        "total_associations": total_associations,
        "study_details": study_details,
        "snp_data": snp_data,
    }


def cross_reference_with_kg(
    gwas_results: dict, kg_genes: dict, disease_id: str = "sle"
) -> dict:
    """
    Cross-reference GWAS gene associations with the knowledge graph genes.

    Identifies:
      1. KG genes also found in GWAS (validated risk genes)
      2. GWAS genes NOT in our KG (potentially novel targets to add)
      3. KG genes NOT in GWAS results (may need more investigation)
    """
    gene_associations = gwas_results["gene_associations"]
    kg_gene_symbols = {}
    kg_gene_ids = {}
    for gene_id, info in kg_genes.items():
        entry = {
            "gene_id": gene_id,
            "name": info["name"],
            "category": info.get("category", ""),
            "odds_ratio": info.get("odds_ratio"),
            "chromosome": info.get("chromosome", ""),
        }
        kg_gene_symbols[gene_id.lower()] = entry
        kg_gene_ids[gene_id.lower()] = entry

    # Match: GWAS genes found in KG (by gene symbol OR gene ID)
    validated = {}
    for gwas_gene, gwas_info in gene_associations.items():
        key = gwas_gene.lower()
        matched = kg_gene_symbols.get(key) or kg_gene_ids.get(key)
        if matched:
            validated[gwas_gene] = {
                **matched,
                "n_gwas_studies": gwas_info["n_studies"],
                "gwas_best_p": gwas_info["best_p_value"],
                "gwas_studies": gwas_info["studies"],
            }

    # Novel: GWAS genes NOT in KG (by symbol OR gene ID)
    kg_match_keys = set(kg_gene_symbols.keys()) | set(kg_gene_ids.keys())
    novel = {}
    for gwas_gene, gwas_info in gene_associations.items():
        if gwas_gene.lower() not in kg_match_keys:
            novel[gwas_gene] = gwas_info

    # Missing: KG genes NOT in GWAS results (check by gene ID)
    gwas_lower = {g.lower() for g in gene_associations}
    missing = {}
    for gene_id, info in kg_genes.items():
        if gene_id.lower() not in gwas_lower:
            missing[gene_id] = {
                "gene_id": gene_id,
                "name": info["name"],
                "category": info.get("category", ""),
                "odds_ratio": info.get("odds_ratio"),
                "chromosome": info.get("chromosome", ""),
            }

    # Filter drug-target genes from KG before flagging as missing
    from med_research.diseases.base import Disease

    drug_target_genes = Disease(disease_id).get_drug_target_exclusions()
    missing = {k: v for k, v in missing.items() if k not in drug_target_genes}

    return {
        "validated": validated,
        "novel": novel,
        "missing": missing,
        "n_validated": len(validated),
        "n_novel": len(novel),
        "n_missing": len(missing),
    }


def analyze(gwas_results: dict, crossref: dict, kg_genes: dict):
    """Print GWAS annotation summary."""
    logger.info("\n" + "=" * 70)
    logger.info("🧬 GWAS CATALOG ANNOTATION")
    logger.info("=" * 70)

    logger.info(
        f"\n  Studies analyzed: {gwas_results['total_studies_analyzed']}"
    )
    logger.info(
        f"  Total SNP associations: {gwas_results['total_associations']}"
    )
    logger.info(
        f"  Unique genes with associations: "
        f"{len(gwas_results['gene_associations'])}"
    )

    logger.info("\n  📊 Cross-reference with Knowledge Graph:")
    logger.info(f"     ✅ Validated (GWAS + KG): {crossref['n_validated']}")
    logger.info(f"     🆕 Novel (GWAS only):    {crossref['n_novel']}")
    logger.info(f"     ❓ Missing (KG only):    {crossref['n_missing']}")

    # Validated genes
    validated = crossref.get("validated", {})
    if validated:
        logger.info("\n  🎯 KG genes validated by GWAS:")
        for gene_name, info in sorted(
            validated.items(),
            key=lambda x: x[1]["n_gwas_studies"],
            reverse=True,
        ):
            logger.info(
                f"     • {gene_name:<25} "
                f"{info['n_gwas_studies']} GWAS studies | "
                f"KG odds ratio: {info.get('odds_ratio', 'N/A')}"
            )

    # Novel genes (top 10)
    novel = crossref.get("novel", {})
    if novel:
        logger.info("\n  🆕 Top GWAS genes NOT in knowledge graph:")
        for gene_name, info in sorted(
            novel.items(),
            key=lambda x: x[1]["n_studies"],
            reverse=True,
        )[:10]:
            logger.info(
                f"     • {gene_name:<25} "
                f"{info['n_studies']} GWAS studies | "
                f"Best P={info['best_p_value']:.1e}"
            )

    # Missing genes
    missing = crossref.get("missing", {})
    if missing:
        logger.info(
            "\n  ❓ KG genes with NO GWAS hit (may need more investigation):"
        )
        for gene_id, info in sorted(missing.items()):
            logger.info(
                f"     • {info['name'][:40]:<42} "
                f"({gene_id}) — {info.get('category', '')}"
            )


def run_gwas_analysis(
    disease_id: str = "sle",
    max_studies: int = 30,
    use_cache: bool = True,
    resolve_snps: bool = True,
    progress_callback: StandardProgress | None = None,
) -> dict:
    """Run GWAS Catalog annotation for a disease (engine entry point)."""
    from med_research.diseases.coverage import module_coverage

    coverage = module_coverage(disease_id, "gwas", ("genes", "gwas_search_terms"))
    if not coverage.is_runnable:
        return {
            "coverage": coverage.to_dict(),
            "status": "blocked",
            "gwas_results": {},
            "crossref": {},
        }

    logger.info("🔄 Loading knowledge graph genes...")
    kg_genes = {}
    genes_data = config_load_genes(disease_id)
    for g in genes_data["genes"]:
        kg_genes[g["id"]] = g
    logger.info(f"   Loaded {len(kg_genes)} KG genes")

    logger.info("🔄 Searching GWAS Catalog...")
    search_terms = disease_search_terms(disease_id)
    all_studies = []
    term_count = min(len(search_terms), 2)
    for idx, term in enumerate(search_terms[:2], 1):
        studies = search_gwas_studies(
            term,
            max_results=max_studies // 2,
        )
        all_studies.extend(studies)
        _tick(progress_callback, "searching GWAS catalog", idx, term_count)
        rate_limited_sleep(0.5)

    seen = set()
    unique_studies = []
    for s in all_studies:
        acc = s.get("accessionId")
        if acc and acc not in seen:
            seen.add(acc)
            unique_studies.append(s)

    logger.info(f"   Total unique studies: {len(unique_studies)}")

    all_results = None
    if use_cache:
        cached = cache_get(NS_GWAS, disease_id, use_cache=True)
        if cached is None:
            legacy = load_legacy_json(gwas_cache_path(disease_id))
            if legacy and "gwas_results" in legacy and "crossref" in legacy:
                cached = {
                    "gwas_results": legacy["gwas_results"],
                    "crossref": legacy["crossref"],
                }
                cache_set(NS_GWAS, disease_id, cached, use_cache=True)
        if cached:
            try:
                logger.info("📦 Loading GWAS results from cache...")
                _tick(progress_callback, "loading GWAS results", 1, 1)
                gwas_results = cached["gwas_results"]
                crossref = cached["crossref"]
                all_results = cached
            except KeyError:
                logger.warning("   ⚠️  Corrupt cache, re-running GWAS...")

    if all_results is None:
        logger.info("\n🔄 Extracting gene-level associations...")
        gwas_results = extract_gene_associations(
            unique_studies,
            max_studies=max_studies,
            resolve_snps=resolve_snps,
            progress_callback=progress_callback,
        )

        logger.info("\n🔄 Cross-referencing with knowledge graph...")
        crossref = cross_reference_with_kg(gwas_results, kg_genes, disease_id=disease_id)

        cache_data = {"gwas_results": gwas_results, "crossref": crossref}
        try:
            cache_set(NS_GWAS, disease_id, cache_data, use_cache=use_cache)
            logger.info("💾 Cached GWAS results (namespace=%s, key=%s)", NS_GWAS, disease_id)
        except OSError as e:
            logger.warning(f"   ⚠️  Cache write error: {e}")

    analyze(gwas_results, crossref, kg_genes)

    os.makedirs(DATA_DIR, exist_ok=True)
    output = {
        "coverage": coverage.to_dict(),
        "status": "ready",
        "gwas_results": {
            "gene_associations": gwas_results["gene_associations"],
            "total_studies_analyzed": gwas_results["total_studies_analyzed"],
            "total_associations": gwas_results["total_associations"],
            "study_details": gwas_results["study_details"],
            "snp_data": gwas_results.get("snp_data", []),
        },
        "crossref": crossref,
    }
    out_path = DATA_DIR / "gwas_results.json"
    out_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.info(f"\n💾 Results saved to {out_path}")

    return output


def main():
    parser = argparse.ArgumentParser(
        description="GWAS Catalog Annotation (disease-aware)"
    )
    parser.add_argument(
        "--max-studies",
        type=int,
        default=30,
        help="Max GWAS studies to fetch (default: 30)",
    )
    parser.add_argument(
        "--export-html", action="store_true", help="Generate HTML report"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip cache, re-fetch from GWAS Catalog",
    )
    parser.add_argument(
        "--no-snp-resolve",
        action="store_true",
        help="Skip SNP-to-gene resolution (faster but fewer genes)",
    )
    parser.add_argument(
        "--disease", "-d", default="sle", help="Disease ID (default: sle)"
    )
    args = parser.parse_args()

    result = run_gwas_analysis(
        disease_id=args.disease,
        max_studies=args.max_studies,
        use_cache=not args.no_cache,
        resolve_snps=not args.no_snp_resolve,
    )
    if result.get("status") == "blocked":
        logger.error(
            f"❌ GWAS analysis blocked for {args.disease}: "
            f"{', '.join(result['coverage'].get('missing_inputs', []))}"
        )
        return result

    if args.export_html:
        from med_research.pipeline.bioinformatics.report import generate_bioinformatics_report
        from med_research.pipeline.provenance import build_provenance

        provenance = build_provenance(
            disease_id=args.disease,
            module="bioinformatics",
            sources=["gwas_catalog"],
            cache_or_live="cache",
            scoring={"analysis": "gwas_crossref"},
        )
        report_path = generate_bioinformatics_report(
            None,
            None,
            None,
            None,
            None,
            result["gwas_results"],
            result["crossref"],
            disease_id=args.disease,
            provenance=provenance,
        )
        logger.info(f"\n✅ Report generated: {report_path}")

    return result["gwas_results"]


if __name__ == "__main__":
    result = main()
    if isinstance(result, dict) and result.get("status") == "blocked":
        raise SystemExit(1)
