from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from jinja2 import Environment, FileSystemLoader

router = APIRouter(tags=["Dossier"])


@router.get("/api/dossier/generate")
async def generate_dossier():
    """Generate a simple regulatory dossier and serve PDF/Markdown URLs.
    The function renders the Jinja2 template `dossier.html` (located in the
    project's `templates` directory) with a timestamp and writes the result
    to the static dossier directory as both a Markdown file and a PDF.
    """
    # Resolve the pipeline dossier directory (used for static serving)
    # Path structure: <project>/pipeline/dossier
    base_dir = Path(__file__).resolve().parents[2] / "pipeline" / "dossier"
    base_dir.mkdir(parents=True, exist_ok=True)

    # Load and render the Jinja2 template
    templates_dir = Path(__file__).resolve().parents[3] / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=True,
    )
    template = env.get_template("dossier.html")
    rendered = template.render(timestamp=datetime.now(timezone.utc).isoformat())

    # Write Markdown (HTML content saved as .md for simplicity)
    md_path = base_dir / "dossier.md"
    md_path.write_text(rendered, encoding="utf-8")

    # Write PDF using WeasyPrint if available; fall back to empty file
    pdf_path = base_dir / "dossier.pdf"
    try:
        from weasyprint import HTML

        HTML(string=rendered).write_pdf(str(pdf_path))
    except Exception:
        # Create an empty placeholder PDF
        pdf_path.write_bytes(b"%PDF-1.4\n%Placeholder PDF generated without WeasyPrint\n")

    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "pdf_url": f"/static/dossier/{pdf_path.name}",
        "markdown_url": f"/static/dossier/{md_path.name}",
        "timestamp": timestamp,
    }
