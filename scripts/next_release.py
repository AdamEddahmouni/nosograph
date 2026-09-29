"""Preview the next release classification and version from Conventional Commits.

Read-only: this script never edits a version, tag, or changelog. Release Please is
the authority for the actual release PR (see RELEASING.md); this is the offline
preview that lets a contributor or agent answer "none, patch, minor, or major?"
without a token or a network call.

It mirrors the release-please-config.json bump policy:
    * bump-minor-pre-major          -> BREAKING CHANGE bumps MINOR while pre-1.0
    * bump-patch-for-minor-pre-major -> off, so feat bumps MINOR

Usage::

    python scripts/next_release.py
    python scripts/next_release.py --range v0.2.1..HEAD
    python scripts/next_release.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
MANIFEST = ROOT / ".release-please-manifest.json"
CONFIG = ROOT / "release-please-config.json"

_BUMP_ORDER = {"none": 0, "patch": 1, "minor": 2, "major": 3}

# Types that never on their own justify a release (RELEASING.md decision table).
_NO_RELEASE_TYPES = {"build", "chore", "ci", "deps", "docs", "refactor", "style", "test"}
_PATCH_TYPES = {"fix", "perf"}

_HEADER_RE = re.compile(
    r"^(?P<type>[a-z][a-z0-9-]*)(?:\((?P<scope>[^()\s]+)\))?(?P<breaking>!)?: (?P<description>\S.*)$"
)
_BREAKING_FOOTER_RE = re.compile(r"^BREAKING[ -]CHANGE:\s*\S", re.MULTILINE)
_EXEMPT_SUBJECT_RE = re.compile(
    r"^(?:Merge (?:branch|remote-tracking branch|pull request|tag)\b|Revert \"|(?:fixup|squash)! )"
)
_RECORD_SEP = "\x1e"
_FIELD_SEP = "\x1f"
_LOG_FORMAT = _FIELD_SEP.join(("%h", "%s", "%b")) + _RECORD_SEP


def _run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def latest_release_tag() -> str | None:
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    tag = result.stdout.strip() if result.returncode == 0 else ""
    return tag or None


def current_version() -> tuple[str, str | None]:
    """Return (version, source) preferring the Release Please manifest."""
    manifest_version = None
    if MANIFEST.is_file():
        manifest_version = json.loads(MANIFEST.read_text(encoding="utf-8")).get(".")
    pyproject_version = None
    if PYPROJECT.is_file():
        pyproject_version = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"][
            "version"
        ]
    if manifest_version:
        return str(
            manifest_version
        ), "manifest" if manifest_version == pyproject_version else "manifest (pyproject differs)"
    if pyproject_version:
        return str(pyproject_version), "pyproject.toml"
    raise SystemExit("cannot determine the current version")


def bump_policy() -> dict[str, bool]:
    if not CONFIG.is_file():
        return {"bump_minor_pre_major": False, "bump_patch_for_minor_pre_major": False}
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    return {
        "bump_minor_pre_major": bool(config.get("bump-minor-pre-major", False)),
        "bump_patch_for_minor_pre_major": bool(config.get("bump-patch-for-minor-pre-major", False)),
    }


def classify(commit_type: str, breaking: bool, policy: dict[str, bool], major: int) -> str:
    pre_major = major == 0
    if breaking:
        if pre_major and policy["bump_minor_pre_major"]:
            return "minor"
        return "major"
    if commit_type == "feat":
        if pre_major and policy["bump_patch_for_minor_pre_major"]:
            return "patch"
        return "minor"
    if commit_type in _PATCH_TYPES:
        return "patch"
    if commit_type == "revert":
        return "patch"
    return "none"


def next_version(version: str, bump: str) -> str:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)
    if not match:
        raise SystemExit(f"current version {version!r} is not a plain MAJOR.MINOR.PATCH")
    major, minor, patch = (int(part) for part in match.groups())
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return version


def collect(revision_range: str) -> list[dict[str, object]]:
    commits: list[dict[str, object]] = []
    for record in _run_git(["log", f"--format={_LOG_FORMAT}", revision_range]).split(_RECORD_SEP):
        record = record.strip("\n")
        if not record:
            continue
        fields = record.split(_FIELD_SEP)
        if len(fields) < 3:
            continue
        sha, subject, body = fields[:3]
        if _EXEMPT_SUBJECT_RE.match(subject):
            continue
        header = _HEADER_RE.match(subject)
        commits.append(
            {
                "sha": sha,
                "subject": subject,
                "type": header.group("type") if header else "unparsed",
                "breaking": bool(
                    (header and header.group("breaking")) or _BREAKING_FOOTER_RE.search(body)
                ),
            }
        )
    return commits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--range", dest="revision_range", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    tag = latest_release_tag()
    revision_range = args.revision_range or (f"{tag}..HEAD" if tag else "HEAD")

    version, source = current_version()
    policy = bump_policy()
    major = int(version.split(".")[0])
    commits = collect(revision_range)

    bump = "none"
    per_type: dict[str, int] = {}
    breaking_commits: list[dict[str, object]] = []
    for commit in commits:
        commit_type = str(commit["type"])
        per_type[commit_type] = per_type.get(commit_type, 0) + 1
        if commit["breaking"]:
            breaking_commits.append(commit)
        candidate = classify(commit_type, bool(commit["breaking"]), policy, major)
        if _BUMP_ORDER[candidate] > _BUMP_ORDER[bump]:
            bump = candidate

    target = next_version(version, bump)
    report = {
        "current_version": version,
        "version_source": source,
        "range": revision_range,
        "commits": len(commits),
        "classification": bump,
        "next_version": target,
        "release": bump != "none",
        "commits_by_type": dict(sorted(per_type.items())),
        "breaking_changes": breaking_commits,
        "policy": policy,
    }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print("Release plan (offline preview; Release Please is authoritative)")
    print()
    print(f"  Current version : {version} ({source})")
    print(f"  Range           : {revision_range}")
    print(f"  Commits parsed  : {len(commits)}")
    print()
    print(f"  Classification  : {bump.upper()}")
    if bump == "none":
        print("  Next version    : (unchanged - no release warranted yet)")
    else:
        print(f"  Next version    : {target}   tag: v{target}")
    print()
    if per_type:
        print("  Commits by type:")
        for commit_type, count in sorted(per_type.items(), key=lambda item: (-item[1], item[0])):
            impact = (
                classify(commit_type, False, policy, major) if commit_type != "unparsed" else "n/a"
            )
            print(f"    {commit_type:<10} {count:>4}   {impact}")
    if breaking_commits:
        print()
        print("  BREAKING CHANGES (must be documented in the release notes):")
        for commit in breaking_commits:
            print(f"    {commit['sha']}  {commit['subject']}")
    no_release = sorted(t for t in per_type if t in _NO_RELEASE_TYPES)
    if no_release:
        print()
        print(f"  No release on their own: {', '.join(no_release)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
