# NosoGraph visual system

The production visual system is generated from one canonical symbol geometry in `scripts/generate_brand_assets.py`. The generated assets use a shared graph mark: teal connections, blue intelligence paths, violet graph depth, and light evidence nodes.

Run:

```bash
python scripts/generate_brand_assets.py
python scripts/generate_brand_assets.py --check
```

| File | Use |
|------|-----|
| `symbol.svg` | Canonical transparent geometry source |
| `mark.svg` | Full-color dark compact mark |
| `mark-light.svg` | Full-color light compact mark |
| `compact.svg` | Compact application mark |
| `micro.svg` / `favicon.svg` | Simplified small-size mark |
| `logo-dark.svg` | Dark-background horizontal lockup |
| `logo-light.svg` | Light-background horizontal lockup |
| `tagline-lockup.svg` | Canonical tagline lockup |
| `github-avatar.svg` | GitHub/avatar-size mark |
| `hero.svg` | README and public visual treatment |
| `social-preview.svg` | Canonical GitHub/OG source treatment |
| `social-preview.png` | 1280×640 GitHub and social-metadata export |

The detailed mark is not blindly shrunk for micro sizes. All variants intentionally derive from the same anchor geometry, with secondary edges removed only where needed for legibility. The gradient is a signature asset, not a general-purpose status or interaction color.
