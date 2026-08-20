import pytest

from med_research.pipeline.spatial_transcriptomics import (
    compute_morans_i,
    parse_visium_csv,
    score_ligand_receptor_colocalization,
)


@pytest.mark.unit
def test_parse_visium_csv(tmp_path):
    csv_file = tmp_path / "tissue_positions_list.csv"
    csv_file.write_text(
        "barcode,in_tissue,array_row,array_col,pixel_x,pixel_y\n"
        "AAACAACGAATAGTTC-1,1,0,0,100,100\n"
        "AAACAAGTATCTCCCA-1,1,0,1,100,200\n"
        "AAACACCAAMTTTACT-1,0,1,0,200,100\n",
        encoding="utf-8",
    )
    spots = parse_visium_csv(csv_file)
    assert len(spots) == 3
    assert spots[0]["barcode"] == "AAACAACGAATAGTTC-1"
    assert spots[0]["in_tissue"] == "1"


@pytest.mark.unit
def test_compute_morans_i():
    coords = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (10.0, 10.0), (11.0, 10.0)]
    # Clustered high values near (0,0) and low values near (10,10)
    values = [10.0, 9.5, 9.8, 1.0, 1.2]
    moran = compute_morans_i(coords, values, distance_threshold=5.0)
    assert moran > 0.0


@pytest.mark.unit
def test_ligand_receptor_colocalization():
    coords = [(0.0, 0.0), (1.0, 1.0), (100.0, 100.0)]
    ligand = [5.0, 0.0, 0.0]
    receptor = [0.0, 4.0, 0.0]
    score = score_ligand_receptor_colocalization(coords, ligand, receptor, radius=10.0)
    assert score > 0.0
