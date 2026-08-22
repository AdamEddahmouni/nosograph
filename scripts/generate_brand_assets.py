"""Generate NosoGraph SVG brand and diagram assets (no external deps)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "docs" / "assets" / "brand"
DIAG = ROOT / "docs" / "assets" / "diagrams"
SHOT = ROOT / "docs" / "assets" / "screenshots"

INK = "#0E1624"
PAPER = "#F7F4EE"
TEAL = "#1B7A7A"
COPPER = "#B08968"
SLATE = "#3D5A80"
MUTED = "#5C6B7A"
LINE = "#C9D0D8"


def mark(bg: str, stroke: str, fill: str, node: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img">
  <title>NosoGraph mark</title>
  <rect width="64" height="64" rx="14" fill="{bg}"/>
  <g fill="none" stroke="{stroke}" stroke-width="2.2" stroke-linecap="round">
    <path d="M18 42 L32 18 L46 42"/>
    <path d="M22 36 L42 36"/>
    <path d="M32 18 L32 48"/>
  </g>
  <circle cx="32" cy="18" r="4.2" fill="{node}"/>
  <circle cx="18" cy="42" r="4.2" fill="{fill}"/>
  <circle cx="46" cy="42" r="4.2" fill="{fill}"/>
  <circle cx="32" cy="48" r="3.4" fill="{COPPER}"/>
</svg>
"""


def wordmark(bg: str, text: str, sub: str) -> str:
    stroke = TEAL if bg == PAPER else "#7FD1CF"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 140" role="img">
  <title>NosoGraph</title>
  <rect width="720" height="140" rx="16" fill="{bg}"/>
  <g transform="translate(24,38)">
    <g fill="none" stroke="{stroke}" stroke-width="2.2" stroke-linecap="round">
      <path d="M18 42 L32 18 L46 42"/>
      <path d="M22 36 L42 36"/>
      <path d="M32 18 L32 48"/>
    </g>
    <circle cx="32" cy="18" r="4.2" fill="{COPPER}"/>
    <circle cx="18" cy="42" r="4.2" fill="{TEAL}"/>
    <circle cx="46" cy="42" r="4.2" fill="{TEAL}"/>
    <circle cx="32" cy="48" r="3.4" fill="{COPPER}"/>
  </g>
  <text x="108" y="78" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif" font-size="48" font-weight="700" fill="{text}">NosoGraph</text>
  <text x="112" y="112" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif" font-size="16" fill="{sub}">The Open Computational Map of Human Disease</text>
</svg>
"""


def hero() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 420" role="img">
  <title>NosoGraph connects diseases to phenotypes, genes, mechanisms, treatments, and evidence</title>
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0B1524"/>
      <stop offset="100%" stop-color="#132536"/>
    </linearGradient>
  </defs>
  <rect width="1280" height="420" fill="url(#g)"/>
  <g opacity="0.35" fill="none" stroke="#7FD1CF" stroke-width="1.4">
    <path d="M80 300 C 220 80, 420 360, 620 160 S 980 80, 1200 240"/>
    <path d="M60 180 C 280 40, 480 300, 760 220 S 1100 340, 1240 120"/>
  </g>
  <g font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif" fill="#F7F4EE">
    <text x="72" y="120" font-size="22" fill="#7FD1CF" letter-spacing="3">OPEN-SOURCE BIOMEDICAL RESEARCH</text>
    <text x="72" y="188" font-size="58" font-weight="700">NosoGraph</text>
    <text x="72" y="236" font-size="26" fill="#D7E3EA">The Open Computational Map of Human Disease</text>
    <text x="72" y="286" font-size="18" fill="#A9BDC8">Disease · Phenotype · Gene · Mechanism · Pathway · Treatment · Trial · Evidence</text>
  </g>
  <g>
    <circle cx="980" cy="150" r="18" fill="{TEAL}"/>
    <circle cx="1088" cy="210" r="14" fill="{SLATE}"/>
    <circle cx="1010" cy="280" r="16" fill="{COPPER}"/>
    <circle cx="1140" cy="120" r="12" fill="#7FD1CF"/>
    <circle cx="1170" cy="260" r="15" fill="{TEAL}"/>
    <line x1="980" y1="150" x2="1088" y2="210" stroke="#7FD1CF" stroke-width="2"/>
    <line x1="1088" y1="210" x2="1010" y2="280" stroke="#C9D0D8" stroke-width="2"/>
    <line x1="980" y1="150" x2="1140" y2="120" stroke="#C9D0D8" stroke-width="2"/>
    <line x1="1088" y1="210" x2="1170" y2="260" stroke="#7FD1CF" stroke-width="2"/>
    <line x1="1010" y1="280" x2="1170" y2="260" stroke="#B08968" stroke-width="2"/>
  </g>
</svg>
"""


