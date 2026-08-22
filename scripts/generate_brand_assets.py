"""Generate NosoGraph brand assets from one canonical graph-mark geometry source.

The generated SVGs intentionally share the same anchor geometry. Compact and micro
marks use the same geometry with fewer secondary edges for small-size legibility.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "brand"

NAVY = "#08142D"
LAYER = "#102246"
TEAL = "#19D2C7"
BLUE = "#2F86FF"
VIOLET = "#7252F4"
MIST = "#DCE4EF"
WHITE = "#F8FBFF"
SLATE = "#73819A"

SYMBOL_BODY = """<g id="ng-symbol" fill="none" stroke-linecap="round" stroke-linejoin="round">
  <path d="M24 24 V96" stroke="#19D2C7" stroke-width="5"/>
  <path d="M24 24 L60 58 L96 24" stroke="url(#ng-gradient)" stroke-width="5"/>
  <path d="M24 96 L48 70 L96 96" stroke="url(#ng-gradient)" stroke-width="5"/>
  <path d="M60 58 L96 96" stroke="#7252F4" stroke-width="5"/>
  <path d="M48 70 L96 24" stroke="#2F86FF" stroke-width="4"/>
  <circle cx="24" cy="24" r="9" fill="#19D2C7" stroke="none"/>
  <circle cx="24" cy="96" r="9" fill="#19D2C7" stroke="none"/>
  <circle cx="96" cy="24" r="9" fill="#2F86FF" stroke="none"/>
  <circle cx="96" cy="96" r="9" fill="#7252F4" stroke="none"/>
  <circle cx="60" cy="58" r="7" fill="#2F86FF" stroke="none"/>
  <circle cx="48" cy="70" r="5" fill="#DCE4EF" stroke="#2F86FF" stroke-width="3"/>
