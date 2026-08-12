from __future__ import annotations

from pathlib import Path

from med_research.biomed.imports.models import ImportRecordCounts, ImportReport
from med_research.biomed.imports.mondo import MondoAdapter
from med_research.biomed.models import ResourcePolicy


def mondo_policy() -> ResourcePolicy:
    return ResourcePolicy(
        resource_name="mondo",
        license_id="CC-BY-4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        redistribution_policy="redistributable",
    )


def test_import_bundle_requires_snapshot_and_checksum() -> None:
    bundle = MondoAdapter().parse(
        Path("tests/fixtures/biomed/mondo/minimal.json"),
        policy=mondo_policy(),
    )
    assert bundle.snapshot.checksum
    assert bundle.snapshot.resource_name == "mondo"
    assert bundle.counts.entity_revisions >= 1


def test_import_report_records_warnings_and_fingerprint() -> None:
    from uuid import uuid4

    report = ImportReport.empty("mondo")
    report = report.add_warning("unresolved_mapping", "OMIM:12345 has no exact Mondo join")
    dumped = report.to_dict()
    assert dumped["warnings"]
    assert dumped["fingerprint"] == ""

    report = report.with_snapshot(uuid4(), ImportRecordCounts(entity_revisions=1))
    dumped = report.to_dict()
    assert dumped["fingerprint"]
