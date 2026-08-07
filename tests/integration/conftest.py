"""Integration test configuration — auto-mark tests in this directory."""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        if "/integration/" in item.nodeid.replace("\\", "/"):
            item.add_marker(pytest.mark.integration)
