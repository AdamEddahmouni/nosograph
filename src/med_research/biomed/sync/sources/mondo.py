"""MONDO disease-ontology sync source backed by a local OBO-JSON artifact.

Unlike the Open Targets source, MONDO has no automated download path in
NosoGraph. The ontology artifact is supplied by the operator
(``data/bulk/mondo/*.json`` by default) or taken from the checked-in minimal
fixture, and staged as-is; the sync lifecycle only adds version discovery,
artifact verification, provenance, and an inspection summary. Concept,
hierarchy, and cross-reference normalization stay single-sourced in
:class:`~med_research.biomed.imports.mondo.MondoAdapter`, so this module never
re-derives mapping rules.

Version semantics:

* ``meta.version`` inside the artifact wins — it is the only value that names a
  real MONDO release;
* when the artifact carries no ``meta.version``, an explicit operator pin
  (``VERSION`` next to the artifact, or in ``data/bulk/mondo/``) is used;
* when neither exists :meth:`MondoSyncSource.discover_version` raises instead of
  inventing an upstream release number.

Obsolescence policy: obsolete concepts stay in the bundle with
``EntityRevision.obsolete=True`` plus their published ``replaced_by`` /
``consider`` values. They are never rewritten onto an active concept and never
collapsed by string similarity. Active-concept resolution must filter on
``EntityRevision.obsolete``.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from med_research.biomed.errors import BiomedicalValidationError
from med_research.biomed.identifiers import fingerprint_json
from med_research.biomed.imports.models import ImportBundle, _artifact_checksum
from med_research.biomed.imports.mondo import MondoAdapter
from med_research.biomed.models import ResourcePolicy
from med_research.biomed.sync.models import SyncDiff, SyncProvenance, SyncStage

# Count keys reported by ``diff``; iterated in a fixed order so repeated runs
# produce byte-identical output.
_COUNT_KEYS: tuple[str, ...] = (
    "entities",
    "entity_revisions",
    "mappings",
    "claims",
    "evidence",
)


class MondoSyncSource:
    """Sync lifecycle for the Mondo Disease Ontology artifact."""

    source_id = "mondo"
    resource_name = "mondo"

    DEFAULT_ARTIFACT_DIR = Path("data/bulk/mondo")
    VERSION_PIN_NAME = "VERSION"
    IMPORTER_VERSION = "1.0.0"

    def __init__(
        self,
        *,
        artifact_path: Path | None = None,
        fixtures_root: Path | None = None,
        expected_checksums: Iterable[str] | None = None,
    ) -> None:
        self._artifact_path = artifact_path
        self._fixtures_root = fixtures_root or Path("tests/fixtures/biomed/mondo")
        self._expected_checksums = (
            frozenset(value for value in expected_checksums if value)
            if expected_checksums is not None
            else None
        )
        # (mtime_ns, size) -> version, so discovery does not re-read a large artifact.
        self._version_cache: dict[tuple[int, int], str] = {}

    @property
    def artifact_path(self) -> Path:
        """Operator artifact when configured, else the first bulk JSON, else the fixture."""
        if self._artifact_path is not None:
            return self._artifact_path
        if self.DEFAULT_ARTIFACT_DIR.is_dir():
            candidates = sorted(self.DEFAULT_ARTIFACT_DIR.glob("*.json"))
            if candidates:
                return candidates[0]
        return self._fixtures_root / "minimal.json"

    @property
    def policy(self) -> ResourcePolicy:
        return ResourcePolicy(
            resource_name=self.resource_name,
            license_id="CC-BY-4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            redistribution_policy="permitted",
        )

    def discover_version(self, *, staging_root: Path) -> str:
        """Return ``meta.version`` from the artifact, else the operator pin.

        ``staging_root`` is accepted for protocol symmetry with the other
        sources; MONDO discovery reads the artifact itself.
        """
        del staging_root
        artifact = self.artifact_path
        if not artifact.is_file():
            raise FileNotFoundError(
                f"MONDO artifact not found at {artifact}. Place the Mondo OBO-JSON "
                f"artifact there, add a {self.VERSION_PIN_NAME} pin file, or pass "
                "artifact_path=..."
            )
        stat = artifact.stat()
        cache_key = (stat.st_mtime_ns, stat.st_size)
        cached = self._version_cache.get(cache_key)
        if cached is not None:
            return cached

        version = self._artifact_version(artifact)
        if not version:
            pin = self._version_pin(artifact)
            if pin is not None:
                version = pin.read_text(encoding="utf-8").strip()
        if not version:
            raise BiomedicalValidationError(
                f"MONDO artifact {artifact} declares no meta.version and no "
                f"{self.VERSION_PIN_NAME} pin exists; refusing to invent an upstream release"
            )
        self._version_cache[cache_key] = version
        return version

    def fetch(self, *, staging_root: Path, version: str, dry_run: bool) -> Path:
        """Stage the operator artifact. MONDO is never downloaded."""
        artifact = self.artifact_path
        if not artifact.is_file():
            raise FileNotFoundError(
                f"MONDO artifact not found at {artifact}; MONDO is operator-supplied and "
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
        """Checksum the staged artifact (and the version pin when present).

        When ``expected_checksums`` was supplied, a mismatch raises instead of
        being reported as a passing verification. No checksum is ever fabricated.
        """
        artifact = self._locate_json(artifact_root)
        if artifact is None:
            raise ValueError(
                f"No MONDO artifact found under {artifact_root}; expected an OBO-JSON .json file"
            )
        checksum = _artifact_checksum(artifact)
        if self._expected_checksums is not None and checksum not in self._expected_checksums:
            pinned = ", ".join(sorted(self._expected_checksums)) or "(none supplied)"
            raise ValueError(
                f"MONDO artifact checksum {checksum} for {artifact.name} does not match "
                f"any pinned checksum: {pinned}"
            )
        checksums = {artifact.name: checksum}
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
        """Delegate parsing to ``MondoAdapter`` so mapping rules stay single-sourced.

        ``mondo_mappings`` is accepted for protocol symmetry and ignored: MONDO is
        the source of those mappings, so consuming them here would be circular.
        """
        del mondo_mappings
        artifact = self._locate_json(artifact_root)
        if artifact is None:
            raise FileNotFoundError(
                f"No MONDO artifact under {artifact_root}; cannot normalize version {version}"
            )
        bundle = MondoAdapter().parse(artifact, self.policy)
        if not bundle.entities:
            raise BiomedicalValidationError(
                f"MONDO artifact {artifact} produced no condition entities; expected "
                "OBO-JSON nodes under graphs[0].nodes"
            )
        summary = _summarize(bundle)
        return bundle.model_copy(update={"metadata": {**bundle.metadata, **summary}})

    def diff(
        self,
        bundle: ImportBundle,
        *,
        previous_checksum: str | None,
        previous_counts: dict[str, int] | None,
    ) -> SyncDiff:
        """Return a deterministic diff: fixed key order, no timestamped values."""
        current_counts = _current_counts(bundle)
        counts_delta: dict[str, int] = {}
        if previous_counts:
            for key in _COUNT_KEYS:
                counts_delta[key] = current_counts[key] - int(previous_counts.get(key, 0))
        changed = previous_checksum != bundle.snapshot.checksum
        return SyncDiff(
            previous_checksum=previous_checksum,
            current_checksum=bundle.snapshot.checksum,
            # Sorted so the serialized diff is canonical, not merely stable.
            counts_delta=dict(sorted(counts_delta.items())),
            changed=changed or any(value != 0 for value in counts_delta.values()),
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
            "upstream_version": bundle.snapshot.upstream_version,
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
            importer_name="MondoSyncSource",
            importer_version=self.IMPORTER_VERSION,
            stages_completed=[SyncStage(item) for item in stages_completed],
        )

    def _artifact_version(self, artifact: Path) -> str:
        from med_research.biomed.imports.json_io import load_json

        payload = load_json(artifact)
        if not isinstance(payload, dict):
            raise BiomedicalValidationError(
                f"MONDO artifact {artifact} is not a JSON object; expected OBO-JSON"
            )
        meta = payload.get("meta")
        version = str(meta.get("version", "")) if isinstance(meta, dict) else ""
        return version.strip()

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

    def _locate_json(self, artifact_root: Path) -> Path | None:
        artifact = self.artifact_path
        if artifact.is_file():
            try:
                artifact.resolve().relative_to(artifact_root.resolve())
            except ValueError:
                pass
            else:
                return artifact
        if artifact_root.is_file():
            return artifact_root if artifact_root.suffix == ".json" else None
        if not artifact_root.is_dir():
            return None
        candidates = sorted(artifact_root.glob("*.json")) + sorted(artifact_root.glob("*/*.json"))
        return candidates[0] if candidates else None


def _current_counts(bundle: ImportBundle) -> dict[str, int]:
    counts = bundle.counts
    return {
        "entities": counts.entities,
        "entity_revisions": counts.entity_revisions,
        "mappings": counts.mappings,
        "claims": counts.claims,
        "evidence": counts.evidence,
    }


def _summarize(bundle: ImportBundle) -> dict[str, Any]:
    """Describe obsolescence and cross-references without altering any record.

    Every value is derived from the parsed bundle; nothing is inferred. Lists are
    sorted and mapping counts are key-sorted so the metadata is deterministic.
    """
    curie_by_entity_id = {entity.id: entity.primary_curie for entity in bundle.entities}
    obsolete_entity_ids = {revision.entity_id for revision in bundle.revisions if revision.obsolete}
    active_curies = {
        entity.primary_curie for entity in bundle.entities if entity.id not in obsolete_entity_ids
    }

    obsolete_concepts = 0
    obsolete_with_replacement = 0
    missing_targets: set[str] = set()
    without_replacement: list[str] = []
    ordered_revisions = sorted(
        bundle.revisions, key=lambda revision: curie_by_entity_id.get(revision.entity_id, "")
    )
    for revision in ordered_revisions:
        if not revision.obsolete:
            continue
        obsolete_concepts += 1
        curie = curie_by_entity_id.get(revision.entity_id, "")
        if revision.replaced_by:
            obsolete_with_replacement += 1
            if revision.replaced_by not in active_curies:
                missing_targets.add(revision.replaced_by)
        elif not revision.consider:
            without_replacement.append(curie)

    prefix_counts: dict[str, int] = {}
    for mapping in bundle.mappings:
        prefix = mapping.object_curie.split(":", 1)[0]
        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1

    return {
        "ontology": "MONDO",
        "concept_curie_pattern": "MONDO:NNNNNNN",
        "active_concepts": len(active_curies),
        "obsolete_concepts": obsolete_concepts,
        "obsolete_with_replacement": obsolete_with_replacement,
        "obsolete_without_replacement": sorted(without_replacement),
        "obsolete_replacement_targets_missing": sorted(missing_targets),
        "xref_mapping_counts": {key: prefix_counts[key] for key in sorted(prefix_counts)},
    }
