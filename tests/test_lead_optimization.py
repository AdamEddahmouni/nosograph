import pandas as pd
import pytest

from med_research.pipeline.lead_opt.pipeline import process_dataframe, run_batch_analysis
from med_research.pipeline.lead_opt.utils import parse_smiles_text


@pytest.mark.unit
def test_lead_optimization_batch_analysis():
    smiles_list = ["CCO", "c1ccccc1O", "CC(=O)Oc1ccccc1C(=O)O", "invalid_smiles_string"]
    df = run_batch_analysis(smiles_list)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 4
    assert "smiles" in df.columns
    assert "mw" in df.columns
    assert "logp" in df.columns
    assert "lipinski_pass" in df.columns
    assert "bbb_pass" in df.columns
    assert "herg_risk" in df.columns

    # Check valid molecules have non-null properties
    ethanol_row = df[df["smiles"] == "CCO"].iloc[0]
    assert bool(ethanol_row["lipinski_pass"])
    assert ethanol_row["mw"] < 100


@pytest.mark.unit
def test_process_dataframe_and_utils():
    text = "CCO\nc1ccccc1O"
    parsed_df = parse_smiles_text(text)
    assert len(parsed_df) == 2
    res_df = process_dataframe(parsed_df)
    assert len(res_df) == 2
    assert "lipinski_pass" in res_df.columns
