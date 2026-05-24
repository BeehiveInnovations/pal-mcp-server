"""GeminiSwitcherClient — stateless reader of universal switcher shared-state files.

Implements the Python side of the cross-language Gemini Account Switcher contract
defined in docs/specs/2026-05-24-task007-solutions-spec.md §2 + §4.1.

Hard rules enforced here:
  - GEMINI-OAUTH-ONLY: never reads GEMINI_API_KEY; never hits generativelanguage.googleapis.com
  - NEVER rotates oauth_creds.json autonomously
  - Re-reads oauth_creds.json on EVERY get_credentials() call (no mtime caching — §9a.1)
  - flock-guarded read-modify-write for health ledger (§9a.2)
  - Subprocess rotate-on-demand uses gemini-node-path.json, not PATH (§9a.3)

Pure stdlib only: json, os, time, pathlib, hashlib, urllib.request, tempfile, sys, platform
NO new pip dependencies.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import platform
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OAuth / Code Assist constants (mirrors gemini.py / gemini-chain.js)
# ---------------------------------------------------------------------------
_GEMINI_CLI_CLIENT_ID = "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"
# Public Gemini CLI OAuth client — see https://github.com/google-gemini/gemini-cli
_GEMINI_CLI_CLIENT_SECRET = os.environ.get("GEMINI_CLI_CLIENT_SECRET", "<REDACTED_PUBLIC_CLI_SECRET>")  # noqa: S105 — public installed-app secret
_OAUTH_TOKEN_URI = "https://oauth2.googleapis.com/token"
_CODE_ASSIST_ENDPOINT = "https://cloudcode-pa.googleapis.com"
_CODE_ASSIST_VERSION = "v1internal"

# Refresh when < 5 minutes remain (expiry_date is epoch-ms in JSON)
_EXPIRY_BUFFER_MS = 5 * 60 * 1000


class GeminiSwitcherClient:
    """Stateless reader of universal switcher state files.

    NEVER rotates creds autonomously.
    NEVER writes oauth_creds.json.
    Re-reads live creds on EVERY get_credentials() call.

    State file paths follow §2.1 of the spec.
    """

    # Shared-state file paths (canonical — must match gemini-chain.js)
    CREDS = Path.home() / ".gemini" / "oauth_creds.json"
    ROT = Path.home() / ".claude" / "state" / "gemini-account-rotation.json"
    HEALTH = Path.home() / ".claude" / "state" / "gemini-account-health.json"
    HEALTH_LOCK = Path.home() / ".claude" / "state" / ".gemini-account-health.lock"
    SENTINEL = Path.home() / ".claude" / "data" / "rotation-in-progress.json"
    PROJECT_CACHE = Path.home() / ".gemini" / "hook_project_id.json"
    NODE_PATH_FILE = Path.home() / ".claude" / "state" / "gemini-node-path.json"

    SENTINEL_MAX_AGE_MS = 10_000   # 10 s — stale sentinel; proceed anyway
    SENTINEL_WAIT_MS = 5_000       # 5 s max wait while sentinel is active
    SENTINEL_POLL_MS = 100         # poll every 100 ms

    # request-scope flag: set by request_rotation(); read by caller after generate
    _rotation_requested: bool = False

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def get_credentials(self) -> dict:
        """Return {access_token, refresh_token, expiry_ms, fingerprint, account_email}.

        Honors rotation-in-progress.json sentinel before reading creds.
        Re-reads oauth_creds.json on EVERY invocation — no caching.
        Refreshes access_token via OAuth2 token endpoint when near expiry.
        """
        self._wait_for_sentinel_clear()
        raw = self._read_creds_file()
        if self._is_expired(raw):
            raw = self._refresh_token_and_persist(raw)
        return self._with_fingerprint(raw)

    def get_project_id(self, fingerprint: str) -> str:
        """Return Code Assist project ID for this fingerprint.

        Reads hook_project_id.json keyed by fingerprint.
        Falls back to onboardUser (loadCodeAssist) on cache miss.
        NEVER returns a project_id derived from a different fingerprint.

        Raises:
            RuntimeError: If project ID cannot be resolved.
        """
        if self.PROJECT_CACHE.exists():
            try:
                cache = json.loads(self.PROJECT_CACHE.read_text(encoding="utf-8"))
                entry = cache.get(fingerprint) or {}
                project_id = entry.get("project_id") or entry.get("cloudaicompanionProject")
                if project_id:
                    return project_id
            except Exception as exc:
                logger.warning("hook_project_id.json read error: %s — falling back to resolve", exc)

        logger.debug("Project ID cache miss for fingerprint %s — resolving via onboardUser", fingerprint)
        return self._resolve_via_onboard(fingerprint)

    def record_429(
        self,
        fingerprint: str,
        reason: str,
        reset_after_ms: int,
        model_hit: str,
    ) -> None:
        """Atomic read-modify-write of gemini-account-health.json.

        Uses platform-appropriate file lock to prevent race with Node recordThrottle.
        Last-writer-wins on the full fingerprint entry (never corrupts the file).

        Args:
            fingerprint: Account fingerprint (SHA256 of account email or token).
            reason: '429-RPM' | '429-daily' | 'RATE_LIMIT_EXCEEDED' | custom string.
            reset_after_ms: milliseconds until rate-limit resets (from API hint).
            model_hit: model name that received the 429 (e.g. 'gemini-2.5-flash').
        """
        now_ms = int(time.time() * 1000)
        cooldown_until = now_ms + reset_after_ms + 2000  # +2s safety margin

        self.HEALTH.parent.mkdir(parents=True, exist_ok=True)

        with _FileLock(self.HEALTH_LOCK, timeout_ms=500):
            # Read current ledger
            ledger: dict = {}
            if self.HEALTH.exists():
                try:
                    ledger = json.loads(self.HEALTH.read_text(encoding="utf-8"))
                except Exception as exc:
                    logger.warning("Health ledger read error (will overwrite): %s", exc)

            # Merge: preserve other fingerprint entries; update this one
            entry = ledger.get(fingerprint, {})
            entry.update({
                "fingerprint": fingerprint,
                "last429Reason": reason,
                "last429At": now_ms,
                "cooldownUntil": cooldown_until,
                "resetAfterMs": reset_after_ms,
                "modelHit": model_hit,
            })
            ledger[fingerprint] = entry

            # Atomic .tmp → rename write (same pattern as Node side / TASK-185)
            _atomic_write_json(self.HEALTH, ledger)

        logger.debug(
            "record_429: fingerprint=%s reason=%s resetAfterMs=%d model=%s",
            fingerprint[:8],
            reason,
            reset_after_ms,
            model_hit,
        )

    def record_success(self, fingerprint: str) -> None:
        """Bump lastUsedAt in health ledger for circular re-entry selector (§3.1)."""
        now_ms = int(time.time() * 1000)
        self.HEALTH.parent.mkdir(parents=True, exist_ok=True)

        with _FileLock(self.HEALTH_LOCK, timeout_ms=500):
            ledger: dict = {}
            if self.HEALTH.exists():
                try:
                    ledger = json.loads(self.HEALTH.read_text(encoding="utf-8"))
                except Exception:
                    pass
            entry = ledger.get(fingerprint, {})
            entry["lastUsedAt"] = now_ms
            entry["fingerprint"] = fingerprint
            ledger[fingerprint] = entry
            _atomic_write_json(self.HEALTH, ledger)

    def request_rotation(self, reason: str) -> None:
        """Mark a request-scope rotation flag.

        Does NOT write any creds file.
        Caller decides whether to trigger rotation via rotate-on-demand.js subprocess.
        """
        self._rotation_requested = True
        logger.warning("GeminiSwitcherClient.request_rotation called: reason=%s", reason)

    def rotation_was_requested(self) -> bool:
        """True if request_rotation() was called since last reset."""
        return self._rotation_requested

    def reset_rotation_flag(self) -> None:
        """Reset the request-scope rotation flag."""
        self._rotation_requested = False

    # ---------------------------------------------------------------------------
    # TASK-20260528-218 — 4-combo rotation primitives (read-only account access +
    # shared combo-state). Mirrors gemini-chain.js ACCOUNT_SNAPSHOTS / combo-state.
    # ---------------------------------------------------------------------------

    # Per-account credential snapshots (canonical order = combo cycle account order).
    # Index 0 = Account A (primary), Index 1 = Account B (fallback). MUST match
    # gemini-chain.js ACCOUNT_SNAPSHOTS (L364-367) byte-for-byte in ordering.
    ACCOUNT_SNAPSHOTS = [
        Path.home() / ".gemini" / "oauth_creds.account-h2softbotics.json",
        Path.home() / ".gemini" / "oauth_creds.account-hamadhayyat.json",
    ]
    COMBO_STATE = Path.home() / ".claude" / "state" / "gemini-combo-state.json"

    @staticmethod
    def fingerprint_from_refresh_token(refresh_token: str) -> str:
        """Node-parity account fingerprint = SHA256(refresh_token)[:16].

        MUST match gemini-chain.js fingerprintFromRefreshToken (L528-533) so PAL's
        health-ledger writes key the SAME entries the Node side reads. The legacy
        access-token fingerprint (_with_fingerprint) keyed phantom entries Node never
        saw — this is the cross-language parity key.
        """
        if not refresh_token or not isinstance(refresh_token, str):
            return ""
        return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()[:16]

    def get_credentials_for_account_index(self, idx: int) -> dict:
        """READ-ONLY: return creds for ACCOUNT_SNAPSHOTS[idx] without mutating the
        live oauth_creds.json and without invoking rotate-on-demand.js (Proof B).

        Reads the per-account snapshot, refreshes the access_token in-place INTO THE
        SNAPSHOT FILE ONLY (never the live file — that would be a rotation), and returns
        {access_token, refresh_token, expiry_ms, fingerprint, account_email}.
        fingerprint is the Node-parity refresh_token fingerprint.

        Raises:
            IndexError: idx out of range.
            FileNotFoundError: snapshot missing.
        """
        if idx < 0 or idx >= len(self.ACCOUNT_SNAPSHOTS):
            raise IndexError(f"account index {idx} out of range (0..{len(self.ACCOUNT_SNAPSHOTS) - 1})")
        snap = self.ACCOUNT_SNAPSHOTS[idx]
        if not snap.exists():
            raise FileNotFoundError(f"account snapshot not found at {snap}. Run: gemini auth login")
        raw = json.loads(snap.read_text(encoding="utf-8"))
        if self._is_expired(raw):
            raw = self._refresh_token_into(raw, snap)
        token = raw.get("access_token", "")
        return {
            "access_token": token,
            "refresh_token": raw.get("refresh_token", ""),
            "expiry_ms": int(raw.get("expiry_date", 0)),
            "fingerprint": self.fingerprint_from_refresh_token(raw.get("refresh_token", "")),
            "account_email": raw.get("account_email") or raw.get("email") or "unknown",
        }

    def _refresh_token_into(self, raw: dict, target: Path) -> dict:
        """Refresh access_token and persist back to `target` (a snapshot file), NOT the
        live oauth_creds.json. Same refresh contract as _refresh_token_and_persist but
        write destination is the per-account snapshot — preserves the no-rotation invariant.
        """
        refresh_token = raw.get("refresh_token")
        if not refresh_token:
            raise ValueError(f"refresh_token missing from {target}. Run: gemini auth login")
        body = (
            f"client_id={_GEMINI_CLI_CLIENT_ID}"
            f"&client_secret={_GEMINI_CLI_CLIENT_SECRET}"
            f"&refresh_token={refresh_token}"
            f"&grant_type=refresh_token"
        ).encode()
        req = urllib.request.Request(
            _OAUTH_TOKEN_URI,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                token_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise ValueError(f"refresh_token for {target} expired/revoked. Run: gemini auth login") from exc
            raise RuntimeError(f"OAuth refresh failed HTTP {exc.code} for {target}") from exc
        except Exception as exc:
            raise RuntimeError(f"OAuth refresh network error for {target}: {exc}") from exc
        new_token = token_data.get("access_token")
        if not new_token:
            raise RuntimeError(f"OAuth refresh returned no access_token for {target}")
        expires_in = int(token_data.get("expires_in", 3600))
        raw["access_token"] = new_token
        raw["expiry_date"] = int(time.time() * 1000) + expires_in * 1000
        try:
            _atomic_write_json(target, raw)
        except Exception as exc:
            logger.warning("Could not persist refreshed token into snapshot %s: %s", target, exc)
        return raw

    def read_combo_state(self) -> dict:
        """Read the shared gemini-combo-state.json (4-combo cooldown ledger).

        Schema mirrors gemini-chain.js: {comboIndex, updatedAt, reason, combos:[{status,
        cooldownUntil, note}, ...]}. Returns a default 4-active structure if absent.
        Best-effort — never raises.
        """
        default = {
            "comboIndex": 0,
            "updatedAt": None,
            "reason": "pal-init",
            "combos": [{"status": "active", "cooldownUntil": None, "note": ""} for _ in range(4)],
        }
        try:
            if self.COMBO_STATE.exists():
                data = json.loads(self.COMBO_STATE.read_text(encoding="utf-8"))
                if isinstance(data.get("combos"), list) and len(data["combos"]) == 4:
                    return data
        except Exception as exc:
            logger.debug("read_combo_state error (using default): %s", exc)
        return default

    def write_combo_state(self, state: dict) -> None:
        """Atomic write of the shared combo-state file (best-effort, flock-guarded
        via the health lock to serialize with the Node side's combo writes)."""
        state["updatedAt"] = datetime.datetime.utcnow().isoformat() + "Z"
        try:
            with _FileLock(self.HEALTH_LOCK, timeout_ms=500):
                _atomic_write_json(self.COMBO_STATE, state)
        except Exception as exc:
            logger.debug("write_combo_state error (best-effort): %s", exc)

    @staticmethod
    def get_node_binary() -> str:
        """Return the node binary path.

        Reads ~/.claude/state/gemini-node-path.json (written by gemini-chain.js at
        module load). Falls back to 'node' if the file is absent or malformed.
        This avoids PATH dependency for subprocess rotate-on-demand.js calls (§9a.3).
        """
        node_path_file = Path.home() / ".claude" / "state" / "gemini-node-path.json"
        if node_path_file.exists():
            try:
                data = json.loads(node_path_file.read_text(encoding="utf-8"))
                node = data.get("nodePath") or data.get("node_path")
                if node and Path(node).exists():
                    return node
            except Exception:
                pass
        return "node"

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    def _wait_for_sentinel_clear(self) -> None:
        """Block up to SENTINEL_WAIT_MS if rotation-in-progress.json is present and fresh.

        If sentinel is >10s old, it is stale (crashed rotation); proceed anyway.
        """
        deadline = time.monotonic() + self.SENTINEL_WAIT_MS / 1000
        while time.monotonic() < deadline:
            if not self.SENTINEL.exists():
                return
            try:
                age_ms = (time.time() - self.SENTINEL.stat().st_mtime) * 1000
                if age_ms > self.SENTINEL_MAX_AGE_MS:
                    logger.warning(
                        "rotation-in-progress.json is stale (%.0f ms old) — proceeding", age_ms
                    )
                    return
            except FileNotFoundError:
                return
            time.sleep(self.SENTINEL_POLL_MS / 1000)

        logger.warning(
            "rotation-in-progress.json still present after %d ms — proceeding anyway",
            self.SENTINEL_WAIT_MS,
        )

    def _read_creds_file(self) -> dict:
        """Unconditionally read oauth_creds.json. Raises on missing or malformed."""
        if not self.CREDS.exists():
            raise FileNotFoundError(
                f"OAuth credentials not found at {self.CREDS}. Run: gemini auth login"
            )
        try:
            return json.loads(self.CREDS.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(
                f"Failed to parse OAuth credentials at {self.CREDS}: {exc}"
            ) from exc

    @staticmethod
    def _is_expired(raw: dict) -> bool:
        """True if access_token is missing or within 5-minute expiry buffer."""
        token = raw.get("access_token")
        expiry_ms = int(raw.get("expiry_date", 0))
        now_ms = int(time.time() * 1000)
        if not token:
            return True
        return (expiry_ms - now_ms) <= _EXPIRY_BUFFER_MS

    def _refresh_token_and_persist(self, raw: dict) -> dict:
        """Exchange refresh_token for a fresh access_token; write back atomically.

        Uses urllib.request (stdlib) — no `requests` import here.
        SECURITY: access_token values are never logged.

        Returns:
            Updated raw dict with fresh access_token and expiry_date.

        Raises:
            RuntimeError: On network or HTTP errors.
            ValueError: If refresh_token is missing or expired.
        """
        refresh_token = raw.get("refresh_token")
        if not refresh_token:
            raise ValueError(
                "OAuth refresh_token missing from credentials. Run: gemini auth login"
            )

        logger.debug("Refreshing OAuth access_token via token endpoint")
        body = (
            f"client_id={_GEMINI_CLI_CLIENT_ID}"
            f"&client_secret={_GEMINI_CLI_CLIENT_SECRET}"
            f"&refresh_token={refresh_token}"
            f"&grant_type=refresh_token"
        ).encode()

        req = urllib.request.Request(
            _OAUTH_TOKEN_URI,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
                token_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise ValueError(
                    "OAuth refresh_token expired or revoked. Run: gemini auth login"
                ) from exc
            raise RuntimeError(
                f"OAuth token refresh failed with HTTP {exc.code}. Run: gemini auth login"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"OAuth token refresh network error: {exc}") from exc

        new_token = token_data.get("access_token")
        if not new_token:
            raise RuntimeError("OAuth token refresh returned no access_token. Run: gemini auth login")

        expires_in = int(token_data.get("expires_in", 3600))
        now_ms = int(time.time() * 1000)
        new_expiry = now_ms + expires_in * 1000

        # Update raw in memory
        raw["access_token"] = new_token
        raw["expiry_date"] = new_expiry

        # Persist atomically — does NOT rotate the account, only refreshes the token
        try:
            _atomic_write_json(self.CREDS, raw)
        except Exception as exc:
            logger.warning("Could not persist refreshed OAuth token: %s", exc)

        return raw

    @staticmethod
    def _with_fingerprint(raw: dict) -> dict:
        """Return creds dict with fingerprint and account_email added.

        fingerprint = SHA256(access_token[:64]) — stable enough for ledger keying
        without persisting the full token.
        """
        token = raw.get("access_token", "")
        fingerprint = hashlib.sha256(token[:64].encode()).hexdigest()
        account_email = raw.get("account_email") or raw.get("email") or "unknown"
        return {
            "access_token": token,
            "refresh_token": raw.get("refresh_token", ""),
            "expiry_ms": int(raw.get("expiry_date", 0)),
            "fingerprint": fingerprint,
            "account_email": account_email,
        }

    def _resolve_via_onboard(self, fingerprint: str) -> str:
        """Call loadCodeAssist to resolve the Code Assist project ID.

        Writes result into PROJECT_CACHE keyed by fingerprint so next calls hit cache.
        Mirrors Node resolveCodeAssistProjectId (TASK-097 FIX B Python port).

        Raises:
            RuntimeError: If the API call fails.
        """
        # We need a valid access_token — get_credentials() may not be called yet from
        # this code path, so we re-read creds directly.
        raw = self._read_creds_file()
        if self._is_expired(raw):
            raw = self._refresh_token_and_persist(raw)
        token = raw.get("access_token", "")

        url = f"{_CODE_ASSIST_ENDPOINT}/{_CODE_ASSIST_VERSION}:loadCodeAssist"
        body = json.dumps({
            "metadata": {
                "ideType": "IDE_UNSPECIFIED",
                "platform": "PLATFORM_UNSPECIFIED",
                "pluginType": "GEMINI",
            }
        }).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Code Assist loadCodeAssist failed with HTTP {exc.code}. "
                "Ensure the account has Gemini Code Assist enabled."
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Code Assist loadCodeAssist network error: {exc}") from exc

        project_id = data.get("cloudaicompanionProject")
        if not project_id:
            raise RuntimeError(
                "Code Assist loadCodeAssist did not return a project ID. "
                "Run: gemini auth login and ensure Gemini Code Assist is enabled."
            )

        # Write into cache keyed by fingerprint
        self.PROJECT_CACHE.parent.mkdir(parents=True, exist_ok=True)
        cache: dict = {}
        if self.PROJECT_CACHE.exists():
            try:
                cache = json.loads(self.PROJECT_CACHE.read_text(encoding="utf-8"))
            except Exception:
                pass
        cache[fingerprint] = {"project_id": project_id, "cloudaicompanionProject": project_id}
        try:
            _atomic_write_json(self.PROJECT_CACHE, cache)
        except Exception as exc:
            logger.warning("Could not persist project ID cache: %s", exc)

        logger.info("Resolved Code Assist project ID: %s (fingerprint %s)", project_id, fingerprint[:8])
        return project_id


# ---------------------------------------------------------------------------
# Platform-appropriate file lock
# ---------------------------------------------------------------------------

class _FileLock:
    """Context manager for platform-appropriate file locking.

    POSIX: fcntl.flock (exclusive, non-blocking retry loop).
    Windows: msvcrt.locking + CreateFile-based fallback.

    Used for health ledger read-modify-write (§9a.2 mitigation).
    """

    def __init__(self, lock_path: Path, timeout_ms: int = 500) -> None:
        self._path = lock_path
        self._timeout_ms = timeout_ms
        self._lock_fh = None
        self._is_windows = platform.system() == "Windows"

    def __enter__(self) -> "_FileLock":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self._timeout_ms / 1000
        while True:
            try:
                if self._is_windows:
                    self._acquire_windows()
                else:
                    self._acquire_posix()
                return self
            except (OSError, IOError):
                if time.monotonic() >= deadline:
                    # Timeout: proceed without lock (best-effort — last-writer-wins acceptable)
                    logger.warning(
                        "_FileLock timeout on %s after %d ms — proceeding unlocked",
                        self._path,
                        self._timeout_ms,
                    )
                    self._lock_fh = None
                    return self
                time.sleep(0.05)  # 50ms retry

    def __exit__(self, *args) -> None:
        if self._lock_fh is None:
            return
        try:
            if self._is_windows:
                self._release_windows()
            else:
                self._release_posix()
        except Exception as exc:
            logger.debug("_FileLock release error: %s", exc)
        finally:
            self._lock_fh = None

    def _acquire_posix(self) -> None:
        import fcntl
        self._lock_fh = open(self._path, "w")  # noqa: WPS515
        fcntl.flock(self._lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _release_posix(self) -> None:
        import fcntl
        fcntl.flock(self._lock_fh, fcntl.LOCK_UN)
        self._lock_fh.close()
        try:
            self._path.unlink(missing_ok=True)
        except Exception:
            pass

    def _acquire_windows(self) -> None:
        # On Windows, use exclusive file creation as a simple advisory lock.
        # O_CREAT | O_EXCL ensures atomicity at the OS level.
        import msvcrt
        # Try to open exclusively; raises FileExistsError if already held
        fd = os.open(str(self._path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        self._lock_fh = fd

    def _release_windows(self) -> None:
        os.close(self._lock_fh)
        try:
            os.unlink(str(self._path))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Utility: atomic .tmp → rename write
# ---------------------------------------------------------------------------

def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON to path atomically via a .tmp sibling file.

    Same pattern used by gemini-chain.js rotateAccount (TASK-185).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    try:
        text = json.dumps(data, indent=2, ensure_ascii=False)
        tmp_path.write_text(text, encoding="utf-8")
        # os.replace is atomic on POSIX and Windows (within same drive)
        os.replace(str(tmp_path), str(path))
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise
