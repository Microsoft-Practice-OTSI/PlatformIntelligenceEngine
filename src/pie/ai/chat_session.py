"""In-memory chat session store providing conversational continuity across PIE chat turns.

Each conversation is keyed by an owner (session token) plus a frontend-generated chat
session id. History is capped and sessions expire after a TTL so memory stays bounded.
"""

import threading
import time
from typing import Optional

from pie.ai.models import ChatMessage, ChatRole


class ChatSession:
    """A single conversational thread with a bounded message list."""

    def __init__(self, session_id: str, factory_name: str):
        self.session_id = session_id
        self.factory_name = factory_name
        self.messages: list[ChatMessage] = []
        self.created_at = time.time()
        self.last_activity = time.time()

    def add_message(self, role: ChatRole, content: str) -> None:
        self.messages.append(ChatMessage(role=role, content=content))
        self.last_activity = time.time()

    def get_history(self, limit: int = 20) -> list[ChatMessage]:
        if limit and limit > 0:
            return self.messages[-limit:]
        return self.messages

    def is_expired(self, ttl_seconds: float) -> bool:
        return (time.time() - self.last_activity) > ttl_seconds


class ChatSessionStore:
    """Thread-safe bounded store of chat sessions shared across API requests."""

    def __init__(self, max_sessions: int = 200, max_history: int = 20, ttl_seconds: float = 1800):
        self._lock = threading.Lock()
        self._sessions: dict[str, ChatSession] = {}
        self._max_sessions = max_sessions
        self._max_history = max_history
        self._ttl_seconds = ttl_seconds

    def _key(self, owner_id: Optional[str], session_id: str) -> str:
        return f"{(owner_id or 'anon').strip().lower()}:{session_id}"

    def get_or_create(self, owner_id: Optional[str], session_id: str, factory_name: str) -> ChatSession:
        key = self._key(owner_id, session_id)
        now = time.time()
        with self._lock:
            session = self._sessions.get(key)
            if session is not None:
                # Factory changed -> start a fresh thread so context never leaks across factories.
                if session.factory_name != factory_name:
                    session = ChatSession(session_id, factory_name)
                    self._sessions[key] = session
                session.last_activity = now
                return session

            if len(self._sessions) >= self._max_sessions:
                expired = [k for k, s in self._sessions.items() if s.is_expired(self._ttl_seconds)]
                for k in expired:
                    del self._sessions[k]
                if len(self._sessions) >= self._max_sessions:
                    oldest_key = min(self._sessions, key=lambda k: self._sessions[k].last_activity)
                    del self._sessions[oldest_key]

            session = ChatSession(session_id, factory_name)
            self._sessions[key] = session
            return session

    def add_message(self, owner_id: Optional[str], session_id: str, role: ChatRole, content: str) -> None:
        key = self._key(owner_id, session_id)
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                return
            session.add_message(role, content)
            if len(session.messages) > self._max_history * 2:
                session.messages = session.messages[-self._max_history:]

    def get_history(self, owner_id: Optional[str], session_id: str, limit: int = 10) -> list[ChatMessage]:
        key = self._key(owner_id, session_id)
        with self._lock:
            session = self._sessions.get(key)
            return session.get_history(limit) if session else []

    def clear_owner(self, owner_id: Optional[str]) -> int:
        prefix = f"{(owner_id or 'anon').strip().lower()}:"
        with self._lock:
            keys = [k for k in self._sessions if k.startswith(prefix)]
            for k in keys:
                del self._sessions[k]
            return len(keys)

    def cleanup(self) -> int:
        with self._lock:
            expired = [k for k, s in self._sessions.items() if s.is_expired(self._ttl_seconds)]
            for k in expired:
                del self._sessions[k]
            return len(expired)


_store: Optional[ChatSessionStore] = None
_store_lock = threading.Lock()


def get_chat_session_store() -> ChatSessionStore:
    """Return the process-wide shared chat session store singleton."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = ChatSessionStore()
    return _store
