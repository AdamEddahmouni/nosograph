"""Tests for the environment lock verifier."""

import sys
from pathlib import Path

from scripts.lock_verify import parse_pins


def test_parse_pins_honors_environment_markers():
    """Only pins applicable to the active platform should be verified."""
    lock_path = Path(__file__).parent / "fixtures" / "requirements-lock-markers.txt"

    expected_platform_package = (
        {"windows-package": "2.0"} if sys.platform == "win32" else {"linux-package": "3.0"}
    )
    assert parse_pins(lock_path) == {
        "base-package": "1.0",
        "worker": "4.0",
        **expected_platform_package,
    }
