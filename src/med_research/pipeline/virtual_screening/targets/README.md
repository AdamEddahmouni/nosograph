# 🧬 Docking Targets Directory

> **Current runtime note:** This README describes the target data used by the packaged `med_research` pipeline. Use the unified CLI (`python -m med_research.cli screening ...`) and install dependencies from the repository root; the old root-level `virtual_screening/` script path shown in historical examples is not the supported entry point.

This directory stores everything needed for AutoDock Vina molecular docking:
curated PDB mappings, downloaded receptor structures, prepared ligand files,
and docking output.

## 📁 Directory Structure

```
targets/
├── README.md                ← You are here
├── targets_config.json      ← Curated PDB IDs + grid boxes per gene
├── receptors/               ← Downloaded & prepared receptor PDBQTs
│   ├── BLK.pdb              #   Raw PDB from RCSB (gitignored)
│   ├── BLK_clean.pdb        #   BioPython-cleaned (gitignored)
│   └── BLK.pdbqt            #   Meeko-prepared for docking (gitignored)
├── ligands/                 ← Prepared ligand PDBQTs (gitignored)
│   ├── baricitinib.pdbqt
│   └── ...
├── docking_output/          ← Per-target, per-ligand Vina results (gitignored)
│   └── BLK/
│       └── baricitinib/
│           └── docked.pdbqt
└── bin/                     ← AutoDock Vina binary (optional, gitignored)
    ├── vina                 #   Linux/macOS
    └── vina.exe             #   Windows
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
python -m pip install -e ".[cheminformatics]"
```

### 2. Install AutoDock Vina

**Option A: Download binary** (recommended)

```bash
# Linux
wget https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_1.2.5_linux_x86_64
chmod +x vina_1.2.5_linux_x86_64
mv vina_1.2.5_linux_x86_64 targets/bin/vina

# macOS
wget https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_1.2.5_mac
chmod +x vina_1.2.5_mac
mv vina_1.2.5_mac targets/bin/vina

# Windows (PowerShell)
Invoke-WebRequest -Uri "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_1.2.5_win64.exe" -OutFile "targets/bin/vina.exe"
```

**Option B: System install**

```bash
# macOS (Homebrew)
brew install vina

# Linux (conda)
conda install -c conda-forge vina

# Ubuntu/Debian
sudo apt install autodock-vina
```

### 3. Check Your Setup

```bash
python -c "from med_research.pipeline.virtual_screening.docking import get_docking_status; print(get_docking_status())"
```

You should see all `true` values:
```json
{
  "rdkit_available": true,
  "meeko_available": true,
  "biopython_available": true,
  "vina_available": true,
  "docking_possible": true
}
```

### 4. Run Virtual Screening with Real Docking

```bash
# From the project root:
# Full run (expect 20-60 min depending on hardware):
python -m med_research.cli screening --disease sle --use-vina --top 15 --export-html

# Quick test with a single target:
python -m med_research.cli screening --disease sle --use-vina --gene BLK --top 5 --export-html
```

When `--use-vina` is passed, the screening engine will:
1. Download PDB structures for all validated targets in `targets_config.json`
2. Prepare ligands from SMILES strings (RDKit → Meeko → PDBQT)
3. Run property-based scoring on all compound-target pairings
4. Select the top 5 compounds per target for real Vina docking
5. Replace property-based binding estimates with real docking scores
6. Generate the HTML report with docking badges

---

## 📋 Adding a New Docking Target

### Step 1: Find a Good PDB Structure

