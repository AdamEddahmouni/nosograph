"""
Tests for the Drug Combination Synergy Prediction module."""

import json
import sys
from pathlib import Path

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from med_research.pipeline.drug_synergy.engine import (
    compute_synergy,
    get_mechanism_group,
    score_combined_evidence,
    score_drug_pair,
    score_drug_pairs,
    score_mechanism_orthogonality,
    score_pathway_diversity,
    score_safety_non_overlap,
    score_target_complementarity,
)
from med_research.pipeline.drug_synergy.report import escape_html, generate_html_report

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def sample_drug_a():
    return {
        "id": "belimumab",
        "name": "Belimumab (Benlysta)",
        "type": "Monoclonal Antibody",
        "target": "BAFF (BLyS)",
        "mechanism": "Binds and neutralizes soluble BAFF",
        "category": "Biologic - B Cell Modulation",
        "approval": "FDA approved 2011 (SLE), 2020 (lupus nephritis)",
        "route": "IV infusion",
    }


@pytest.fixture(scope="module")
def sample_drug_b():
    return {
        "id": "deucravacitinib",
        "name": "Deucravacitinib (Sotyktu)",
        "type": "Small Molecule",
        "target": "TYK2",
        "mechanism": "Highly selective allosteric TYK2 inhibitor",
        "category": "Targeted Synthetic - TYK2 Inhibitor",
        "approval": "FDA approved 2022 (plaque psoriasis); Phase 2 in SLE",
        "route": "Oral, once daily",
    }


@pytest.fixture(scope="module")
def sample_drug_c():
    return {
        "id": "hydroxychloroquine",
        "name": "Hydroxychloroquine (Plaquenil)",
        "type": "Small Molecule",
        "target": "TLR7/TLR9 endosomal signaling",
        "mechanism": "Inhibits endosomal acidification",
        "category": "Immunomodulator - Antimalarial",
        "approval": "Standard of care for all SLE patients",
        "route": "Oral, daily",
    }


@pytest.fixture(scope="module")
def sample_drug_same_target():
    return {
        "id": "rituximab",
        "name": "Rituximab (Rituxan)",
        "type": "Monoclonal Antibody",
        "target": "CD20",
        "mechanism": "Depletes CD20+ B cells",
        "category": "Biologic - B Cell Depletion",
        "approval": "Off-label for refractory SLE",
        "route": "IV infusion",
    }


@pytest.fixture(scope="module")
def sample_drug_same_target2():
    return {
        "id": "obinutuzumab",
        "name": "Obinutuzumab (Gazyva)",
        "type": "Monoclonal Antibody",
        "target": "CD20",
        "mechanism": "Type II anti-CD20 antibody",
        "category": "Biologic - B Cell Depletion (Next-Gen)",
        "approval": "Phase 3 in lupus nephritis",
        "route": "IV infusion",
    }


# ── Unit: Mechanism Groups ────────────────────────────────────────────────


def test_mechanism_group_biologic():
    drug = {"type": "Monoclonal Antibody", "category": "Biologic - B Cell Modulation"}
    assert get_mechanism_group(drug) == "B Cell"


def test_mechanism_group_small_molecule():
    drug = {"type": "Small Molecule", "category": "Targeted Synthetic - BTK Inhibitor"}
    assert get_mechanism_group(drug) == "BTK"


def test_mechanism_group_unknown():
    drug = {"type": "UnknownType", "category": "Unknown"}
    assert get_mechanism_group(drug) == "UnknownType"


# ── Unit: Target Complementarity ──────────────────────────────────────────


def test_target_complementarity_different_targets(sample_drug_a, sample_drug_b):
    score = score_target_complementarity(sample_drug_a, sample_drug_b)
    assert 8.0 <= score <= 10.0


def test_target_complementarity_same_target(sample_drug_same_target, sample_drug_same_target2):
    drug_a_copy = dict(sample_drug_same_target)
    drug_a_copy["id"] = "rituximab"
    drug_b_copy = dict(sample_drug_same_target2)
    drug_b_copy["target"] = "CD20"
    drug_a_copy["target"] = "CD20"
    assert drug_a_copy["target"].lower() == drug_b_copy["target"].lower()
    score = score_target_complementarity(drug_a_copy, drug_b_copy)
    assert score == 2.0


def test_target_complementarity_same_group_different_target():
    """Both are B Cell biologics but with different targets."""
    drug_a = {"id": "rituximab", "type": "Monoclonal Antibody", "target": "CD20", "category": "Biologic - B Cell Depletion"}
    drug_b = {"id": "belimumab", "type": "Monoclonal Antibody", "target": "BAFF (BLyS)", "category": "Biologic - B Cell Modulation"}
    score = score_target_complementarity(drug_a, drug_b)
    assert score == 6.0


def test_target_complementarity_return_range(sample_drug_a, sample_drug_b):
    score = score_target_complementarity(sample_drug_a, sample_drug_b)
    assert 0.0 <= score <= 10.0


# ── Unit: Pathway Diversity ───────────────────────────────────────────────