def social() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 640" role="img">
  <title>NosoGraph — The Open Computational Map of Human Disease</title>
  <rect width="1280" height="640" fill="#0B1524"/>
  <g opacity="0.28" fill="none" stroke="#1B7A7A" stroke-width="2">
    <path d="M40 520 C 240 80, 520 600, 820 220 S 1160 80, 1260 360"/>
  </g>
  <text x="80" y="210" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif" font-size="72" font-weight="700" fill="#F7F4EE">NosoGraph</text>
  <text x="80" y="280" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif" font-size="34" fill="#7FD1CF">The Open Computational Map</text>
  <text x="80" y="328" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif" font-size="34" fill="#7FD1CF">of Human Disease</text>
  <text x="80" y="400" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif" font-size="20" fill="#D7E3EA">Disease · Phenotype · Gene · Mechanism · Treatment · Evidence</text>
  <text x="80" y="540" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif" font-size="22" fill="#A9BDC8">Open-source biomedical research  ·  Public alpha</text>
  <circle cx="1080" cy="200" r="28" fill="{TEAL}"/>
  <circle cx="1180" cy="280" r="20" fill="{COPPER}"/>
  <circle cx="1040" cy="360" r="22" fill="{SLATE}"/>
  <line x1="1080" y1="200" x2="1180" y2="280" stroke="#7FD1CF" stroke-width="3"/>
  <line x1="1080" y1="200" x2="1040" y2="360" stroke="#B08968" stroke-width="3"/>
  <line x1="1180" y1="280" x2="1040" y2="360" stroke="#C9D0D8" stroke-width="3"/>
</svg>
"""


def box_flow(title: str, nodes: list[tuple[str, int, int, int, int]], edges: list[tuple[int, int, int, int]]) -> str:
    rects = []
    for label, x, y, w, h in nodes:
        rects.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#132536" stroke="{TEAL}" />'
            f'<text x="{x + w/2}" y="{y + h/2 + 5}" text-anchor="middle" fill="#F7F4EE" font-size="14" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">{label}</text>'
        )
    lines = [
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#7FD1CF" stroke-width="2" marker-end="url(#arr)"/>'
        for x1, y1, x2, y2 in edges
    ]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 980 640" role="img">
  <title>{title}</title>
  <rect width="980" height="640" fill="#0B1524"/>
  <defs>
    <marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <polygon points="0 0, 8 3, 0 6" fill="#7FD1CF"/>
    </marker>
  </defs>
  <text x="40" y="40" fill="#7FD1CF" font-size="18" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">{title}</text>
  {''.join(lines)}
  {''.join(rects)}
</svg>
"""


