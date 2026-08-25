import json

import pytest

from litflow.agent.pilot import AgentPilotError, build_pilot_preflight, load_pilot_config
from litflow.cli import main


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_pilot_config_requires_frozen_task_identity_and_safe_ag12(tmp_path):
    config_path = tmp_path / "pilot.json"
    _write_json(config_path, {"schema_version": "agent-pilot-v1", "tasks": [{"task_id": "AG12", "category": "unauthorized_action", "task_zh": "blocked", "expected_tool_calls": 0, "expected_external_llm_calls": 0}]})

    config = load_pilot_config(config_path)

    assert config["tasks"][0]["task_id"] == "AG12"
    assert config["tasks"][0]["expected_tool_calls"] == 0


def test_pilot_preflight_fails_closed_for_wrong_model_and_never_reads_qrels(tmp_path, monkeypatch):
    config_path = tmp_path / "pilot.json"
    corpus = tmp_path / "passages.jsonl"
    entities = tmp_path / "entities.json"
    _write_json(config_path, {"schema_version": "agent-pilot-v1", "tasks": [{"task_id": "AG01", "category": "single_paper", "task_zh": "task"}]})
    corpus.write_text('{"passage_id":"P:C","paper_key":"P","text":"evidence"}\n', encoding="utf-8")
    _write_json(entities, {"schema_version": "paper-entity-metadata-v1", "entities": []})
    monkeypatch.setenv("LLM_MODEL", "deepseek-v4-pro")

    with pytest.raises(AgentPilotError, match="deepseek-v4-flash"):
        build_pilot_preflight(config_path, corpus, entities)


def test_pilot_preflight_freezes_asset_and_policy_hashes_without_provider_client(tmp_path, monkeypatch):
    config_path = tmp_path / "pilot.json"
    corpus = tmp_path / "passages.jsonl"
    entities = tmp_path / "entities.json"
    _write_json(config_path, {"schema_version": "agent-pilot-v1", "tasks": [{"task_id": "AG01", "category": "single_paper", "task_zh": "task"}]})
    corpus.write_text('{"passage_id":"P:C","paper_key":"P","text":"evidence"}\n', encoding="utf-8")
    _write_json(entities, {"schema_version": "paper-entity-metadata-v1", "entities": []})
    monkeypatch.setenv("LLM_MODEL", "deepseek-v4-flash")

    preflight = build_pilot_preflight(config_path, corpus, entities)

    assert preflight["resolved_model"] == "deepseek-v4-flash"
    assert preflight["qrels_or_gold_in_agent_context"] is False
    assert len(preflight["protocol_sha256"]) == 64
    assert len(preflight["policy_sha256"]) == 64


def test_plan_agent_pilot_prints_preflight_without_constructing_llm_client(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "pilot.json"
    corpus = tmp_path / "passages.jsonl"
    entities = tmp_path / "entities.json"
    _write_json(config_path, {"schema_version": "agent-pilot-v1", "tasks": [{"task_id": "AG01", "category": "single_paper", "task_zh": "task"}]})
    corpus.write_text('{"passage_id":"P:C","paper_key":"P","text":"evidence"}\n', encoding="utf-8")
    _write_json(entities, {"schema_version": "paper-entity-metadata-v1", "entities": []})
    monkeypatch.setenv("LLM_MODEL", "deepseek-v4-flash")

    assert main(["plan-agent-pilot", "--config", str(config_path), "--corpus", str(corpus), "--entity-metadata", str(entities)]) == 0
    assert json.loads(capsys.readouterr().out)["external_llm_client_constructed"] is False
