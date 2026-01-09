"""API Key Rotation Manager for handling multiple API keys with rate limit tracking.

This module provides a thread-safe mechanism to rotate through multiple API keys
while respecting per-key rate limits returned by API.
"""

import logging
import threading
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class RotationStrategy:
    """Strategies for selecting next API key."""

    ROUND_ROBIN = "round_robin"
    LEAST_USED = "least_used"
    RANDOM = "random"


@dataclass
class KeyUsageTracker:
    """Track usage statistics for a single API key."""

    api_key: str
    requests_remaining: int = field(default_factory=lambda: 999999)
    requests_limit: int = field(default_factory=lambda: 1000)
    last_reset_time: float = field(default_factory=time.time)
    last_used_time: float = field(default_factory=time.time)
    is_exhausted: bool = field(default=False)
    backoff_until: float = field(default=0.0)


@dataclass
class RateLimitHeaders:
    """Parsed rate limit information from API response headers."""

    limit_minute: Optional[int] = None
    limit_hour: Optional[int] = None
    limit_day: Optional[int] = None
    remaining_minute: Optional[int] = None
    remaining_hour: Optional[int] = None
    remaining_day: Optional[int] = None
    reset_time: Optional[float] = None


class APIKeyRotator:
    """
    Thread-safe API key rotator with rate limit tracking and automatic rotation.

    Features:
    - Tracks multiple API keys with per-key rate limit monitoring
    - Supports multiple rotation strategies (round-robin, least-used, random)
    - Automatic backoff when keys hit rate limits
    - Thread-safe key selection for concurrent requests
    - Detailed logging for debugging and monitoring
    """

    def __init__(
        self,
        api_keys: List[str],
        strategy: str = RotationStrategy.ROUND_ROBIN,
        backoff_seconds: int = 60,
    ):
        """
        Initialize API key rotator.

        Args:
            api_keys: List of API keys to rotate through
            strategy: Rotation strategy (round_robin, least_used, random)
            backoff_seconds: How long to wait (in seconds) before retrying an exhausted key
        """

        if not api_keys:
            raise ValueError("API key list cannot be empty")

        # Remove empty keys and duplicates
        self.api_keys = [key.strip() for key in api_keys if key and key.strip()]
        self.api_keys = list(dict.fromkeys(self.api_keys).keys())  # Remove duplicates

        if not self.api_keys:
            raise ValueError("No valid API keys provided")

        self.strategy = strategy
        self.backoff_seconds = backoff_seconds

        # Initialize usage trackers for each key
        self.usage_trackers: Dict[str, KeyUsageTracker] = {key: KeyUsageTracker() for key in self.api_keys}

        # Round-robin index
        self.current_index = 0

        # Lock for thread-safe operations
        self._lock = threading.RLock()

        logger.info(f"Initialized APIKeyRotator with {len(self.api_keys)} keys using '{strategy}' strategy")

    def _parse_rate_limit_headers(self, headers: Dict[str, str]) -> RateLimitHeaders:
        """
        Parse rate limit information from response headers.

        Args:
            headers: Dictionary of HTTP headers

        Returns:
            RateLimitHeaders with parsed rate limit data
        """
        # SAIA uses standard rate limit headers
        # x-ratelimit-limit-minute, x-ratelimit-limit-hour, x-ratelimit-limit-day
        # x-ratelimit-remaining-minute, x-ratelimit-remaining-hour, x-ratelimit-remaining-day
        # ratelimit-reset (seconds until counter resets)

        result = RateLimitHeaders()

        for key, attr_name in [
            ("x-ratelimit-limit-minute", "limit_minute"),
            ("x-ratelimit-limit-hour", "limit_hour"),
            ("x-ratelimit-limit-day", "limit_day"),
            ("x-ratelimit-remaining-minute", "remaining_minute"),
            ("x-ratelimit-remaining-hour", "remaining_hour"),
            ("x-ratelimit-remaining-day", "remaining_day"),
            ("ratelimit-reset", "reset_time"),
        ]:
            if key in headers:
                try:
                    setattr(result, attr_name, int(headers[key]))
                except (ValueError, TypeError):
                    logger.debug(f"Failed to parse rate limit header '{key}': {headers[key]}")

        # Parse reset time (ratelimit-reset: seconds until counter resets)
        if "ratelimit-reset" in headers:
            try:
                result.reset_time = time.time() + float(headers["ratelimit-reset"])
            except (ValueError, TypeError):
                logger.debug(f"Failed to parse ratelimit-reset: {headers.get('ratelimit-reset')}")

        return result

    def _update_key_usage(self, api_key: str, headers: Dict[str, str]) -> None:
        """
        Update usage tracker for a specific key based on rate limit headers.

        Args:
            api_key: The API key that was used
            headers: Response headers containing rate limit info
        """
        rate_limits = self._parse_rate_limit_headers(headers)

        # Prioritize remaining requests from most restrictive window (minute > hour > day)
        # SAIA typically enforces per-minute limits strictly
        if rate_limits.remaining_minute is not None:
            return

        remaining = rate_limits.remaining_minute
        limit = rate_limits.limit_minute if rate_limits.limit_minute else 1000

        with self._lock:
            tracker = self.usage_trackers.get(api_key)

            if tracker:
                tracker.requests_remaining = remaining
                tracker.requests_limit = limit
                tracker.last_reset_time = time.time()
                tracker.last_used_time = time.time()

                # Mark as exhausted if below threshold
                tracker.is_exhausted = remaining < 10

                logger.debug(f"Updated key usage: {api_key[:10]}... - {remaining}/{limit} remaining (minute window)")

    def get_next_key(self, skip_exhausted: bool = False) -> tuple[str, Optional[RateLimitHeaders]]:
        """
        Get next available API key based on rotation strategy.

        Args:
            skip_exhausted: If True, skip keys that are currently exhausted

        Returns:
            Tuple of (api_key, current_rate_limit_info)
        """
        with self._lock:
            available_keys = []

            for key in self.api_keys:
                tracker = self.usage_trackers.get(key)
                if not tracker:
                    available_keys.append(key)
                elif not tracker.is_exhausted:
                    # Check if backoff period has expired
                    if time.time() > tracker.backoff_until:
                        # Reset for reuse
                        tracker.is_exhausted = False
                        tracker.requests_remaining = tracker.requests_limit
                        logger.info(f"Backoff expired for key {key[:10]}... - resetting for rotation")
                    # Add to available if not skipping exhausted
                    available_keys.append(key)
                else:
                    logger.debug(
                        f"Key {key[:10]}... exhausted - "
                        f"backing off for {self.backoff_seconds}s "
                        f"({int(tracker.backoff_until - time.time())}s remaining)"
                    )
            if not available_keys:
                if skip_exhausted:
                    # All keys exhausted - wait for next reset
                    logger.warning(f"All SAIA API keys exhausted. Waiting {self.backoff_seconds}s for reset...")
                    time.sleep(self.backoff_seconds)
