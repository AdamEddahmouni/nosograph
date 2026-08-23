import datetime
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from med_research.web.config import PIPELINE_DIR
from med_research.web.services.dossier_service import (
    collect_module_data,
    data_to_markdown,
    html_to_pdf,
    render_dossier_html,
)

router = APIRouter(prefix="/api/dossier", tags=["Dossier"])
logger = logging.getLogger(__name__)


@router.get("/generate")
async def generate_dossier():
    """Generate regulatory IND‑ready dossier as PDF and Markdown.
    Returns JSON with download URLs for the generated files.
    """
    # 1. Gather data from all pipeline modules
    module_data = collect_module_data()
    if not module_data:
        raise HTTPException(status_code=404, detail="No module results found to generate dossier.")

    # 2. Render HTML using Jinja2 template
    html_content = render_dossier_html(module_data)

    # 3. Create timestamped filenames
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dossier_dir = PIPELINE_DIR / "dossier"
    dossier_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = dossier_dir / f"{timestamp}_dossier.pdf"
    md_path = dossier_dir / f"{timestamp}_dossier.md"

    # 4. Convert HTML to PDF
    html_to_pdf(html_content, pdf_path)

    # 5. Convert data to Markdown
    md_content = data_to_markdown(module_data)
    md_path.write_text(md_content, encoding="utf-8")

    logger.info("Generated dossier PDF %s and Markdown %s", pdf_path, md_path)

    return JSONResponse(
        content={
            "pdf_url": f"/static/dossier/{pdf_path.name}",
            "markdown_url": f"/static/dossier/{md_path.name}",
            "timestamp": timestamp,
        }
    )