def test_pathway_diversity_different_mechanisms(sample_drug_a, sample_drug_b):
    score = score_pathway_diversity(sample_drug_a, sample_drug_b)
    assert score >= 8.0


def test_pathway_diversity_same_group(sample_drug_same_target, sample_drug_same_target2):
    score = score_pathway_diversity(sample_drug_same_target, sample_drug_same_target2)
    assert score <= 5.0


def test_pathway_diversity_return_range(sample_drug_a, sample_drug_b):
    score = score_pathway_diversity(sample_drug_a, sample_drug_b)
    assert 0.0 <= score <= 10.0


# ── Unit: Mechanism Orthogonality ─────────────────────────────────────────


def test_mechanism_orthogonality_different(sample_drug_a, sample_drug_b):
    score = score_mechanism_orthogonality(sample_drug_a, sample_drug_b)
    assert score >= 5.0


def test_mechanism_orthogonality_same_group(sample_drug_same_target, sample_drug_same_target2):
    score = score_mechanism_orthogonality(sample_drug_same_target, sample_drug_same_target2)
    assert score == 2.0


def test_mechanism_orthogonality_return_range(sample_drug_a, sample_drug_b):
    score = score_mechanism_orthogonality(sample_drug_a, sample_drug_b)
    assert 0.0 <= score <= 10.0


# ── Unit: Safety Non-overlap ──────────────────────────────────────────────


def test_safety_non_overlap_different(sample_drug_a, sample_drug_b):
    score = score_safety_non_overlap(sample_drug_a, sample_drug_b)
    assert score >= 5.0


def test_safety_non_overlap_same_group(sample_drug_same_target, sample_drug_same_target2):
    score = score_safety_non_overlap(sample_drug_same_target, sample_drug_same_target2)
    assert score <= 5.0


def test_safety_non_overlap_return_range(sample_drug_a, sample_drug_b):
    score = score_safety_non_overlap(sample_drug_a, sample_drug_b)
    assert 0.0 <= score <= 10.0


# ── Unit: Combined Evidence ───────────────────────────────────────────────


def test_combined_evidence_known_combination():
    drug_a = {"id": "belimumab", "name": "Belimumab", "approval": "FDA approved 2011 (SLE)"}
    drug_b = {"id": "rituximab", "name": "Rituximab", "approval": "Off-label for SLE"}
    score = score_combined_evidence(drug_a, drug_b)
    assert score >= 7.0


def test_combined_evidence_reverse_order():
    drug_a = {"id": "rituximab", "name": "Rituximab", "approval": "Off-label for SLE"}
    drug_b = {"id": "belimumab", "name": "Belimumab", "approval": "FDA approved 2011 (SLE)"}
    score = score_combined_evidence(drug_a, drug_b)
    assert score >= 7.0


def test_combined_evidence_both_lupus():
    drug_a = {"id": "baricitinib", "name": "Bari", "approval": "Phase 3 trials in SLE"}
    drug_b = {"id": "deucravacitinib", "name": "Deucra", "approval": "Phase 2 in SLE"}
    score = score_combined_evidence(drug_a, drug_b)
    assert score >= 4.0


def test_combined_evidence_no_evidence():
    drug_a = {"id": "unknown1", "name": "Unknown1", "approval": "Not approved"}
    drug_b = {"id": "unknown2", "name": "Unknown2", "approval": "Not approved"}
    score = score_combined_evidence(drug_a, drug_b)
    assert score == 1.0


# ── Unit: Full Pair Scoring ───────────────────────────────────────────────


def test_score_drug_pair_returns_all_dimensions(sample_drug_a, sample_drug_b):
    result = score_drug_pair(sample_drug_a, sample_drug_b)
    assert "composite_score" in result
    assert "target_complementarity" in result
    assert "pathway_diversity" in result
    assert "mechanism_orthogonality" in result
    assert "safety_non_overlap" in result
    assert "combined_evidence" in result
    assert "tier" not in result  # tier is assigned by score_drug_pairs


def test_score_drug_pair_score_range(sample_drug_a, sample_drug_b):
    result = score_drug_pair(sample_drug_a, sample_drug_b)
    assert 0.0 <= result["composite_score"] <= 10.0


def test_score_drug_pair_includes_metadata(sample_drug_a, sample_drug_b):
    result = score_drug_pair(sample_drug_a, sample_drug_b)
    assert result["drug_a_id"] == "belimumab"
    assert result["drug_b_id"] == "deucravacitinib"
    assert result["drug_a_type"] == "Monoclonal Antibody"
    assert result["drug_b_type"] == "Small Molecule"


# ── Unit: Batch Pair Scoring ──────────────────────────────────────────────


