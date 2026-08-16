"""Integration test configuration — auto-mark tests in this directory.

Marker policy (see also ``tests/conftest.py`` and ``pyproject.toml``):

- Every test under ``tests/integration/`` receives ``@pytest.mark.integration``.
- Fast tests under ``tests/`` declare ``@pytest.mark.unit`` explicitly; tests
  without ``slow`` or ``integration`` still receive ``unit`` via
  ``tests/conftest.py`` as a fallback.
"""

from __future__ import annotations

import socket

import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        if "/integration/" in item.nodeid.replace("\\", "/"):
            item.add_marker(pytest.mark.integration)


def _redis_available() -> bool:
    """Return True when Redis is reachable on localhost:6379."""
    try:
        sock = socket.create_connection(("localhost", 6379), timeout=1)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


REDIS_AVAILABLE = _redis_available()
skip_without_redis = pytest.mark.skipif(
    not REDIS_AVAILABLE,
    reason="Redis server not available on localhost:6379",
)


CORE_DISEASES: tuple[str, ...] = ("sle", "ra", "ms", "ss", "ssc", "t1d", "ibd")


def all_disease_ids() -> tuple[str, ...]:
    """Return sorted disease IDs discovered from disease profile data.

    Defaults to the 7 core benchmark diseases to avoid inflating test parametrization
    to 22,000+ items. Set TEST_ALL_DISEASES=1 to run against the entire scaffolded corpus.
    """
    import os

    if os.environ.get("TEST_ALL_DISEASES"):
        from med_research.pipeline.knowledge_graph.config import list_diseases

        return tuple(sorted(list_diseases().keys()))
    return CORE_DISEASES


ALL_DISEASES = all_disease_ids()


@pytest.fixture
def evidence_api_mocks(evidence_http_mocks):
    """Alias for integration CLI smokes."""
    return evidence_http_mocks


@pytest.fixture
def celery_eager():
    """Run Celery tasks inline (no worker) while keeping the Redis result backend."""
    from med_research.web.tasks.analysis_tasks import celery_app

    prior = {
        "task_always_eager": celery_app.conf.task_always_eager,
        "task_eager_propagates": celery_app.conf.task_eager_propagates,
    }
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield celery_app
    celery_app.conf.task_always_eager = prior["task_always_eager"]
    celery_app.conf.task_eager_propagates = prior["task_eager_propagates"]


@pytest.fixture
def integration_client(celery_eager):
    """FastAPI TestClient with eager Celery for job lifecycle integration tests."""
    from fastapi.testclient import TestClient

    from med_research.web.main import app

    with TestClient(app) as client:
        yield client
