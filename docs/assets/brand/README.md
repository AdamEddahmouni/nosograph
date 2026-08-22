# NosoGraph visual system

The production visual system is generated from one canonical symbol geometry in `scripts/generate_brand_assets.py`. The seven-node mark is constructed as an **N** and a connected evidence graph: four primary anchors represent evidence sources, while three secondary nodes and their links express normalization, connection, and provenance. Teal denotes connection, blue denotes intelligence paths, and violet denotes graph depth.

Run:

```bash
python scripts/generate_brand_assets.py
python scripts/generate_brand_assets.py --check
```

| File | Use |
|------|-----|
| `symbol.svg` | Canonical transparent geometry source |
| `symbol-mono-dark.svg` / `symbol-reversed.svg` | Single-color symbol variants |
| `mark.svg` | Full-color dark compact mark |
| `mark-light.svg` | Full-color light compact mark |
| `compact.svg` | Compact application mark |
| `micro.svg` / `favicon.svg` | Simplified small-size mark |
| `logo-dark.svg` | Dark-background horizontal lockup |
| `logo-light.svg` | Light-background horizontal lockup |
| `logo-mono-dark.svg` / `logo-reversed.svg` | Monochrome and reversed horizontal lockups |
| `tagline-lockup.svg` | Canonical tagline lockup |
| `github-avatar.svg` | GitHub/avatar-size mark |
| `hero.svg` | README and public visual treatment |
| `social-preview.svg` | Canonical GitHub/OG source treatment |
| `social-preview.png` | 1280×640 GitHub and social-metadata export |

Dashboard copies of the core symbol, icon, favicon, and dark logo are generated into `src/med_research/web/static/brand/` from the same source.

## Usage rules

- Keep clear space around a lockup equal to at least the diameter of its smallest primary node.
- Use full color on Deep Navy or White. Use the monochrome asset where reproduction cannot preserve the palette, and the reversed asset on dark photography or flat dark surfaces.
- Never redraw, rotate, skew, recolor individual edges, add effects, or place the symbol inside another decorative badge.
- Do not use the detailed mark below 32 px. Use `micro.svg` or `favicon.svg` at small sizes.
- Keep **NosoGraph** as one word with a capital **N** and **G**. The canonical tagline is **Disease Intelligence. Connected.**
- Reserve the teal–blue–violet gradient for the mark, the **Graph** portion of the wordmark, and rare graph moments. It is not a status palette.

The wordmark uses Sora at a light regular weight. Body/UI copy uses Inter; technical and data labels use JetBrains Mono. Local font files are bundled so public surfaces do not depend on runtime font requests.
