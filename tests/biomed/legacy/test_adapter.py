from __future__ import annotations

from med_research.biomed.legacy.adapter import LegacyMigrationAdapter

DISEASES = ["sle", "ra", "ms", "ss", "ssc", "t1d", "ibd"]


def test_build_bundle_covers_all_seven_diseases() -> None:
    bundle = LegacyMigrationAdapter().build_bundle()
    mapped = {entry["legacy_id"] for entry in bundle.metadata["diseases"]}
    assert mapped == set(DISEASES)


def test_bundle_snapshot_uses_legacy_curated_resource_name() -> None:
    bundle = LegacyMigrationAdapter().build_bundle(["sle"])
    assert bundle.snapshot.resource_name == "legacy-curated"
    assert bundle.snapshot.checksum
