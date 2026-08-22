"""Generate the canonical NosoGraph SVG identity from one geometry source.

The full mark follows the approved seven-node N construction. Compact and micro
variants intentionally remove secondary links while preserving the same anchors.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "brand"
WEB_OUT = ROOT / "src" / "med_research" / "web" / "static" / "brand"

NAVY = "#08142D"
LAYER = "#102246"
TEAL = "#19D2C7"
BLUE = "#2F86FF"
VIOLET = "#7252F4"
MIST = "#DCE4EF"
WHITE = "#F8FBFF"
SLATE = "#73819A"


def symbol_body(*, monochrome: str | None = None) -> str:
    primary = monochrome or "url(#ng-gradient)"
    teal = monochrome or TEAL
    blue = monochrome or BLUE
    violet = monochrome or VIOLET
    cutout = "none"
    return f'''<g id="ng-symbol" fill="none" stroke-linecap="round" stroke-linejoin="round">
  <path d="M24 16 V104" stroke="{teal}" stroke-width="5"/>
  <path d="M104 24 V104" stroke="{primary}" stroke-width="4"/>
  <path d="M24 16 L68 60 L104 104" stroke="{primary}" stroke-width="7"/>
  <path d="M24 56 L48 80 L68 60" stroke="{blue}" stroke-width="3"/>
  <path d="M24 104 L48 80 L104 24" stroke="{blue}" stroke-width="3"/>
  <path d="M24 56 L68 60" stroke="{primary}" stroke-width="3"/>
  <path d="M48 80 L104 104" stroke="{violet}" stroke-width="3"/>
  <circle cx="24" cy="16" r="11" fill="{teal}" stroke="none"/>
  <circle cx="24" cy="56" r="6" fill="{cutout}" stroke="{teal}" stroke-width="3"/>
  <circle cx="24" cy="104" r="8" fill="{cutout}" stroke="{teal}" stroke-width="4"/>
  <circle cx="68" cy="60" r="10" fill="{blue}" stroke="none"/>
  <circle cx="48" cy="80" r="6" fill="{cutout}" stroke="{blue}" stroke-width="3"/>
  <circle cx="104" cy="24" r="8" fill="{cutout}" stroke="{blue}" stroke-width="4"/>
  <circle cx="104" cy="104" r="13" fill="{violet}" stroke="none"/>
</g>'''


SYMBOL_BODY = symbol_body()


def svg_document(
    body: str,
    width: int,
    height: int,
    *,
    defs: str = "",
    title: str = "NosoGraph — Disease Intelligence. Connected.",
) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">
  <title id="title">{title}</title>
  <defs>
    <linearGradient id="ng-gradient" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{TEAL}"/>
      <stop offset="0.52" stop-color="{BLUE}"/>
      <stop offset="1" stop-color="{VIOLET}"/>
    </linearGradient>{defs}
  </defs>
{body}
</svg>
'''


def symbol_use(x: int, y: int, size: int, *, monochrome: str | None = None) -> str:
    scale = size / 120
    body = symbol_body(monochrome=monochrome).replace(' id="ng-symbol"', "")
    return f'<g transform="translate({x} {y}) scale({scale:g})">{body}</g>'


def wordmark(
    *,
    x: int,
    y: int,
    size: int,
    text: str,
    graph: str = "url(#ng-gradient)",
    weight: int = 400,
) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Sora, Inter, Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" letter-spacing="-1.8" fill="{text}">'
        f'Noso<tspan fill="{graph}">Graph</tspan></text>'
    )


def tagline(*, x: int, y: int, text: str, accent: str, size: int = 15) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Inter, Arial, sans-serif" '
        f'font-size="{size}" font-weight="600" letter-spacing="6" fill="{text}">'
        f'DISEASE INTELLIGENCE. <tspan fill="{accent}">CONNECTED.</tspan></text>'
    )


def network_field() -> str:
    return f'''<g opacity=".22" fill="none" stroke="{BLUE}" stroke-width="2">
  <path d="M930 54 L1030 130 L1110 72 L1218 166 L1350 82"/>
  <path d="M1030 130 L980 250 L1134 230 L1218 166 L1298 300 L1415 216"/>
  <path d="M980 250 L1080 385 L1210 336 L1298 300 L1388 420"/>
  <path d="M1080 385 L1190 500 L1325 468 L1388 420"/>
</g>
<g opacity=".32" fill="{BLUE}">
  <circle cx="930" cy="54" r="7"/><circle cx="1030" cy="130" r="11"/><circle cx="1110" cy="72" r="7"/>
  <circle cx="1218" cy="166" r="14"/><circle cx="1350" cy="82" r="10"/><circle cx="980" cy="250" r="8"/>
  <circle cx="1134" cy="230" r="12"/><circle cx="1298" cy="300" r="17"/><circle cx="1415" cy="216" r="9"/>
  <circle cx="1080" cy="385" r="9"/><circle cx="1210" cy="336" r="7"/><circle cx="1388" cy="420" r="12"/>
  <circle cx="1190" cy="500" r="8"/><circle cx="1325" cy="468" r="10"/>
</g>'''


def build_assets() -> dict[str, str]:
    symbol = svg_document(SYMBOL_BODY, 120, 120, title="NosoGraph symbol")
    symbol_mono = svg_document(
        symbol_body(monochrome=NAVY), 120, 120, title="NosoGraph monochrome symbol"
    )
    symbol_reversed = svg_document(
        symbol_body(monochrome=WHITE), 120, 120, title="NosoGraph reversed symbol"
    )
    dark_mark = svg_document(
        f'<rect width="120" height="120" rx="26" fill="{NAVY}"/>\n  {symbol_use(0, 0, 120)}',
        120,
        120,
        title="NosoGraph application icon",
    )
    light_mark = svg_document(
        f'<rect width="120" height="120" rx="26" fill="{WHITE}"/>\n  {symbol_use(0, 0, 120)}',
        120,
        120,
        title="NosoGraph light application icon",
    )
    micro = svg_document(
        f'''<rect width="120" height="120" rx="26" fill="{NAVY}"/>
  <path d="M35 28 V88 M35 28 L86 88" stroke="url(#ng-gradient)" stroke-width="9" stroke-linecap="round"/>
  <circle cx="35" cy="28" r="12" fill="{TEAL}"/>
  <circle cx="86" cy="88" r="12" fill="{VIOLET}"/>''',
        120,
        120,
        title="NosoGraph micro mark",
    )

    full_lockup = (
        f"{symbol_use(18, 17, 120)}\n  "
        f"{wordmark(x=164, y=78, size=58, text=WHITE)}\n  "
        f"{tagline(x=168, y=121, text=MIST, accent=TEAL, size=14)}"
    )
    dark_logo = svg_document(
        f'<rect width="760" height="154" rx="18" fill="{NAVY}"/>\n  {full_lockup}',
        760,
        154,
    )
    light_logo = svg_document(
        f'''<rect width="760" height="154" rx="18" fill="{WHITE}"/>
  {symbol_use(18, 17, 120)}
  {wordmark(x=164, y=78, size=58, text=NAVY)}
  {tagline(x=168, y=121, text=SLATE, accent=BLUE, size=14)}''',
        760,
        154,
    )
    tagline_lockup = svg_document(full_lockup, 760, 154)
    logo_mono = svg_document(
        f'''<rect width="760" height="154" rx="18" fill="{WHITE}"/>
  {symbol_use(18, 17, 120, monochrome=NAVY)}
  {wordmark(x=164, y=78, size=58, text=NAVY, graph=NAVY)}
  {tagline(x=168, y=121, text=NAVY, accent=NAVY, size=14)}''',
        760,
        154,
        title="NosoGraph monochrome logo",
    )
    logo_reversed = svg_document(
        f'''<rect width="760" height="154" rx="18" fill="{NAVY}"/>
  {symbol_use(18, 17, 120, monochrome=WHITE)}
  {wordmark(x=164, y=78, size=58, text=WHITE, graph=WHITE)}
  {tagline(x=168, y=121, text=WHITE, accent=WHITE, size=14)}''',
        760,
        154,
        title="NosoGraph reversed logo",
    )
    avatar = svg_document(
        f'<rect width="512" height="512" rx="112" fill="{NAVY}"/>\n  {symbol_use(56, 56, 400)}',
        512,
        512,
        title="NosoGraph avatar",
    )
    hero = svg_document(
        f'''<rect width="1440" height="560" fill="{NAVY}"/>
  {network_field()}
  {symbol_use(94, 124, 220)}
  {wordmark(x=354, y=253, size=104, text=WHITE)}
  {tagline(x=364, y=326, text=MIST, accent=TEAL, size=22)}
  <text x="368" y="396" font-family="Inter, Arial, sans-serif" font-size="21" fill="{MIST}">Open-source research software for connected biomedical discovery.</text>
  <text x="368" y="448" font-family="JetBrains Mono, monospace" font-size="14" letter-spacing="1.4" fill="{SLATE}">DISEASE → CLAIM → EVIDENCE → PROVENANCE → SOURCE</text>''',
        1440,
        560,
        title="NosoGraph connects disease evidence and provenance",
    )
    social = svg_document(
        f'''<rect width="1280" height="640" fill="{NAVY}"/>
  {network_field()}
  {symbol_use(76, 190, 190)}
  {wordmark(x=300, y=296, size=88, text=WHITE)}
  {tagline(x=308, y=362, text=MIST, accent=TEAL, size=18)}
  <text x="312" y="426" font-family="Inter, Arial, sans-serif" font-size="21" fill="{MIST}">Open-source research software for connected biomedical discovery.</text>''',
        1280,
        640,
        title="NosoGraph social preview",
    )
    return {
        "symbol.svg": symbol,
        "symbol-mono-dark.svg": symbol_mono,
        "symbol-reversed.svg": symbol_reversed,
        "mark.svg": dark_mark,
        "mark-light.svg": light_mark,
        "compact.svg": dark_mark,
        "micro.svg": micro,
        "favicon.svg": micro,
        "github-avatar.svg": avatar,
        "logo-dark.svg": dark_logo,
        "logo-light.svg": light_logo,
        "logo-mono-dark.svg": logo_mono,
        "logo-reversed.svg": logo_reversed,
        "tagline-lockup.svg": tagline_lockup,
        "hero.svg": hero,
        "social-preview.svg": social,
    }


def _write_assets(assets: dict[str, str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    WEB_OUT.mkdir(parents=True, exist_ok=True)
    for name, content in assets.items():
        (OUT / name).write_text(content, encoding="utf-8")
    for name in ("symbol.svg", "mark.svg", "micro.svg", "favicon.svg", "logo-dark.svg"):
        (WEB_OUT / name).write_text(assets[name], encoding="utf-8")


def _check_assets(assets: dict[str, str]) -> None:
    drift: list[str] = []
    for name, expected in assets.items():
        path = OUT / name
        if not path.is_file():
            drift.append(f"missing docs asset: {name}")
        elif path.read_text(encoding="utf-8") != expected:
            drift.append(f"stale docs asset: {name}")
    for name in ("symbol.svg", "mark.svg", "micro.svg", "favicon.svg", "logo-dark.svg"):
        path = WEB_OUT / name
        if not path.is_file():
            drift.append(f"missing dashboard asset: {name}")
        elif path.read_text(encoding="utf-8") != assets[name]:
            drift.append(f"stale dashboard asset: {name}")
    if drift:
        raise SystemExit("brand asset drift detected:\n- " + "\n- ".join(drift))
    print(f"brand assets current ({len(assets)} docs assets; 5 dashboard assets)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check generated assets for drift")
    args = parser.parse_args()
    assets = build_assets()
    if args.check:
        _check_assets(assets)
        return
    _write_assets(assets)
    print(f"generated {len(assets)} NosoGraph assets in {OUT} and {WEB_OUT}")


if __name__ == "__main__":
    main()
