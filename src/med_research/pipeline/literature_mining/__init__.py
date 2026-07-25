"""
Lupus Literature Mining Engine

Searches PubMed for SLE-related articles, extracts named entities
(genes, drugs, pathways) using dictionary-based matching against
the Lupus Knowledge Graph, and cross-references findings against
drug repurposing candidates.

Usage:
    python -m literature_mining.miner              # Full pipeline
    python -m literature_mining.miner --max 50      # Limit to 50 articles
    python -m literature_mining.miner --query "BTK lupus"  # Custom query
"""
