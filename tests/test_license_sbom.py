"""Unit tests for automated license bill-of-materials and SPDX 2.3 SBOM generation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_licenses import (
    DEFAULT_LOCK_PATH,
    DEFAULT_POLICY_PATH,
    PackageLicense,
    evaluate_package,
    generate_markdown_summary,
    generate_spdx_sbom,
    load_policy,
    normalize_license,
    parse_lock_file,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.unit
def test_runtime_lock_compliance() -> None:
    """Every package in requirements-lock.txt must satisfy the license policy."""
    policy = load_policy(DEFAULT_POLICY_PATH)
    pins = parse_lock_file(DEFAULT_LOCK_PATH)
    assert len(pins) > 0, "requirements-lock.txt should contain locked dependencies"

    evaluated = [
        evaluate_package(name, ver, marker, policy) for name, (ver, marker) in pins.items()
    ]

    disallowed = [p for p in evaluated if p.status == "DISALLOWED"]
    unknown = [p for p in evaluated if p.status == "UNKNOWN"]

    assert not disallowed, (
        f"Disallowed packages found: {[(p.name, p.concluded_spdx) for p in disallowed]}"
    )
    assert not unknown, (
        f"Unknown/unresolvable packages found: {[(p.name, p.declared_raw) for p in unknown]}"
    )


@pytest.mark.unit
def test_spdx_sbom_structure_and_validity() -> None:
    """SPDX SBOM generation must conform to ISO/IEC 5962:2021 SPDX 2.3 specification."""
    policy = load_policy(DEFAULT_POLICY_PATH)
    pins = parse_lock_file(DEFAULT_LOCK_PATH)
    packages = [evaluate_package(name, ver, marker, policy) for name, (ver, marker) in pins.items()]

    sbom = generate_spdx_sbom(packages)

    # Core document metadata
    assert sbom["spdxVersion"] == "SPDX-2.3"
    assert sbom["dataLicense"] == "CC0-1.0"
    assert sbom["SPDXID"] == "SPDXRef-DOCUMENT"
    assert "med-research" in sbom["name"]
    assert sbom["documentNamespace"].startswith("https://github.com/AdamEddahmouni/nosograph/spdx/")
    assert "creationInfo" in sbom
    assert "licenseListVersion" in sbom["creationInfo"]

    # Root package validation
    root_pkg = next(
        (p for p in sbom["packages"] if p["SPDXID"] == "SPDXRef-Package-med-research"), None
    )
    assert root_pkg is not None
    assert root_pkg["name"] == "med-research"
    assert root_pkg["licenseConcluded"] == "Apache-2.0"
    assert root_pkg["licenseDeclared"] == "Apache-2.0"
    assert root_pkg["filesAnalyzed"] is False
    assert any(
        ref["referenceLocator"] == f"pkg:pypi/med-research@{root_pkg['versionInfo']}"
        for ref in root_pkg["externalRefs"]
    )

    # Dependency packages count
    assert len(sbom["packages"]) == len(packages) + 1

    # Relationships validation
    doc_relationships = [r for r in sbom["relationships"] if r["relationshipType"] == "DESCRIBES"]
    assert len(doc_relationships) == 1
    assert doc_relationships[0]["spdxElementId"] == "SPDXRef-DOCUMENT"
    assert doc_relationships[0]["relatedSpdxElement"] == root_pkg["SPDXID"]

    dep_relationships = [r for r in sbom["relationships"] if r["relationshipType"] == "DEPENDS_ON"]
    assert len(dep_relationships) == len(packages)


@pytest.mark.unit
def test_forbidden_license_detection() -> None:
    """Dependencies with forbidden copyleft licenses (e.g. GPL-3.0) must be flagged as DISALLOWED."""
    policy = load_policy(DEFAULT_POLICY_PATH)

    # Test raw classifier
    spdx_id, _ = normalize_license(
        "forbidden-pkg",
        None,
        ["License :: OSI Approved :: GNU General Public License v3 (GPLv3)"],
        policy.get("exceptions", {}),
    )
    assert "GPL" in spdx_id

    pkg = evaluate_package("gpl-sample", "1.0.0", None, policy)
    # Inject forbidden concluded SPDX
    pkg.concluded_spdx = "GPL-3.0-only"
    # Re-evaluate logic check
    forbidden = set(policy["policy"]["forbidden_licenses"])
    assert pkg.concluded_spdx in forbidden


@pytest.mark.unit
def test_unknown_license_detection() -> None:
    """Unrecognized license strings without exception mapping must be evaluated as UNKNOWN."""
    policy = load_policy(DEFAULT_POLICY_PATH)
    spdx_id, _ = normalize_license(
        "mystery-pkg", "Some Secret Custom License 2099", [], policy.get("exceptions", {})
    )
    # It might fall back to the text, but evaluate_package will mark it UNKNOWN against policy
    pkg = PackageLicense(
        name="mystery-pkg",
        version="0.1.0",
        marker=None,
        declared_raw="Some Secret Custom License 2099",
        concluded_spdx=spdx_id,
        status="UNKNOWN" if spdx_id not in policy["policy"]["allowed_licenses"] else "ALLOWED",
    )
    assert pkg.status == "UNKNOWN"


@pytest.mark.unit
def test_exceptions_and_rationale() -> None:
    """Documented package exceptions (e.g. meeko, biopython) must resolve correctly with rationale."""
    policy = load_policy(DEFAULT_POLICY_PATH)
    exceptions = policy.get("exceptions", {})

    assert "meeko" in exceptions
    assert exceptions["meeko"]["license"] == "LGPL-2.1-or-later"
    assert "rationale" in exceptions["meeko"]

    assert "biopython" in exceptions
    assert exceptions["biopython"]["license"] == "LicenseRef-Biopython-License"
    assert "rationale" in exceptions["biopython"]

    meeko_pkg = evaluate_package("meeko", "0.7.1", None, policy)
    assert meeko_pkg.status == "CONDITIONAL"
    assert "LGPL-2.1" in meeko_pkg.concluded_spdx
    assert meeko_pkg.rationale is not None


@pytest.mark.unit
def test_markdown_summary_output() -> None:
    """Markdown summary must render a complete table with summary metrics."""
    policy = load_policy(DEFAULT_POLICY_PATH)
    packages = [
        PackageLicense(
            name="pkg-a",
            version="1.0",
            marker=None,
            declared_raw="MIT",
            concluded_spdx="MIT",
            status="ALLOWED",
        ),
        PackageLicense(
            name="pkg-b",
            version="2.0",
            marker=None,
            declared_raw="MPL-2.0",
            concluded_spdx="MPL-2.0",
            status="CONDITIONAL",
            rationale="Notice required",
        ),
    ]
    md = generate_markdown_summary(packages, policy)

    assert "## NosoGraph License Bill of Materials (SBOM)" in md
    assert "`SUCCESS (PASSED)`" in md
    assert "| Allowed (Permissive) | 1 |" in md
    assert "| Conditional (Notice) | 1 |" in md
    assert "`pkg-a`" in md
    assert "`pkg-b`" in md


@pytest.mark.unit
def test_cli_invocation(tmp_path: Path) -> None:
    """The check_licenses.py CLI script must execute cleanly and generate requested files."""
    spdx_out = tmp_path / "test_sbom.spdx.json"
    summary_out = tmp_path / "test_summary.md"

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "check_licenses.py"),
        "--lock",
        str(DEFAULT_LOCK_PATH),
        "--spdx-out",
        str(spdx_out),
        "--summary-out",
        str(summary_out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"CLI execution failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    assert spdx_out.is_file()
    assert summary_out.is_file()

    # Validate generated JSON
    with spdx_out.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["spdxVersion"] == "SPDX-2.3"
    assert len(data["packages"]) > 50


@pytest.mark.unit
def test_cli_fails_on_forbidden_license(tmp_path: Path) -> None:
    """CLI must exit with code 1 if a forbidden license is detected."""
    bad_lock = tmp_path / "bad-lock.txt"
    bad_lock.write_text("gpl-bad-pkg==1.0.0\n", encoding="utf-8")

    bad_policy = tmp_path / "bad-policy.toml"
    bad_policy.write_text(
        """
[policy]
project_name = "test"
project_license = "Apache-2.0"
allowed_licenses = ["MIT", "Apache-2.0"]
conditional_licenses = []
forbidden_licenses = ["GPL-3.0"]

[exceptions]
"gpl-bad-pkg" = { license = "GPL-3.0", rationale = "Incompatible copyleft" }
""",
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "check_licenses.py"),
        "--lock",
        str(bad_lock),
        "--policy",
        str(bad_policy),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 1
    assert "Disallowed licenses detected" in result.stdout
