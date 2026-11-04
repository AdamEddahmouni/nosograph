# Community experience prototype — static, synthetic, read-only

A local interface sketch of how disease-linked lived-experience posts could be
presented *beside* NosoGraph's evidence model without being part of it.

**This is not a feature. It is a design artefact.** It is not deployed, it has no
backend, it accepts no submissions, and it stores nothing.

## Open it

No build step and no server are required:

```bash
# Windows (Git Bash)
start src/med_research/web/static/community/prototype.html

# macOS / Linux
xdg-open src/med_research/web/static/community/prototype.html   # or: open ...
```

It also renders from the local FastAPI app's static mount when the app is
running, and it degrades to plain fallback colours if `css/tokens.css` is not
reachable.

## Read this before using it

- **Community experience is not scientific evidence.** Every post is a fabricated
  placeholder written for layout testing. None of it is an observation from a
  real person, and none of it can support, contradict, or weight a claim.
- **Privacy architecture has not been assessed.** The page does not collect,
  transmit, or store anything — but that is a property of this static file, not a
  privacy guarantee for a real system.
- **Complete anonymity is not claimed.** Local file access, browser history, and
  any hosting layer that served this file would each record metadata that has not
  been reviewed.
- **Do not paste personal health information here.** The page is not designed to
  receive it and cannot protect it.

## What is here

- `prototype.html` — the page. Self-contained styles; consumes `../css/tokens.css`.
- `prototype.js` — the fixed synthetic fixture list and the static renderer.
- This README.

Design rationale, the moderation-state vocabulary, the verbatim disclosure
intent, and the full list of what a real implementation would still require live
in [`docs/concepts/community-prototype.md`](../../../../../docs/concepts/community-prototype.md).

## What is deliberately absent

No submissions · no persistence · no network calls · no accounts · no moderation
backend · no reporting backend · no email or export · no ingestion of records
from any other system.

`tests/test_community_prototype.py` pins those absences as assertions, so a later
edit cannot quietly add a network call, a storage write, or a submit path to
these files.
