"""
Storage backends for conversation threads.

This module provides multiple storage backends for conversation contexts:
- InMemoryStorage: For MCP server mode (single persistent process)
- SQLiteStorage: For Skills mode (cross-process persistence)

The backend is selected via PAL_SKILL_STORAGE environment variable:
- "memory" (default): Use in-memory storage (MCP mode)
- "sqlite": Use SQLite for cross-process persistence (Skills mode)

⚠️  PROCESS-SPECIFIC vs CROSS-PROCESS:
    - InMemoryStorage: Data confined to single Python process
    - SQLiteStorage: Data persists across process invocations
"""

import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from utils.env import get_env

logger = logging.getLogger(__name__)


# =============================================================================
# Storage Protocol
# =============================================================================


@runtime_checkable
class StorageBackend(Protocol):
    """Protocol for storage backends."""

    def get(self, key: str) -> Optional[str]:
        """Retrieve value by key, returns None if not found or expired."""
        ...

    def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        """Store value with TTL (time-to-live) in seconds."""
        ...

    def set_with_ttl(self, key: str, ttl_seconds: int, value: str) -> None:
        """Alias for setex, for compatibility."""
        ...


# =============================================================================
# In-Memory Storage (for MCP mode)
# =============================================================================


class InMemoryStorage:
    """Thread-safe in-memory storage for conversation threads.

    Suitable for MCP server mode where the process persists.
    Data is lost when the process exits.
    """

    def __init__(self):
        self._store: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        # Match Redis behavior: cleanup interval based on conversation timeout
        # Run cleanup at 1/10th of timeout interval (e.g., 18 mins for 3 hour timeout)
        timeout_hours = int(get_env("CONVERSATION_TIMEOUT_HOURS", "3") or "3")
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


# =============================================================================
# SQLite Storage (for Skills mode - cross-process persistence)
# =============================================================================


class SQLiteStorage:
    """SQLite-based storage for cross-process persistence.

    Suitable for Skills mode where each invocation is a separate process.
    Data persists in ~/.pal_mcp/sessions.db across process invocations.

    Features:
    - WAL mode for better concurrent access
    - Automatic TTL expiration
    - Thread-safe with RLock
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize SQLite storage.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.pal_mcp/sessions.db
        """
        if db_path is None:
            db_path = os.path.expanduser("~/.pal_mcp/sessions.db")

        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()

        # Initialize database
        self._init_db()

        logger.info(f"SQLite storage initialized at {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Create a new connection for the current thread."""
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=10.0,
            isolation_level=None,  # autocommit mode
        )
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=10000;")
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        expire_at REAL
                    );
                    """
                )
                # Create index for expiration queries
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_expire_at ON sessions(expire_at);
                    """
                )
            finally:
                conn.close()

    def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        """Store value with TTL."""
        expire_at = time.time() + ttl_seconds
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO sessions (key, value, expire_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        expire_at = excluded.expire_at;
                    """,
                    (key, value, expire_at),
                )
                logger.debug(f"SQLite: Stored key {key} with TTL {ttl_seconds}s")

                # Probabilistic cleanup (2% chance)
                self._maybe_cleanup(conn)
            finally:
                conn.close()

    def set_with_ttl(self, key: str, ttl_seconds: int, value: str) -> None:
        """Alias for setex."""
        self.setex(key, ttl_seconds, value)

    def get(self, key: str) -> Optional[str]:
        """Retrieve value if not expired."""
        now = time.time()
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT value, expire_at FROM sessions WHERE key = ?;",
                    (key,),
                )
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"SQLite: Key {key} not found")
                    return None

                value, expire_at = row

                if expire_at is not None and expire_at <= now:
                    # Expired, delete it
                    conn.execute("DELETE FROM sessions WHERE key = ?;", (key,))
                    logger.debug(f"SQLite: Key {key} expired and removed")
                    return None

                logger.debug(f"SQLite: Retrieved key {key}")
                return value
            finally:
                conn.close()

    def _maybe_cleanup(self, conn: sqlite3.Connection, probability: float = 0.02) -> None:
        """Probabilistic cleanup of expired entries.

        Only runs with given probability to avoid overhead on every write.
        """
        if os.urandom(1)[0] / 255.0 <= probability:
            deleted = conn.execute(
                "DELETE FROM sessions WHERE expire_at IS NOT NULL AND expire_at <= ?;",
                (time.time(),),
            ).rowcount
            if deleted:
                logger.debug(f"SQLite: Cleaned up {deleted} expired sessions")

    def cleanup_expired(self) -> int:
        """Force cleanup of all expired entries. Returns count of deleted entries."""
        with self._lock:
            conn = self._get_connection()
            try:
                deleted = conn.execute(
                    "DELETE FROM sessions WHERE expire_at IS NOT NULL AND expire_at <= ?;",
                    (time.time(),),
                ).rowcount
                if deleted:
                    logger.info(f"SQLite: Cleaned up {deleted} expired sessions")
                return deleted
            finally:
                conn.close()


# =============================================================================
# Storage Backend Factory
# =============================================================================

# Global singleton instance
_storage_instance: Optional[StorageBackend] = None
_storage_lock = threading.Lock()


def get_storage_backend() -> StorageBackend:
    """Get the global storage instance (singleton pattern).

    The backend is selected via PAL_SKILL_STORAGE environment variable:
    - "memory" (default): InMemoryStorage for MCP mode
    - "sqlite": SQLiteStorage for Skills mode (cross-process persistence)

    For Skills mode, set PAL_SKILL_STORAGE=sqlite before importing this module.
    """
    global _storage_instance

    if _storage_instance is not None:
        return _storage_instance

    with _storage_lock:
        if _storage_instance is not None:
            return _storage_instance

        storage_type = os.environ.get("PAL_SKILL_STORAGE", "memory").lower()

        if storage_type == "sqlite":
            # SQLite storage for Skills mode
            db_path = os.environ.get("PAL_SKILL_STORAGE_PATH")
            try:
                _storage_instance = SQLiteStorage(db_path)
                logger.info("Using SQLite storage for cross-process persistence")
            except Exception as e:
                logger.warning(f"Failed to initialize SQLite storage: {e}, falling back to memory")
                _storage_instance = InMemoryStorage()
        else:
            # Default: in-memory storage for MCP mode
            _storage_instance = InMemoryStorage()
            logger.info("Using in-memory storage (MCP mode)")

        return _storage_instance
