from __future__ import annotations

import csv
import json
import re
from io import StringIO
from pathlib import Path
from typing import Any


class QrelsUnicodeError(ValueError):
    pass


def load_queries(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    queries = payload.get("queries")
    if not isinstance(queries, list):
        raise QrelsUnicodeError("queries payload must contain a queries list")
    validate_queries(queries)
    return queries


def validate_queries(queries: list[dict[str, Any]]) -> None:
    ids = []
    for query in queries:
        query_id = query.get("query_id")
        query_zh = query.get("query_zh")
        if not isinstance(query_id, str) or not isinstance(query_zh, str):
            raise QrelsUnicodeError("query_id and query_zh must be strings")
        if "\ufffd" in query_zh or re.search(r"\?{3,}", query_zh):
            raise QrelsUnicodeError(f"corrupted query_zh: {query_id}")
        ids.append(query_id)
    if len(ids) != len(set(ids)):
        raise QrelsUnicodeError("duplicate query_id")


def write_queries_json(path: Path, metadata: dict[str, Any], queries: list[dict[str, Any]]) -> None:
    validate_queries(queries)
    path.write_text(json.dumps({"metadata": metadata, "queries": queries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_qrels_review_csv(path: Path, queries: list[dict[str, Any]]) -> None:
    validate_queries(queries)
    fields = ["query_id", "query_zh", "query_en", "query_type", "expected_answerable", "relevant_paper_keys", "relevant_passage_ids", "gold_evidence_summary", "review_status", "query_translation_correct", "answerable_correct", "relevant_passages_correct", "passages_to_add", "passages_to_remove", "evidence_summary_correct", "reviewer_notes"]
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for query in queries:
        writer.writerow({**query, "relevant_paper_keys": ";".join(query.get("relevant_paper_keys", [])), "relevant_passage_ids": ";".join(query.get("relevant_passage_ids", [])), "query_translation_correct": "", "answerable_correct": "", "relevant_passages_correct": "", "passages_to_add": "", "passages_to_remove": "", "evidence_summary_correct": "", "reviewer_notes": ""})
    path.write_text(stream.getvalue(), encoding="utf-8-sig", newline="")


def import_ai_assisted_qrels(source_csv: Path, original_queries_path: Path, output_path: Path) -> list[dict[str, Any]]:
    with source_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    original_payload = json.loads(original_queries_path.read_text(encoding="utf-8-sig"))
    historical_queries = original_payload.get("queries")
    if not isinstance(historical_queries, list) or any(not isinstance(query.get("query_id"), str) for query in historical_queries):
        raise QrelsUnicodeError("historical qrels must contain structured query IDs")
    original = {query["query_id"]: query for query in historical_queries}
    if set(row.get("query_id") for row in rows) != set(original):
        raise QrelsUnicodeError("AI-assisted qrels query IDs do not match original query IDs")
    queries = []
    for row in rows:
        baseline = original[row["query_id"]]
        query = {**baseline, "query_zh": row["query_zh"], "query_en": row.get("query_en") or baseline["query_en"], "review_status": "ai_assisted_review_pending_author_confirmation"}
        if row.get("relevant_passage_ids"):
            query["relevant_passage_ids"] = [item for item in row["relevant_passage_ids"].split(";") if item]
        if row.get("relevant_paper_keys"):
            query["relevant_paper_keys"] = [item for item in row["relevant_paper_keys"].split(";") if item]
        queries.append(query)
    write_queries_json(output_path, {"qrels_status": "AI-assisted review pending author confirmation", "source_csv": source_csv.name}, queries)
    return queries
