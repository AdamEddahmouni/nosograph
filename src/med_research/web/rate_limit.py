"""Distributed sliding-window rate limiting with an in-memory fallback.

Implements the ``RateLimitStore`` contract used by ``RateLimitMiddleware``:
a sliding-window admission check that records each allowed request and
rejects once the request count in the trailing window reaches the limit.

Two backends:

- :class:`InMemoryRateLimitStore` — per-process, list of timestamps per key
  (the original middleware behavior, extracted for reuse).
- :class:`RedisRateLimitStore` — distributed via a Redis sorted set per key,
  trimmed atomically by a Lua script, so multiple app instances share one
  limit.

:func:`create_rate_limit_store` picks Redis when reachable and falls back to
the in-memory store otherwise, so a Redis outage degrades to per-process
limiting instead of disabling the API.
"""

import abc
import os
import time
import uuid
from collections import defaultdict

import redis

# Redis URL for the distributed store. Prefer an explicit
# REDIS_RATE_LIMIT_URL; otherwise reuse the Celery broker's Redis.
REDIS_RATE_LIMIT_URL = (
    os.environ.get("REDIS_RATE_LIMIT_URL")
    or os.environ.get("CELERY_BROKER_URL")
    or "redis://localhost:6379/0"
)

# Atomic sliding-window trim + admission. Returns {allowed, retry_after}:
#   allowed     — 1 if the request is admitted (and recorded), else 0
#   retry_after — seconds until the oldest in-window request expires
#                 (0 when admitted), so clients get a precise backoff.
_SLIDING_WINDOW_LUA = """
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
local count = redis.call('ZCARD', KEYS[1])
if count >= limit then
  local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  local retry_after = window
  if oldest[2] then
    retry_after = (tonumber(oldest[2]) + window) - now
    if retry_after < 0 then retry_after = 0 end
  end
  return {0, retry_after}
end
redis.call('ZADD', KEYS[1], now, member)
redis.call('PEXPIRE', KEYS[1], math.floor(window * 1000))
return {1, 0}
"""


class RateLimitStore(abc.ABC):
    """Sliding-window admission store keyed by client identity."""

    @abc.abstractmethod
    def check(
        self,
        key: str,
        limit: int,
        window: float,
        now: float | None = None,
    ) -> tuple[bool, float]:
        """Return ``(allowed, retry_after)`` for ``key``.

        ``allowed`` is True when the request is admitted and recorded.
        When False, ``retry_after`` is seconds until the oldest request in
        the current window expires (0.0 when admitted).
        """


class InMemoryRateLimitStore(RateLimitStore):
    """Per-process sliding-window store (list of timestamps per key)."""

    def __init__(self) -> None:
        self._store: dict[str, list[float]] = defaultdict(list)

    def check(
        self,
        key: str,
        limit: int,
        window: float,
        now: float | None = None,
    ) -> tuple[bool, float]:
        current = now if now is not None else time.time()
        cutoff = current - window
        timestamps = self._store[key]
        timestamps = [t for t in timestamps if t > cutoff]

        if len(timestamps) >= limit:
            # List is kept in chronological order, so the head is the oldest.
            retry_after = max(0.0, timestamps[0] + window - current)
            return False, retry_after

        timestamps.append(current)
        if timestamps:
            self._store[key] = timestamps
        else:
            self._store.pop(key, None)
        return True, 0.0


class RedisRateLimitStore(RateLimitStore):
    """Distributed sliding-window store backed by a Redis sorted set.

    Each key maps to a sorted set of request timestamps; a Lua script
    trims expired members and admits/records atomically so concurrent
    app instances agree on the same limit. A Redis error fails open
    (allows the request) rather than bricking the API during an outage.
    """

    def __init__(self, client: redis.Redis | None = None, url: str | None = None) -> None:
        self._redis = (
            client
            if client is not None
            else redis.Redis.from_url(
                url or REDIS_RATE_LIMIT_URL,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
                decode_responses=True,
            )
        )
        self._script = self._redis.register_script(_SLIDING_WINDOW_LUA)

    def check(
        self,
        key: str,
        limit: int,
        window: float,
        now: float | None = None,
    ) -> tuple[bool, float]:
        current = now if now is not None else time.time()
        member = f"{current:.6f}:{uuid.uuid4().hex}"
        try:
            result = self._script(keys=[key], args=[current, window, limit, member])
        except redis.RedisError:
            # Fail open: Redis hiccups must not lock out legitimate clients.
            return True, 0.0
        allowed, retry_after = result
        return bool(int(allowed)), float(retry_after)


def create_rate_limit_store(url: str | None = None) -> RateLimitStore:
    """Return a Redis store when reachable, otherwise an in-memory store.

    Connectivity is probed with a short ``ping`` so an absent Redis falls
    back to per-process limiting quickly (1s worst case).
    """
    try:
        client = redis.Redis.from_url(
            url or REDIS_RATE_LIMIT_URL,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
            decode_responses=True,
        )
        client.ping()
        return RedisRateLimitStore(client=client)
    except (redis.RedisError, OSError, ConnectionError, TimeoutError, ValueError, TypeError):
        return InMemoryRateLimitStore()
