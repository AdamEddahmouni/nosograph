"""Typed option keys shared by pipeline module adapters.

Adapters receive options via ``**opts: Unpack[AdapterOptions]`` so
``opts.get(...)`` inside ``run``/``build_provenance`` is type-checked and
misspelled keys are flagged at the call boundary. The dispatch seams
(CLI/web) still build plain ``dict[str, Any]`` from user input and pass
them through ``**``, which mypy accepts against an unpacked TypedDict.
"""

from __future__ import annotations

from typing import Any, Callable, TypedDict

# Cross-cutting runtime-wired callback; engines accept either progress
# convention (``StandardProgress`` or ``LegacyProgress``), so keep it loose.
ProgressCallback = Callable[..., Any]


class AdapterOptions(TypedDict, total=False):
    """Union of every option key read by any adapter.

    ``total=False`` so any subset may be supplied. Keys are grouped by
    concern; the runtime contract is unchanged — this only gives the
    adapter bodies (and their callers) static types.
    """

    # Caching / persistence.
    use_cache: bool
    save: bool
    cache_or_live: str

    # Queries, sources, and result limits.
    query: str
    queries: list[str]
    question: str
    sources: list[str]
    max: int
    max_results: int
    max_per_query: int
    max_per_source: int
    max_studies: int
    max_articles: int
    top: int
    top_n: int
    top_synergy: int
    expand_neighbors: int

    # Toggles.
    untargeted_only: bool
    targeted: bool
    targeted_candidates: bool
    extract: bool
    extract_content: bool
    resolve_snps: bool
    cross_reference: bool
    use_vina: bool
    comparative: bool
    diff: bool

    # Identifiers and selection.
    gene: str
    gene_id: str
    email: str
    model: str
    metric: str
    operation: str
    tissue: str
    signature_source: str
    candidate_type: str
    confidence: float
    target_genes: list[str]
    compound_library: list[Any]

    # Data objects (loosely typed: engine-specific shapes).
    graph: Any
    llm_client: Any
    request: Any
    scoring: dict[str, Any]
    signature: dict[str, Any]

    # Runtime wiring.
    progress_callback: ProgressCallback | None
