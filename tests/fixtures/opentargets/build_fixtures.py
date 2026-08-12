"""Build minimal Open Targets parquet fixtures for offline tests."""

from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "25.03"
VERSION = "25.03"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "disease").mkdir(exist_ok=True)
    con = duckdb.connect()

    # disease
    con.execute(
        """
        CREATE OR REPLACE TABLE disease AS
        SELECT * FROM (
            VALUES
            ('EFO_0001370', 'Rheumatoid Arthritis', 'Chronic inflammatory joint disease.', '["RA","Rheumatoid arthritis"]'),
            ('EFO_0000384', 'Crohn disease', 'Inflammatory bowel disease.', '["Crohn''s disease"]'),
            ('EFO_0005855', 'psoriatic arthritis', 'Arthritis associated with psoriasis.', '[]')
        ) AS t(id, name, description, synonyms)
        """
    )
    con.execute(f"COPY disease TO '{OUT / 'disease' / 'disease.parquet'}' (FORMAT PARQUET)")

    # association_overall_direct
    (OUT / "association_overall_direct").mkdir(exist_ok=True)
    con.execute(
        """
        CREATE OR REPLACE TABLE assoc AS
        SELECT * FROM (
            VALUES
            ('EFO_0001370', 0.97, 'ENSG00000232810', 'TNF', 'Tumor necrosis factor', 'protein_coding'),
            ('EFO_0001370', 0.90, 'ENSG00000175084', 'IL6R', 'Interleukin-6 receptor', 'protein_coding'),
            ('EFO_0001370', 0.80, 'ENSG00000138378', 'STAT4', 'STAT4', 'protein_coding'),
            ('EFO_0001370', 0.75, 'ENSG00000134242', 'PTPN22', 'PTPN22', 'protein_coding'),
            ('EFO_0001370', 0.70, 'ENSG00000096968', 'JAK2', 'JAK2', 'protein_coding'),
            ('EFO_0000384', 0.85, 'ENSG00000170458', 'NOD2', 'NOD2', 'protein_coding')
        ) AS t(diseaseId, score, targetId, approvedSymbol, approvedName, biotype)
        """
    )
    con.execute(
        f"COPY assoc TO '{OUT / 'association_overall_direct' / 'association.parquet'}' (FORMAT PARQUET)"
    )

    # known_drug
    (OUT / "known_drug").mkdir(exist_ok=True)
    con.execute(
        """
        CREATE OR REPLACE TABLE drugs AS
        SELECT * FROM (
            VALUES
            ('EFO_0001370', 'CHEMBL1201581', 'Adalimumab', 'Antibody', 0, 'Approved', 'TNF', 'TNF-alpha inhibitor'),
            ('EFO_0001370', 'CHEMBL2073839', 'Baricitinib', 'Small molecule', 3, 'Phase 3', 'JAK1', 'JAK inhibitor'),
            ('EFO_0000384', 'CHEMBL1201581', 'Adalimumab', 'Antibody', 0, 'Approved', 'TNF', 'TNF-alpha inhibitor')
        ) AS t(diseaseId, drugId, drugName, drugType, phase, status, targetSymbol, mechanism)
        """
    )
    con.execute(f"COPY drugs TO '{OUT / 'known_drug' / 'known_drug.parquet'}' (FORMAT PARQUET)")

    # disease_phenotype
    (OUT / "disease_phenotype").mkdir(exist_ok=True)
    con.execute(
        """
        CREATE OR REPLACE TABLE pheno AS
        SELECT * FROM (
            VALUES
            ('EFO_0001370', 'HP:0001369', 'Arthritis', 5.0),
            ('EFO_0001370', 'HP:0002829', 'Joint stiffness', 4.0),
            ('EFO_0000384', 'HP:0002027', 'Abdominal pain', 4.5)
        ) AS t(diseaseId, phenotypeId, phenotypeLabel, frequency)
        """
    )
    con.execute(
        f"COPY pheno TO '{OUT / 'disease_phenotype' / 'disease_phenotype.parquet'}' (FORMAT PARQUET)"
    )

    con.close()
    print(f"Fixtures written to {OUT}")


if __name__ == "__main__":
    main()
