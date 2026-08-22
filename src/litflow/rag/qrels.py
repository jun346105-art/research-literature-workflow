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
    revisions = []
    for row in rows:
        baseline = original[row["query_id"]]
        revised_en = row.get("query_en") or baseline["query_en"]
        passages = set(_split(row.get("ai_draft_relevant_passage_ids")) or baseline.get("relevant_passage_ids", []))
        passages.update(_split(row.get("passages_to_add")))
        passages.difference_update(_split(row.get("passages_to_remove")))
        query = {**baseline, "query_zh": row["query_zh"], "query_en": revised_en, "relevant_paper_keys": _split(row.get("ai_draft_relevant_paper_keys")) or baseline.get("relevant_paper_keys", []), "relevant_passage_ids": sorted(passages), "review_status": "ai_assisted_review_pending_author_confirmation", "query_revision": {"original_query_en": baseline["query_en"], "revised_query_en": revised_en, "revision_reason": row.get("reviewer_notes") or "", "query_scope_revised_during_ai_assisted_review": revised_en != baseline["query_en"]}}
        if query["review_status"] != "ai_assisted_review_pending_author_confirmation":
            raise QrelsUnicodeError("AI-assisted import cannot mark qrels as human-reviewed")
        if query["query_revision"]["query_scope_revised_during_ai_assisted_review"]:
            revisions.append(query["query_id"])
        queries.append(query)
    write_queries_json(output_path, {"qrels_status": "AI-assisted review pending author confirmation", "source_csv": source_csv.name, "query_scope_revised_during_ai_assisted_review": revisions}, queries)
    manifest_path = output_path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps({"role": "ai_assisted_qrels_import", "source_csv": source_csv.name, "query_count": len(queries), "query_scope_revised_during_ai_assisted_review": revisions, "original_query_en": {query["query_id"]: query["query_revision"]["original_query_en"] for query in queries}, "revised_query_en": {query["query_id"]: query["query_revision"]["revised_query_en"] for query in queries}, "revision_reason": {query["query_id"]: query["query_revision"]["revision_reason"] for query in queries if query["query_revision"]["query_scope_revised_during_ai_assisted_review"]}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return queries


def freeze_human_reviewed_qrels(pending_queries_path: Path, source_csv: Path, corpus_path: Path, output_path: Path) -> dict[str, Any]:
    queries = load_queries(pending_queries_path)
    passages = {json.loads(line)["passage_id"] for line in corpus_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()}
    unknown = {item for query in queries for item in query.get("relevant_passage_ids", []) if item not in passages}
    if unknown:
        raise QrelsUnicodeError(f"human-reviewed qrels reference unknown passages: {sorted(unknown)}")
    frozen_queries = [{**query, "review_status": "human_reviewed_pilot"} for query in queries]
    write_queries_json(output_path, {"qrels_status": "human-reviewed pilot benchmark", "benchmark_id": "human_reviewed_pilot_qrels_v1", "reviewer": "author", "ai_assisted_review_provenance": source_csv.name, "query_count": len(frozen_queries)}, frozen_queries)
    source_rows = {row["query_id"]: row for row in _read_csv(source_csv)}
    revisions = [query["query_id"] for query in frozen_queries if query.get("query_revision", {}).get("query_scope_revised_during_ai_assisted_review")]
    manifest = {"benchmark_id": "human_reviewed_pilot_qrels_v1", "reviewer": "author", "source_csv_sha256": _sha256_file(source_csv), "corpus_sha256": _sha256_file(corpus_path), "query_sha256": _sha256_file(output_path), "query_ids": [query["query_id"] for query in frozen_queries], "ai_assisted_review_provenance": source_csv.name, "q08_passage_revision": {"add": _split(source_rows.get("Q08", {}).get("passages_to_add")), "remove": _split(source_rows.get("Q08", {}).get("passages_to_remove"))}, "query_scope_revised_during_ai_assisted_review": revisions}
    output_path.with_suffix(".manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_path.with_suffix(".validation.json").write_text(json.dumps({"valid": True, "query_count": len(frozen_queries), "answerable_query_count": sum(bool(q["expected_answerable"]) for q in frozen_queries), "no_answer_query_count": sum(not q["expected_answerable"] for q in frozen_queries), "unicode_question_mark_runs": sum(bool(re.search(r"\?{3,}", q["query_zh"])) for q in frozen_queries), "replacement_character_count": sum(q["query_zh"].count("\ufffd") for q in frozen_queries)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def qrels_evaluation_label(path: Path) -> str:
    metadata = json.loads(path.read_text(encoding="utf-8-sig")).get("metadata", {})
    return "human_reviewed_pilot_qrels_v1" if metadata.get("benchmark_id") == "human_reviewed_pilot_qrels_v1" else "preliminary_on_AI_drafted_silver_qrels"


def _split(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(";") if item.strip()]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
