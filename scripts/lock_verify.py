"""Verify the local environment matches requirements-lock.txt.

Parses every ``pkg==version`` pin from requirements-lock.txt (skipping
pip-tools' ``# via`` continuation lines) and compares each against the
installed distribution. Exits non-zero on missing or mismatched
packages, so it can gate CI or a local ``make lock-verify``.

With ``--compare-locks``, instead compares the runtime lock against a
second lock file (e.g. requirements-dev-lock.txt) and fails if any
shared package is pinned at a different version, so the two locks
cannot silently diverge.

Usage:
    python scripts/lock_verify.py [--lock requirements-lock.txt]
    python scripts/lock_verify.py --compare-locks requirements-dev-lock.txt
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


def compare_locks(runtime: Path, dev: Path) -> list[str]:
    """Return divergences where two locks pin a shared package differently."""
    runtime_pins = parse_pins(runtime)
    dev_pins = parse_pins(dev)
    divergences: list[str] = []
    for pkg, runtime_ver in sorted(runtime_pins.items()):
        dev_ver = dev_pins.get(pkg)
        if dev_ver is not None and dev_ver != runtime_ver:
            divergences.append(f"{pkg}: runtime {runtime_ver}, dev {dev_ver}")
    return divergences


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lock",
        type=Path,
        default=Path("requirements-lock.txt"),
        help="pip-tools lock file to check against (default: requirements-lock.txt)",
    )
    parser.add_argument(
        "--compare-locks",
        type=Path,
        metavar="DEV_LOCK",
        help="compare the runtime lock against another lock (e.g. "
        "requirements-dev-lock.txt) instead of the installed environment",
    )
    args = parser.parse_args()

    if args.compare_locks:
        divergences = compare_locks(args.lock, args.compare_locks)
        if divergences:
            print(f"lock files disagree on shared packages ({args.lock} vs {args.compare_locks}):")
            print("\n".join(f"  {d}" for d in divergences))
            print(f"{len(divergences)} divergence(s)", file=sys.stderr)
            return 1
        print(f"runtime and {args.compare_locks.name} agree on all shared packages")
        return 0

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
