from __future__ import annotations

from typing import Any, Protocol

from litflow.zotero.client import ZoteroReadClient, ZoteroReadError


class ZoteroChildrenReadable(Protocol):
    def get_item_children(self, item_key: str) -> list[dict[str, Any]]: ...


def read_zotero_notes(item_key: str, client: ZoteroChildrenReadable | None = None) -> dict[str, Any]:
    client = client or ZoteroReadClient()
    warnings: list[str] = []
    items: list[dict[str, Any]] = []
    try:
        children = client.get_item_children(item_key)
    except ZoteroReadError as exc:
        return {
            "annotation_count": 0,
            "note_count": 0,
            "items": [],
            "warnings": [f"failed to read Zotero children: {exc}"],
        }

    for child in children:
        data = child.get("data", {})
        item_type = data.get("itemType")
        if item_type == "annotation":
            items.append(
                {
                    "type": "annotation",
                    "text": data.get("annotationText") or "",
                    "comment": data.get("annotationComment") or "",
                    "page_label": data.get("annotationPageLabel") or "",
                    "color": data.get("annotationColor") or "",
                    "date_modified": data.get("dateModified") or "",
                }
            )
        elif item_type == "note":
            items.append(
                {
                    "type": "note",
                    "text": data.get("note") or "",
                    "comment": "",
                    "page_label": "",
                    "color": "",
                    "date_modified": data.get("dateModified") or "",
                }
            )

    return {
        "annotation_count": sum(1 for item in items if item["type"] == "annotation"),
        "note_count": sum(1 for item in items if item["type"] == "note"),
        "items": items,
        "warnings": warnings,
    }

