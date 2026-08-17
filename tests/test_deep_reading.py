from __future__ import annotations

import json
from pathlib import Path

import pytest

from litflow.llm.client import LLMError
from litflow.llm.deep_reading import extract_deep_reading_objects, plan_deep_reading
from litflow.llm.deep_reading_models import DeepReadingSidecar, ValueStatus
from litflow.llm.models import StructuredReadingNote
from litflow.obsidian.deep_reading_preview import preview_deep_reading_objects


class FakeLLM:
    def __init__(self, response: dict):
        self.response = response
        self.calls = 0

    def complete_json(self, _prompt: str) -> str:
        self.calls += 1
        return json.dumps(self.response)


def test_plan_only_uses_full_context_without_client(tmp_path):
    clean, bank = _inputs(tmp_path)
    plan = plan_deep_reading(bank, clean, model="fake")

    assert plan["estimated_calls"] == 1
    assert plan["full_context_char_count"] == sum(len(chunk) for chunk in ["Method source. New operation source.", "Experiment source.", "Ablation source."])
    assert plan["candidate_evidence_char_count"] > 0
    assert plan["prompt_char_count"] > plan["candidate_evidence_char_count"]
    assert plan["context_guard"]["within_limit"] is True
    with pytest.raises(ValueError, match="context limit"):
        plan_deep_reading(bank, clean, model="fake", context_limit_tokens=1, max_output_tokens=1, safety_margin_tokens=0)


def test_extract_resolves_existing_and_new_evidence_at_field_level(tmp_path):
    clean, bank = _inputs(tmp_path)
    out = tmp_path / "sidecar.json"
    sidecar = extract_deep_reading_objects(bank, clean, out, client=FakeLLM(_payload()))

    component = sidecar.method_components[0]
    assert component.name.evidence_ids == ["P1_ev_0001"]
    assert component.operation_description.evidence_ids == ["P1_deep_ev_0002"]
    assert component.operation_description.value == "uses a convolution"
    assert sidecar.ablation_records[0].ablation_design.value == "full_model_comparison"
    assert sidecar.ablation_records[0].changed_components.value == ["P1:component:0001", "P1:component:0002"]
    assert sidecar.experiment_records[0].metrics[0].value.value == 95.8
    assert sidecar.experiment_records[0].metrics[0].unit.value == "%"
    assert out.is_file()
    assert (tmp_path / "raw_response.txt").is_file()
    assert (tmp_path / "run_manifest.json").is_file()
    assert (tmp_path / "evidence_registry.json").is_file()
    assert (tmp_path / "anchor_failure_ledger.json").is_file()
    assert (tmp_path / "validation_report.json").is_file()


def test_unanchorable_new_quote_is_downgraded_not_stated(tmp_path):
    clean, bank = _inputs(tmp_path)
    payload = _payload()
    payload["method_components"][0]["insertion_point"] = _quote("missing quote", "P1_chunk_0001", "backbone")
    sidecar = extract_deep_reading_objects(bank, clean, tmp_path / "sidecar.json", client=FakeLLM(payload))

    assert sidecar.method_components[0].insertion_point.status == ValueStatus.not_found
    assert sidecar.method_components[0].insertion_point.value is None
    assert sidecar.method_components[0].insertion_point.evidence_ids == []


def test_cross_paper_evidence_and_unknown_component_are_rejected(tmp_path):
    clean, bank = _inputs(tmp_path)
    payload = _payload()
    payload["paper_stated_claims"][0]["statement"] = _existing("P2_ev_0001", "claim")
    with pytest.raises(LLMError):
        extract_deep_reading_objects(bank, clean, tmp_path / "bad.json", client=FakeLLM(payload))

    payload = _payload()
    payload["ablation_records"][0]["changed_components"] = _existing("P1_ev_0003", ["P1:component:9999"])
    with pytest.raises(LLMError):
        extract_deep_reading_objects(bank, clean, tmp_path / "bad-components.json", client=FakeLLM(payload))

    payload = _payload()
    payload["method_components"][0]["insertion_point"]["status"] = "not_stated"
    with pytest.raises(LLMError):
        extract_deep_reading_objects(bank, clean, tmp_path / "bad-status.json", client=FakeLLM(payload))


