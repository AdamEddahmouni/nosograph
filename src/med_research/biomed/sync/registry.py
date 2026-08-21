"""Inventory of biomedical upstream sources and sync metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceMatrixEntry:
    source: str
    domain: str
    adapter: str
    access: str
    version_mechanism: str
    license: str
    cache: str
    transforms: str
    provenance: str
    tests: str


SOURCE_MATRIX: tuple[SourceMatrixEntry, ...] = (
    SourceMatrixEntry(
        source="mondo",
        domain="disease ontology",
        adapter="MondoAdapter",
        access="local OBO-JSON artifact",
        version_mechanism="meta.version in artifact",
        license="CC-BY-4.0",
        cache="snapshot checksum in SQLite",
        transforms="entities, IS_A claims, xrefs",
        provenance="ResourceSnapshot + ImportReport fingerprint",
        tests="tests/biomed/imports/test_mondo_adapter.py",
    ),
    SourceMatrixEntry(
        source="hp / hpo",
        domain="phenotype ontology",
        adapter="HpoOntologyAdapter",
        access="local OBO-JSON artifact",
        version_mechanism="meta.version in artifact",
        license="HPO-custom",
        cache="snapshot checksum",
        transforms="phenotype entities, IS_A hierarchy",
        provenance="ResourceSnapshot",
        tests="tests/biomed/imports/test_hpo_adapter.py",
    ),
    SourceMatrixEntry(
        source="hpoa",
        domain="disease-phenotype annotations",
        adapter="HpoAnnotationAdapter",
        access="local TSV artifact",
        version_mechanism="artifact mtime / operator pin",
        license="HPO-custom",
        cache="snapshot checksum",
        transforms="HAS_PHENOTYPE claims + supporting evidence",
        provenance="ClaimEvidence.source_record_id",
        tests="tests/biomed/imports/test_hpoa_adapter.py",
    ),
    SourceMatrixEntry(
        source="go",
        domain="gene function ontology",
        adapter="GOImportAdapter",
        access="local JSON artifact",
        version_mechanism="meta.version",
        license="CC-BY-4.0",
        cache="snapshot checksum",
        transforms="pathway/function entities",
        provenance="ResourceSnapshot",
        tests="tests/biomed/imports/test_go_adapter.py",
    ),
    SourceMatrixEntry(
        source="reactome",
        domain="pathways",
        adapter="ReactomeImportAdapter",
        access="local JSON artifact",
        version_mechanism="release tag in artifact",
        license="CC-BY-4.0",
        cache="snapshot checksum",
        transforms="INVOLVES_PATHWAY claims",
        provenance="ClaimEvidence",
        tests="tests/biomed/imports/test_reactome_adapter.py",
    ),
    SourceMatrixEntry(
        source="uberon",
        domain="anatomy",
        adapter="UberonImportAdapter",
        access="local OBO-JSON artifact",
        version_mechanism="meta.version",
        license="CC-BY-4.0",
        cache="snapshot checksum",
        transforms="anatomy entities",
        provenance="ResourceSnapshot",
        tests="tests/biomed/imports/test_uberon_adapter.py",
    ),
    SourceMatrixEntry(
        source="clinvar",
        domain="variant-disease",
        adapter="ClinVarImportAdapter",
        access="local JSON artifact",
        version_mechanism="release date in artifact",
        license="NCBI-ClinVar",
        cache="snapshot checksum",
        transforms="gene association claims",
        provenance="ClaimEvidence",
        tests="tests/biomed/imports/test_clinvar_openfda_cli.py",
    ),
    SourceMatrixEntry(
        source="openfda",
        domain="drug labels",
        adapter="OpenFDAImportAdapter",
        access="local JSON artifact",
        version_mechanism="operator pin",
        license="US-public-domain",
        cache="snapshot checksum",
        transforms="TREATED_BY intervention claims",
        provenance="ClaimEvidence",
        tests="tests/biomed/imports/test_clinvar_openfda_cli.py",
    ),
    SourceMatrixEntry(
        source="open_targets",
        domain="target-disease associations",
        adapter="OpenTargetsImportAdapter + OpenTargetsSyncSource",
        access="FTP parquet bulk + GraphQL live fallback",
        version_mechanism="bulk manifest.version (e.g. 25.03)",
        license="Open-Targets-data",
        cache="parquet checksums + SyncProvenance",
        transforms="gene/phenotype/intervention claims via EFO→MONDO join",
        provenance="SyncReport + ClaimEvidence (association scores)",
        tests="tests/biomed/sync/test_opentargets_sync.py",
    ),
    SourceMatrixEntry(
        source="pubmed",
        domain="literature",
        adapter="pipeline/evidence_workspace/sources",
        access="Entrez API (ENTREZ_EMAIL)",
        version_mechanism="live retrieval timestamp",
        license="NCBI-terms",
        cache="pipeline cache dir",
        transforms="EvidenceRecord → Claim (workspace)",
        provenance="build_provenance() fingerprint",
        tests="tests/test_evidence_gatherer.py",
    ),
    SourceMatrixEntry(
        source="clinicaltrials_gov",
        domain="trials",
        adapter="pipeline/external/clinicaltrials",
        access="ClinicalTrials.gov v2 API",
        version_mechanism="live API",
        license="CT.gov-terms",
        cache="pipeline cache",
        transforms="trial EvidenceRecord",
        provenance="build_provenance()",
        tests="tests/test_pipeline_contracts.py",
    ),
    SourceMatrixEntry(
        source="chembl / pubchem",
        domain="compounds",
        adapter="ChEMBLImportAdapter / PubChemImportAdapter",
        access="local JSON or live API",
        version_mechanism="release / operator pin",
        license="EBI-ChEMBL / NCBI-PubChem",
        cache="snapshot or live cache",
        transforms="intervention entities",
        provenance="ResourceSnapshot",
        tests="tests/biomed/test_live_api_adapters.py",
    ),
    SourceMatrixEntry(
        source="legacy curated modules",
        domain="disease KG projections",
        adapter="LegacyMigrationAdapter",
        access="repo disease JSON bundles",
        version_mechanism="git commit short hash",
        license="Apache-2.0 (repo) + upstream refs",
        cache="legacy-curated snapshot",
        transforms="claims from relationships.json",
        provenance="ResourceSnapshot + parity report",
        tests="tests/biomed/legacy/test_adapter.py",
    ),
)


def list_syncable_sources() -> list[str]:
    return ["open_targets"]