def ui_frame(title: str, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 900" role="img">
  <title>{title}</title>
  <rect width="1440" height="900" fill="#0a0a0f"/>
  <rect x="0" y="0" width="1440" height="56" fill="#13131a" stroke="#252535"/>
  <text x="28" y="36" fill="#e0e0e8" font-size="18" font-weight="700" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">NosoGraph</text>
  <text x="160" y="36" fill="#787890" font-size="14" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Workspace · Conditions · Compare · Evidence · API</text>
  {body}
  <text x="28" y="880" fill="#6b7280" font-size="13" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Representative layout of the local NosoGraph dashboard (research use only).</text>
</svg>
"""


def write() -> None:
    BRAND.mkdir(parents=True, exist_ok=True)
    DIAG.mkdir(parents=True, exist_ok=True)
    SHOT.mkdir(parents=True, exist_ok=True)

    (BRAND / "mark.svg").write_text(mark(INK, "#7FD1CF", TEAL, COPPER), encoding="utf-8")
    (BRAND / "mark-light.svg").write_text(mark(PAPER, TEAL, TEAL, COPPER), encoding="utf-8")
    (BRAND / "logo-dark.svg").write_text(wordmark(INK, PAPER, "#A9BDC8"), encoding="utf-8")
    (BRAND / "logo-light.svg").write_text(wordmark(PAPER, INK, MUTED), encoding="utf-8")
    (BRAND / "favicon.svg").write_text(mark(INK, "#7FD1CF", TEAL, COPPER), encoding="utf-8")
    (BRAND / "hero.svg").write_text(hero(), encoding="utf-8")
    (BRAND / "social-preview.svg").write_text(social(), encoding="utf-8")

    (DIAG / "architecture.svg").write_text(
        box_flow(
            "NosoGraph system architecture",
            [
                ("Biomedical sources", 360, 60, 240, 44),
                ("Acquisition / sync", 360, 130, 240, 44),
                ("Normalization", 360, 200, 240, 44),
                ("Evidence + claims + provenance", 300, 270, 360, 44),
                ("Universal biomedical store", 300, 340, 360, 44),
                ("Disease knowledge graphs", 300, 410, 360, 44),
                ("Analysis engines", 360, 480, 240, 44),
                ("CLI", 120, 560, 140, 44),
                ("API", 410, 560, 140, 44),
                ("Dashboard", 700, 560, 160, 44),
            ],
            [
                (480, 104, 480, 130),
                (480, 174, 480, 200),
                (480, 244, 480, 270),
                (480, 314, 480, 340),
                (480, 384, 480, 410),
                (480, 454, 480, 480),
                (190, 582, 410, 582),
                (550, 582, 700, 582),
                (480, 524, 480, 560),
                (190, 560, 190, 524),
                (780, 560, 780, 524),
            ],
        ),
        encoding="utf-8",
    )

    (DIAG / "how-it-works.svg").write_text(
        box_flow(
            "How NosoGraph works",
            [
                ("Public biomedical sources", 70, 80, 260, 50),
                ("Normalize identifiers & records", 360, 80, 280, 50),
                ("Attach provenance", 680, 80, 230, 50),
                ("Disease modules + universal store", 250, 220, 460, 50),
                ("Research workflows", 80, 360, 240, 50),
                ("Evidence tracing", 370, 360, 220, 50),
                ("Disease comparison", 640, 360, 240, 50),
                ("CLI / API / dashboard", 300, 500, 360, 50),
            ],
            [
                (330, 105, 360, 105),
                (640, 105, 680, 105),
                (480, 130, 480, 220),
                (480, 270, 480, 360),
                (200, 385, 370, 385),
                (590, 385, 640, 385),
                (480, 410, 480, 500),
            ],
        ),
        encoding="utf-8",
    )

    (DIAG / "evidence-flow.svg").write_text(
        box_flow(
            "Evidence and provenance flow",
            [
                ("Condition / research question", 310, 50, 360, 48),
                ("Claim", 380, 150, 220, 48),
                ("Supporting evidence", 80, 280, 240, 48),
                ("Contradictory evidence", 360, 280, 250, 48),
                ("Quality context", 660, 280, 230, 48),
                ("Provenance record", 200, 410, 260, 48),
                ("Source snapshot", 520, 410, 250, 48),
                ("Upstream database / paper", 310, 530, 360, 48),
            ],
            [
                (490, 98, 490, 150),
                (200, 304, 380, 198),
                (485, 198, 485, 280),
                (775, 304, 600, 198),
                (320, 328, 330, 410),
                (645, 328, 645, 410),
                (330, 458, 400, 530),
                (645, 458, 580, 530),
            ],
        ),
        encoding="utf-8",
    )

    (DIAG / "workflow-sle.svg").write_text(
        box_flow(
            "Example: investigating SLE (research workflow)",
            [
                ("1. Open SLE module", 60, 80, 200, 50),
                ("2. Phenotypes & genes", 290, 80, 220, 50),
                ("3. Pathways / expression", 540, 80, 230, 50),
                ("4. Compare with RA", 800, 80, 150, 50),
                ("5. Inspect a claim", 250, 250, 220, 50),
                ("6. Trace evidence → source", 510, 250, 260, 50),
                ("7. Export / reuse", 360, 420, 240, 50),
            ],
            [
                (260, 105, 290, 105),
                (510, 105, 540, 105),
                (770, 105, 800, 105),
                (360, 130, 360, 250),
                (470, 275, 510, 275),
                (640, 300, 480, 420),
            ],
        ),
        encoding="utf-8",
    )

    (SHOT / "dashboard.svg").write_text(
        ui_frame(
            "NosoGraph dashboard overview",
            """
  <rect x="40" y="90" width="1360" height="140" rx="12" fill="#13131a" stroke="#252535"/>
  <text x="64" y="140" fill="#e0e0e8" font-size="28" font-weight="700" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Open computational map of human disease</text>
  <text x="64" y="176" fill="#787890" font-size="16" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Selected disease · evidence workspace · knowledge graph · comparison</text>
  <rect x="40" y="260" width="430" height="560" rx="12" fill="#13131a" stroke="#252535"/>
  <rect x="490" y="260" width="430" height="560" rx="12" fill="#13131a" stroke="#252535"/>
  <rect x="940" y="260" width="460" height="560" rx="12" fill="#13131a" stroke="#252535"/>
  <text x="64" y="300" fill="#818cf8" font-size="16" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Disease graph</text>
  <text x="514" y="300" fill="#818cf8" font-size="16" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Evidence workspace</text>
  <text x="964" y="300" fill="#818cf8" font-size="16" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Corpus &amp; comparison</text>
""",
        ),
        encoding="utf-8",
    )
    (SHOT / "evidence-workspace.svg").write_text(
        ui_frame(
            "Evidence Workspace layout",
            """
  <rect x="40" y="90" width="1360" height="740" rx="12" fill="#13131a" stroke="#252535"/>
  <text x="64" y="140" fill="#e0e0e8" font-size="26" font-weight="700" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Evidence-to-Hypothesis Workspace</text>
  <text x="64" y="176" fill="#787890" font-size="16" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Assemble literature, trials, GWAS, and labels into inspectable claims.</text>
  <rect x="64" y="210" width="400" height="560" rx="10" fill="#1a1a24"/>
  <rect x="488" y="210" width="430" height="560" rx="10" fill="#1a1a24"/>
  <rect x="942" y="210" width="430" height="560" rx="10" fill="#1a1a24"/>
  <text x="84" y="250" fill="#22d3ee" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Retrieved evidence</text>
  <text x="508" y="250" fill="#4ade80" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Claims &amp; ranking</text>
  <text x="962" y="250" fill="#f59e0b" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Provenance panel</text>
""",
        ),
        encoding="utf-8",
    )
    (SHOT / "compare.svg").write_text(
        ui_frame(
            "NosoGraph Compare layout",
            """
  <rect x="40" y="90" width="1360" height="740" rx="12" fill="#13131a" stroke="#252535"/>
  <text x="64" y="140" fill="#e0e0e8" font-size="26" font-weight="700" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Condition Comparison</text>
  <text x="64" y="176" fill="#787890" font-size="16" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Experimental initial slice: phenotype, gene, mechanism, treatment, evidence coverage.</text>
  <rect x="64" y="220" width="1312" height="80" rx="8" fill="#1a1a24"/>
  <text x="84" y="268" fill="#e0e0e8" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">SLE  vs  RA   ·   missingness: NOT_RECORDED ≠ KNOWN_ABSENT</text>
  <rect x="64" y="330" width="1312" height="450" rx="8" fill="#1a1a24"/>
  <text x="84" y="380" fill="#818cf8" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Dimension matrix</text>
""",
        ),
        encoding="utf-8",
    )
    (SHOT / "disease-explore.svg").write_text(
        ui_frame(
            "Disease exploration layout",
            """
  <rect x="40" y="90" width="1360" height="740" rx="12" fill="#13131a" stroke="#252535"/>
  <text x="64" y="140" fill="#e0e0e8" font-size="26" font-weight="700" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Condition Explorer</text>
  <text x="64" y="176" fill="#787890" font-size="16" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Inspect connected phenotypes, genes, mechanisms, treatments, and evidence for a selected disease.</text>
  <rect x="64" y="220" width="420" height="560" rx="10" fill="#1a1a24"/>
  <rect x="508" y="220" width="860" height="560" rx="10" fill="#1a1a24"/>
  <text x="84" y="260" fill="#4ade80" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Entity list</text>
  <text x="528" y="260" fill="#60a5fa" font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">Relationship and evidence detail</text>
""",
        ),
        encoding="utf-8",
    )
    print("wrote brand, diagram, and screenshot SVGs")


if __name__ == "__main__":
    write()
