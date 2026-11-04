"""Resolve PMIDs, DOIs, and ClinVar IDs and fail on dead identifiers.

This is the runtime companion to the evidence-density gate. Density answers
"does a record carry an identifier?"; this check answers "does that identifier
still resolve?". It deliberately checks only identifiers declared in the
reference and CI-validated disease sets, so CI does not walk the 10k scaffold
registry or depend on every module having curated provenance.

Exit codes:
    0  every declared identifier resolved
    1  at least one identifier is dead or could not be checked
    2  the selection or data could not be read

The checker is fail-closed: a transient upstream failure after retries is an
error, not a pass. PMIDs and ClinVar IDs are batched through NCBI E-utilities;
DOIs use the DOI Handle API.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Sequence

ROOT = Path(__file__).resolve().parents[1]
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DOI_API = "https://doi.org/api/handles/"
USER_AGENT = "NosoGraph-reference-check/1.0"

ResolutionStatus = Literal["resolved", "dead", "error"]
RequestJson = Callable[..., dict[str, Any] | None]

_PMID_PATTERN = re.compile(r"\bPMID\s*[:_]?\s*(\d+)", re.IGNORECASE)
_CLINVAR_PATTERN = re.compile(r"\bCLINVAR\s*[:_]?\s*(\d+)", re.IGNORECASE)
_DOI_PATTERN = re.compile(r"\b(10\.\d{4,9}/[^\s,;\]\)]+)", re.IGNORECASE)
_DOI_TRAILING = ".,;:]}"

Collections = (
    ("genes", "load_genes"),
    ("drugs", "load_drugs"),
    ("pathways", "load_pathways"),
)


class ResolutionError(RuntimeError):
    """An upstream request could not be completed after retries."""


@dataclass(frozen=True)
class Occurrence:
    """Where a declared identifier appears in the disease corpus."""

    disease_id: str
    collection: str
    record_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "disease_id": self.disease_id,
            "collection": self.collection,
            "record_id": self.record_id,
        }


@dataclass
class Identifier:
    """A deduplicated identifier with every record that declares it."""

    scheme: str
    value: str
    occurrences: set[Occurrence] = field(default_factory=set)


@dataclass(frozen=True)
class Resolution:
    """One identifier's resolution result."""

    scheme: str
    value: str
    status: ResolutionStatus
    detail: str = ""


def extract_identifiers(reference: str) -> list[tuple[str, str]]:
    """Extract all supported identifier schemes from one reference string.

    The parser is deliberately tolerant of the free-text forms already present
    in the corpus (``PMID:123``, ``PMID 123``, ``DOI:10...``, and
    ``CLINVAR:7105``). It never invents an identifier from a bare word.
    """
    text = str(reference)
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(scheme: str, value: str) -> None:
        item = (scheme, value)
        if item not in seen:
            seen.add(item)
            found.append(item)

    for match in _PMID_PATTERN.finditer(text):
        add("PMID", match.group(1))
    for match in _CLINVAR_PATTERN.finditer(text):
        add("CLINVAR", match.group(1))
    for match in _DOI_PATTERN.finditer(text):
        doi = match.group(1).rstrip(_DOI_TRAILING)
        if doi:
            add("DOI", doi)
    return found


def _append_identifier(
    by_key: dict[tuple[str, str], Identifier],
    scheme: str,
    value: str,
    occurrence: Occurrence,
) -> None:
    value = str(value).strip()
    if not value:
        return
    key = (scheme, value)
    identifier = by_key.setdefault(key, Identifier(scheme=scheme, value=value))
    identifier.occurrences.add(occurrence)


def collect_identifiers(disease_ids: Sequence[str]) -> list[Identifier]:
    """Collect declared PMID/DOI/ClinVar identifiers from disease records."""
    from med_research.diseases.base import Disease

    by_key: dict[tuple[str, str], Identifier] = {}
    for disease_id in disease_ids:
        disease = Disease(disease_id)
        for collection, accessor in Collections:
            payload = getattr(disease, accessor)()
            records = payload.get(collection) or []
            for record in records:
                record_id = str(record.get("id") or record.get("name") or "unknown")
                occurrence = Occurrence(disease_id, collection, record_id)
                references = record.get("references") or []
                if isinstance(references, str):
                    references = [references]
                for reference in references:
                    for scheme, value in extract_identifiers(str(reference)):
                        _append_identifier(by_key, scheme, value, occurrence)
                variants = record.get("variants") or []
                if isinstance(variants, dict):
                    variants = [variants]
                for variant in variants:
                    clinvar_id = variant.get("clinvar_id")
                    if clinvar_id:
                        _append_identifier(by_key, "CLINVAR", str(clinvar_id), occurrence)
                    variant_refs = variant.get("references") or []
                    if isinstance(variant_refs, str):
                        variant_refs = [variant_refs]
                    for reference in variant_refs:
                        for scheme, value in extract_identifiers(str(reference)):
                            _append_identifier(by_key, scheme, value, occurrence)

    return sorted(by_key.values(), key=lambda item: (item.scheme, item.value))


