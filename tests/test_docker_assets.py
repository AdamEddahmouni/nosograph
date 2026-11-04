"""Runtime configuration validation for containerized deployment.

These tests are pure unit checks: they never talk to Docker or a live server.
They pin the injected-``PORT`` contract, the aggregated startup validation, and
the demo write guard that the hosting path depends on.
"""

from __future__ import annotations

import importlib

import pytest

from med_research.web import config as web_config

pytestmark = pytest.mark.unit


# ── PORT resolution ───────────────────────────────────────────────────────


def test_resolve_port_defaults_when_unset() -> None:
    assert web_config.DEFAULT_PORT == 8000
    assert web_config.resolve_port({}) == web_config.DEFAULT_PORT
    assert web_config.resolve_port({"PORT": ""}) == web_config.DEFAULT_PORT
    assert web_config.resolve_port({"PORT": "   "}) == web_config.DEFAULT_PORT


def test_resolve_port_accepts_platform_injected_value() -> None:
    assert web_config.resolve_port({"PORT": "8080"}) == 8080
    assert web_config.resolve_port({"PORT": " 65535 "}) == 65535
    assert web_config.resolve_port({"PORT": "1"}) == 1


@pytest.mark.parametrize("value", ["not-a-port", "80.5", "0", "-1", "65536", "99999"])
def test_resolve_port_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="PORT must be an integer between 1 and 65535"):
        web_config.resolve_port({"PORT": value})


def test_runtime_port_is_an_int() -> None:
    assert isinstance(web_config.RUNTIME_PORT, int)
    assert 1 <= web_config.RUNTIME_PORT <= 65535


def test_runtime_port_raises_for_invalid_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # PORT is resolved once, when config is imported — exactly what a container
    # start does. Re-import under a mutated environment to simulate that process,
    # then restore the module so later tests keep the outer environment's values.
    try:
        with monkeypatch.context() as fresh:
            fresh.setenv("PORT", "not-a-port")
            reloaded = importlib.reload(web_config)
            with pytest.raises(ValueError, match="PORT must be an integer"):
                _ = reloaded.RUNTIME_PORT
    finally:
        importlib.reload(web_config)


def test_module_port_stays_import_compatible(monkeypatch: pytest.MonkeyPatch) -> None:
    """An invalid PORT must not crash import; it is reported at startup instead."""
    assert isinstance(web_config.PORT, int)
    try:
        with monkeypatch.context() as fresh:
            fresh.setenv("PORT", "not-a-port")
            reloaded = importlib.reload(web_config)
            assert isinstance(reloaded.PORT, int)
            problems = reloaded.validate_runtime_config()
            assert any("PORT must be an integer" in problem for problem in problems)
    finally:
        importlib.reload(web_config)


# ── validate_runtime_config ──────────────────────────────────────────────


def test_valid_production_config_has_no_problems() -> None:
    problems = web_config.validate_runtime_config(
        {
            "DEBUG": "false",
            "API_KEY": "a-long-random-secret",
            "CORS_ORIGINS": "https://research.example.org",
            "PORT": "8080",
        }
    )
    assert problems == []


def test_debug_allows_local_development_without_api_key() -> None:
    assert web_config.validate_runtime_config({"DEBUG": "true"}) == []


def test_api_key_required_when_debug_false() -> None:
    problems = web_config.validate_runtime_config(
        {"DEBUG": "false", "CORS_ORIGINS": "https://research.example.org"}
    )
    assert len(problems) == 1
    assert "API_KEY must be set when DEBUG=false" in problems[0]


def test_demo_mode_exempts_api_key_requirement() -> None:
    problems = web_config.validate_runtime_config(
        {
            "DEBUG": "false",
            "DEMO_MODE": "true",
            "CORS_ORIGINS": "https://demo.example.org",
        }
    )
    assert problems == []


def test_invalid_port_is_reported() -> None:
    problems = web_config.validate_runtime_config({"DEBUG": "true", "PORT": "eighty"})
    assert any("PORT must be an integer" in problem for problem in problems)


def test_out_of_range_port_is_reported() -> None:
    problems = web_config.validate_runtime_config({"DEBUG": "true", "PORT": "70000"})
    assert any("PORT must be an integer between 1 and 65535" in problem for problem in problems)


def test_empty_cors_origins_rejected_when_debug_false() -> None:
    problems = web_config.validate_runtime_config(
        {"DEBUG": "false", "API_KEY": "secret", "CORS_ORIGINS": ""}
    )
    assert any(
        "CORS_ORIGINS must list at least one explicit origin" in problem for problem in problems
    )


def test_wildcard_cors_origins_rejected_when_debug_false() -> None:
    problems = web_config.validate_runtime_config(
        {"DEBUG": "false", "API_KEY": "secret", "CORS_ORIGINS": "*"}
    )
    assert any("must not contain '*'" in problem for problem in problems)


def test_cors_origins_may_be_absent_in_debug_mode() -> None:
    assert web_config.validate_runtime_config({"DEBUG": "true", "CORS_ORIGINS": ""}) == []


@pytest.mark.parametrize("flag", ["DEMO_ALLOW_WRITES", "ALLOW_WRITES", "DEMO_WRITE_ENABLED"])
def test_demo_mode_refuses_write_enabled_configuration(flag: str) -> None:
    problems = web_config.validate_runtime_config(
        {
            "DEBUG": "false",
            "DEMO_MODE": "true",
            "CORS_ORIGINS": "https://demo.example.org",
            flag: "true",
        }
    )
    assert any(flag in problem and "read-only" in problem for problem in problems)


def test_write_flags_are_ignored_outside_demo_mode() -> None:
    problems = web_config.validate_runtime_config(
        {
            "DEBUG": "false",
            "API_KEY": "secret",
            "CORS_ORIGINS": "https://research.example.org",
            "DEMO_ALLOW_WRITES": "true",
        }
    )
    assert problems == []


def test_all_problems_are_aggregated_not_just_the_first() -> None:
    problems = web_config.validate_runtime_config(
        {
            "DEBUG": "false",
            "PORT": "not-a-port",
            "CORS_ORIGINS": "",
            "DEMO_MODE": "true",
            "DEMO_ALLOW_WRITES": "true",
        }
    )
    joined = "\n".join(problems)
    assert "PORT must be an integer" in joined
    assert "CORS_ORIGINS must list" in joined
    assert "DEMO_ALLOW_WRITES" in joined
    assert len(problems) >= 3
