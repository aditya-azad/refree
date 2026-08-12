import threading

from app.zotero_browser_plugin.schemas import ConnectorItem, SavedReference


class ConnectorSessionEntry:
    def __init__(self, reference: SavedReference, item: ConnectorItem) -> None:
        self.reference = reference
        self.item = item


class ConnectorSession:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.entries: dict[str, ConnectorSessionEntry] = {}

    def add_entry(
        self, item_id: str, reference: SavedReference, item: ConnectorItem
    ) -> None:
        self.entries[item_id] = ConnectorSessionEntry(reference, item)

    def get_entry(self, item_id: str) -> ConnectorSessionEntry | None:
        return self.entries.get(item_id)


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

    def add_reference(
        self,
        session_id: str,
        item_id: str,
        reference: SavedReference,
        item: ConnectorItem,
    ) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = ConnectorSession(session_id)
                self._sessions[session_id] = session
            session.add_entry(item_id, reference, item)

    def get_entry(
        self, session_id: str, item_id: str
    ) -> ConnectorSessionEntry | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            return session.get_entry(item_id)

    def close(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
