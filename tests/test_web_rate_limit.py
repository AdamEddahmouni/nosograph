"""Tests for the distributed sliding-window rate limit store.

Covers :class:`InMemoryRateLimitStore` semantics, the Redis store's script
calls and fail-open behavior, the create/fallback factory, and the
middleware's 429 integration.
"""

import pytest
import redis

from med_research.web.middleware import RateLimitMiddleware
from med_research.web.rate_limit import (
    InMemoryRateLimitStore,
    RedisRateLimitStore,
    create_rate_limit_store,
)

pytestmark = pytest.mark.unit


# ── In-memory store ─────────────────────────────────────────────────────────


class TestInMemoryRateLimitStore:
    def test_allows_until_limit(self):
        store = InMemoryRateLimitStore()
        now = 1000.0
        for i in range(3):
            allowed, retry = store.check("1.2.3.4", limit=3, window=60, now=now + i)
            assert allowed is True
            assert retry == 0.0
        allowed, retry = store.check("1.2.3.4", limit=3, window=60, now=now + 3)
        assert allowed is False
        assert retry > 0

    def test_window_expiry_lets_requests_through(self):
        store = InMemoryRateLimitStore()
        now = 1000.0
        for i in range(3):
            store.check("ip", limit=3, window=60, now=now + i)
        # Advance past the window: the old entries expire.
        allowed, _ = store.check("ip", limit=3, window=60, now=now + 61)
        assert allowed is True

    def test_retry_after_tracks_oldest_entry(self):
        store = InMemoryRateLimitStore()
        now = 1000.0
        for i in range(3):
            store.check("ip", limit=3, window=60, now=now + i)  # 1000, 1001, 1002
        allowed, retry = store.check("ip", limit=3, window=60, now=now + 5)
        assert allowed is False
        # Oldest (1000.0) expires at 1060.0, so ~55s remain.
        assert 54.0 <= retry <= 60.0

    def test_keys_are_independent(self):
        store = InMemoryRateLimitStore()
        store.check("a", limit=1, window=60, now=1000.0)
        allowed, _ = store.check("b", limit=1, window=60, now=1000.0)
        assert allowed is True


# ── Redis store (fake client) ───────────────────────────────────────────────


class _FakeScript:
    def __init__(self, result):
        self.result = result
        self.keys = None
        self.args = None

    def __call__(self, keys=None, args=None):
        self.keys = keys
        self.args = args
        return self.result


class _FakeRedisClient:
    def __init__(self, script):
        self.script = script

    def register_script(self, _lua):
        return self.script


class TestRedisRateLimitStore:
    def _store(self, script_result):
        script = _FakeScript(script_result)
        store = RedisRateLimitStore(client=_FakeRedisClient(script))
        return store, script

    def test_allowed_forwards_window_and_limit(self):
        store, script = self._store([1, 0])
        allowed, retry = store.check("ip", limit=60, window=60, now=1234.5)
        assert allowed is True
        assert retry == 0.0
        assert script.keys == ["ip"]
        assert script.args[0] == 1234.5
        assert script.args[1] == 60
        assert script.args[2] == 60
        # The member must be unique per request (timestamps + uuid suffix).
        assert isinstance(script.args[3], str)

    def test_blocked_reports_retry_after(self):
        store, _ = self._store([0, 42.5])
        allowed, retry = store.check("ip", limit=60, window=60, now=1000.0)
        assert allowed is False
        assert retry == 42.5

    def test_redis_error_fails_open(self):
        store, _ = self._store([1, 0])

        def boom(**kwargs):
            raise redis.exceptions.RedisError("backend down")

        store._script = boom
        allowed, retry = store.check("ip", limit=60, window=60, now=1000.0)
        assert allowed is True
        assert retry == 0.0


# ── Factory / fallback ──────────────────────────────────────────────────────


class TestCreateRateLimitStore:
    def test_falls_back_to_memory_when_redis_unreachable(self, monkeypatch):
        class Unreachable:
            def __init__(self, *a, **kw):
                pass

            def ping(self):
                raise redis.exceptions.ConnectionError("down")

        monkeypatch.setattr(
            "med_research.web.rate_limit.redis.Redis.from_url",
            staticmethod(lambda *a, **kw: Unreachable()),
        )
        store = create_rate_limit_store(url="redis://localhost:1/0")
        assert isinstance(store, InMemoryRateLimitStore)

    def test_uses_redis_when_reachable(self, monkeypatch):
        class Reachable:
            def __init__(self, *a, **kw):
                pass

            def ping(self):
                return True

            def register_script(self, _lua):
                return lambda keys=None, args=None: [1, 0]

        monkeypatch.setattr(
            "med_research.web.rate_limit.redis.Redis.from_url",
            staticmethod(lambda *a, **kw: Reachable()),
        )
        store = create_rate_limit_store(url="redis://localhost:6379/0")
        assert isinstance(store, RedisRateLimitStore)


# ── Middleware integration ──────────────────────────────────────────────────


class TestRateLimitMiddleware:
    def test_returns_429_after_limit(self, monkeypatch):
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        from med_research.web import middleware as mw

        monkeypatch.setattr(mw, "RATE_LIMIT_REQUESTS", 2)
        monkeypatch.setattr(mw, "RATE_LIMIT_WINDOW", 60)
        monkeypatch.setattr(mw, "create_rate_limit_store", lambda: InMemoryRateLimitStore())

        app = FastAPI()

        @app.get("/api/jobs/status")
        def status():
            return {"ok": True}

        app.add_middleware(RateLimitMiddleware)
        with TestClient(app) as client:
            assert client.get("/api/jobs/status").status_code == 200
            assert client.get("/api/jobs/status").status_code == 200
            blocked = client.get("/api/jobs/status")
            assert blocked.status_code == 429
            body = blocked.json()
            assert "retry_after" in body
            assert body["retry_after"] > 0

    def test_disabled_when_limit_zero(self, monkeypatch):
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        from med_research.web import middleware as mw

        monkeypatch.setattr(mw, "RATE_LIMIT_REQUESTS", 0)
        app = FastAPI()

        @app.get("/api/jobs/status")
        def status():
            return {"ok": True}

        app.add_middleware(RateLimitMiddleware)
        with TestClient(app) as client:
            for _ in range(5):
                assert client.get("/api/jobs/status").status_code == 200
