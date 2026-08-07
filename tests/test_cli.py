"""Unit tests for CLI behavior that should not require subprocesses."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest


def test_serve_reload_disabled_when_debug_false(monkeypatch):
    """--reload must not enable uvicorn reload unless DEBUG=true."""
    monkeypatch.setenv("DEBUG", "false")

    from med_research.cli import cmd_serve

    args = SimpleNamespace(host="127.0.0.1", port=8000, reload=True)

    with (
        patch("med_research.web.config.DEBUG", False),
        patch("uvicorn.run") as mock_run,
    ):
        cmd_serve(args)

    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["reload"] is False


def test_serve_reload_enabled_when_debug_true(monkeypatch):
    """--reload is honored when DEBUG=true."""
    monkeypatch.setenv("DEBUG", "true")

    from med_research.cli import cmd_serve

    args = SimpleNamespace(host="127.0.0.1", port=8000, reload=True)

    with (
        patch("med_research.web.config.DEBUG", True),
        patch("uvicorn.run") as mock_run,
    ):
        cmd_serve(args)

    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["reload"] is True


@pytest.mark.parametrize(
    ("debug", "reload_flag", "expected_reload"),
    [
        (True, False, False),
        (True, True, True),
        (False, True, False),
        (False, False, False),
    ],
)
def test_serve_reload_guard(debug, reload_flag, expected_reload):
    """Reload follows both the --reload flag and DEBUG guard."""
    from med_research.cli import cmd_serve

    args = SimpleNamespace(host="127.0.0.1", port=8000, reload=reload_flag)

    with (
        patch("med_research.web.config.DEBUG", debug),
        patch("uvicorn.run") as mock_run,
    ):
        cmd_serve(args)

    assert mock_run.call_args.kwargs["reload"] is expected_reload
