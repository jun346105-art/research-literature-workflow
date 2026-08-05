from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen


class ZoteroReadError(RuntimeError):
    pass


class ZoteroReadClient:
    def __init__(self, base_url: str = "http://127.0.0.1:23119", user_id: int = 0) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_id = user_id

    def get_collections(self) -> list[dict[str, Any]]:
        return self._get_json(f"/api/users/{self.user_id}/collections")

    def get_collection_items(self, collection_key: str) -> list[dict[str, Any]]:
        key = quote(collection_key, safe="")
        return self._get_json(f"/api/users/{self.user_id}/collections/{key}/items")

    def get_items(self) -> list[dict[str, Any]]:
        return self._get_json(f"/api/users/{self.user_id}/items?limit=100")

    def get_item_children(self, item_key: str) -> list[dict[str, Any]]:
        key = quote(item_key, safe="")
        return self._get_json(f"/api/users/{self.user_id}/items/{key}/children")

    def get_attachment_file_path(self, attachment_key: str) -> str | None:
        key = quote(attachment_key, safe="")
        try:
            text = self._get_text(f"/api/users/{self.user_id}/items/{key}/file/view/url").strip()
        except ZoteroReadError:
            return None
        if not text:
            return None
        if text.startswith("file:"):
            path = unquote(urlparse(text).path)
            if len(path) >= 3 and path[0] == "/" and path[2] == ":":
                path = path[1:]
                return str(PureWindowsPath(path))
            return str(Path(path))
        return text

    def _get_json(self, path: str) -> Any:
        text = self._get_text(path)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ZoteroReadError(f"Invalid Zotero JSON response from {path}: {exc}") from exc

    def _get_text(self, path: str) -> str:
        request = Request(
            f"{self.base_url}{path}",
            headers={"Zotero-API-Version": "3"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=15) as response:
                return response.read().decode("utf-8")
        except HTTPError as exc:
            if exc.code == 403:
                raise ZoteroReadError(
                    "Zotero local API returned 403 Forbidden. "
                    "Zotero Desktop may be running only the Connector server; enable the local API, then retry."
                ) from exc
            raise ZoteroReadError(f"Zotero local API HTTP {exc.code}: {path}") from exc
        except URLError as exc:
            raise ZoteroReadError(f"Zotero local API unavailable: {exc}") from exc
