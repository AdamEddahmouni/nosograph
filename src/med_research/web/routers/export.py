"""Export endpoints — download module results as JSON or rendered reports.

Provides a stable download surface for every pipeline module's latest
results file, plus a JSON "snapshot" of the report inputs so downstream
tooling (notebooks, dashboards, papers) can consume the data directly.
"""

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from med_research.web.config import PIPELINE_DIR

router = APIRouter(prefix="/api/export", tags=["Export"])

# module name -> (results filename inside the module's data dir, label)
MODULE_FILES: dict[str, str] = {
    "repurpose": "candidates.json",
    "bioinformatics-gwas": "gwas_results.json",
    "bioinformatics-enrichment": "enrichment_results.json",
    "bioinformatics-ppi": "ppi_results.json",
    "cart": "car_t_scores.json",
    "biomarker": "biomarker_matrix.json",
    "trials": "ct_results.json",
    "cross-disease": "cross_disease_analysis.json",
    "synergy": "synergy_results.json",
    "safety": "safety_scores.json",
    "safety-profiles": "profiles.json",
    "expression": "expression_correlations.json",
    "ml": "ml_predictions.json",
    "screening": "screening_results.json",
    "network": "network_analysis.json",
    "literature": "pubmed_cache.json",
}

# module name -> (report filename, module data dir) for HTML exports
MODULE_REPORTS: dict[str, tuple[str, str]] = {
    "repurpose": ("report.html", "drug_repurposing"),
    "cart": ("report.html", "car_t_predictor"),
    "biomarker": ("report.html", "biomarker_discovery"),
    "trials": ("ct_report.html", "clinical_trials"),
    "cross-disease": ("report.html", "cross_disease"),
    "synergy": ("report.html", "drug_synergy"),
    "safety": ("report.html", "adverse_events"),
    "expression": ("report.html", "gene_expression"),
    "ml": ("ml_report.html", "ml_predictor"),
    "screening": ("screening_report.html", "virtual_screening"),
    "network": ("report.html", "network_pharmacology"),
    "literature": ("literature_report.html", "literature_mining"),
    "bioinformatics": ("bioinformatics_report.html", "bioinformatics"),
}


def _module_data_dir(module_dir: str) -> Path:
    """Resolve a module's data directory under the pipeline tree."""
    return PIPELINE_DIR / module_dir / "data"


def _all_pipeline_data_dirs() -> list[Path]:
    """All module data directories under the pipeline tree."""
    if not PIPELINE_DIR.exists():
        return []
    return sorted(p / "data" for p in PIPELINE_DIR.iterdir() if (p / "data").exists())


@router.get("/modules")
def list_export_modules() -> dict[str, Any]:
    """List all modules available for JSON export with their file names."""
    items = []
    for name, fname in MODULE_FILES.items():
        items.append(
            {
                "module": name,
                "file": fname,
                "available": _find_results_file(fname) is not None,
            }
        )
    return {"modules": items}


@router.get("/json/{module}")
def export_module_json(module: str) -> JSONResponse:
    """Download a module's latest results as raw JSON."""
    fname = MODULE_FILES.get(module)
    if fname is None:
        raise HTTPException(status_code=404, detail=f"Unknown export module: {module}")

    path = _find_results_file(fname)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail=f"No results file '{fname}' found. Run the '{module}' pipeline first.",
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Results file is corrupt: {exc}") from exc

    return JSONResponse(content=data)


@router.get("/raw/{module}")
def export_module_raw(module: str) -> FileResponse:
    """Download a module's raw results file (original JSON layout)."""
    fname = MODULE_FILES.get(module)
    if fname is None:
        raise HTTPException(status_code=404, detail=f"Unknown export module: {module}")

    path = _find_results_file(fname)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail=f"No results file '{fname}' found. Run the '{module}' pipeline first.",
        )
    return FileResponse(
        path,
        media_type="application/json",
        filename=f"{module}_results.json",
    )


@router.get("/report/{module}")
def export_module_report(module: str) -> FileResponse:
    """Download a module's rendered HTML report."""
    entry = MODULE_REPORTS.get(module)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No report export for module: {module}")
    report_name, module_dir = entry

    path = _module_data_dir(module_dir) / report_name
    # Some reports land in the module root instead of data/
    if not path.exists():
        alt = PIPELINE_DIR / module_dir / report_name
        if alt.exists():
            path = alt
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Report '{report_name}' not found for module '{module}'. Generate it with --export-html first.",
        )
    return FileResponse(path, media_type="text/html", filename=path.name)


@router.get("/report/{module}/print.css")
def export_print_stylesheet(module: str) -> PlainTextResponse:
    """Serve the shared print stylesheet used when saving reports to PDF."""
    css = _PRINT_CSS
    return PlainTextResponse(css, media_type="text/css")


def _find_results_file(fname: str) -> Path | None:
    """Search all module data dirs for a results file by name."""
    for data_dir in _all_pipeline_data_dirs():
        candidate = data_dir / fname
        if candidate.exists():
            return candidate
    for data_dir in _all_pipeline_data_dirs():
        for p in data_dir.glob("*.json"):
            if p.name == fname:
                return p
    return None


# Shared print stylesheet — turns the dark reports into clean light PDFs
_PRINT_CSS = """\
/* Medical Research Platform — print/PDF stylesheet */
@media print {
    * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    body { background: #ffffff !important; color: #111827 !important; }
    .hero, .container, .table-container, .stat-card, .match-card,
    .hit-card, .chart-card, .methodology, .method-card, .vina-box,
    .target-section, .kg-explorer, .cd-card {
        background: #ffffff !important; color: #111827 !important;
        border-color: #d1d5db !important; box-shadow: none !important;
    }
    h1, h2, h3, h4, th { color: #111827 !important; }
    .subtitle, .muted, footer, .stat-label, .hit-count, .target-category,
    .target-mean, .vina-note, .rel-desc { color: #4b5563 !important; }
    table { border-collapse: collapse; width: 100%; }
    th { background: #f3f4f6 !important; }
    td, th { border: 1px solid #d1d5db !important; }
    a { color: #2563eb !important; text-decoration: none; }
    .stat-card, .match-card, .hit-card { break-inside: avoid; }
    .section-title { border-bottom-color: #d1d5db !important; }
    footer { border-top-color: #d1d5db !important; }
    @page { margin: 1.5cm; }
}
"""
