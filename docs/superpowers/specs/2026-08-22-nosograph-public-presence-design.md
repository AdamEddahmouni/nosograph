# NosoGraph Public Presence Design

**Status:** Approved for execution  
**Date:** 2026-08-22

## Goal

Make GitHub Pages the NosoGraph product/public front door and the GitHub README the repository/developer front door, using one evidence-first identity: **Disease Intelligence. Connected.**

## Public story

NosoGraph is open-source research software for connecting disease knowledge, evidence, and provenance across biomedical sources. The public alpha must communicate what exists today, what is experimental or planned, and what the software does not claim.

The conceptual backbone is:

```text
fragmented biomedical evidence
        ↓
structured claims + relationships
        ↓
evidence + provenance
        ↓
connected disease intelligence
        ↓
researcher inspection / developer extension
```

Supporting claims are not automatic proof, associations are not causation, contradictory evidence may coexist, and missing metadata remains unknown rather than silently becoming certainty.

## Visual system

- Deep Navy `#08142D`
- Navy Layer `#102246`
- Noso Teal `#19D2C7`
- Intelligence Blue `#2F86FF`
- Graph Violet `#7252F4`
- Cool Slate `#73819A`
- Mist Gray `#DCE4EF`
- White `#F8FBFF`

Semantic use: teal for connections/evidence relationships, blue for navigation and primary interaction, violet for graph depth/secondary relationships, dark navy for the product world, and mist/white for readable research surfaces. Flat colors must remain meaningful without gradients. The teal-blue-violet gradient is reserved for the canonical symbol, selected wordmark treatments, and key graph moments.

Typography uses Sora for display/brand moments, Inter for body/UI, and JetBrains Mono for technical/data contexts, with robust system fallbacks and no runtime Google Fonts dependency.

## Asset architecture

`scripts/generate_brand_assets.py` is the authoritative geometry source for the primary N mark. It produces standalone SVG assets: canonical symbol, compact/micro marks, horizontal wordmarks, tagline lockup, full-color/monochrome/reversed variants, favicon, avatar, hero, and social/OG treatment. Small variants simplify the topology intentionally but derive from the same anchor geometry.

## Homepage

The Pages homepage keeps MkDocs navigation, search, deep links, and responsive documentation behavior. It presents:

1. Hero with the canonical identity, primary documentation CTA, local-run CTA, GitHub CTA, and a labeled NosoGraph-specific evidence graph.
2. Researcher/developer orientation with real documentation destinations.
3. Fragmented-source problem statement.
4. Source → normalization → claim → evidence → provenance transformation.
5. Evidence traceability demonstration, including supporting/contradictory/inconclusive directions and unknown metadata semantics.
6. Researcher workflow: explore disease → inspect claims → inspect evidence → trace provenance → compare.
7. Developer workflow: understand architecture → run locally → inspect API/data model → extend → validate → contribute.
8. Current capability/maturity table and dated repository snapshot from `docs/generated/public-status.yaml`.
9. Scientific/technical credibility based on provenance, source transparency, deterministic extraction, conservative quality semantics, validation, and reproducibility.
10. Documentation index, open-source CTA, and restrained footer.

No hosted application is implied: the public hosted demo is planned and not deployed.

## README

README remains concise and operational. It uses the new lockup and positioning, a small visual treatment, verified release/status badges, quick start, evidence/provenance model, researcher/developer routes, architecture, maturity limitations, documentation, contribution, citation, license, and research-use boundary. It must not include invented project metrics or duplicate every homepage section.

## Consistency and QA

Current public facts are owned by `docs/generated/public-status.yaml`; public pages link to that source and the metadata check validates current-version surfaces. Historical release/audit references remain historical. MkDocs inner pages retain light reading surfaces, code-block usability, search, TOC, responsive layout, keyboard behavior, and accessible focus states.

The graph has a static SVG meaning and a progressive enhancement layer for focus/hover/path highlighting. It is labeled as illustrative when it is not a live query and has a text fallback. Motion is disabled or minimized under `prefers-reduced-motion`.
