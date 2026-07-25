"""
Lupus Virtual Screening — Molecular Docking Engine

Provides real AutoDock Vina molecular docking to replace property-based
binding affinity estimates. Supports:

  1. Receptor PDB fetching from RCSB PDB API (with local caching)
  2. Ligand preparation: SMILES → RDKit 3D → Meeko → PDBQT
  3. Receptor preparation: BioPython PDB cleanup → Meeko → PDBQT
  4. Parallel AutoDock Vina execution via ProcessPoolExecutor
  5. Score normalization: Vina ΔG (kcal/mol) → 0-10 binding score

All components degrade gracefully: if Vina/RDKit/Meeko are unavailable,
the engine reports the status and returns empty results — the calling
code falls back to property-based scoring.

Usage:
    from virtual_screening.docking import DockingEngine, get_docking_status

    engine = DockingEngine()
    status = engine.get_status()        # Check what's available
    engine.prepare_all_targets()         # Download + prepare all receptors
    engine.prepare_all_ligands(library)  # Prepare ligands from compound library
    results = engine.dock_target("BLK", ligand_ids=["baricitinib", "acalabrutinib"])
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TARGETS_DIR = Path(__file__).parent / "targets"
CONFIG_PATH = TARGETS_DIR / "targets_config.json"

# ── Optional dependency detection ─────────────────────────────────────

_RDKIT = False
_MEEKO = False
_BIOPYTHON = False
_VINA_PATH = None


def _detect_rdkit() -> bool:
    """Check if RDKit is importable."""
    global _RDKIT
    if not _RDKIT:
        try:
            from rdkit import Chem  # noqa: F401
            from rdkit.Chem import AllChem, Descriptors  # noqa: F401
            _RDKIT = True
        except ImportError:
            pass
    return _RDKIT


def _detect_meeko() -> bool:
    """Check if Meeko (AutoDock molecule preparation library) is importable."""
    global _MEEKO
    if not _MEEKO:
        try:
            from meeko import MoleculePreparation, PDBQTWriterLegacy  # noqa: F401
            from meeko import PDBQTReceptor  # noqa: F401
            _MEEKO = True
        except ImportError:
            pass
    return _MEEKO


def _detect_biopython() -> bool:
    """Check if BioPython is importable."""
    global _BIOPYTHON
    if not _BIOPYTHON:
        try:
            from Bio.PDB import PDBParser, PDBIO  # noqa: F401
            _BIOPYTHON = True
        except ImportError:
            pass
    return _BIOPYTHON


def _find_vina_binary() -> str | None:
    """Locate the AutoDock Vina binary on the system.

    Searches:
      1. System PATH (shutil.which)
      2. Project-local bin/ directory
      3. Common install locations
    """
    global _VINA_PATH
    if _VINA_PATH is not None:
        return _VINA_PATH

    # Check PATH
    candidates = ["vina", "vina.exe"]
    for name in candidates:
        path = shutil.which(name)
        if path:
            _VINA_PATH = path
            return _VINA_PATH

    # Check project bin/
    bin_dir = Path(__file__).parent / "bin"
    for name in candidates:
        candidate = bin_dir / name
        if candidate.is_file():
            _VINA_PATH = str(candidate)
            return _VINA_PATH

    # Check common locations on Windows
    if sys.platform == "win32":
        common = [
            Path(os.environ.get("ProgramFiles", "C:\\Program Files"), "AutoDock Vina", "vina.exe"),
            Path(os.environ.get("LOCALAPPDATA", ""), "AutoDock Vina", "vina.exe"),
        ]
        for p in common:
            if p.is_file():
                _VINA_PATH = str(p)
                return _VINA_PATH

    _VINA_PATH = None  # Tried, not found
    return None


# ═══════════════════════════════════════════════════════════════════════
#  Receptor Preparation
# ═══════════════════════════════════════════════════════════════════════


class _CleanSelect:
    """BioPython Select class: keep only standard amino acids, target chain."""

    def __init__(self, chain_id: str = "A"):
        self.chain_id = chain_id
        self._standard = {
            "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS",
            "ILE", "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP",
            "TYR", "VAL",
        }

    def accept_chain(self, chain):
        return chain.get_id() == self.chain_id

    def accept_residue(self, residue):
        """Keep only standard amino acid residues."""
        hetfield = residue.get_id()[0]
        if hetfield.strip() != "":
            return False
        return residue.get_resname() in self._standard

    def accept_atom(self, atom):
        """Keep all atoms of accepted residues."""
        return True


def _fetch_pdb(pdb_id: str, output_path: Path) -> bool:
    """Download a PDB file from RCSB.

    Args:
        pdb_id: 4-character PDB ID (e.g., '3TUD').
        output_path: Where to save the .pdb file.

    Returns:
        True if download succeeded, False otherwise.
    """
    import urllib.request
    import urllib.error

    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LupusPlatform/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            output_path.write_bytes(resp.read())
        return True
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
        print(f"   ⚠️  PDB download failed ({pdb_id}): {e}")
        return False


def _clean_receptor(pdb_path: Path, cleaned_path: Path, chain: str = "A") -> bool:
    """Clean a PDB structure: extract target chain, remove waters and ligands.

    Requires BioPython.

    Args:
        pdb_path: Input PDB file path.
        cleaned_path: Output cleaned PDB file path.
        chain: Chain ID to keep.

    Returns:
        True if cleaning succeeded.
    """
    if not _detect_biopython():
        return False

    try:
        from Bio.PDB import PDBParser, PDBIO

        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("receptor", str(pdb_path))

        io = PDBIO()
        io.set_structure(structure)
        io.save(str(cleaned_path), _CleanSelect(chain))
        return True
    except Exception as e:
        print(f"   ⚠️  Receptor cleaning failed: {e}")
        return False


def prepare_receptor(gene_id: str, config: dict, force: bool = False) -> str | None:
    """Prepare a receptor PDBQT file for docking.

    Steps:
      1. Download PDB from RCSB (if not cached)
      2. Clean PDB: extract chain, remove non-standard residues
      3. Convert to PDBQT (requires Meeko)

    Args:
        gene_id: Gene identifier from targets_config.json.
        config: Target config dict (with pdb_id, chain, etc.).
        force: If True, re-download and re-prepare even if cached.

    Returns:
        Path to receptor PDBQT file, or None on failure.
    """
    pdb_id = config.get("pdb_id", "")
    chain = config.get("chain", "A")
    method = config.get("method", "")

    # Skip AlphaFold models — manual preparation required
    if method and "AlphaFold" in method:
        print(f"   ⚠️  Skipping {gene_id}: AlphaFold model — manual preparation required")
        return None

    receptors_dir = TARGETS_DIR / "receptors"
    receptors_dir.mkdir(parents=True, exist_ok=True)

    pdb_path = receptors_dir / f"{gene_id}.pdb"
    cleaned_path = receptors_dir / f"{gene_id}_clean.pdb"
    pdbqt_path = receptors_dir / f"{gene_id}.pdbqt"

    # Return cached if available
    if pdbqt_path.exists() and not force:
        return str(pdbqt_path)

    # Step 1: Download PDB
    if not pdb_path.exists() or force:
        print(f"   📥 Downloading {pdb_id} for {gene_id}...")
        if not _fetch_pdb(pdb_id, pdb_path):
            return None

    # Step 2: Clean (optional — skip if BioPython unavailable)
    if not cleaned_path.exists() or force:
        if _detect_biopython():
            _clean_receptor(pdb_path, cleaned_path, chain)
        else:
            # Use raw PDB as-is
            shutil.copy(pdb_path, cleaned_path)

    # Step 3: Convert to PDBQT
    if not pdbqt_path.exists() or force:
        if _detect_meeko():
            try:
                from meeko import PDBQTReceptor

                # Meeko's receptor preparation adds hydrogens and Gasteiger charges
                success = PDBQTReceptor.write_pdbqt_file(
                    str(cleaned_path), str(pdbqt_path)
                )
                if not success:
                    print(f"   ⚠️  Meeko PDBQT conversion failed for {gene_id}")
                    return None
            except Exception as e:
                print(f"   ⚠️  Meeko receptor prep error ({gene_id}): {e}")
                return None
        else:
            # Without Meeko, we can't produce PDBQT
            print(f"   ⚠️  Meeko not available — cannot prepare receptor {gene_id}")
            return None

    return str(pdbqt_path)


# ═══════════════════════════════════════════════════════════════════════
#  Ligand Preparation
# ═══════════════════════════════════════════════════════════════════════


def _smiles_to_3d_mol(smiles: str):
    """Convert SMILES to an RDKit Mol with 3D coordinates.

    Returns RDKit Mol object or None on failure.
    """
    if not smiles or not _detect_rdkit():
        return None

    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None

        mol = Chem.AddHs(mol)
        params = AllChem.ETKDGv3()
        params.randomSeed = 42
        status = AllChem.EmbedMolecule(mol, params)
        if status != 0:
            # Fallback: basic distance geometry
            status = AllChem.EmbedMolecule(mol, AllChem.ETKDG())
            if status != 0:
                return None

        AllChem.MMFFOptimizeMolecule(mol)
        return mol
    except Exception:
        return None


def prepare_ligand(
    drug_id: str,
    smiles: str,
    force: bool = False,
) -> str | None:
    """Prepare a ligand PDBQT file from a SMILES string.

    Steps:
      1. SMILES → RDKit Mol with 3D coordinates
      2. RDKit Mol → Meeko MoleculePreparation → PDBQT string
      3. Write PDBQT to disk

    Args:
        drug_id: Compound identifier.
        smiles: SMILES string.
        force: If True, re-prepare even if cached.

    Returns:
        Path to ligand PDBQT file, or None on failure.
    """
    if not smiles:
        return None

    ligands_dir = TARGETS_DIR / "ligands"
    ligands_dir.mkdir(parents=True, exist_ok=True)

    pdbqt_path = ligands_dir / f"{drug_id}.pdbqt"

    if pdbqt_path.exists() and not force:
        return str(pdbqt_path)

    # Step 1: SMILES → 3D
    mol = _smiles_to_3d_mol(smiles)
    if mol is None:
        print(f"   ⚠️  Could not generate 3D conformer for {drug_id}")
        return None

    # Step 2 & 3: Meeko prep → PDBQT
    if not _detect_meeko():
        print(f"   ⚠️  Meeko not available — cannot prepare ligand {drug_id}")
        return None

    try:
        from meeko import MoleculePreparation, PDBQTWriterLegacy

        preparator = MoleculePreparation()
        mol_setups = preparator.prepare(mol)
        if not mol_setups:
            return None

        pdbqt_string, is_ok = PDBQTWriterLegacy.write_string(mol_setups[0])
        if not is_ok:
            return None

        pdbqt_path.write_text(pdbqt_string, encoding="utf-8")
        return str(pdbqt_path)
    except Exception as e:
        print(f"   ⚠️  Ligand prep error ({drug_id}): {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
#  AutoDock Vina Execution
# ═══════════════════════════════════════════════════════════════════════


def run_vina_docking(
    receptor_pdbqt: str,
    ligand_pdbqt: str,
    output_dir: str,
    grid_center: list,
    grid_size: list,
    exhaustiveness: int = 8,
    num_modes: int = 5,
    timeout: int = 300,
) -> dict:
    """Run a single AutoDock Vina docking job.

    Args:
        receptor_pdbqt: Path to receptor PDBQT file.
        ligand_pdbqt: Path to ligand PDBQT file.
        output_dir: Directory for Vina output PDBQT.
        grid_center: [x, y, z] center of docking grid (Å).
        grid_size: [x, y, z] size of docking grid (Å).
        exhaustiveness: Vina search exhaustiveness (default 8).
        num_modes: Number of binding modes to output.
        timeout: Subprocess timeout in seconds.

    Returns:
        dict with best_score, all_scores, modes_found, or empty dict on failure.
    """
    vina_bin = _find_vina_binary()
    if not vina_bin:
        return {"error": "Vina binary not found", "best_score": None}

    os.makedirs(output_dir, exist_ok=True)
    output_pdbqt = os.path.join(output_dir, "docked.pdbqt")

    cmd = [
        vina_bin,
        "--receptor", receptor_pdbqt,
        "--ligand", ligand_pdbqt,
        "--out", output_pdbqt,
        "--center_x", str(grid_center[0]),
        "--center_y", str(grid_center[1]),
        "--center_z", str(grid_center[2]),
        "--size_x", str(grid_size[0]),
        "--size_y", str(grid_size[1]),
        "--size_z", str(grid_size[2]),
        "--exhaustiveness", str(exhaustiveness),
        "--num_modes", str(num_modes),
        "--cpu", "1",  # Single-threaded — we parallelize at the Python level
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=output_dir,
        )

        # Parse scores from Vina output
        # Format: "   1       -8.3      0.000      0.000"
        scores = []
        for line in result.stdout.split("\n"):
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    mode_num = int(parts[0])
                    if 1 <= mode_num <= num_modes:
                        scores.append(float(parts[1]))
                except (ValueError, IndexError):
                    continue

        return {
            "best_score": min(scores) if scores else None,
            "all_scores": scores,
            "output_file": output_pdbqt,
            "modes_found": len(scores),
            "vina_stdout": result.stdout[-500:] if result.stdout else "",
        }

    except subprocess.TimeoutExpired:
        return {"error": "Vina timed out", "best_score": None}
    except FileNotFoundError:
        return {"error": f"Vina binary not found at {vina_bin}", "best_score": None}
    except Exception as e:
        return {"error": str(e), "best_score": None}


def _normalize_vina_score(vina_kcal: float | None) -> float:
    """Convert Vina affinity (kcal/mol) to a 0-10 binding score.

    Mapping (approximate):
      -11.0 kcal/mol → 10.0  (exceptional binding)
       -9.0 kcal/mol →  7.5  (strong binding)
       -7.0 kcal/mol →  5.0  (moderate binding)
       -5.0 kcal/mol →  0.0  (weak binding)
    """
    if vina_kcal is None:
        return 0.0

    # Clamp to typical range
    clamped = max(-12.0, min(-4.0, vina_kcal))

    # Linear mapping: -4.0→0, -12.0→10
    normalized = (clamped + 4.0) / -8.0 * 10.0
    return round(max(0.0, min(10.0, normalized)), 1)


# ═══════════════════════════════════════════════════════════════════════
#  Parallel docking helper (module-level for ProcessPool picklability)
# ═══════════════════════════════════════════════════════════════════════


def _dock_one_ligand(args: tuple) -> tuple:
    """Run a single Vina docking job. Module-level so ProcessPool can pickle it.

    Args:
        args: (drug_id, lig_path, rec_path, output_dir, grid_center, grid_size, exhaustiveness)

    Returns:
        (drug_id, vina_result_dict)
    """
    drug_id, lig_path, rec_path, output_dir, grid_center, grid_size, exhaustiveness = args
    vina_result = run_vina_docking(
        receptor_pdbqt=rec_path,
        ligand_pdbqt=lig_path,
        output_dir=output_dir,
        grid_center=grid_center,
        grid_size=grid_size,
        exhaustiveness=exhaustiveness,
    )
    return drug_id, vina_result


# ═══════════════════════════════════════════════════════════════════════
#  Docking Engine (Orchestrator)
# ═══════════════════════════════════════════════════════════════════════


class DockingEngine:
    """Main orchestrator for molecular docking.

    Manages receptor/ligand preparation, grid config loading,
    and parallel Vina execution.
    """

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or CONFIG_PATH
        self._config: dict = {}
        self._loaded = False

    # ── Configuration ───────────────────────────────────────────────

    def load_config(self) -> dict:
        """Load targets_config.json."""
        if self._loaded:
            return self._config

        if not self.config_path.exists():
            print(f"⚠️  Config not found: {self.config_path}")
            self._loaded = True
            return {}

        self._config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self._loaded = True
        return self._config

    def get_dockable_targets(self) -> dict:
        """Return targets with grid_validated=True and grid_center set."""
        config = self.load_config()
        targets = config.get("targets", {})
        return {
            gid: cfg
            for gid, cfg in targets.items()
            if isinstance(cfg, dict)
            and cfg.get("grid_validated")
            and cfg.get("grid_center") is not None
        }

    def get_validation_targets(self) -> list:
        """Return validation targets from config."""
        config = self.load_config()
        return config.get("targeted_genes_for_validation", [])

    # ── Status ──────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Return availability status of all docking dependencies."""
        vina_bin = _find_vina_binary()
        return {
            "rdkit_available": _detect_rdkit(),
            "meeko_available": _detect_meeko(),
            "biopython_available": _detect_biopython(),
            "vina_binary": vina_bin,
            "vina_available": vina_bin is not None,
            "docking_possible": (
                _detect_rdkit()
                and _detect_meeko()
                and vina_bin is not None
            ),
            "config_loaded": self.config_path.exists() if not self._loaded else True,
        }

    # ── Preparation ─────────────────────────────────────────────────

    def prepare_all_targets(self, force: bool = False) -> dict[str, str | None]:
        """Download and prepare all validated receptor targets.

        Returns:
            Dict mapping gene_id → receptor PDBQT path (or None if failed).
        """
        config = self.load_config()
        targets = self.get_dockable_targets()
        results = {}

        print(f"\n🧬 Preparing receptors for {len(targets)} targets...")
        for gene_id, tcfg in targets.items():
            print(f"   🎯 {gene_id} (PDB: {tcfg.get('pdb_id', '?')})")
            results[gene_id] = prepare_receptor(gene_id, tcfg, force=force)

        n_ok = sum(1 for v in results.values() if v)
        print(f"   ✅ {n_ok}/{len(targets)} receptors prepared")
        return results

    def prepare_all_ligands(
        self,
        compound_library: list[dict],
        force: bool = False,
    ) -> dict[str, str | None]:
        """Prepare all ligands from a compound library.

        Skips biologics (MW > 5000) — Vina cannot dock large molecules.

        Args:
            compound_library: List of compound dicts (from build_compound_library()).
            force: If True, re-prepare even if cached.

        Returns:
            Dict mapping drug_id → ligand PDBQT path (or None if failed/skipped).
        """
        results = {}
        skipped = 0

        print(f"\n💊 Preparing ligands for {len(compound_library)} compounds...")
        for compound in compound_library:
            drug_id = compound["id"]
            smiles = compound.get("smiles", "")
            mw = compound.get("mw", 0)

            # Skip biologics
            if mw > 5000 or not smiles:
                skipped += 1
                continue

            pdbqt_path = prepare_ligand(drug_id, smiles, force=force)
            results[drug_id] = pdbqt_path
            if pdbqt_path:
                print(f"   ✅ {drug_id}")
            else:
                print(f"   ⚠️  {drug_id} — prep failed")

        print(f"   ✅ {len([v for v in results.values() if v])} prepared, {skipped} skipped (biologics)")
        return results

    # ── Docking ─────────────────────────────────────────────────────

    def dock_target(
        self,
        gene_id: str,
        ligand_ids: list[str] | None = None,
        receptor_paths: dict[str, str | None] | None = None,
        ligand_paths: dict[str, str | None] | None = None,
        max_workers: int = 4,
    ) -> dict:
        """Dock ligands against a single protein target.

        Args:
            gene_id: Gene ID from targets_config.
            ligand_ids: List of drug IDs to dock (None = all prepared ligands).
            receptor_paths: Pre-computed receptor path map (from prepare_all_targets).
            ligand_paths: Pre-computed ligand path map (from prepare_all_ligands).
            max_workers: Number of parallel Vina processes.

        Returns:
            dict with per-ligand Vina results.
        """
        from concurrent.futures import ProcessPoolExecutor, as_completed

        config = self.load_config()
        targets = config.get("targets", {})

        # Get target config
        tcfg = targets.get(gene_id)
        if tcfg is None or not isinstance(tcfg, dict):
            return {"error": f"Target {gene_id} not found in config"}

        if not tcfg.get("grid_validated") or tcfg.get("grid_center") is None:
            return {"error": f"Target {gene_id}: grid not validated"}

        # Get receptor path
        rec_path = None
        if receptor_paths:
            rec_path = receptor_paths.get(gene_id)
        if not rec_path:
            rec_path = prepare_receptor(gene_id, tcfg)
        if not rec_path:
            return {"error": f"Receptor preparation failed for {gene_id}"}

        # Get ligand paths
        if ligand_ids is None and ligand_paths:
            ligand_ids = list(ligand_paths.keys())
        elif ligand_ids is None:
            return {"error": "No ligand_ids specified and no ligand_paths provided"}

        grid_center = tcfg["grid_center"]
        grid_size = tcfg["grid_size"]
        exhaustiveness = tcfg.get("exhaustiveness", 8)

        # Run dockings in parallel
        output_base = TARGETS_DIR / "docking_output" / gene_id
        output_base.mkdir(parents=True, exist_ok=True)

        results = {}

        if ligand_paths is None:
            return {"error": "No ligand_paths provided"}

        eligible = [lid for lid in ligand_ids if ligand_paths.get(lid)]
        print(f"   🧬 Docking {len(eligible)} ligands against {gene_id} "
              f"(grid: {grid_center}, size: {grid_size})")

        if max_workers > 1 and len(eligible) > 1:
            # Build task args for module-level helper (picklable)
            tasks = [
                (lid, ligand_paths[lid], str(rec_path), str(output_base / lid),
                 grid_center, grid_size, exhaustiveness)
                for lid in eligible
            ]
            with ProcessPoolExecutor(max_workers=min(max_workers, len(eligible))) as executor:
                futures = {executor.submit(_dock_one_ligand, task): task[0] for task in tasks}
                for future in as_completed(futures):
                    try:
                        drug_id, vina_result = future.result()
                        results[drug_id] = vina_result
                    except Exception as e:
                        lid = futures[future]
                        results[lid] = {"error": str(e), "best_score": None}
        else:
            for lid in eligible:
                task = (lid, ligand_paths[lid], str(rec_path), str(output_base / lid),
                        grid_center, grid_size, exhaustiveness)
                drug_id, vina_result = _dock_one_ligand(task)
                results[drug_id] = vina_result

        return results

    def dock_all(
        self,
        compound_library: list[dict],
        top_n_per_target: int = 5,
        max_workers: int = 4,
        force_prep: bool = False,
    ) -> dict:
        """Run the complete docking pipeline: prep targets → prep ligands → dock.

        Only docks the top-N compounds per target (using property-based scores
        as a pre-filter), then runs real Vina docking for those.

        Args:
            compound_library: Compound library from build_compound_library().
            top_n_per_target: Number of top property-scored compounds to dock per target.
            max_workers: Parallel Vina processes.
            force_prep: Re-prepare all receptors and ligands.

        Returns:
            dict mapping gene_id → {vina_results, ...}.
        """
        status = self.get_status()
        if not status["docking_possible"]:
            print("❌ Docking not possible. Missing dependencies:")
            for key, val in status.items():
                if not val and key not in ("config_loaded",):
                    print(f"   - {key}")
            return {"error": "Dependencies missing", "status": status}

        # Phase 1: Prepare receptors
        receptor_paths = self.prepare_all_targets(force=force_prep)
        ready_targets = [gid for gid, path in receptor_paths.items() if path]
        if not ready_targets:
            return {"error": "No receptors prepared"}

        # Phase 2: Prepare ligands
        ligand_paths = self.prepare_all_ligands(compound_library, force=force_prep)
        ready_ligands = [did for did, path in ligand_paths.items() if path]
        if not ready_ligands:
            return {"error": "No ligands prepared"}

        # Phase 3: Pre-score with property-based method (filter to top N)
        # Use lazy import to avoid circular dependency at module level
        import importlib
        vs_screening = importlib.import_module("virtual_screening.screening")
        compute_binding_estimate = vs_screening.compute_binding_estimate
        load_kg_genes_fn = vs_screening.load_kg_genes

        all_genes = load_kg_genes_fn()
        top_ligands_per_target = {}

        for gene_id in ready_targets:
            gene_info = all_genes.get(gene_id, {"id": gene_id, "name": gene_id})
            scored = []
            for compound in compound_library:
                if compound["id"] not in ready_ligands:
                    continue
                score = compute_binding_estimate(compound, gene_info)
                scored.append((compound["id"], score))
            scored.sort(key=lambda x: x[1], reverse=True)
            top = [lid for lid, _ in scored[:top_n_per_target]]
            top_ligands_per_target[gene_id] = top if top else ready_ligands[:top_n_per_target]
            print(f"   📊 {gene_id}: selected top {len(top_ligands_per_target[gene_id])} ligands for docking")

        # Phase 4: Dock
        all_results = {}
        for gene_id in ready_targets:
            print(f"\n🔬 Docking {gene_id}...")
            results = self.dock_target(
                gene_id=gene_id,
                ligand_ids=top_ligands_per_target.get(gene_id, ready_ligands[:top_n_per_target]),
                receptor_paths=receptor_paths,
                ligand_paths=ligand_paths,
                max_workers=max_workers,
            )
            all_results[gene_id] = results

        return {
            "docking_results": all_results,
            "receptors_prepared": len(ready_targets),
            "ligands_prepared": len(ready_ligands),
            "status": status,
        }