</g>"""


def svg_document(body: str, width: int, height: int, defs: str = "") -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">\n  <title>NosoGraph connected disease intelligence</title>\n    <defs>\n    <linearGradient id="ng-gradient" x1="0" y1="0" x2="1" y2="1">\n      <stop offset="0" stop-color="{TEAL}"/>\n      <stop offset="0.52" stop-color="{BLUE}"/>\n      <stop offset="1" stop-color="{VIOLET}"/>\n    </linearGradient>{defs}\n  </defs>\n{body}\n</svg>\n'''


def symbol_use(x: int, y: int, size: int) -> str:
    scale = size / 120
    body = SYMBOL_BODY.replace('id="ng-symbol"', "")
    return f'<g transform="translate({x} {y}) scale({scale:g})">{body}</g>'


def write(name: str, content: str) -> None:
    (OUT / name).write_text(content, encoding="utf-8")


def build_assets() -> dict[str, str]:
    symbol = svg_document(SYMBOL_BODY, 120, 120)
    dark_mark = svg_document(
        f'<rect width="120" height="120" rx="28" fill="{NAVY}"/>\n  {symbol_use(0, 0, 120)}',
        120,
        120,
    )
    light_mark = svg_document(
        f'<rect width="120" height="120" rx="28" fill="{WHITE}"/>\n  {symbol_use(0, 0, 120)}',
        120,
        120,
    )
    micro = svg_document(
        '<rect width="120" height="120" rx="28" fill="#08142D"/>\n  <path d="M34 32 V88 M34 32 L86 88" stroke="url(#ng-gradient)" stroke-width="9" stroke-linecap="round"/>\n  <circle cx="34" cy="32" r="11" fill="#19D2C7"/>\n  <circle cx="86" cy="88" r="11" fill="#7252F4"/>',
        120,
        120,
    )
    wordmark = f"""<g>{symbol_use(0, 0, 120)}</g>\n  <text x="148" y="72" font-family="Sora, Inter, Arial, sans-serif" font-size="56" font-weight="650" fill="{{text}}">Noso<tspan fill="url(#ng-gradient)">Graph</tspan></text>"""
    dark_logo = svg_document(
        f'<rect width="760" height="154" rx="22" fill="{NAVY}"/>\n  {wordmark.format(text=WHITE)}\n  <text x="151" y="118" font-family="Inter, Arial, sans-serif" font-size="17" letter-spacing="3.4" fill="{MIST}">DISEASE INTELLIGENCE. <tspan fill="{TEAL}">CONNECTED.</tspan></text>',
        760,
        154,
    )
    light_logo = svg_document(
        f'<rect width="760" height="154" rx="22" fill="{WHITE}"/>\n  {wordmark.format(text=NAVY)}\n  <text x="151" y="118" font-family="Inter, Arial, sans-serif" font-size="17" letter-spacing="3.4" fill="{SLATE}">DISEASE INTELLIGENCE. <tspan fill="{BLUE}">CONNECTED.</tspan></text>',
        760,
        154,
    )
    avatar = svg_document(
        f'<rect width="512" height="512" rx="112" fill="{NAVY}"/>\n  {symbol_use(56, 56, 400)}',
        512,
        512,
    )
    hero = svg_document(
        f'''<rect width="1440" height="560" fill="{NAVY}"/>
  <g opacity=".4" fill="none" stroke="{BLUE}" stroke-width="2">
    <path d="M930 80 C1100 10 1140 220 1390 90"/>
    <path d="M880 420 C1060 190 1170 520 1430 300"/>
    <path d="M1010 520 C1110 300 1270 400 1440 180"/>
  </g>
  <g transform="translate(72 112)">{symbol_use(0, 0, 120)}</g>
  <text x="230" y="190" font-family="Sora, Inter, Arial, sans-serif" font-size="64" font-weight="650" fill="{WHITE}">Noso<tspan fill="url(#ng-gradient)">Graph</tspan></text>
  <text x="234" y="248" font-family="Sora, Inter, Arial, sans-serif" font-size="30" fill="{TEAL}">Disease Intelligence. Connected.</text>
  <text x="234" y="306" font-family="Inter, Arial, sans-serif" font-size="19" fill="{MIST}">Open-source research software for connecting disease knowledge,</text>
  <text x="234" y="338" font-family="Inter, Arial, sans-serif" font-size="19" fill="{MIST}">evidence, and provenance across biomedical sources.</text>
  <text x="234" y="420" font-family="JetBrains Mono, monospace" font-size="14" fill="{SLATE}">DISEASE → CLAIM → EVIDENCE → PROVENANCE → SOURCE</text>''',
        1440,
        560,
    )
    social = svg_document(
        f'''<rect width="1280" height="640" fill="{NAVY}"/>
  <g opacity=".32" fill="none" stroke="{TEAL}" stroke-width="2"><path d="M750 100 C920 250 880 360 1230 180"/><path d="M720 510 C920 300 1080 580 1260 350"/></g>
  <g transform="translate(80 168)">{symbol_use(0, 0, 120)}</g>
  <text x="240" y="236" font-family="Sora, Inter, Arial, sans-serif" font-size="70" font-weight="650" fill="{WHITE}">Noso<tspan fill="url(#ng-gradient)">Graph</tspan></text>
  <text x="244" y="312" font-family="Sora, Inter, Arial, sans-serif" font-size="34" fill="{TEAL}">Disease Intelligence. Connected.</text>
  <text x="244" y="384" font-family="Inter, Arial, sans-serif" font-size="21" fill="{MIST}">Open-source biomedical research software</text>''',
        1280,
        640,
    )
    return {
        "symbol.svg": symbol,
        "mark.svg": dark_mark,
        "mark-light.svg": light_mark,
        "compact.svg": dark_mark,
        "micro.svg": micro,
        "favicon.svg": dark_mark,
        "github-avatar.svg": avatar,
        "logo-dark.svg": dark_logo,
        "logo-light.svg": light_logo,
        "tagline-lockup.svg": dark_logo,
        "hero.svg": hero,
        "social-preview.svg": social,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check expected assets exist")
    args = parser.parse_args()
    assets = build_assets()
    if args.check:
        missing = sorted(name for name in assets if not (OUT / name).exists())
        if missing:
            raise SystemExit("missing generated assets: " + ", ".join(missing))
        print(f"brand assets present ({len(assets)} files)")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for name, content in assets.items():
        write(name, content)
    print(f"generated {len(assets)} NosoGraph brand assets in {OUT}")


if __name__ == "__main__":
    main()
