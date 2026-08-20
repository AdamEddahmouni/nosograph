"""Utility functions for Lead Optimization file parsing and serialization."""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

import pandas as pd


def parse_csv(content: str) -> pd.DataFrame:
    """Parse CSV text into a pandas DataFrame."""
    return pd.read_csv(io.StringIO(content))


def parse_json(content: str) -> pd.DataFrame:
    """Parse JSON string into a pandas DataFrame."""
    data = json.loads(content)
    if isinstance(data, list):
        return pd.DataFrame(data)
    elif isinstance(data, dict):
        if "smiles" in data and isinstance(data["smiles"], list):
            return pd.DataFrame({"smiles": data["smiles"]})
        return pd.DataFrame([data])
    return pd.DataFrame()


def parse_smiles_text(text: str) -> pd.DataFrame:
    """Parse raw newline/comma-separated SMILES into a DataFrame."""
    lines = [line.strip() for line in text.replace(",", "\n").splitlines() if line.strip()]
    return pd.DataFrame({"smiles": lines})


def save_result_csv(df: pd.DataFrame, job_id: str) -> str:
    """Save result DataFrame to temporary CSV file and return the path."""
    tmp_dir = Path(tempfile.gettempdir()) / "lead_opt_results"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / f"result_{job_id}.csv"
    df.to_csv(out_path, index=False)
    return str(out_path)
