import threading

from app.zotero_browser_plugin.schemas import SavedReference


class ConnectorSession:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.references: list[SavedReference] = []


class ConnectorSessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, ConnectorSession] = {}
        self._lock = threading.Lock()

    def open(self, session_id: str) -> ConnectorSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = ConnectorSession(session_id)
                self._sessions[session_id] = session
            return session

    def get(self, session_id: str) -> ConnectorSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def add_reference(self, session_id: str, reference: SavedReference) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = ConnectorSession(session_id)
                self._sessions[session_id] = session
            session.references.append(reference)

    def close(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