def _chunks(values: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _request_json(
    url: str,
    *,
    timeout: float,
    sleeper: Callable[[float], None] = time.sleep,
    attempts: int = 3,
) -> dict[str, Any] | None:
    """Fetch a JSON object, retrying transient failures.

    ``None`` means a definitive HTTP 404 (the identifier does not exist).
    Repeated 429/5xx/network failures raise :class:`ResolutionError`; a checker
    must not turn an upstream outage into a clean bill of health.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ResolutionError(f"non-object JSON from {url}")
                return payload
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            retryable = exc.code in {429, 500, 502, 503, 504}
            if retryable and attempt < attempts - 1:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    delay = float(retry_after) if retry_after else 2.0 * (attempt + 1)
                except ValueError:
                    delay = 2.0 * (attempt + 1)
                sleeper(delay)
                continue
            raise ResolutionError(f"HTTP {exc.code} from {url}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            if attempt < attempts - 1:
                sleeper(2.0 * (attempt + 1))
                continue
            raise ResolutionError(f"{type(exc).__name__}: {exc}") from exc

    raise ResolutionError(f"request retries exhausted for {url}")


def _ncbi_url(db: str, ids: Sequence[str]) -> str:
    params = {
        "db": db,
        "id": ",".join(ids),
        "retmode": "json",
        "tool": "nosograph",
    }
    email = os.environ.get("NCBI_EMAIL")
    if email:
        params["email"] = email
    return f"{EUTILS}/esummary.fcgi?{urllib.parse.urlencode(params)}"


def _resolve_ncbi(
    values: Sequence[str],
    *,
    scheme: str,
    db: str,
    request: RequestJson,
    timeout: float,
    sleeper: Callable[[float], None],
    batch_size: int,
) -> dict[str, Resolution]:
    results: dict[str, Resolution] = {}
    for batch in _chunks(list(values), max(1, batch_size)):
        try:
            payload = request(_ncbi_url(db, batch), timeout=timeout, sleeper=sleeper)
        except ResolutionError as exc:
            for value in batch:
                results[value] = Resolution(scheme, value, "error", str(exc))
            continue

        if payload is None:
            for value in batch:
                results[value] = Resolution(scheme, value, "error", "empty NCBI response")
            continue

        entries = payload.get("result") or {}
        for value in batch:
            item = entries.get(str(value))
            valid = (
                isinstance(item, dict)
                and not item.get("error")
                and (item.get("uid") or item.get("accession"))
            )
            if valid:
                results[value] = Resolution(scheme, value, "resolved")
            else:
                detail = (
                    item.get("error") if isinstance(item, dict) else "not found in NCBI response"
                )
                results[value] = Resolution(scheme, value, "dead", str(detail))
        if len(batch) > 1:
            sleeper(0.4)
    return results


def resolve_pmids(
    pmids: Sequence[str],
    *,
    request: RequestJson = _request_json,
    timeout: float = 20.0,
    sleeper: Callable[[float], None] = time.sleep,
    batch_size: int = 200,
) -> dict[str, Resolution]:
    """Resolve PMIDs in batches through NCBI E-utilities."""
    return _resolve_ncbi(
        sorted(set(pmids)),
        scheme="PMID",
        db="pubmed",
        request=request,
        timeout=timeout,
        sleeper=sleeper,
        batch_size=batch_size,
    )


def resolve_clinvars(
    clinvar_ids: Sequence[str],
    *,
    request: RequestJson = _request_json,
    timeout: float = 20.0,
    sleeper: Callable[[float], None] = time.sleep,
    batch_size: int = 200,
) -> dict[str, Resolution]:
    """Resolve ClinVar variation IDs in batches through NCBI E-utilities."""
    return _resolve_ncbi(
        sorted(set(clinvar_ids)),
        scheme="CLINVAR",
        db="clinvar",
        request=request,
        timeout=timeout,
        sleeper=sleeper,
        batch_size=batch_size,
    )


def resolve_dois(
    dois: Sequence[str],
    *,
    request: RequestJson = _request_json,
    timeout: float = 20.0,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Resolution]:
    """Resolve DOIs through the DOI Handle API."""
    results: dict[str, Resolution] = {}
    for doi in sorted(set(dois)):
        url = DOI_API + urllib.parse.quote(doi, safe="/")
        try:
            payload = request(url, timeout=timeout, sleeper=sleeper)
        except ResolutionError as exc:
            results[doi] = Resolution("DOI", doi, "error", str(exc))
            continue
        if payload is None:
            results[doi] = Resolution("DOI", doi, "dead", "HTTP 404")
        elif payload.get("responseCode") == 1:
            results[doi] = Resolution("DOI", doi, "resolved")
        else:
            results[doi] = Resolution(
                "DOI",
                doi,
                "dead",
                f"handle responseCode={payload.get('responseCode')}",
            )
    return results


def resolve_all(
    identifiers: Sequence[Identifier],
    *,
    request: RequestJson = _request_json,
    timeout: float = 20.0,
    sleeper: Callable[[float], None] = time.sleep,
    batch_size: int = 200,
) -> dict[tuple[str, str], Resolution]:
    """Resolve every identifier once, grouped by scheme."""
    by_scheme: dict[str, list[str]] = defaultdict(list)
    for identifier in identifiers:
        by_scheme[identifier.scheme].append(identifier.value)

    resolved: dict[tuple[str, str], Resolution] = {}
    if by_scheme["PMID"]:
        for value, result in resolve_pmids(
            by_scheme["PMID"],
            request=request,
            timeout=timeout,
            sleeper=sleeper,
            batch_size=batch_size,
        ).items():
            resolved[("PMID", value)] = result
    if by_scheme["DOI"]:
        for value, result in resolve_dois(
            by_scheme["DOI"],
            request=request,
            timeout=timeout,
            sleeper=sleeper,
        ).items():
            resolved[("DOI", value)] = result
    if by_scheme["CLINVAR"]:
        for value, result in resolve_clinvars(
            by_scheme["CLINVAR"],
            request=request,
            timeout=timeout,
            sleeper=sleeper,
            batch_size=batch_size,
        ).items():
            resolved[("CLINVAR", value)] = result
    return resolved


def build_report(
    disease_ids: Sequence[str],
    *,
    request: RequestJson = _request_json,
    timeout: float = 20.0,
    sleeper: Callable[[float], None] = time.sleep,
    batch_size: int = 200,
) -> dict[str, Any]:
    """Collect and resolve identifiers, returning a deterministic report."""
    identifiers = collect_identifiers(disease_ids)
    resolutions = resolve_all(
        identifiers,
        request=request,
        timeout=timeout,
        sleeper=sleeper,
        batch_size=batch_size,
    )

    entries: list[dict[str, Any]] = []
    dead: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    by_scheme: dict[str, int] = defaultdict(int)
    for identifier in identifiers:
        by_scheme[identifier.scheme] += 1
        result = resolutions[(identifier.scheme, identifier.value)]
        entry = {
            "scheme": identifier.scheme,
            "value": identifier.value,
            "status": result.status,
            "detail": result.detail,
            "locations": [
                occurrence.as_dict()
                for occurrence in sorted(
                    identifier.occurrences,
                    key=lambda item: (item.disease_id, item.collection, item.record_id),
                )
            ],
        }
        entries.append(entry)
        if result.status == "dead":
            dead.append(entry)
        elif result.status == "error":
            errors.append(entry)

    return {
        "schema": "nosograph.reference_identifiers/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "diseases": list(disease_ids),
            "identifiers_by_scheme": dict(sorted(by_scheme.items())),
        },
        "summary": {
            "checked": len(identifiers),
            "resolved": len(identifiers) - len(dead) - len(errors),
            "dead": len(dead),
            "errors": len(errors),
            "by_scheme": dict(sorted(by_scheme.items())),
        },
        "identifiers": entries,
        "dead": dead,
        "errors": errors,
    }


def _selected_diseases(args: argparse.Namespace) -> list[str]:
    if args.disease:
        return list(dict.fromkeys(args.disease))

    from med_research.diseases.identifiers import (
        CI_VALIDATED_DISEASES,
        REFERENCE_DISEASES,
    )

    if args.tier == "reference":
        return list(REFERENCE_DISEASES)
    if args.tier == "ci_validated":
        return list(CI_VALIDATED_DISEASES)
    return list(dict.fromkeys((*REFERENCE_DISEASES, *CI_VALIDATED_DISEASES)))


def _print_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    scope = report["scope"]
    schemes = ", ".join(f"{key}={value}" for key, value in scope["identifiers_by_scheme"].items())
    print(
        f"Reference identifiers: {summary['checked']} checked "
        f"({schemes or 'none'}) across {len(scope['diseases'])} disease modules"
    )
    print(f"  resolved={summary['resolved']} dead={summary['dead']} errors={summary['errors']}")
    for entry in report["dead"]:
        locations = ", ".join(
            f"{item['disease_id']}/{item['collection']}/{item['record_id']}"
            for item in entry["locations"]
        )
        print(f"  DEAD {entry['scheme']}:{entry['value']} ({entry['detail']}) at {locations}")
    for entry in report["errors"]:
        print(f"  ERROR {entry['scheme']}:{entry['value']} ({entry['detail']})")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tier",
        choices=("both", "reference", "ci_validated"),
        default="both",
        help="Disease slice to check (default: reference + CI-validated)",
    )
    parser.add_argument(
        "--disease",
        action="append",
        dest="disease",
        metavar="ID",
        help="Check a specific disease module (repeatable; overrides --tier)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        dest="json_path",
        help="Write the full resolution report to this path",
    )
    parser.add_argument(
        "--timeout", type=float, default=20.0, help="Per-request timeout in seconds"
    )
    args = parser.parse_args(argv)

    try:
        disease_ids = _selected_diseases(args)
        report = build_report(disease_ids, timeout=args.timeout)
    except Exception as exc:  # noqa: BLE001 - report the failure and fail closed
        print(f"reference identifier check failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Report written to {args.json_path}")

    if not report["identifiers"]:
        print("reference identifier check failed: no PMID, DOI, or ClinVar identifiers found")
        return 1

    _print_report(report)
    return 0 if not report["dead"] and not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
