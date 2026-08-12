import httpx

from app.zotero_import.schemas import (
    CitationKeyResponse,
    ZoteroAttachment,
    ZoteroItem,
)

_LIMIT = 100
_SKIP_ITEM_TYPES = frozenset({"attachment", "note"})


class ZoteroLocalClient:
    def __init__(self, base_url: str, http: httpx.Client) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = http

    def ready(self) -> bool:
        try:
            response = self._http.get(f"{self._base_url}/connector/ping")
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    def list_items(self) -> list[ZoteroItem]:
        items: list[ZoteroItem] = []
        start = 0
        while True:
            response = self._http.get(
                f"{self._base_url}/api/users/0/items",
                params={"format": "json", "limit": _LIMIT, "start": start},
            )
            response.raise_for_status()
            page = response.json()
            for entry in page:
                data = entry.get("data") if isinstance(entry, dict) else None
                if not isinstance(data, dict):
                    continue
                if data.get("itemType") in _SKIP_ITEM_TYPES:
                    continue
                if data.get("deleted"):
                    continue
                items.append(ZoteroItem.model_validate(data))
            if len(page) < _LIMIT:
                break
            start += _LIMIT
        return items

    def citation_keys(self, item_keys: list[str]) -> dict[str, str]:
        if not item_keys:
            return {}
        try:
            response = self._http.post(
                f"{self._base_url}/better-bibtex/json-rpc",
                json={
                    "jsonrpc": "2.0",
                    "method": "item.citationkey",
                    "params": [item_keys],
                },
            )
        except httpx.HTTPError:
            return {}
        if response.status_code != 200:
            return {}
        payload = response.json()
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            return {}
        return CitationKeyResponse.model_validate(result).root

    def list_pdf_attachments(self) -> list[ZoteroAttachment]:
        attachments: list[ZoteroAttachment] = []
        start = 0
        while True:
            response = self._http.get(
                f"{self._base_url}/api/users/0/items",
                params={
                    "format": "json",
                    "limit": _LIMIT,
                    "start": start,
                    "itemType": "attachment",
                },
            )
            response.raise_for_status()
            page = response.json()
            for entry in page:
                data = entry.get("data") if isinstance(entry, dict) else None
                if not isinstance(data, dict):
                    continue
                if data.get("deleted"):
                    continue
                if data.get("contentType") != "application/pdf":
                    continue
                attachments.append(ZoteroAttachment.model_validate(data))
            if len(page) < _LIMIT:
                break
            start += _LIMIT
        return attachments

    def download_attachment(self, item_key: str) -> bytes:
        try:
            response = self._http.get(
                f"{self._base_url}/api/users/0/items/{item_key}/file"
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            msg = f"failed to download attachment {item_key}"
            raise RuntimeError(msg) from e
        return response.content
