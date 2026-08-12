import email.utils
import random
import time
from datetime import datetime, timezone


def rate_limited_sleep(base_seconds: float, jitter: float = 0.5) -> None:
    """Sleep with jitter to avoid thundering herd on fixed-interval rate limits.

    Args:
        base_seconds: The base wait time in seconds.
        jitter: Fraction of base_seconds to use as jitter range (0.0 to 1.0).
                Actual sleep = base * (1 - jitter) + random() * base * jitter * 2
    """
    min_sleep = base_seconds * (1 - jitter)
    max_sleep = base_seconds * (1 + jitter)
    actual = random.uniform(min_sleep, max_sleep)
    time.sleep(actual)


def exponential_backoff(
    attempt: int,
    base_seconds: float = 0.5,
    max_seconds: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: float = 0.5,
) -> float:
    """Calculate sleep duration with exponential backoff and jitter.

    Args:
        attempt: Current retry attempt number (0-based).
        base_seconds: Initial wait time.
        max_seconds: Maximum wait time cap.
        backoff_factor: Multiplicative factor per attempt.
        jitter: Fraction jitter to apply.

    Returns:
        Seconds to sleep before next retry.
    """
    delay = min(base_seconds * (backoff_factor**attempt), max_seconds)
    min_sleep = delay * (1 - jitter)
    max_sleep = delay * (1 + jitter)
    return random.uniform(min_sleep, max_sleep)


def parse_retry_after(value: str | int | None) -> float | None:
    """Parse a ``Retry-After`` header value into seconds to wait."""
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    try:
        seconds = float(raw)
    except ValueError:
        try:
            retry_at = email.utils.parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()

    if seconds <= 0:
        return None
    return seconds


def backoff_sleep(
    attempt: int,
    base_seconds: float = 0.5,
    max_seconds: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: float = 0.5,
    *,
    retry_after: float | None = None,
) -> None:
    """Sleep for an exponential-backoff duration with jitter."""
    if retry_after is not None:
        delay = min(retry_after, max_seconds)
        min_sleep = delay * (1 - jitter)
        max_sleep = delay * (1 + jitter)
        actual = random.uniform(min_sleep, max_sleep)
    else:
        actual = exponential_backoff(
            attempt,
            base_seconds=base_seconds,
            max_seconds=max_seconds,
            backoff_factor=backoff_factor,
            jitter=jitter,
        )
    time.sleep(actual)
