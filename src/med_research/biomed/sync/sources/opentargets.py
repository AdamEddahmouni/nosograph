"""Open Targets Platform sync source — vertical slice for bulk parquet ingestion."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from med_research.biomed.identifiers import fingerprint_json
from med_research.biomed.imports.models import ImportBundle
from med_research.biomed.imports.opentargets_adapter import OpenTargetsImportAdapter
from med_research.biomed.models import ResourcePolicy
from med_research.biomed.sync.models import SyncDiff, SyncProvenance, SyncStage
from med_research.diseases.bulk_store import manifest_path


class OpenTargetsSyncSource:
    source_id = "open_targets"
    resource_name = "open_targets"

    def __init__(
        self,
        *,
        bulk_root: Path | None = None,
        fixtures_root: Path | None = None,
    ) -> None:
        from med_research.diseases.bulk_store import default_bulk_root

        self._bulk_root = bulk_root or default_bulk_root()
        self._fixtures_root = fixtures_root or Path("tests/fixtures/opentargets")

    @property
    def policy(self) -> ResourcePolicy:
        return ResourcePolicy(
            resource_name=self.resource_name,
            license_id="Open-Targets-data",
            license_url="https://platform.opentargets.org/downloads",
            redistribution_policy="user_supplied",
        )

    def discover_version(self, *, staging_root: Path) -> str:
        manifest = self._bulk_root.parent / "manifest.json"
        if manifest.is_file():
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            version = str(payload.get("version") or "")
            if version:
                return version
        fixture_version = next(
            (path.name for path in self._fixtures_root.iterdir() if path.is_dir()),
            "25.03",
        )
        return fixture_version

    def fetch(self, *, staging_root: Path, version: str, dry_run: bool) -> Path:
        target = staging_root / version
        manifest = manifest_path(self._bulk_root)
        live = self._bulk_root / version
        manifest_text = manifest.read_text(encoding="utf-8") if manifest.is_file() else ""
        production_bulk = (
            manifest.is_file()
            and "test-fixtures" not in manifest_text
            and "fixtures" not in manifest_text
            and staging_root.name == "sync"
        )
        if not dry_run and production_bulk and live.is_dir() and any(live.rglob("*.parquet")):
            return self._bulk_root
        if dry_run and (self._fixtures_root / version).is_dir():
            return self._fixtures_root
        fixture_src = self._fixtures_root / version
        if not fixture_src.is_dir():
            raise FileNotFoundError(
                f"No Open Targets bulk data at {live} and fixtures missing at {fixture_src}"
            )
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(fixture_src, target)
        manifest_payload = {
            "version": version,
            "created_at": datetime.now(UTC).isoformat(),
            "source": "fixtures",
            "tables": ["disease", "association_overall_direct", "known_drug", "disease_phenotype"],
            "path": str(target),
        }
        manifest_path_out = staging_root.parent / "manifest.json"
        manifest_path_out.parent.mkdir(parents=True, exist_ok=True)
        manifest_path_out.write_text(
            json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8"
        )
        return staging_root.parent

    def verify(self, artifact_root: Path) -> dict[str, str]:
        checksums: dict[str, str] = {}
        from med_research.biomed.imports.models import _artifact_checksum

        manifest = artifact_root / "manifest.json"
        if manifest.is_file():
            checksums["manifest.json"] = _artifact_checksum(manifest)
        version = self.discover_version(staging_root=artifact_root)
        data_dir = (
            artifact_root / version
            if (artifact_root / version).is_dir()
            else artifact_root / "opentargets" / version
        )
        if not data_dir.is_dir():
            data_dir = self._fixtures_root / version
        for parquet in sorted(data_dir.rglob("*.parquet")):
            checksums[str(parquet.relative_to(data_dir))] = _artifact_checksum(parquet)
        if not checksums:
            raise ValueError(f"No parquet artifacts verified under {artifact_root}")
        return checksums

    def normalize(
        self,
        artifact_root: Path,
        *,
        version: str,
        mondo_mappings: dict[str, str] | None = None,
    ) -> ImportBundle:
        if (artifact_root / version).is_dir():
            bulk_root = artifact_root
        elif (artifact_root / "opentargets" / version).is_dir():
            bulk_root = artifact_root / "opentargets"
        elif (self._fixtures_root / version).is_dir():
            bulk_root = self._fixtures_root
        else:
            bulk_root = artifact_root / "opentargets"
        adapter = OpenTargetsImportAdapter()
        return adapter.parse_bulk(
            bulk_root,
            self.policy,
            version=version,
            mondo_mappings=mondo_mappings,
        )

    def diff(
        self,
        bundle: ImportBundle,
        *,
        previous_checksum: str | None,
        previous_counts: dict[str, int] | None,
    ) -> SyncDiff:
        current_counts = {
            "claims": bundle.counts.claims,
            "evidence": bundle.counts.evidence,
        }
        counts_delta: dict[str, int] = {}
        if previous_counts:
            for key, value in current_counts.items():
                counts_delta[key] = value - int(previous_counts.get(key, 0))
        changed = previous_checksum != bundle.snapshot.checksum
        return SyncDiff(
            previous_checksum=previous_checksum,
            current_checksum=bundle.snapshot.checksum,
            counts_delta=counts_delta,
            changed=changed or bool(counts_delta),
        )

    def build_provenance(
        self,
        bundle: ImportBundle,
        *,
        stages_completed: list[str],
    ) -> SyncProvenance:
        payload = {
            "resource_name": bundle.snapshot.resource_name,
            "version": bundle.snapshot.version,
            "checksum": bundle.snapshot.checksum,
            "counts": bundle.counts.model_dump(),
            "stages": stages_completed,
        }
        return SyncProvenance(
            source_id=self.source_id,
            resource_name=self.resource_name,
            upstream_version=bundle.snapshot.upstream_version or bundle.snapshot.version,
            checksum=bundle.snapshot.checksum,
            snapshot_id=bundle.snapshot.id,
            manifest_fingerprint=fingerprint_json(payload),
            retrieved_at=datetime.now(UTC),
            importer_name="OpenTargetsSyncSource",
            importer_version="1.0.0",
            stages_completed=[SyncStage(item) for item in stages_completed],
        )
