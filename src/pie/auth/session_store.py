"""
In-memory session store for PIE OAuth2 PKCE browser-based authentication.

Stores:
  - pending PKCE flows (state → code_verifier)
  - active authenticated sessions (session_token → claims + access_token)

This is intentionally in-process memory for Phase 3. Phase 5 will migrate to
Redis or Azure Cache for HA deployments.
"""

import uuid
import threading
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PieSession:
    """An authenticated PIE session derived from a completed OAuth2 PKCE flow."""
    session_token: str
    tenant_id: str
    user_id: str
    display_name: str
    access_token: str
    token_expires_at: datetime
    subscriptions: list[dict] = field(default_factory=list)
    auth_mode: str = "oauth2_pkce_browser"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.token_expires_at

    def to_dict(self) -> dict:
        return {
            "session_token": self.session_token,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "display_name": self.display_name,
            "auth_mode": self.auth_mode,
            "token_expires_at": self.token_expires_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "is_expired": self.is_expired,
        }


class SessionStore:
    """Thread-safe in-memory store for PKCE state and authenticated sessions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # state → code_verifier (pending flows, expires ~10 min)
        self._pending: dict[str, dict] = {}
        # session_token → PieSession (authenticated sessions)
        self._sessions: dict[str, PieSession] = {}

    # ------------------------------------------------------------------
    # PKCE Pending Flow Management
    # ------------------------------------------------------------------

    def save_pkce_state(self, state: str, code_verifier: str, redirect_uri: str) -> None:
        """Persist PKCE state before redirecting user to Microsoft login."""
        with self._lock:
            self._pending[state] = {
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
                "created_at": datetime.now(timezone.utc),
            }

    def pop_pkce_state(self, state: str) -> Optional[dict]:
        """Retrieve and remove PKCE state on callback. Returns None if expired/missing."""
        with self._lock:
            entry = self._pending.pop(state, None)
        if not entry:
            return None
        # Reject stale states (older than 10 minutes)
        age = datetime.now(timezone.utc) - entry["created_at"]
        if age > timedelta(minutes=10):
            return None
        return entry

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------

    def create_session(
        self,
        tenant_id: str,
        user_id: str,
        display_name: str,
        access_token: str,
        expires_in_seconds: int = 3600,
    ) -> PieSession:
        """Create and persist an authenticated session. Returns the session."""
        session_token = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
        session = PieSession(
            session_token=session_token,
            tenant_id=tenant_id,
            user_id=user_id,
            display_name=display_name,
            access_token=access_token,
            token_expires_at=expires_at,
        )
        with self._lock:
            self._sessions[session_token] = session
        return session

    def get_session(self, session_token: str) -> Optional[PieSession]:
        """Look up a session by token. Returns None if missing or expired."""
        with self._lock:
            session = self._sessions.get(session_token)
        if session and session.is_expired:
            self.delete_session(session_token)
            return None
        return session

    def delete_session(self, session_token: str) -> None:
        """Remove a session (logout)."""
        with self._lock:
            self._sessions.pop(session_token, None)

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for s in self._sessions.values() if not s.is_expired)


# Singleton — one store per process
_store: Optional[SessionStore] = None
_store_lock = threading.Lock()


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = SessionStore()
    return _store