1. Go to [RCSB PDB](https://www.rcsb.org/) and search for your gene/protein
2. Filter by:
   - **Resolution:** < 3.0 Å (prefer < 2.5 Å)
   - **Method:** X-ray diffraction (or Cryo-EM for large receptors)
   - **Ligand:** prefer structures with bound inhibitors (validates the binding pocket)
3. Note the **PDB ID** (4-character code, e.g., `3TUD`)
4. Note which **chain** contains the binding site (usually `A`)

### Step 2: Define the Docking Grid Box

Open the PDB in PyMOL or UCSF Chimera:

**PyMOL method:**
```python
# Load structure
fetch 3TUD

# Select the co-crystallized ligand (if present)
select lig, organic

# Get center of ligand
center_of_mass lig

# Example output: [22.5, 8.3, 18.7]
```

**Chimera method:**
```
open 3TUD
# Click the ligand to select it, or use its 3-letter residue code:
sel :ATP
measure center sel
```

If no co-crystallized ligand is available, identify the binding site residues
from the literature and compute their center of mass.

**Grid size guidelines:**
- Small binding pocket (e.g., ATP site): `[20, 20, 20]`
- Medium pocket (e.g., peptide-binding groove): `[24, 24, 24]`
- Large cavity (e.g., TLR LRR pocket): `[25, 25, 25]`
- Always add 4-5 Å padding beyond the known binding residues

### Step 3: Add to `targets_config.json`

Add your target under the `"targets"` section. Use this template:

```json
"GENE_ID": {
  "pdb_id": "XXXX",
  "chain": "A",
  "resolution": 2.00,
  "method": "X-ray diffraction",
  "binding_site": "Brief description of the binding pocket",
  "co_crystallized_ligand": "Ligand code or null",
  "grid_center": [x, y, z],
  "grid_size": [20, 20, 20],
  "grid_validated": true,
  "exhaustiveness": 8,
  "uniprot": "PXXXXX",
  "notes": "Any relevant information about the structure quality or binding site."
}
```

**Required fields:** `pdb_id`, `chain`, `grid_center`, `grid_size`, `grid_validated`
**Recommended:** `resolution`, `method`, `binding_site`, `notes`

### Step 4: Validate the Docking

Before committing, test that your new target docks correctly:

```bash
# Test receptor preparation
python -c "
from med_research.pipeline.virtual_screening.docking import DockingEngine
engine = DockingEngine()
engine.prepare_all_targets()
"

# Test docking a known ligand
python -c "
from med_research.pipeline.virtual_screening.docking import DockingEngine, prepare_ligand

engine = DockingEngine()
engine.prepare_all_targets()

# Prepare a test ligand
lig_path = prepare_ligand('test_drug', 'CC(=O)OC1=CC=CC=C1C(=O)O')  # aspirin
if lig_path:
    lig_paths = {'test_drug': lig_path}
    result = engine.dock_target('YOUR_GENE_ID', ['test_drug'], ligand_paths=lig_paths)
    print(result)
"
```

---

## 🔧 Refining Grid Boxes

### When to Refine

Grid boxes need refinement when:
- The initial docking produces all poor scores (< -5 kcal/mol)
- The top-ranked poses are outside the expected binding site
- You're using a homology model or AlphaFold structure
- The co-crystallized ligand was removed but the apo structure has conformational changes

### How to Refine

**Method 1: Center on co-crystallized ligand** (best, if available)
```python
# PyMOL
fetch YOUR_PDB
select lig, organic
center_of_mass lig
# Use these coordinates for grid_center
```

**Method 2: Center on catalytic residues** (for enzymes)
```python
# PyMOL  
fetch YOUR_PDB
# Example: catalytic triad
select active_site, resi 103+256+272 and name CA
center_of_mass active_site
```

**Method 3: FPocket (blind pocket detection)**
```bash
# Install fpocket
conda install -c conda-forge fpocket

# Detect pockets
fpocket -f YOUR_PDB.pdb

# View results
cat YOUR_PDB_out/pockets/pocket1_atm.pdb
```

**Method 4: Blind docking with enlarged grid**
Temporarily set `grid_size` to `[60, 60, 60]` centered on the protein's
center of mass. Run a test docking, identify where the ligand clusters,
then tighten the grid around that region.

### After Refining

1. Update `grid_center` and/or `grid_size` in `targets_config.json`
2. Set `grid_validated: true`
3. Delete cached receptor files so they regenerate:
   ```bash
   rm targets/receptors/YOUR_GENE.*
   ```
4. Re-run docking to verify improved scores

---

## 🧪 Validation Targets

`targeted_genes_for_validation` contains 3 kinases with known inhibitors.
These serve as positive controls for the docking pipeline:

| Gene | PDB | Known Inhibitor | Expected Result |
|------|-----|-----------------|-----------------|
| JAK1 | 6N7A (1.33Å) | Baricitinib | Should rank in top 5 |
| BTK | 6DI5 (1.80Å) | Acalabrutinib | Should rank in top 5 |
| TYK2 | 6PW8 (1.95Å) | Deucravacitinib | **Should NOT rank highly** (deucravacitinib binds JH2, 6PW8 is JH1 — negative control for domain specificity) |

To run a validation:
```bash
python -c "
from med_research.pipeline.virtual_screening.docking import DockingEngine, prepare_ligand
engine = DockingEngine()
status = engine.get_status()
print(f'Docking possible: {status[\"docking_possible\"]}')

# Known inhibitor SMILES (from screening.py)
# Note: _DRUG_SMILES is a private variable; paste SMILES directly for stability
BARICITINIB_SMILES = 'CCS(=O)(=O)CC1=NNC(=C1)C2=C3C=CNC3=NC(=N2)C4=CC=C(C=C4)S(=O)(=O)CC'
ACALABRUTINIB_SMILES = 'CC#CC(=O)N1CCC[C@H]1C2=NC(=C3N2C=CC(=N3)C4=CC=C(C=C4)C(=O)N)C5=CC=C(C=C5)F'

baricitinib_path = prepare_ligand('baricitinib', BARICITINIB_SMILES)
acalabrutinib_path = prepare_ligand('acalabrutinib', ACALABRUTINIB_SMILES)

if baricitinib_path and acalabrutinib_path:
    engine.prepare_all_targets()
    
    # Positive control: dock baricitinib against JAK1
    result = engine.dock_target('JAK1', ['baricitinib'],
                                ligand_paths={'baricitinib': baricitinib_path})
    print(f'Baricitinib → JAK1: {result}')
    
    # Positive control: dock acalabrutinib against BTK  
    result = engine.dock_target('BTK', ['acalabrutinib'],
                                ligand_paths={'acalabrutinib': acalabrutinib_path})
    print(f'Acalabrutinib → BTK: {result}')
"
```

---

## ⚠️ Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| `docking_possible: false` | Missing deps or Vina binary | Check `pip list`, verify Vina is on PATH or in `targets/bin/` |
| `Receptor preparation failed` | PDB download failed, BioPython error | Check internet, verify PDB ID is correct on rcsb.org |
| `Ligand prep failed` | Invalid SMILES, RDKit error | Verify SMILES string, check RDKit installation |
| All Vina scores = 0 or None | Wrong grid box, Vina crash | Check `targets/docking_output/GENE/drug/vina_stdout`, refine grid |
| Vina timeout (300s) | Grid too large, exhaustiveness too high | Reduce `grid_size` or `exhaustiveness` |
| `No module named 'meeko'` | Meeko not installed | `pip install meeko` |
| `ImportError: libxcb.so.1` (Linux) | Missing Qt deps for RDKit | `sudo apt install libxcb-cursor0` or use RDKit without GUI |

---

## 📊 Score Normalization

Vina scores (ΔG in kcal/mol) are normalized to the 0-10 binding estimate
scale used by the screening engine:

| Vina Score | Normalized | Interpretation |
|-----------|-----------|----------------|
| -11.0 kcal/mol | 10.0 | Exceptional binding |
| -9.0 kcal/mol | 7.5 | Strong binding |
| -7.0 kcal/mol | 5.0 | Moderate binding |
| -5.0 kcal/mol | 0.0 | Weak or non-specific binding |

The normalization formula is:
```
normalized = min(10, max(0, (vina_score + 4.0) / -8.0 * 10.0))
```

---

## 🤝 Contributing New Targets

When adding a new docking target, please:

1. **Research the PDB thoroughly** — pick the highest-resolution structure
   with a co-crystallized inhibitor if possible
2. **Define the grid carefully** — measure from the co-crystallized ligand
   or catalytic site residues
3. **Set `grid_validated: true`** only after test-docking confirms sensible results
4. **Add Uniprot accession** for traceability
5. **Include informative notes** — drug discovery context, structural caveats,
   relevant publications

---

## 📚 References

- [AutoDock Vina Manual](https://autodock-vina.readthedocs.io/)
- [RCSB PDB](https://www.rcsb.org/)
- [Meeko Documentation](https://github.com/forlilab/Meeko)
- [RDKit Cookbook](https://www.rdkit.org/docs/Cookbook.html)
- [BioPython PDB Module](https://biopython.org/wiki/The_Biopython_Structural_Bioinformatics_FAQ)
