"""Regression tests for dependency ranges that affect automated updates."""

import tomllib
from pathlib import Path

import yaml
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]


def _project_requirement(name: str) -> Requirement:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return next(
        requirement
        for raw_requirement in project["dependencies"]
        if (requirement := Requirement(raw_requirement)).name == name
    )


def _requirements_input(name: str) -> Requirement:
    return next(
        requirement
        for raw_line in (ROOT / "requirements.in").read_text(encoding="utf-8").splitlines()
        if (line := raw_line.strip())
        and not line.startswith(("#", "-"))
        and (requirement := Requirement(line)).name == name
    )


def test_redis_runtime_constraints_exclude_versions_unsupported_by_kombu() -> None:
    for requirement in (_project_requirement("redis"), _requirements_input("redis")):
        assert requirement.specifier.contains("6.4.0")
        assert not requirement.specifier.contains("6.5.0")
        assert not requirement.specifier.contains("8.1.0")


def test_dependabot_ignores_redis_versions_unsupported_by_kombu() -> None:
    config = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    pip_updates = next(
        update for update in config["updates"] if update["package-ecosystem"] == "pip"
    )
    redis_ignore = next(
        rule for rule in pip_updates["ignore"] if rule["dependency-name"] == "redis"
    )

    assert ">=6.5" in redis_ignore["versions"]
