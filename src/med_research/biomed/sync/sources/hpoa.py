"""HPO disease-annotation (HPOA) sync source backed by an operator-supplied TSV.

Unlike the Open Targets source, HPOA has no automated download path in NosoGraph.
The annotation file is supplied by the operator (``data/bulk/hpoa/*.tsv`` by
default) and staged as-is; the sync lifecycle only adds version discovery,
artifact verification, provenance, and the ``HAS_PHENOTYPE`` normalization that
``HpoAnnotationAdapter`` already owns.

Version semantics are deliberately conservative:

* an explicit operator pin (``VERSION`` next to the artifact, or in
  ``data/bulk/hpoa/``) wins, because it is the only value that can name a real
  HPO release;
* otherwise the artifact's mtime in nanoseconds is used as a local token;
* when no artifact exists at all, :meth:`HpoaSyncSource.discover_version` raises
  instead of inventing an upstream release number.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from med_research.biomed.identifiers import fingerprint_json
from med_research.biomed.imports.hpoa import HpoAnnotationAdapter
from med_research.biomed.imports.models import ImportBundle, _artifact_checksum
from med_research.biomed.models import ResourcePolicy
from med_research.biomed.sync.models import SyncDiff, SyncProvenance, SyncStage


class HpoaSyncSource:
    """Sync lifecycle for the HPO disease-phenotype annotation file."""

    source_id = "hpoa"
    resource_name = "hpoa"

    DEFAULT_ARTIFACT_DIR = Path("data/bulk/hpoa")
    VERSION_PIN_NAME = "VERSION"

    def __init__(
        self,
        *,
        artifact_path: Path | None = None,
        fixtures_root: Path | None = None,
    ) -> None:
        self._artifact_path = artifact_path
        self._fixtures_root = fixtures_root or Path("tests/fixtures/biomed/hpoa")

    @property
    def artifact_path(self) -> Path:
        """Operator artifact when configured, else the first bulk TSV, else the fixture."""
        if self._artifact_path is not None:
            return self._artifact_path
        if self.DEFAULT_ARTIFACT_DIR.is_dir():
            candidates = sorted(self.DEFAULT_ARTIFACT_DIR.glob("*.tsv"))
            if candidates:
                return candidates[0]
        return self._fixtures_root / "minimal.tsv"

    @property
    def policy(self) -> ResourcePolicy:
        return ResourcePolicy(
            resource_name=self.resource_name,
            license_id="HPO-custom",
            license_url="https://hpo.jax.org/",
            redistribution_policy="user_supplied",
        )

    def discover_version(self, *, staging_root: Path) -> str:
        """Return the operator pin, else a local mtime token; never a guessed release."""
        artifact = self.artifact_path
        pin = self._version_pin(artifact)
        if pin is not None:
            version = pin.read_text(encoding="utf-8").strip()
            if version:
                return version
        if artifact.is_file():
            return f"mtime-{artifact.stat().st_mtime_ns}"
        raise FileNotFoundError(
            f"HPOA artifact not found at {artifact}. Place the HPO disease-annotation TSV "
            f"there, add a {self.VERSION_PIN_NAME} pin file, or pass artifact_path=..."
        )

    def fetch(self, *, staging_root: Path, version: str, dry_run: bool) -> Path:
        """Stage the operator artifact. HPOA is never downloaded."""
        artifact = self.artifact_path
        if not artifact.is_file():
            raise FileNotFoundError(
                f"HPOA artifact not found at {artifact}; HPOA is operator-supplied and "
                "NosoGraph does not download it automatically"
            )
        if dry_run:
            return artifact.parent

        target_dir = staging_root / version
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(artifact, target_dir / artifact.name)
        pin = self._version_pin(artifact)
        if pin is not None:
            shutil.copy2(pin, target_dir / self.VERSION_PIN_NAME)
        return staging_root

    def verify(self, artifact_root: Path) -> dict[str, str]:
        """Checksum the staged TSV (and the version pin when present)."""
        tsv = self._locate_tsv(artifact_root)
        if tsv is None:
            raise ValueError(
                f"No HPOA artifact found under {artifact_root}; expected a .tsv annotation file"
            )
        checksums = {tsv.name: _artifact_checksum(tsv)}
        pin = artifact_root / self.VERSION_PIN_NAME
        if pin.is_file():
            checksums[self.VERSION_PIN_NAME] = _artifact_checksum(pin)
        return checksums

    def normalize(
        self,
        artifact_root: Path,
        *,
        version: str,
        mondo_mappings: dict[str, str] | None = None,
    ) -> ImportBundle:
        """Delegate row parsing to ``HpoAnnotationAdapter`` so mapping rules stay single-sourced."""
        tsv = self._locate_tsv(artifact_root)
        if tsv is None:
            raise FileNotFoundError(
                f"No HPOA TSV under {artifact_root}; cannot normalize version {version}"
            )
        return HpoAnnotationAdapter().parse(tsv, self.policy, mondo_mappings=mondo_mappings)

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
            importer_name="HpoaSyncSource",
            importer_version="1.0.0",
            stages_completed=[SyncStage(item) for item in stages_completed],
        )

    def _version_pin_candidates(self, artifact: Path) -> list[Path]:
        candidates = [artifact.parent / self.VERSION_PIN_NAME]
        bulk_pin = self.DEFAULT_ARTIFACT_DIR / self.VERSION_PIN_NAME
        if bulk_pin not in candidates:
            candidates.append(bulk_pin)
        return candidates

    def _version_pin(self, artifact: Path) -> Path | None:
        for candidate in self._version_pin_candidates(artifact):
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _locate_tsv(artifact_root: Path) -> Path | None:
        if artifact_root.is_file():
            return artifact_root if artifact_root.suffix == ".tsv" else None
        if not artifact_root.is_dir():
            return None
        candidates = sorted(artifact_root.glob("*.tsv")) + sorted(artifact_root.glob("*/*.tsv"))
        return candidates[0] if candidates else None