# ═══════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════


def get_docking_status() -> dict:
    """Quick status check for docking availability."""
    engine = DockingEngine()
    return engine.get_status()


def compute_real_binding_score(
    compound: dict,
    gene_id: str,
    vina_results: dict | None,
) -> float | None:
    """Compute a real binding score from Vina results.

    If Vina results are available and contain a valid best_score,
    returns the normalized 0-10 score. Otherwise returns None
    (caller should fall back to property-based scoring).

    Args:
        compound: Compound dict (needs 'mw' for biologics check).
        gene_id: Target gene ID.
        vina_results: Per-gene dict of {drug_id: vina_output} from DockingEngine.

    Returns:
        Normalized binding score (0-10) or None if no Vina result available.
    """
    if vina_results is None:
        return None

    drug_id = compound.get("id", "")

    # Check MW — biologics can't be docked
    if compound.get("mw", 0) > 5000:
        return None

    gene_results = vina_results.get(gene_id, {})
    if isinstance(gene_results, dict) and "error" not in gene_results:
        vina_out = gene_results.get(drug_id, {})
    elif isinstance(vina_results, dict) and gene_id not in vina_results:
        # vina_results might be flat: {drug_id: vina_output}
        vina_out = vina_results.get(drug_id, {})
    else:
        return None

    if not vina_out or "error" in vina_out:
        return None

    best_score = vina_out.get("best_score")
    if best_score is not None:
        return _normalize_vina_score(best_score)

    return None


def get_vina_status_text() -> str:
    """Human-readable Vina availability status for reports."""
    status = get_docking_status()
    if status["docking_possible"]:
        return f"active ({status['vina_binary']})"
    parts = []
    if not status["vina_available"]:
        parts.append("Vina binary not found")
    if not status["rdkit_available"]:
        parts.append("RDKit not installed")
    if not status["meeko_available"]:
        parts.append("Meeko not installed")
    if parts:
        return "not available (" + ", ".join(parts) + ")"
    return "not available"
