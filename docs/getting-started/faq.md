---
title: FAQ
description: Frequently asked questions about NosoGraph scope, data, citation, and compatibility.
---

# FAQ

**What is NosoGraph?** An open computational map of human disease: software that connects diseases to biomedical knowledge while preserving evidence.

**Who is it for?** Researchers, developers, students, curators, and institutions evaluating open research software.

**Is NosoGraph medical advice?** No.

**How many diseases does it support?** 10,407 registry modules in v2.4.0; 88 pass strict L2 validation. Counts: [public-status.yaml](../generated/public-status.yaml).

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

**Can I deploy it myself?** Yes. [Deployment](../developers/deployment.md).

**What is NosoGraph Compare?** An experimental multidimensional comparison slice.

**What is the Evidence Workspace?** A BETA workflow that assembles evidence into claims and ranked hypotheses.

**Why is the Python package still called med-research?** Compatibility. See [package naming](../project/package-naming.md).
