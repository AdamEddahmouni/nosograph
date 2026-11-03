---
title: Community experience prototype
description: A static, synthetic, read-only prototype of a disease-linked lived-experience surface — and why it is deliberately kept outside NosoGraph's evidence model.
---

# Community experience prototype

!!! warning "This is a static prototype, not a product surface"

    The prototype is a single local HTML file with a fixed fixture list. It is not
    deployed, it has no backend, it accepts no submissions, and it stores nothing.
    Every post in it is fabricated for layout testing.

    **Community experience is not scientific evidence.** Nothing on that page is
    part of the claim or evidence model, and no post there may be read as
    supporting or contradicting a biomedical association.

## Why it exists

NosoGraph's evidence model is deliberately narrow: typed claims, evidence
direction, provenance, and explicit missingness (`NOT_RECORDED` ≠
`KNOWN_ABSENT`). See [Evidence](../architecture/evidence-model.md) and
[Claims](claims.md).

People also describe their own experience of a condition, and readers of a
research tool may reasonably expect somewhere for that material to live. The
prototype explores the *interface and safety shape* of such a place without
making any scientific claim about it and without shipping a community feature.

The design intent is separation, not fusion:

```text
evidence surface   ── typed claims, evidence direction, provenance   (research)
experience surface ── narrative, unverified, clearly labelled         (not research)
```

There is no join key between the two, by design. A prototype post cannot be
cited as evidence for a claim, and no claim can be "supported" by a post.

## Files

| Path | Role |
| --- | --- |
| `src/med_research/web/static/community/prototype.html` | Self-contained page, styles inline, consumes `css/tokens.css` |
| `src/med_research/web/static/community/prototype.js` | Fixed synthetic fixture list and static rendering |
| `src/med_research/web/static/community/README.md` | How to open it locally and what it is not |
| `tests/test_community_prototype.py` | Static, file-content assertions that pin the safety invariants |

Open `prototype.html` directly in a browser, or serve it from the local FastAPI
app's static mount. No build step, no dependencies, no configuration.

## What is implemented

1. **Disease-linked views.** Three fixture slugs (`sle`, `ra`, `t1d`) filter a
   fixed in-file list. The labels are abbreviation expansions only; they are not
   curated registry metadata and carry no curation tier.
2. **Synthetic example posts.** Eight posts. Each carries `synthetic: true` and
   `content_origin: "fabricated_placeholder"` as data, and renders a visible
   `Synthetic example` badge. The renderer fails closed: a post whose
   `synthetic` flag is not literally `true` is not rendered at all.
3. **Moderation states.** `pending_review`, `published`, and
   `hidden_insufficient_context` are rendered as the verbatim state token plus a
   plain-language gloss, plus a distinct glyph and border style per state. No
   state is conveyed by colour alone.
4. **Reporting control.** A non-submitting button that toggles an in-memory,
   per-tab flag and announces the outcome through a live region. It sends
   nothing and survives no reload.
5. **Privacy and consent disclosure.** A first-panel notice written in plain
   language, with no consent capture, because there is nothing to consent to.
6. **Accessible controls.** Visible labels, keyboard-operable selects, a
   `:focus-visible` ring on every interactive element, a skip link, and two
   `role="status"` live regions (result count, report state).
7. **Mobile-first layout.** Single column by default, fixed reading measure,
   no horizontal scrolling, 44px minimum tap targets.
8. **Separation from evidence.** A persistent sticky banner, an inline
   disclaimer in the page body, and a footer note.

## What is deliberately not implemented

- No submissions, no compose box, no drafts.
- No persistence of any kind — no storage API, no cookies, no client database.
- No network calls of any kind.
- No accounts, identity, or pseudonymity mechanism.
- No moderation queue, no reporting backend, no reviewer tooling.
- No notification, email, or export path.
- No ingestion of records from any other system.

## Moderation-state design notes

The states are modelled as an explicit, closed vocabulary rather than a boolean
"visible" flag, because "not shown" conflates two very different situations:

| State | Meaning | Reader-facing treatment |
| --- | --- | --- |
| `published` | Shown as-is in this prototype | Solid border, filled glyph, state token + gloss |
| `pending_review` | Not yet assessed against any policy | Dashed border, half-filled glyph, state token + gloss |
| `hidden_insufficient_context` | Withheld because required context is missing | Dotted border, barred glyph, italic body, state token + gloss |

`hidden_insufficient_context` is intentionally *not* called "removed" or
"rejected". A missing-context withholding is a curation gap, not a finding about
the person or the content. Keeping that distinction visible matters for the same
reason `NOT_RECORDED` and `KNOWN_ABSENT` are kept distinct in the evidence
model: absence of curation is not evidence of absence.

In this prototype, withheld posts remain visible to the reader so the state is
inspectable rather than silent. A real deployment would show them only to the
author and to moderators, and that policy does not exist yet.

## Privacy and consent disclosure (verbatim intent)

The prototype's first panel states, in substance:

- Privacy architecture has not been assessed.
- The page does not collect, transmit, or store anything.
- Complete anonymity is not claimed or verified.
- Local file access, browser history, and any hosting layer that served the file
  would each record metadata that has not been reviewed.
- Personal health information must not be pasted into the page, because the page
  is not designed to receive it and cannot protect it.
- Real submissions, moderation, reporting, and retention are unimplemented.

### On anonymity

**NosoGraph has not assessed the privacy architecture required for anonymous
posting, and this prototype must not be described as anonymous.** "Anonymous" is
a claim about an adversary model. No such model exists here. Specifically
unaddressed:

- **Network metadata.** Any hosting layer observes source addresses, request
  timing, and user agents. No proxy, mixnet, or log-suppression design exists.
- **Client metadata.** Browser history, cached files, and local file paths are
  outside this page's control.
- **Content-level re-identification.** Free-text narratives routinely identify
  their author through detail, chronology, or rarity. No scrubbing or
  generalisation design exists.
- **Pseudonymity and linkage.** No identity or pseudonym system exists, so there
  is nothing to unlink and nothing to rotate.
- **Moderation exposure.** Moderators read content. Their access, logging, and
  retention are undefined.
- **Legal exposure.** Jurisdiction, lawful-access handling, and takedown
  procedure are undefined.

Describing this surface as anonymous before those are designed and reviewed
would be a false assurance to a vulnerable population. The correct description
is: *not collected, not transmitted, not persisted, and not assessed.*

## What a real implementation would require

Before any public deployment, at minimum:

1. **Threat model** covering re-identification, network metadata, moderation
   insiders, and lawful access.
2. **Data-retention and deletion policy**, with a working deletion path and a
   stated maximum retention period.
3. **Consent and terms** that a person can actually understand, recording scope,
   purpose, and revocation — and a mechanism to honour revocation.
4. **Moderation duty-of-care plan**: escalation for crisis content, reviewer
   wellbeing, appeals, and transparent outcome reporting.
5. **Safety response path** for posts describing imminent harm, with a clear
   statement of what the system does and does not do.
6. **Abuse handling**: rate limiting, spam and brigading defence, and a
   reporting backend that this prototype does not have.
7. **Independent privacy and security review**, published in outline.
8. **Accessibility conformance audit** against WCAG 2.2 AA on the real surface,
   not only the static sketch.
9. **Explicit product decision** and owner authorization to run a community
   surface at all, since it commits the project to ongoing moderation labour.
10. **A visible, permanent separation** from evidence surfaces — the banner in
    this prototype is the minimum, not the finished design.

Until those exist, the honest status of this work is: **interface sketch,
synthetic data, no submissions, not assessed.**
