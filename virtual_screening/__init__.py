"""
Lupus Virtual Drug Screening Engine

Computationally screens compound libraries against lupus protein targets
using molecular property scoring, similarity analysis, and optional
molecular docking (AutoDock Vina).

Usage:
    python -m virtual_screening.screening                 # Full pipeline
    python -m virtual_screening.screening --top 15         # Top 15 compounds per target
    python -m virtual_screening.screening --gene BTK       # Screen against BTK only
    python -m virtual_screening.screening --export-html    # Generate HTML report
"""
