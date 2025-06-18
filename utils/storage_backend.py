"""
In-memory storage backend for conversation threads

This module provides a thread-safe, in-memory alternative to Redis for storing
conversation contexts. It's designed for ephemeral MCP server sessions where
conversations only need to persist during a single Claude session.

⚠️  PROCESS-SPECIFIC STORAGE: This storage is confined to a single Python process.
    Data stored in one process is NOT accessible from other processes or subprocesses.
    This is why simulator tests that run server.py as separate subprocesses cannot
    share conversation state between tool calls.

Key Features:
- Thread-safe operations using locks
- TTL support with automatic expiration
- Background cleanup thread for memory management
- Singleton pattern for consistent state within a single process
- Drop-in replacement for Redis storage (for single-process scenarios)
"""

import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class InMemoryStorage:
    """Thread-safe in-memory storage for conversation threads"""

    def __init__(self):
        self._store: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        # Match Redis behavior: cleanup interval based on conversation timeout
        # Run cleanup at 1/10th of timeout interval (e.g., 18 mins for 3 hour timeout)
        timeout_hours = int(os.getenv("CONVERSATION_TIMEOUT_HOURS", "3"))
        self._cleanup_interval = (timeout_hours * 3600) // 10
        self._cleanup_interval = max(300, self._cleanup_interval)  # Minimum 5 minutes
        self._shutdown = False

        # Start background cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()

        logger.info(
            f"In-memory storage initialized with {timeout_hours}h timeout, cleanup every {self._cleanup_interval//60}m"
        )

    def set_with_ttl(self, key: str, ttl_seconds: int, value: str) -> None:
        """Store value with expiration time"""
        with self._lock:
            expires_at = time.time() + ttl_seconds
            self._store[key] = (value, expires_at)
            logger.debug(f"Stored key {key} with TTL {ttl_seconds}s")

    def get(self, key: str) -> Optional[str]:
        """Retrieve value if not expired"""
        with self._lock:
            if key in self._store:
                value, expires_at = self._store[key]
                if time.time() < expires_at:
                    logger.debug(f"Retrieved key {key}")
                    return value
                else:
                    # Clean up expired entry
                    del self._store[key]
                    logger.debug(f"Key {key} expired and removed")
        return None

    def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        """Redis-compatible setex method"""
        self.set_with_ttl(key, ttl_seconds, value)

    def _cleanup_worker(self):
        """Background thread that periodically cleans up expired entries"""
        while not self._shutdown:
            time.sleep(self._cleanup_interval)
            self._cleanup_expired()

    def _cleanup_expired(self):
        """Remove all expired entries"""
        with self._lock:
            current_time = time.time()
            expired_keys = [k for k, (_, exp) in self._store.items() if exp < current_time]
            for key in expired_keys:
                del self._store[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired conversation threads")

    def shutdown(self):
        """Graceful shutdown of background thread"""
        self._shutdown = True
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=1)


# Global singleton instance
_storage_instance = None
_storage_lock = threading.Lock()


def get_storage_backend() -> InMemoryStorage:
    """Get the global storage instance (singleton pattern)"""
    global _storage_instance
    if _storage_instance is None:
        with _storage_lock:
            if _storage_instance is None:
                _storage_instance = InMemoryStorage()
                logger.info("Initialized in-memory conversation storage")
    return _storage_instance
