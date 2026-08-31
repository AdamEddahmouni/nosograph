# Bundled web fonts

NosoGraph bundles the three font families used by the public documentation site so pages do not depend on a runtime Google Fonts request. Each family is represented by one variable font file; the CSS exposes only the weight ranges used by the design system.

## Files

| Family | Local file | Format | CSS weight range | License |
|---|---|---|---:|---|
| Sora | `Sora-Variable.woff2` | WOFF2 variable | 100–800 | SIL Open Font License 1.1 |
| Inter | `InterVariable.woff2` | WOFF2 variable | 100–900 | SIL Open Font License 1.1 |
| JetBrains Mono | `JetBrainsMono-Variable.woff2` | WOFF2 variable | 100–800 | SIL Open Font License 1.1 |

All three sources are pinned to upstream repository commits rather than floating branch URLs. The complete license text is in [`OFL-1.1.txt`](OFL-1.1.txt), with copyright and source attribution in [`manifest.json`](manifest.json).

## Updating the bundle

1. Download a replacement from the authoritative source.
2. Update the source reference and SHA-256 value in `manifest.json`.
3. Run:

   ```bash
   python scripts/check_public_fonts.py
   ```

4. Confirm that `docs/stylesheets/base.css` still declares the matching local file and that no external font stylesheet or font URL has been introduced.

Do not add a font file without recording its license and source. Do not replace these local files with a runtime `fonts.googleapis.com` dependency.
