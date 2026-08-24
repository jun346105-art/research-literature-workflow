from __future__ import annotations

import json

import pytest

from litflow.llm.client import LLMCompletion
from litflow.rag.translation import TranslationContractError, TranslationResponse, _numbers_and_units, _protected_entities, build_translation_prompt, plan_query_translation, replay_query_translation, run_query_translation, write_translation_review_packet


class FakeTranslationClient:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def complete_json_with_usage(self, _prompt, **_kwargs):
        self.calls += 1
        return LLMCompletion(json.dumps(self.response, ensure_ascii=False), input_tokens=12, output_tokens=6, total_tokens=18)


def test_translation_prompt_excludes_human_translation_and_qrels(tmp_path):
    query = _queries(tmp_path)[0]
    prompt = build_translation_prompt(query)
    assert query["query_zh"] in prompt
    assert query["query_en"] not in prompt
    assert query["gold_evidence_summary"] not in prompt
    assert "relevant_passage_ids" not in prompt


def test_translation_contract_rejects_unknown_fields_and_lost_entity():
    with pytest.raises(Exception):
        TranslationResponse.model_validate({"query_id": "Q1", "source_language": "zh", "target_language": "en", "translated_query": "TPMN", "preserved_entities": ["TPMN"], "preserved_numbers_and_units": [], "extra": True})
    response = TranslationResponse.model_validate({"query_id": "Q1", "source_language": "zh", "target_language": "en", "translated_query": "What is mAP at 0.5?", "preserved_entities": [], "preserved_numbers_and_units": ["0.5"]})
    with pytest.raises(TranslationContractError, match="entity preservation"):
        response.validate_against_query({"query_id": "Q1", "query_zh": "TPMN的mAP@0.5是多少？"})


def test_translation_runner_caches_by_identity_and_round_trips_unicode(tmp_path):
    queries_path = _queries_file(tmp_path)
    response = {"query_id": "Q1", "source_language": "zh", "target_language": "en", "translated_query": "What is the mAP@0.5 of TPMN?", "preserved_entities": ["TPMN", "mAP"], "preserved_numbers_and_units": ["0.5"]}
    client = FakeTranslationClient(response)
    plan = plan_query_translation(queries_path, model="fake", query_ids=["Q1"])
    assert plan["maximum_calls"] == 1
    run_query_translation(queries_path, tmp_path / "run", model="fake", query_ids=["Q1"], client=client)
    assert client.calls == 1
    run_query_translation(queries_path, tmp_path / "run", model="fake", query_ids=["Q1"], client=client, resume=True)
    assert client.calls == 1
    packet = tmp_path / "packet.md"
    write_translation_review_packet(tmp_path / "run", queries_path, packet)
    assert "TPMN" in packet.read_text(encoding="utf-8")


def test_protected_entity_tokenizer_preserves_composite_technical_terms_without_single_letters():
    values = _protected_entities("混合2D/3D、RGB-D、WT-C3k2、YOLOv8n、mAP@0.5、P2/P3/P5与RANSAC、SSD、TPMN")
    for expected in ("2D/3D", "RGB-D", "WT-C3k2", "YOLOv8n", "mAP@0.5", "P2/P3/P5", "RANSAC", "SSD", "TPMN"):
        assert expected in values
    assert "D" not in values and "P" not in values
    assert _numbers_and_units("混合2D/3D与P2/P3/P5，mAP@0.5") == ["0.5"]


def test_q11_style_translation_replays_without_calling_a_client(tmp_path, monkeypatch):
    queries_path = _queries_file(tmp_path)
    payload = json.loads(queries_path.read_text(encoding="utf-8"))
    payload["queries"][0].update({"query_id": "Q11", "query_zh": "混合2D/3D检测报告了什么单一模具局限？", "query_en": "What single mold limitation does hybrid 2D/3D detection report?"})
    queries_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    source = tmp_path / "source"
    raw = {"query_id": "Q11", "source_language": "zh", "target_language": "en", "translated_query": "What single mold limitation does hybrid 2D/3D detection report?", "preserved_entities": [], "preserved_numbers_and_units": []}
    (source / "queries" / "Q11").mkdir(parents=True)
    raw_path = source / "queries" / "Q11" / "raw_response_attempt_1.txt"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    (source / "queries" / "Q11" / "checkpoint_1.json").write_text(json.dumps({"raw_sha256": __import__("hashlib").sha256(raw_path.read_bytes()).hexdigest()}), encoding="utf-8")
    (source / "run_manifest.json").write_text(json.dumps({"plan": {"model": "fake"}}), encoding="utf-8")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    replay = replay_query_translation(source, queries_path, tmp_path / "replay")
    assert replay["results"][0]["execution_status"] == "success"


def _queries(tmp_path):
    return json.loads(_queries_file(tmp_path).read_text(encoding="utf-8"))["queries"]


def _queries_file(tmp_path):
    path = tmp_path / "queries.json"
    if not path.exists():
        path.write_text(json.dumps({"queries": [{"query_id": "Q1", "query_zh": "TPMN的mAP@0.5是多少？", "query_en": "What is the mAP@0.5 of TPMN?", "query_type": "metric", "expected_answerable": True, "relevant_paper_keys": ["P1"], "relevant_passage_ids": ["P1:1"], "gold_evidence_summary": "not for prompt", "review_status": "human_reviewed"}]}, ensure_ascii=False), encoding="utf-8")
    return path
