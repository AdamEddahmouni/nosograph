"""Semantic Literature Search — Embedding-based PubMed search."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from med_research.pipeline.semantic_search.engine import SemanticSearchEngine


def __getattr__(name: str):
    if name == "SemanticSearchEngine":
        from med_research.pipeline.semantic_search.engine import SemanticSearchEngine

        return SemanticSearchEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["SemanticSearchEngine"]
