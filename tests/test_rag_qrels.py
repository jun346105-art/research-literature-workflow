from __future__ import annotations

import csv
import json

import pytest

from litflow.rag.qrels import QrelsUnicodeError, freeze_human_reviewed_qrels, import_ai_assisted_qrels, load_queries, write_qrels_review_csv, write_queries_json


def test_query_json_and_csv_round_trip_unicode(tmp_path):
    queries = [_query("Q01", "中文 query with English YOLO"), _query("Q02", "混合 Chinese-English RGB-D 检索")]
    json_path = tmp_path / "queries.json"
    csv_path = tmp_path / "queries.csv"
    write_queries_json(json_path, {"status": "test"}, queries)
    write_qrels_review_csv(csv_path, queries)
    assert load_queries(json_path) == queries
    assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf")
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        assert [row["query_zh"] for row in csv.DictReader(handle)] == [item["query_zh"] for item in queries]


def test_corrupted_query_zh_is_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"queries": [_query("Q01", "????")]}, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(QrelsUnicodeError, match="corrupted query_zh"):
        load_queries(path)


def test_ai_assisted_import_preserves_ids_and_pending_status(tmp_path):
    original = tmp_path / "original.json"
    write_queries_json(original, {}, [_query("Q01", "原始中文"), _query("Q02", "原始中文二")])
    source = tmp_path / "assisted.csv"
    source.write_text("query_id,query_zh,query_en,ai_draft_relevant_paper_keys,ai_draft_relevant_passage_ids,passages_to_add,passages_to_remove,reviewer_notes\nQ01,修复中文,alpha,P1,P1:P1_chunk_0001,,,\nQ02,修复中文二,beta,P2,P2:P2_chunk_0001,,,范围收窄\n", encoding="utf-8")
    output = tmp_path / "imported.json"
    queries = import_ai_assisted_qrels(source, original, output)
    assert [item["query_id"] for item in queries] == ["Q01", "Q02"]
    assert all(item["review_status"] == "ai_assisted_review_pending_author_confirmation" for item in queries)


def test_ai_assisted_import_can_replace_corrupted_historical_query_zh(tmp_path):
    original = tmp_path / "original.json"
    original.write_text(json.dumps({"queries": [_query("Q01", "????")]}, ensure_ascii=False), encoding="utf-8")
    source = tmp_path / "assisted.csv"
    source.write_text("query_id,query_zh,query_en,ai_draft_relevant_paper_keys,ai_draft_relevant_passage_ids,passages_to_add,passages_to_remove,reviewer_notes\nQ01,修复中文,alpha,P1,P1:P1_chunk_0001,,,\n", encoding="utf-8")
    imported = import_ai_assisted_qrels(source, original, tmp_path / "imported.json")
    assert imported[0]["query_zh"] == "修复中文"


def test_ai_assisted_import_applies_passage_revision_and_preserves_en_audit(tmp_path):
    original = tmp_path / "original.json"
    write_queries_json(original, {}, [{**_query("Q01", "原始中文"), "query_en": "broad question", "relevant_passage_ids": ["P1:old"]}])
    source = tmp_path / "assisted.csv"
    source.write_text("query_id,query_zh,query_en,ai_draft_relevant_paper_keys,ai_draft_relevant_passage_ids,passages_to_add,passages_to_remove,reviewer_notes\nQ01,修复中文,narrow question,P1,P1:old,P1:new,P1:old,scope revised\n", encoding="utf-8")
    output = tmp_path / "imported.json"
    imported = import_ai_assisted_qrels(source, original, output)
    assert imported[0]["relevant_passage_ids"] == ["P1:new"]
    assert imported[0]["query_revision"]["original_query_en"] == "broad question"
    assert imported[0]["query_revision"]["revised_query_en"] == "narrow question"
    assert json.loads(output.with_suffix(".manifest.json").read_text(encoding="utf-8"))["query_scope_revised_during_ai_assisted_review"] == ["Q01"]


def test_human_freeze_writes_pilot_manifest(tmp_path):
    pending = tmp_path / "pending.json"
    write_queries_json(pending, {}, [_query("Q01", "确认中文")])
    source = tmp_path / "source.csv"
    source.write_text("query_id,passages_to_add,passages_to_remove\nQ01,P1:P1_chunk_0001,\n", encoding="utf-8")
    corpus = tmp_path / "passages.jsonl"
    corpus.write_text(json.dumps({"passage_id": "P1:P1_chunk_0001"}) + "\n", encoding="utf-8")
    output = tmp_path / "reviewed.json"
    manifest = freeze_human_reviewed_qrels(pending, source, corpus, output)
    assert manifest["benchmark_id"] == "human_reviewed_pilot_qrels_v1"
    assert load_queries(output)[0]["review_status"] == "human_reviewed_pilot"


def _query(query_id: str, query_zh: str) -> dict:
    return {"query_id": query_id, "query_zh": query_zh, "query_en": "alpha", "query_type": "method", "expected_answerable": True, "relevant_paper_keys": ["P1"], "relevant_passage_ids": ["P1:P1_chunk_0001"], "gold_evidence_summary": "", "review_status": "human_review_pending"}
