import random
import time


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
    delay = min(base_seconds * (backoff_factor ** attempt), max_seconds)
    min_sleep = delay * (1 - jitter)
    max_sleep = delay * (1 + jitter)
    return random.uniform(min_sleep, max_sleep)


def backoff_sleep(
    attempt: int,
    base_seconds: float = 0.5,
    max_seconds: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: float = 0.5,
) -> None:
    """Sleep for an exponential-backoff duration with jitter."""
    time.sleep(
        exponential_backoff(
            attempt,
            base_seconds=base_seconds,
            max_seconds=max_seconds,
            backoff_factor=backoff_factor,
            jitter=jitter,
        )
    )
