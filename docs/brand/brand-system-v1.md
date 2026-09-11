# NosoGraph Brand System v1

Status: production candidate on `brand/final-system-v1`.

## Brand premise

NosoGraph makes complex biomedical evidence navigable without hiding uncertainty, provenance, or missingness. The identity therefore uses a connected **N** as both a letterform and a graph: nodes are sources or evidence objects; links are explicit relationships; depth moves from teal through blue to violet.

Canonical public line: **Disease Intelligence. Connected.**

Supporting brand idea: **Dense knowledge, clarified by explicit connections.**

## Identity hierarchy

Use the assets in `docs/assets/brand/system-v1/`.

| Asset | Primary use | Minimum digital size |
|---|---|---:|
| `logo-horizontal-ink.svg` | Main logo on white / very light backgrounds | 160 px wide |
| `logo-horizontal-reversed.svg` | Main logo on Deep Navy / dark backgrounds | 160 px wide |
| `signature-ink.svg` | Formal brand signature with tagline on light backgrounds | 360 px wide |
| `signature-reversed.svg` | Formal brand signature with tagline on dark backgrounds | 360 px wide |
| `symbol-primary.svg` | Product navigation, avatars, compact layouts | 28 px |
| `app-icon-dark.svg` | App / repository / social avatar master on dark tile | 64 px |
| `favicon.svg` | 16–32 px browser and micro surfaces | 16 px |
| `social-card-1200x630.svg` | Open Graph / launch / announcement art | 1200×630 |
| `graph-field-dark.svg` | Background texture for hero and campaign surfaces | crop-safe |
| `brand-board.svg` | Internal reference board | 1600×1000 |

The primary logo intentionally **does not include the tagline**. The tagline belongs to the formal signature, not compact navigation or small product surfaces.

## Clear space and placement

- Keep clear space around the horizontal logo equal to at least **1/4 of the symbol height**.
- Keep clear space around the standalone symbol equal to the diameter of its smallest primary node.
- Never crowd the mark with badges, disclosure copy, UI controls, or another logo.
- Align lockups optically to surrounding text, not mechanically to the outermost node.
- On dark surfaces, prefer Deep Navy `#08142D` rather than true black.

## Color

### Core identity colors

| Token | Hex | Role |
|---|---|---|
| Deep Navy | `#08142D` | Primary dark field, high-contrast ink |
| Navy Layer | `#102246` | Raised dark surface |
| Noso Teal | `#19D2C7` | Connection / first graph anchor |
| Intelligence Blue | `#2F86FF` | Primary interaction and central graph path |
| Graph Violet | `#7252F4` | Depth / terminal graph anchor |
| Cool Slate | `#73819A` | Secondary copy on light surfaces |
| Mist | `#DCE4EF` | Secondary copy on dark surfaces |
| White | `#F8FBFF` | Primary light field / reversed text |

The teal→blue→violet gradient is a **brand signal**, not a semantic status scale. Do not use it to imply good/bad, safe/unsafe, causal/non-causal, or evidence strength.

### Accessibility rules

- Deep Navy on White: ~17.6:1 contrast.
- White on Deep Navy: ~17.6:1.
- Noso Teal is not body text on White; it is a graphic/accent color.
- Intelligence Blue is not normal-size body text on White without an accessible darker treatment.
- Graph Violet is acceptable for normal text on White at roughly AA contrast, but use Deep Navy for long-form reading.
- Mist and Noso Teal are preferred accent/text choices on Deep Navy.
- UI status colors must remain separate from brand colors and meet WCAG contrast requirements in context.

## Typography

- **Sora** — display headings and brand wordmark.
- **Inter** — interface, editorial, research, and explanatory copy.
- **JetBrains Mono** — identifiers, provenance, source metadata, code-like labels, and graph/path notation.

Do not use more than these three families in a branded NosoGraph surface.

## Visual language

Use:
- explicit node-and-link structures;
- restrained graph fields and provenance trails;
- crisp geometry with generous dark negative space;
- research imagery only when it adds information;
- meaningful labels and source context.

Avoid:
- generic hearts, crosses, stethoscopes, ECG lines, DNA-helix clip art, or stock “AI brain” imagery;
- glossy pseudo-clinical gradients;
- decorative network meshes so dense they suggest certainty or causality;
- neon glow as a default treatment;
- graphs without labels, legends, or evidence context when they communicate data.

## Motion

Motion should communicate relationship, not spectacle.

- Edge reveal: 180–320 ms.
- Node focus: 120–180 ms.
- Cross-panel continuity: 220–420 ms.
- Ambient background motion: optional, very slow, and under 4 px apparent travel.
- Respect `prefers-reduced-motion`; all meaning must survive with motion disabled.

## Voice

Brand voice is precise, research-first, transparent about uncertainty, and technically literate.

Prefer: “evidence supports”, “associated with”, “provenance”, “coverage”, “unknown”, “inconclusive”, and “research use”.

Avoid: “proves”, “cures”, “guaranteed”, “AI-powered diagnosis”, or certainty that exceeds the underlying evidence.

## Tagline usage

Canonical tagline: **Disease Intelligence. Connected.**

Use the tagline in launch surfaces, README / repository identity, formal decks, posters, and campaign material. Do not repeat it in every product header.

The separate aspirational line “Trying to help cure the ‘uncurable’” may be developed as a campaign or mission statement, but it should not replace the canonical product tagline until legal/scientific review confirms the claim framing.

## Export and implementation rules

- SVG is the master format.
- Export PNG only for surfaces that cannot consume SVG.
- Preserve transparency for primary horizontal lockups.
- Do not rasterize the wordmark for web use unless required by a host.
- Keep the seven-node symbol geometry canonical; use `favicon.svg` only for the micro tier.
- Do not edit downstream copies by hand. Generate or copy from this system directory.

## Next production set

1. PNG exports at 1×, 2×, and 4× for social/app surfaces.
2. 1280×640 GitHub social preview.
3. LinkedIn/X/Bluesky profile and banner crops.
4. Presentation title/end-slide masters.
5. Paper/poster figure header and conference-poster lockup.
6. Community/forum avatar and anonymous-story card templates.
7. Press/media kit and trademark/attribution guidance.
