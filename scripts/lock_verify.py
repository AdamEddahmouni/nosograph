"""Verify the local environment matches requirements-lock.txt.

Parses every ``pkg==version`` pin from requirements-lock.txt (skipping
pip-tools' ``# via`` continuation lines) and compares each against the
installed distribution. Exits non-zero on missing or mismatched
packages, so it can gate CI or a local ``make lock-verify``.

Usage:
    python scripts/lock_verify.py [--lock requirements-lock.txt]
"""

import argparse
import importlib.metadata
import re
import sys
from pathlib import Path

PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s]+)$")


def parse_pins(lock_path: Path) -> dict[str, str]:
    """Return {package: version} for every pin in a pip-tools lock file."""
    pins: dict[str, str] = {}
    for line in lock_path.read_text(encoding="utf-8").splitlines():
        match = PIN_RE.match(line.strip())
        if match:
            pins[match.group(1)] = match.group(2)
    return pins


def verify(lock_path: Path) -> tuple[list[str], list[str]]:
    """Return (missing_packages, mismatch_messages) against the lock."""
    pins = parse_pins(lock_path)
    missing: list[str] = []
    mismatched: list[str] = []
    for pkg, expected in sorted(pins.items()):
        try:
            installed = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            missing.append(pkg)
            continue
        if installed != expected:
            mismatched.append(f"{pkg}: installed {installed}, locked {expected}")
    return missing, mismatched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lock",
        type=Path,
        default=Path("requirements-lock.txt"),
        help="pip-tools lock file to check against (default: requirements-lock.txt)",
    )
    args = parser.parse_args()

    pins = parse_pins(args.lock)
    if not pins:
        print(f"error: no pins found in {args.lock}", file=sys.stderr)
        return 1

    missing, mismatched = verify(args.lock)
    if missing:
        print("packages not installed:", ", ".join(missing))
    if mismatched:
        print("version mismatches:")
        print("\n".join(f"  {m}" for m in mismatched))
    if missing or mismatched:
        print(
            f"drift detected: {len(missing)} missing, {len(mismatched)} mismatched "
            f"of {len(pins)} pins",
            file=sys.stderr,
        )
        return 1
    print(f"all {len(pins)} locked packages match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