def test_preview_is_sidecar_only_and_old_structured_note_still_valid(tmp_path):
    clean, bank = _inputs(tmp_path)
    sidecar_path = tmp_path / "sidecar.json"
    extract_deep_reading_objects(bank, clean, sidecar_path, client=FakeLLM(_payload()))
    preview = tmp_path / "preview.md"
    target_note = tmp_path / "existing-note.md"
    target_note.write_text("user content", encoding="utf-8")

    preview_deep_reading_objects(sidecar_path, preview)

    assert "## Method Components" in preview.read_text(encoding="utf-8")
    assert target_note.read_text(encoding="utf-8") == "user content"
    assert DeepReadingSidecar.model_validate_json(sidecar_path.read_text(encoding="utf-8")).zotero_key == "P1"
    assert StructuredReadingNote.model_validate({"zotero_key": "P1", "title": "legacy"}).title == "legacy"


def _inputs(tmp_path: Path) -> tuple[Path, Path]:
    clean = tmp_path / "clean.json"
    clean.write_text(json.dumps({"metadata": {"zotero_key": "P1", "citation_key": "cite", "title": "Paper"}, "chunks": [
        {"chunk_id": "P1_chunk_0001", "page_start": 1, "page_end": 1, "section_guess": "method", "text": "Method source. New operation source."},
        {"chunk_id": "P1_chunk_0002", "page_start": 2, "page_end": 2, "section_guess": "experiment", "text": "Experiment source."},
        {"chunk_id": "P1_chunk_0003", "page_start": 3, "page_end": 3, "section_guess": "results", "text": "Ablation source."},
    ]}), encoding="utf-8")
    bank = tmp_path / "bank.json"
    bank.write_text(json.dumps({"candidates": [
        {"chunk_id": "P1_chunk_0001", "page_start": 1, "page_end": 1, "evidence_text": "Method source.", "anchoring_method": "exact_match"},
        {"chunk_id": "P1_chunk_0002", "page_start": 2, "page_end": 2, "evidence_text": "Experiment source.", "anchoring_method": "exact_match"},
        {"chunk_id": "P1_chunk_0003", "page_start": 3, "page_end": 3, "evidence_text": "Ablation source.", "anchoring_method": "exact_match"},
    ]}), encoding="utf-8")
    return clean, bank


def _existing(evidence_id: str, value: object) -> dict:
    return {"value": value, "status": "stated", "existing_evidence_ids": [evidence_id], "quote_hints": [], "raw_value": str(value), "warnings": []}


def _quote(hint: str, chunk_id: str, value: object) -> dict:
    return {"value": value, "status": "stated", "existing_evidence_ids": [], "quote_hints": [{"chunk_id": chunk_id, "quote_hint": hint}], "raw_value": str(value), "warnings": []}


def _missing() -> dict:
    return {"value": None, "status": "not_found_in_available_context", "existing_evidence_ids": [], "quote_hints": [], "raw_value": None, "warnings": []}


def _payload() -> dict:
    return {
        "paper_stated_claims": [{"claim_kind": "method", "statement": _existing("P1_ev_0001", "paper states method"), "scope": _missing()}],
        "method_components": [
            {"name": _existing("P1_ev_0001", "Component A"), "architecture_stage": _quote("Method source.", "P1_chunk_0001", "backbone"), "operation_type": _existing("P1_ev_0001", "convolution"), "insertion_point": _missing(), "input_description": _missing(), "operation_description": _quote("New operation source.", "P1_chunk_0001", "uses a convolution"), "output_description": _missing(), "addressed_problem": _missing(), "author_claimed_effect": _missing(), "stated_design_motivation": _missing()},
            {"name": _existing("P1_ev_0001", "Component B"), "architecture_stage": _missing(), "operation_type": _existing("P1_ev_0001", "fusion"), "insertion_point": _missing(), "input_description": _missing(), "operation_description": _missing(), "output_description": _missing(), "addressed_problem": _missing(), "author_claimed_effect": _missing(), "stated_design_motivation": _missing()},
        ],
        "experiment_records": [{"experiment_kind": "dataset", "task": _existing("P1_ev_0002", "detection"), "dataset": _existing("P1_ev_0002", "Dataset"), "split": _missing(), "training_settings": [], "hardware": _missing(), "input_size": _missing(), "optimizer": _missing(), "metrics": [{"name": "precision", "value": _existing("P1_ev_0002", 95.8), "unit": _existing("P1_ev_0002", "%")}], "comparison_target": _missing()}],
        "ablation_records": [{"ablation_design": _existing("P1_ev_0003", "full_model_comparison"), "baseline": _existing("P1_ev_0003", "Baseline"), "variant": _existing("P1_ev_0003", "Full model"), "changed_components": _existing("P1_ev_0003", ["P1:component:0001", "P1:component:0002"]), "metrics": [], "comparison_conditions": _missing(), "interpretation": _missing()}],
    }
