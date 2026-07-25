"""Evidence Gatherer service layer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from med_research.pipeline.evidence.gatherer import gather_evidence


def run_evidence_gather(
    query: str,
    sources: list = None,
    max_per_source: int = 20,
    use_cache: bool = True,
) -> dict:
    """Run the evidence gatherer and return structured results."""
    return gather_evidence(
        query=query,
        sources=sources,
        max_per_source=max_per_source,
        use_cache=use_cache,
    )
