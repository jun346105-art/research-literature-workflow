from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from litflow.zotero.client import ZoteroReadClient
from litflow.zotero.collection_reader import (
    ZoteroReadable,
    _citation_key,
    _find_collection,
    citation_key_candidate_fields,
)


def diagnose_citekeys(collection_name: str, client: ZoteroReadable | None = None) -> dict[str, Any]:
    client = client or ZoteroReadClient()
    collection = _find_collection(client.get_collections(), collection_name)
    if collection is None:
        raise ValueError(f"Zotero collection not found: {collection_name}")

    items = []
    for item in client.get_collection_items(collection["key"]):
        data = item.get("data", {})
        if data.get("itemType") in {"attachment", "note"}:
            continue
        citation_key, source = _citation_key(data)
        items.append(
            {
                "zotero_key": item.get("key") or data.get("key"),
                "title": data.get("title") or "",
                "doi": data.get("DOI") or data.get("doi"),
                "citation_key": citation_key,
                "citation_key_source": source,
                "raw_candidate_fields": citation_key_candidate_fields(item),
            }
        )

    source_counts = Counter(item["citation_key_source"] for item in items)
    return {
        "metadata": {
            "collection": collection_name,
            "total_items": len(items),
            "citation_key_count": sum(1 for item in items if item["citation_key"]),
            "citation_key_missing_count": sum(1 for item in items if not item["citation_key"]),
            "citation_key_sources": dict(source_counts),
            "read_only": True,
        },
        "items": items,
        "diagnosis": _diagnosis(items),
    }


def write_citekey_diagnostics(collection_name: str, output_path: Path, client: ZoteroReadable | None = None) -> dict[str, Any]:
    report = diagnose_citekeys(collection_name, client)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _diagnosis(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["No regular Zotero items found in this collection."]
    if any(item["citation_key"] for item in items):
        return ["Citation keys are available for at least one Zotero item."]
    return [
        "No citation keys were visible in Zotero local API item data.",
        "Check whether Better BibTeX for Zotero is installed and enabled.",
        "If Better BibTeX is installed but keys are still missing, the local API may not expose them directly.",
        "A later fallback may need to read citekeys from a Better BibTeX BibTeX export sidecar.",
    ]

