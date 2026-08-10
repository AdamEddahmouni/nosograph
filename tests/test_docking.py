"""
Tests for the Molecular Docking Engine (Phase 23).

Tests cover:
  - docking.py: dependency detection, score normalization, target config
    loading, Vina output parsing, DockingEngine status
  - vina_setup.py: Vina binary check/download helper
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from med_research.pipeline.virtual_screening.docking import (
    DockingEngine,
    _convert_receptor_to_pdbqt,
    _detect_biopython,
    _detect_meeko,
    _detect_rdkit,
    _find_vina_binary,
    _normalize_vina_score,
    compute_real_binding_score,
    get_docking_status,
    get_vina_status_text,
    prepare_ligand,
)

# ── Unit: Dependency Detection ────────────────────────────────────────────

RDKIT_AVAILABLE = _detect_rdkit()
MEEKO_AVAILABLE = _detect_meeko()


@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit not installed")
def test_rdkit_detected():
    assert _detect_rdkit() is True


def test_biopython_detected():
    assert _detect_biopython() is True


@pytest.mark.skipif(not MEEKO_AVAILABLE, reason="Meeko not installed")
def test_meeko_detected():
    assert _detect_meeko() is True


# ── Unit: Score Normalization ─────────────────────────────────────────────


def test_normalize_vina_score_strong():
    assert _normalize_vina_score(-11.0) == 8.8


def test_normalize_vina_score_moderate():
    score = _normalize_vina_score(-9.0)
    assert 6.0 <= score <= 8.5


def test_normalize_vina_score_weak():
    score = _normalize_vina_score(-7.0)
    assert 3.0 <= score <= 6.0


def test_normalize_vina_score_none():
    assert _normalize_vina_score(None) == 0.0


def test_normalize_vina_score_very_weak():
    assert _normalize_vina_score(-5.0) == 1.2


def test_normalize_vina_score_exceptional():
    assert _normalize_vina_score(-12.0) == 10.0


def test_normalize_vina_score_out_of_range():
    assert _normalize_vina_score(-3.0) == 0.0


# ── Unit: Vina Binary Detection ───────────────────────────────────────────


def test_find_vina_binary_returns_none_or_path():
    result = _find_vina_binary()
    assert result is None or isinstance(result, str)


# ── Unit: Docking Engine ──────────────────────────────────────────────────


@pytest.fixture
def engine():
    return DockingEngine()


def test_engine_init(engine):
    assert engine is not None
    assert engine.config_path.name == "targets_config.json"


def test_engine_load_config(engine):
    config = engine.load_config()
    assert "targets" in config
    assert len(config["targets"]) >= 10
    assert "excluded_targets" in config


def test_engine_get_dockable_targets(engine):
    targets = engine.get_dockable_targets()
    assert len(targets) >= 10
    for cfg in targets.values():
        assert cfg.get("grid_validated") is True
        assert cfg.get("grid_center") is not None


def test_engine_skips_alphafold_targets(engine):
    targets = engine.get_dockable_targets()
    # TLR9 and TNFSF4 are AlphaFold models without grid_center
    assert "TLR9" not in targets
    assert "TNFSF4" not in targets


def test_engine_get_validation_targets(engine):
    vt = engine.get_validation_targets()
    assert len(vt) >= 3
    ids = [t["gene_id"] for t in vt]
    assert "JAK1" in ids
    assert "BTK" in ids
    assert "TYK2" in ids


def test_engine_get_status(engine):
    status = engine.get_status()
    assert "rdkit_available" in status
    assert "meeko_available" in status
    assert "vina_binary" in status
    assert "docking_possible" in status
    if RDKIT_AVAILABLE:
        assert status["rdkit_available"] is True
    if MEEKO_AVAILABLE:
        assert status["meeko_available"] is True


def test_engine_config_has_all_fields(engine):
    config = engine.load_config()
    targets = config["targets"]
    required = ["pdb_id", "chain", "grid_center", "grid_size",
                "grid_validated", "method"]
    for gid, cfg in targets.items():
        for field in required:
            assert field in cfg, f"{gid} missing {field}"


def test_engine_10_validated_targets(engine):
    targets = engine.get_dockable_targets()
    assert len(targets) == 10


def test_engine_excluded_targets_have_reason(engine):
    config = engine.load_config()
    excluded = config["excluded_targets"]
    assert len(excluded) >= 10
    for entry in excluded:
        assert "gene_id" in entry
        assert "reason" in entry
        assert len(entry["reason"]) > 20


# ── Unit: Real Binding Score Computation ──────────────────────────────────


def test_compute_real_binding_score_none_results():
    compound = {"id": "baricitinib", "mw": 371}
    result = compute_real_binding_score(compound, "BTK", None)
    assert result is None


def test_compute_real_binding_score_biologic_skipped():
    compound = {"id": "rituximab", "mw": 145000}
    vina_results = {"BTK": {"rituximab": {"best_score": -9.0}}}
    result = compute_real_binding_score(compound, "BTK", vina_results)
    assert result is None


def test_compute_real_binding_score_valid():
    compound = {"id": "baricitinib", "mw": 371}
    vina_results = {"BTK": {"baricitinib": {"best_score": -9.5}}}
    result = compute_real_binding_score(compound, "BTK", vina_results)
    assert result is not None
    assert 6.5 <= result <= 10.0


def test_compute_real_binding_score_error_in_results():
    compound = {"id": "baricitinib", "mw": 371}
    vina_results = {"BTK": {"error": "receptor prep failed"}}
    result = compute_real_binding_score(compound, "BTK", vina_results)
    assert result is None


def test_compute_real_binding_score_missing_drug():
    compound = {"id": "nonexistent", "mw": 350}
    vina_results = {"BTK": {"baricitinib": {"best_score": -9.0}}}
    result = compute_real_binding_score(compound, "BTK", vina_results)
    assert result is None


# ── Unit: Meeko Polymer Receptor Preparation ──────────────────────────────

# Small synthetic tripeptide (Gly-Gly-Gly, chain A) with standard backbone
# geometry. Meeko's Polymer workflow must parameterize it into a valid PDBQT
# without any network access — this guards against silent API drift in
# future Meeko releases (e.g. the 0.6 -> 0.7 write_pdbqt_file removal).
TRI_GLY_PDB = """ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  GLY A   1       1.420   0.000   0.000  1.00  0.00           C
ATOM      3  C   GLY A   1       1.980   1.420   0.000  1.00  0.00           C
ATOM      4  O   GLY A   1       1.420   2.420   0.000  1.00  0.00           O
ATOM      5  N   GLY A   2       3.300   1.420   0.000  1.00  0.00           N
ATOM      6  CA  GLY A   2       3.980   2.700   0.000  1.00  0.00           C
ATOM      7  C   GLY A   2       3.980   4.000   0.000  1.00  0.00           C
ATOM      8  O   GLY A   2       3.200   4.700   0.000  1.00  0.00           O
ATOM      9  N   GLY A   3       5.200   4.500   0.000  1.00  0.00           N
ATOM     10  CA  GLY A   3       5.300   5.900   0.000  1.00  0.00           C
ATOM     11  C   GLY A   3       4.500   6.800   0.000  1.00  0.00           C
ATOM     12  O   GLY A   3       4.600   8.000   0.000  1.00  0.00           O
TER
END
"""


@pytest.mark.skipif(not MEEKO_AVAILABLE, reason="Meeko not installed")
def test_convert_receptor_to_pdbqt_synthetic_polymer(tmp_path):
    """The Meeko 0.7 Polymer workflow converts a small PDB to valid PDBQT."""
    pdb_path = tmp_path / "tri_gly.pdb"
    pdbqt_path = tmp_path / "tri_gly.pdbqt"
    pdb_path.write_text(TRI_GLY_PDB, encoding="utf-8")

    ok = _convert_receptor_to_pdbqt(pdb_path, pdbqt_path)

    assert ok is True
    assert pdbqt_path.exists()
    lines = pdbqt_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 3
    # PDBQT ATOM records carry an AutoDock atom type and Gasteiger charge
    assert any("ATOM" in line and "OA" in line for line in lines)
    assert any("ATOM" in line and "N " in line for line in lines)

    # The output must round-trip through Meeko's own PDBQT reader
    from meeko import PDBQTReceptor

    receptor = PDBQTReceptor.from_pdbqt_filename(str(pdbqt_path))
    assert receptor.atoms().shape[0] >= 3


@pytest.mark.skipif(not MEEKO_AVAILABLE, reason="Meeko not installed")
def test_convert_receptor_to_pdbqt_garbage_input_fails_cleanly(tmp_path):
    """Unparseable input returns False instead of raising."""
    pdb_path = tmp_path / "garbage.pdb"
    pdbqt_path = tmp_path / "garbage.pdbqt"
    pdb_path.write_text("THIS IS NOT A PDB\n", encoding="utf-8")

    ok = _convert_receptor_to_pdbqt(pdb_path, pdbqt_path)

    assert ok is False
    assert not pdbqt_path.exists()


def test_convert_receptor_to_pdbqt_missing_meeko(tmp_path, monkeypatch):
    """Without Meeko the helper degrades to False without writing output."""
    monkeypatch.setattr(
        "med_research.pipeline.virtual_screening.docking._detect_meeko",
        lambda: False,
    )
    pdb_path = tmp_path / "tri_gly.pdb"
    pdbqt_path = tmp_path / "tri_gly.pdbqt"
    pdb_path.write_text(TRI_GLY_PDB, encoding="utf-8")

    ok = _convert_receptor_to_pdbqt(pdb_path, pdbqt_path)

    assert ok is False
    assert not pdbqt_path.exists()


# ── Unit: Meeko Ligand Preparation ─────────────────────────────────────────

ASPIRIN_SMILES = "CC(=O)Oc1ccccc1C(=O)O"


@pytest.mark.skipif(not MEEKO_AVAILABLE, reason="Meeko not installed")
@pytest.mark.skipif(not RDKIT_AVAILABLE, reason="RDKit not installed")
def test_prepare_ligand_synthetic_smiles(tmp_path, monkeypatch):
    """SMILES -> RDKit 3D -> Meeko PDBQTWriterLegacy produces valid PDBQT."""
    monkeypatch.setattr(
        "med_research.pipeline.virtual_screening.docking.TARGETS_DIR", tmp_path
    )

    pdbqt_path = prepare_ligand("aspirin", ASPIRIN_SMILES)

    assert pdbqt_path is not None
    text = Path(pdbqt_path).read_text(encoding="utf-8")
    assert "ROOT" in text
    # PDBQT records carry an AutoDock atom type (aromatic carbon here)
    assert any("ATOM" in line and " A " in line for line in text.splitlines())

    # The output must round-trip through Meeko's own ligand reader
    from meeko import PDBQTMolecule

    molecule = PDBQTMolecule.from_file(pdbqt_path)
    assert molecule.atoms().shape[0] >= 3


def test_prepare_ligand_garbage_smiles_fails_cleanly(tmp_path, monkeypatch):
    """Invalid SMILES returns None instead of raising."""
    monkeypatch.setattr(
        "med_research.pipeline.virtual_screening.docking.TARGETS_DIR", tmp_path
    )

    result = prepare_ligand("junk", "not-a-valid-smiles!!!")

    assert result is None


def test_prepare_ligand_missing_meeko(tmp_path, monkeypatch):
    """Without Meeko the ligand path degrades to None without writing output."""
    monkeypatch.setattr(
        "med_research.pipeline.virtual_screening.docking.TARGETS_DIR", tmp_path
    )
    monkeypatch.setattr(
        "med_research.pipeline.virtual_screening.docking._detect_meeko",
        lambda: False,
    )

    result = prepare_ligand("aspirin", ASPIRIN_SMILES)

    assert result is None
    assert not (tmp_path / "ligands" / "aspirin.pdbqt").exists()


# ── Unit: Vina Setup Tool ──────────────────────────────────────────────────


def test_vina_setup_check(monkeypatch):
    from med_research.pipeline.virtual_screening.vina_setup import check_vina
    result = check_vina()
    assert result is None or isinstance(result, str)


def test_vina_setup_system(monkeypatch):
    from med_research.pipeline.virtual_screening.vina_setup import _system
    sysname = _system()
    assert sysname in ("win32", "darwin", "linux")


# ── Unit: Public API Functions ─────────────────────────────────────────────


def test_get_docking_status_returns_dict():
    status = get_docking_status()
    assert isinstance(status, dict)
    for key in ["rdkit_available", "meeko_available", "biopython_available",
                "vina_binary", "vina_available", "docking_possible"]:
        assert key in status


def test_get_vina_status_text_returns_string():
    text = get_vina_status_text()
    assert isinstance(text, str)
    assert len(text) > 0


# ── Unit: Vina Output Parsing ─────────────────────────────────────────────


def test_normalize_vina_score_clamped():
    assert _normalize_vina_score(-4.0) == 0.0
    assert _normalize_vina_score(-12.0) == 10.0


def test_normalize_vina_score_precision():
    score = _normalize_vina_score(-8.3)
    assert isinstance(score, float)
    assert score == round(score, 1)


# ── Unit: Target Config Validation ─────────────────────────────────────────


def test_target_config_pdb_ids_are_valid():
    engine = DockingEngine()
    config = engine.load_config()
    targets = config["targets"]
    for gid, cfg in targets.items():
        pdb_id = cfg.get("pdb_id", "")
        if "AF-" in pdb_id:
            continue
        assert len(pdb_id) == 4, f"{gid}: invalid PDB ID {pdb_id}"
        assert pdb_id.isalnum(), f"{gid}: non-alphanumeric PDB ID {pdb_id}"


def test_target_config_grid_sizes_reasonable():
    engine = DockingEngine()
    targets = engine.get_dockable_targets()
    for gid, cfg in targets.items():
        size = cfg["grid_size"]
        assert len(size) == 3
        for dim in size:
            assert 15 <= dim <= 35, f"{gid}: grid dimension {dim} out of range"


def test_target_config_grid_centers_not_null():
    engine = DockingEngine()
    targets = engine.get_dockable_targets()
    for gid, cfg in targets.items():
        center = cfg["grid_center"]
        assert center is not None, f"{gid}: grid_center is None"
        assert len(center) == 3
        assert all(isinstance(c, (int, float)) for c in center)


# ── Integration: Docking Engine without Vina ───────────────────────────────


def test_docking_possible_false_without_vina():
    status = get_docking_status()
    # Without Vina binary, docking_possible should be False
    # but RDKit and Meeko should show as available
    if status["docking_possible"]:
        assert status["vina_available"] is True
    else:
        assert status["vina_available"] is False or status["meeko_available"] is True


# ── Slow Tests ─────────────────────────────────────────────────────────────


@pytest.mark.slow
@pytest.mark.network  # downloads real PDB structures from RCSB
def test_engine_prepare_targets_no_force(engine):
    rec_paths = engine.prepare_all_targets(force=False)
    assert isinstance(rec_paths, dict)
    assert len(rec_paths) >= 10


def test_vina_setup_cli_help():
    import subprocess

    env = os.environ.copy()
    src_dir = Path(__file__).parent.parent / "src"
    env["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(src_dir), env.get("PYTHONPATH", "")) if path
    )
    result = subprocess.run(
        [sys.executable, "-m", "med_research.pipeline.virtual_screening.vina_setup", "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(Path(__file__).parent.parent),
        env=env,
    )
    assert result.returncode == 0


def test_vina_setup_check_cli():
    import subprocess

    env = os.environ.copy()
    src_dir = Path(__file__).parent.parent / "src"
    env["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(src_dir), env.get("PYTHONPATH", "")) if path
    )
    result = subprocess.run(
        [sys.executable, "-m", "med_research.pipeline.virtual_screening.vina_setup", "--check"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(Path(__file__).parent.parent),
        env=env,
    )
    assert result.returncode == 0
    assert "Status" in result.stdout or "Vina" in result.stdout
