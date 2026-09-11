#!/usr/bin/env python3
"""Audit dependency licenses against policy and generate SPDX 2.3 SBOM."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import re
import sys
import tomllib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packaging.markers import InvalidMarker, Marker

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / "license-policy.toml"
DEFAULT_LOCK_PATH = ROOT / "requirements-lock.txt"
PYPROJECT_PATH = ROOT / "pyproject.toml"

PIN_RE = re.compile(
    r"^([A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?)==([^\s;]+)"
    r"(?:\s*;\s*(.+))?$"
)

# Standard mappings from classifiers to SPDX identifiers
CLASSIFIER_MAP: dict[str, str] = {
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: BSD License": "BSD-3-Clause",
    "License :: OSI Approved :: Python Software Foundation License": "PSF-2.0",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)": "LGPL-2.1-or-later",
    "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0-only",
    "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)": "LGPL-3.0-or-later",
    "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)": "LGPL-2.1-or-later",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)": "GPL-3.0-only",
    "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)": "GPL-3.0-or-later",
    "License :: OSI Approved :: GNU General Public License v2 (GPLv2)": "GPL-2.0-only",
    "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)": "GPL-2.0-or-later",
    "License :: OSI Approved :: GNU General Public License (GPL)": "GPL-3.0-only",
    "License :: OSI Approved :: GNU Affero General Public License v3 (AGPLv3)": "AGPL-3.0-only",
    "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)": "AGPL-3.0-or-later",
    "License :: OSI Approved :: ISC License (ISCL)": "ISC",
    "License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication": "CC0-1.0",
    "License :: Public Domain": "Unlicense",
    "License :: Other/Proprietary License": "Proprietary",
}

# Standard patterns for raw license field normalization
KNOWN_RAW_MAP: dict[str, str] = {
    "apache-2.0": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "apache-2.0 license": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "mit": "MIT",
    "mit license": "MIT",
    "mit-cmu": "MIT-CMU",
    "bsd": "BSD-3-Clause",
    "new bsd": "BSD-3-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "bsd 3-clause": "BSD-3-Clause",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd 2-clause": "BSD-2-Clause",
    "0bsd": "0BSD",
    "isc": "ISC",
    "psf-2.0": "PSF-2.0",
    "python-2.0": "Python-2.0",
    "mpl-2.0": "MPL-2.0",
    "mozilla public license 2.0 (mpl 2.0)": "MPL-2.0",
    "lgpl-2.1": "LGPL-2.1-or-later",
    "lgpl-2.1-or-later": "LGPL-2.1-or-later",
    "gpl-3.0": "GPL-3.0-only",
    "gpl-3.0-only": "GPL-3.0-only",
    "gpl-2.0": "GPL-2.0-only",
    "gpl-2.0-only": "GPL-2.0-only",
    "agpl-3.0": "AGPL-3.0-only",
    "proprietary": "Proprietary",
    "dual license": "Apache-2.0 OR BSD-3-Clause",
    "licenseref-biopython-license": "LicenseRef-Biopython-License",
    "cc0-1.0": "CC0-1.0",
    "unlicense": "Unlicense",
}


@dataclass
class PackageLicense:
    name: str
    version: str
    marker: str | None
    declared_raw: str | None
    concluded_spdx: str
    status: str  # ALLOWED | CONDITIONAL | DISALLOWED | UNKNOWN
    rationale: str | None = None
    homepage: str | None = None


def load_policy(policy_path: Path) -> dict[str, Any]:
    """Load policy configuration from TOML file."""
    if not policy_path.is_file():
        raise FileNotFoundError(f"license policy file not found: {policy_path}")
    return tomllib.loads(policy_path.read_text(encoding="utf-8"))


def parse_lock_file(
    lock_path: Path, all_platforms: bool = False
) -> dict[str, tuple[str, str | None]]:
    """Return {canonical_pkg_name: (version, marker)} from lock file."""
    if not lock_path.is_file():
        raise FileNotFoundError(f"lock file not found: {lock_path}")

    pins: dict[str, tuple[str, str | None]] = {}
    for line in lock_path.read_text(encoding="utf-8").splitlines():
        match = PIN_RE.match(line.strip())
        if not match:
            continue
        raw_name = match.group(1).split("[", 1)[0].lower()
        version = match.group(2)
        marker_text = match.group(3)

        if marker_text and not all_platforms:
            try:
                if not Marker(marker_text).evaluate():
                    continue
            except InvalidMarker as exc:
                raise ValueError(f"invalid marker in {lock_path}: {marker_text}") from exc

        pins[raw_name] = (version, marker_text)
    return pins


def normalize_license(
    name: str,
    raw_header: str | None,
    classifiers: list[str],
    exceptions: dict[str, Any],
) -> tuple[str, str | None]:
    """Resolve package license to an SPDX identifier and optional rationale."""
    # 1. Check explicit policy exceptions
    if name in exceptions:
        exc_entry = exceptions[name]
        return exc_entry.get("license", "UNKNOWN"), exc_entry.get("rationale")

    # 2. Check direct PEP 639 or exact recognized expression in raw header
    cleaned_header = raw_header.strip() if raw_header else ""
    lowered = cleaned_header.lower()

    if lowered in KNOWN_RAW_MAP:
        return KNOWN_RAW_MAP[lowered], None

    # Handle standard SPDX-like composite expressions (e.g., 'MPL-2.0 AND MIT')
    if cleaned_header and all(
        part.strip("() ") in KNOWN_RAW_MAP
        or part.strip("() ").upper()
        in {
            "AND",
            "OR",
            "WITH",
            "MIT",
            "APACHE-2.0",
            "BSD-3-CLAUSE",
            "BSD-2-CLAUSE",
            "0BSD",
            "MPL-2.0",
        }
        for part in re.split(r"\s+(?:AND|OR)\s+", cleaned_header, flags=re.IGNORECASE)
    ):
        return cleaned_header, None

    # 3. Check classifiers
    for classifier in classifiers:
        if classifier in CLASSIFIER_MAP:
            return CLASSIFIER_MAP[classifier], None

    # 4. Check known substrings in header
    if "bsd 3-clause" in lowered or "3-clause bsd" in lowered:
        return "BSD-3-Clause", None
    if "bsd 2-clause" in lowered or "2-clause bsd" in lowered:
        return "BSD-2-Clause", None
    if "mit" in lowered and "license" in lowered:
        return "MIT", None
    if "apache" in lowered and ("2.0" in lowered or "license" in lowered):
        return "Apache-2.0", None
    if "psf" in lowered or "python software foundation" in lowered:
        return "PSF-2.0", None

    # If header is short and clean, use it as fallback; otherwise UNKNOWN
    if cleaned_header and len(cleaned_header) < 60 and "\n" not in cleaned_header:
        return cleaned_header, None

    return "UNKNOWN", None


def evaluate_package(
    name: str,
    version: str,
    marker: str | None,
    policy: dict[str, Any],
) -> PackageLicense:
    """Inspect installed distribution metadata and evaluate against policy."""
    exceptions = policy.get("exceptions", {})
    allowed = set(policy.get("policy", {}).get("allowed_licenses", []))
    conditional = set(policy.get("policy", {}).get("conditional_licenses", []))
    forbidden = set(policy.get("policy", {}).get("forbidden_licenses", []))

    raw_header: str | None = None
    classifiers: list[str] = []
    homepage: str | None = None

    try:
        dist = importlib.metadata.distribution(name)
        meta = dist.metadata
        raw_header = meta.get("License-Expression") or meta.get("License")
        classifiers = [
            c.strip() for c in (meta.get_all("Classifier") or []) if c.startswith("License ::")
        ]
        homepage = meta.get("Home-page") or meta.get("Project-URL")
    except importlib.metadata.PackageNotFoundError:
        pass

    spdx_id, rationale = normalize_license(name, raw_header, classifiers, exceptions)

    # Check if exception overrides disallowed status
    exc = exceptions.get(name, {})
    if exc.get("ignore_disallowed", False):
        status = "CONDITIONAL" if spdx_id in conditional else "ALLOWED"
        return PackageLicense(
            name=name,
            version=version,
            marker=marker,
            declared_raw=raw_header,
            concluded_spdx=spdx_id,
            status=status,
            rationale=rationale or exc.get("rationale"),
            homepage=homepage,
        )

    # Check policy category
    # Handle composite expressions like 'MPL-2.0 AND MIT'
    sub_licenses = [
        re.sub(r"[()]", "", s).strip()
        for s in re.split(r"\s+(?:AND|OR)\s+", spdx_id, flags=re.IGNORECASE)
    ]

    if any(lic in forbidden for lic in sub_licenses) or spdx_id in forbidden:
        status = "DISALLOWED"
    elif spdx_id == "UNKNOWN":
        status = "UNKNOWN"
    elif any(lic in conditional for lic in sub_licenses) or spdx_id in conditional:
        status = "CONDITIONAL"
    elif all(lic in allowed for lic in sub_licenses) or spdx_id in allowed:
        status = "ALLOWED"
    else:
        status = "UNKNOWN"

    return PackageLicense(
        name=name,
        version=version,
        marker=marker,
        declared_raw=raw_header,
        concluded_spdx=spdx_id,
        status=status,
        rationale=rationale,
        homepage=homepage,
    )


def generate_spdx_sbom(
    packages: list[PackageLicense],
    pyproject_path: Path = PYPROJECT_PATH,
) -> dict[str, Any]:
    """Generate ISO/IEC 5962:2021 SPDX 2.3 JSON compliant SBOM."""
    root_name = "med-research"
    root_version = "0.2.1"
    root_license = "Apache-2.0"
    root_description = "NosoGraph — Disease Intelligence. Connected."
    root_homepage = "https://github.com/AdamEddahmouni/nosograph"

    if pyproject_path.is_file():
        try:
            proj = tomllib.loads(pyproject_path.read_text(encoding="utf-8")).get("project", {})
            root_name = proj.get("name", root_name)
            root_version = proj.get("version", root_version)
            root_description = proj.get("description", root_description)
            root_homepage = proj.get("urls", {}).get("Homepage", root_homepage)
        except Exception:
            pass

    doc_id = "SPDXRef-DOCUMENT"
    root_pkg_id = f"SPDXRef-Package-{re.sub(r'[^a-zA-Z0-9.-]', '-', root_name)}"
    created_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc_uuid = str(uuid.uuid4())

    spdx_packages: list[dict[str, Any]] = [
        {
            "SPDXID": root_pkg_id,
            "name": root_name,
            "versionInfo": root_version,
            "downloadLocation": root_homepage,
            "filesAnalyzed": False,
            "homepage": root_homepage,
            "summary": root_description,
            "licenseConcluded": root_license,
            "licenseDeclared": root_license,
            "supplier": "Organization: NosoGraph",
            "originator": "Person: Adam Eddahmouni",
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": f"pkg:pypi/{root_name}@{root_version}",
                }
            ],
        }
    ]

    spdx_relationships: list[dict[str, str]] = [
        {
            "spdxElementId": doc_id,
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": root_pkg_id,
        }
    ]

    for pkg in sorted(packages, key=lambda p: p.name):
        safe_name = re.sub(r"[^a-zA-Z0-9.-]", "-", pkg.name)
        pkg_id = f"SPDXRef-Package-{safe_name}"
        download_url = f"https://pypi.org/project/{pkg.name}/{pkg.version}/"

        declared = pkg.declared_raw or pkg.concluded_spdx
        if (
            len(declared) > 80
            or "\n" in declared
            or declared.startswith("=")
            or "Copyright" in declared
        ):
            declared = pkg.concluded_spdx

        spdx_packages.append(
            {
                "SPDXID": pkg_id,
                "name": pkg.name,
                "versionInfo": pkg.version,
                "downloadLocation": download_url,
                "filesAnalyzed": False,
                "licenseConcluded": pkg.concluded_spdx,
                "licenseDeclared": declared,
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:pypi/{pkg.name}@{pkg.version}",
                    }
                ],
            }
        )

        spdx_relationships.append(
            {
                "spdxElementId": root_pkg_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": pkg_id,
            }
        )

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": doc_id,
        "name": f"{root_name}-{root_version}-sbom",
        "documentNamespace": f"https://github.com/AdamEddahmouni/nosograph/spdx/{root_version}/{doc_uuid}",
        "creationInfo": {
            "created": created_ts,
            "creators": [
                "Tool: nosograph-license-check-1.0",
                "Organization: NosoGraph",
                "Person: Adam Eddahmouni",
            ],
            "licenseListVersion": "3.23",
        },
        "packages": spdx_packages,
        "relationships": spdx_relationships,
    }


def generate_markdown_summary(
    packages: list[PackageLicense],
    policy: dict[str, Any],
) -> str:
    """Generate Markdown summary table for documentation and GitHub Step Summary."""
    counts = {
        "ALLOWED": sum(1 for p in packages if p.status == "ALLOWED"),
        "CONDITIONAL": sum(1 for p in packages if p.status == "CONDITIONAL"),
        "DISALLOWED": sum(1 for p in packages if p.status == "DISALLOWED"),
        "UNKNOWN": sum(1 for p in packages if p.status == "UNKNOWN"),
    }
    total = len(packages)
    passed = counts["DISALLOWED"] == 0 and counts["UNKNOWN"] == 0
    verdict = "PASSED" if passed else "FAILED"
    verdict_emoji = "SUCCESS" if passed else "FAILURE"

    lines: list[str] = [
        "## NosoGraph License Bill of Materials (SBOM)",
        "",
        f"**Audit Status:** `{verdict_emoji} ({verdict})` | **Total Packages:** `{total}`",
        "",
        "| Status | Count | Policy Implication |",
        "|--------|-------|--------------------|",
        f"| Allowed (Permissive) | {counts['ALLOWED']} | Fully compatible with Apache-2.0 |",
        f"| Conditional (Notice) | {counts['CONDITIONAL']} | Permitted with source/linking attribution |",
        f"| Disallowed (Copyleft) | {counts['DISALLOWED']} | Incompatible; blocks distribution |",
        f"| Unknown (Unresolved) | {counts['UNKNOWN']} | Missing or ambiguous metadata |",
        "",
        "### Detailed Dependency Inventory",
        "",
        "| Package | Version | SPDX License | Status | Notes / Rationale |",
        "|---------|---------|--------------|--------|-------------------|",
    ]

    for p in sorted(
        packages, key=lambda x: (x.status != "DISALLOWED", x.status != "UNKNOWN", x.name)
    ):
        status_badge = f"`{p.status}`"
        notes = p.rationale or ""
        lines.append(
            f"| `{p.name}` | {p.version} | `{p.concluded_spdx}` | {status_badge} | {notes} |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lock",
        type=Path,
        default=DEFAULT_LOCK_PATH,
        help="Path to requirements-lock.txt (default: requirements-lock.txt)",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY_PATH,
        help="Path to license-policy.toml (default: license-policy.toml)",
    )
    parser.add_argument(
        "--spdx-out",
        type=Path,
        help="Write SPDX 2.3 JSON document to this path",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        help="Write Markdown summary report to this path",
    )
    parser.add_argument(
        "--github-summary",
        action="store_true",
        help="Append summary directly to $GITHUB_STEP_SUMMARY if available",
    )
    parser.add_argument(
        "--all-platforms",
        action="store_true",
        help="Include packages skipped by environment markers on the current host OS",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any conditional licenses are present without explicit exception",
    )
    args = parser.parse_args()

    policy = load_policy(args.policy)
    pins = parse_lock_file(args.lock, all_platforms=args.all_platforms)

    evaluated_packages: list[PackageLicense] = []
    for pkg_name, (version, marker) in pins.items():
        pkg_res = evaluate_package(pkg_name, version, marker, policy)
        evaluated_packages.append(pkg_res)

    # Print terminal summary
    disallowed = [p for p in evaluated_packages if p.status == "DISALLOWED"]
    unknown = [p for p in evaluated_packages if p.status == "UNKNOWN"]
    conditional = [p for p in evaluated_packages if p.status == "CONDITIONAL"]
    allowed = [p for p in evaluated_packages if p.status == "ALLOWED"]

    print("=" * 72)
    print(
        f"NosoGraph License Audit — {len(evaluated_packages)} packages evaluated from {args.lock.name}"
    )
    print("=" * 72)
    print(f"  Allowed:     {len(allowed)}")
    print(f"  Conditional: {len(conditional)}")
    print(f"  Disallowed:  {len(disallowed)}")
    print(f"  Unknown:     {len(unknown)}")
    print("-" * 72)

    if conditional:
        print("Conditional packages (notice / weak copyleft permitted):")
        for p in conditional:
            print(
                f"  - {p.name}=={p.version} ({p.concluded_spdx}) -> {p.rationale or 'Notice required'}"
            )

    if disallowed:
        print("\nERROR: Disallowed licenses detected:")
        for p in disallowed:
            print(f"  [X] {p.name}=={p.version}: {p.concluded_spdx}")

    if unknown:
        print("\nERROR: Unknown or unresolvable licenses detected:")
        for p in unknown:
            print(f"  [?] {p.name}=={p.version}: {p.declared_raw or 'No license metadata'}")

    # Generate SPDX SBOM
    if args.spdx_out:
        args.spdx_out.parent.mkdir(parents=True, exist_ok=True)
        sbom_data = generate_spdx_sbom(evaluated_packages)
        args.spdx_out.write_text(json.dumps(sbom_data, indent=2), encoding="utf-8")
        print(f"\nSPDX 2.3 JSON written to {args.spdx_out}")

    # Generate Markdown summary
    summary_md = generate_markdown_summary(evaluated_packages, policy)
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(summary_md, encoding="utf-8")
        print(f"Markdown summary written to {args.summary_out}")

    # Handle GitHub Step Summary
    if args.github_summary or os.environ.get("GITHUB_STEP_SUMMARY"):
        step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if step_summary_path:
            with open(step_summary_path, "a", encoding="utf-8") as f:
                f.write(summary_md + "\n")
            print("Appended summary to $GITHUB_STEP_SUMMARY")

    # Determine exit code
    if disallowed or unknown:
        print("\nAudit FAILED: License violations or unresolvable licenses found.")
        return 1

    if args.strict and conditional:
        # If strict, ensure all conditional packages have an explicit rationale
        unexempted = [p for p in conditional if not p.rationale]
        if unexempted:
            print("\nAudit FAILED (--strict): Unexempted conditional packages found:")
            for p in unexempted:
                print(f"  [!] {p.name} ({p.concluded_spdx}) lacks documented rationale")
            return 1

    print("\nAudit PASSED: All packages comply with NosoGraph license policy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
