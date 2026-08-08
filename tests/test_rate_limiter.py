"""Unit tests for rate limiting and backoff helpers."""

from datetime import datetime, timedelta, timezone

import pytest

from med_research.rate_limiter import (
    backoff_sleep,
    exponential_backoff,
    parse_retry_after,
    rate_limited_sleep,
)


class TestParseRetryAfter:
    def test_none_returns_none(self):
        assert parse_retry_after(None) is None

    def test_integer_seconds(self):
        assert parse_retry_after("5") == 5.0
        assert parse_retry_after(12) == 12.0

    def test_http_date_in_future(self, monkeypatch):
        future = datetime.now(timezone.utc) + timedelta(seconds=30)
        header = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
        assert parse_retry_after(header) == pytest.approx(30.0, abs=1.0)

    def test_invalid_value_returns_none(self):
        assert parse_retry_after("not-a-date") is None
        assert parse_retry_after("") is None


class TestExponentialBackoff:
    def test_attempt_zero_within_bounds(self, monkeypatch):
        monkeypatch.setattr("med_research.rate_limiter.random.uniform", lambda lo, hi: lo)
        assert exponential_backoff(0, base_seconds=1.0, jitter=0.0) == 1.0

    def test_respects_max_seconds(self, monkeypatch):
        monkeypatch.setattr("med_research.rate_limiter.random.uniform", lambda lo, hi: hi)
        delay = exponential_backoff(10, base_seconds=1.0, max_seconds=5.0, jitter=0.0)
        assert delay == 5.0


class TestRateLimitedSleep:
    def test_uses_jittered_bounds(self, monkeypatch):
        slept: list[float] = []
        monkeypatch.setattr("med_research.rate_limiter.time.sleep", lambda s: slept.append(s))
        monkeypatch.setattr("med_research.rate_limiter.random.uniform", lambda lo, hi: lo)

        rate_limited_sleep(1.0, jitter=0.5)
        assert slept == [0.5]


class TestBackoffSleep:
    def test_exponential_path(self, monkeypatch):
        slept: list[float] = []
        monkeypatch.setattr("med_research.rate_limiter.time.sleep", lambda s: slept.append(s))
        monkeypatch.setattr(
            "med_research.rate_limiter.exponential_backoff",
            lambda *args, **kwargs: 2.5,
        )

        backoff_sleep(1)
        assert slept == [2.5]

    def test_retry_after_path(self, monkeypatch):
        slept: list[float] = []
        monkeypatch.setattr("med_research.rate_limiter.time.sleep", lambda s: slept.append(s))
        monkeypatch.setattr("med_research.rate_limiter.random.uniform", lambda lo, hi: lo)

        backoff_sleep(0, retry_after=10.0, jitter=0.0)
        assert slept == [10.0]
