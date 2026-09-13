---
title: FAQ
description: Frequently asked questions about NosoGraph scope, data, citation, and compatibility.
---

# FAQ

**NosoGraph v0.2.1.** Disease Intelligence. Connected. Open-source research software for connecting disease knowledge, evidence, and provenance across biomedical sources.

**Who is it for?** Researchers, developers, students, curators, and institutions evaluating open research software.

**Is NosoGraph medical advice?** No.

**How many disease modules are in the registry?** 10,404 discoverable modules (`Disease.list_all()`) in the current snapshot; 10,406 on-disk directories including two blocked slugs; 10,391 harvest-catalog ids. Public L2=88 and L3=2 are an **n=500 sample**. Registry breadth is not "supported diseases." Counts: [public-status.yaml](../generated/public-status.yaml) and [coverage](../data/coverage.md).

**Are all diseases equally curated?** No. Registry ≠ curation depth.

**Where does the data come from?** Upstream ontologies and databases. [Sources](../data/sources.md).

**Can I use it offline?** CLI and fixture-backed tests can run offline. Live connectors need the network.

**Does it require an LLM?** No. Optional LLM enrichment is experimental.

**Does it use OpenAI?** Only if you set `OPENAI_API_KEY` for optional workflows.

**Can I add a disease?** Yes, via the curation path.

**Can I add a data source?** Propose it with the data-source issue template; integration is a reviewed engineering change.

**Can I use it in academic research?** Yes, with citation and license/data-term compliance.

**How do I cite it?** [Citation](../project/citation.md).

**What license?** Apache-2.0 for code; upstream terms for data.

**Can I deploy it myself?** Yes. See [self-hosted deployment](../deployment.md).

**What is NosoGraph Compare?** A beta workflow for deterministic two-to-five-disease comparisons with explicit missingness, evidence drill-down, and JSON/Markdown exports.

**What is the Evidence Workspace?** A BETA workflow that assembles evidence into claims and ranked hypotheses.

**Why is the Python package still called med-research?** Compatibility. See [package naming](../project/package-naming.md).