def test_score_drug_pairs_sorted_by_score():
    drugs = {
        "deucravacitinib": {
            "id": "deucravacitinib",
            "name": "Deucravacitinib",
            "type": "Small Molecule",
            "target": "TYK2",
            "category": "Targeted Synthetic - TYK2 Inhibitor",
            "mechanism": "TYK2 inhibitor",
            "approval": "Phase 2 in SLE",
        },
        "rituximab": {
            "id": "rituximab",
            "name": "Rituximab",
            "type": "Monoclonal Antibody",
            "target": "CD20",
            "category": "Biologic - B Cell Depletion",
            "mechanism": "Depletes B cells",
            "approval": "Off-label for SLE",
        },
        "belimumab": {
            "id": "belimumab",
            "name": "Belimumab",
            "type": "Monoclonal Antibody",
            "target": "BAFF (BLyS)",
            "category": "Biologic - B Cell Modulation",
            "mechanism": "Neutralizes BAFF",
            "approval": "FDA approved 2011 (SLE)",
        },
    }
    pairs = score_drug_pairs(drugs)
    assert len(pairs) == 3  # 3 choose 2 = 3
    assert pairs[0]["composite_score"] >= pairs[-1]["composite_score"]
    # All should have tiers
    for p in pairs:
        assert "tier" in p


def test_score_drug_pairs_empty():
    pairs = score_drug_pairs({})
    assert pairs == []


def test_score_drug_pairs_single_drug():
    drugs = {
        "belimumab": {
            "id": "belimumab",
            "name": "Belimumab",
            "type": "Monoclonal Antibody",
            "target": "BAFF",
            "category": "Biologic",
            "mechanism": "Neutralizes BAFF",
            "approval": "FDA approved",
        },
    }
    pairs = score_drug_pairs(drugs)
    assert pairs == []


# ── Integration: compute_synergy ──────────────────────────────────────────


@pytest.mark.slow
def test_compute_synergy_loads_drugs():
    """Verify compute_synergy loads drugs from the KG and scores all pairs."""
    pairs = compute_synergy()
    assert len(pairs) > 0
    # With 26 drugs, there should be 325 unique pairs
    assert len(pairs) == 325


@pytest.mark.slow
def test_compute_synergy_ranked():
    pairs = compute_synergy()
    # Pairs should be sorted by composite score descending
    for i in range(len(pairs) - 1):
        assert pairs[i]["composite_score"] >= pairs[i + 1]["composite_score"]


@pytest.mark.slow
def test_compute_synergy_saves_json(tmp_path, monkeypatch):
    """Verify that compute_synergy saves results to JSON."""
    monkeypatch.setattr(
        "drug_synergy.engine.DATA_DIR",
        tmp_path,
    )
    pairs = compute_synergy()
    json_path = tmp_path / "synergy_results.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert data["total_pairs"] == len(pairs)


@pytest.mark.slow
def test_compute_synergy_all_dimensions():
    pairs = compute_synergy()
    for p in pairs[:10]:
        assert 0.0 <= p["target_complementarity"] <= 10.0
        assert 0.0 <= p["pathway_diversity"] <= 10.0
        assert 0.0 <= p["mechanism_orthogonality"] <= 10.0
        assert 0.0 <= p["safety_non_overlap"] <= 10.0
        assert 0.0 <= p["combined_evidence"] <= 10.0
        assert 0.0 <= p["composite_score"] <= 10.0
        assert "tier" in p


# ── Report Generation ─────────────────────────────────────────────────────


def test_escape_html():
    assert escape_html("<script>alert('xss')</script>") == "&lt;script&gt;alert('xss')&lt;/script&gt;"
    assert escape_html("A & B") == "A &amp; B"
    assert escape_html('quote"test') == "quote&quot;test"
    assert escape_html(None) == ""
    assert escape_html("") == ""


def test_generate_html_report_creates_file(tmp_path, monkeypatch):
    """Verify report generation works with a small subset of pairs."""
    pairs = compute_synergy()
    result = generate_html_report(pairs[:5])
    assert "report.html" in result
    from pathlib import Path
    assert Path(result).exists()


def test_generate_html_report_with_empty_pairs():
    result = generate_html_report([])
    assert "report.html" in result
    with open(result, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Drug Combination Synergy Report" in content
    assert "0 Drug Pairs" in content


# ── API Service ───────────────────────────────────────────────────────────


@pytest.mark.slow
def test_run_synergy_service():
    from med_research.web.services.synergy_service import run_synergy

    result = run_synergy(top_n=10)
    assert result["total_pairs"] == 325
    assert len(result["pairs"]) == 10
    assert "tier1_count" in result
    assert "tier2_count" in result
    assert "avg_score" in result
    assert "max_score" in result


# ── CLI Integration ───────────────────────────────────────────────────────


@pytest.mark.slow
def test_synergy_cli_help():
    import subprocess

    result = subprocess.run(
        [sys.executable, "main.py", "synergy", "--help"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0
    assert "Predict synergistic drug combinations" in result.stdout


@pytest.mark.slow
def test_synergy_cli_top():
    import subprocess

    result = subprocess.run(
        [sys.executable, "main.py", "synergy", "--top", "5"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
        timeout=30,
    )
    assert result.returncode == 0
    assert "TOP 5 SYNERGISTIC" in result.stdout
    assert "DRUG SYNERGY ANALYSIS SUMMARY" in result.stdout
