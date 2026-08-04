import json

import pytest

from litflow.llm.client import LLMError
from litflow.llm.evidence_bank_note import generate_note_from_evidence_bank


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def complete_json(self, prompt):
        self.prompts.append(prompt)
        return self.response


def _candidate_bank():
    return {
        "candidates": [
            {
                "claim": f"claim {i}",
                "evidence_type": "method",
                "chunk_id": "P1_chunk_0001",
                "page_start": 1,
                "page_end": 1,
                "evidence_text": f"evidence {i}",
                "anchoring_method": "exact_match",
                "status": "anchored",
            }
            for i in range(1, 4)
        ]
    }


def _clean_context():
    return {"chunks": [{"chunk_id": "P1_chunk_0001", "page_start": 1, "page_end": 1, "text": "evidence 1 evidence 2 evidence 3"}]}


def _llm_response(ids=None):
    ids = ids or ["P1_ev_0001", "P1_ev_0002", "P1_ev_0003"]
    return json.dumps(
        {
            "one_sentence_summary": "一句话总结",
            "research_background": "背景",
            "research_gap": "gap",
            "core_contribution": "贡献",
            "method_summary": "方法",
            "data_or_experiment": "实验",
            "model_or_algorithm": "模型",
            "objective_or_task": "任务",
            "key_results": "结果",
            "limitations": "局限",
            "relevance_to_my_research": "相关",
            "related_concepts": ["concept"],
            "tags_suggestion": ["tag"],
            "evidence_selections": [{"claim": f"selected {i}", "candidate_id": candidate_id, "evidence_text": "fake"} for i, candidate_id in enumerate(ids, 1)],
            "warnings": [],
        }
    )


def test_generate_note_maps_candidate_ids_to_evidence_links(tmp_path):
    bank = tmp_path / "bank.json"
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    bank.write_text(json.dumps(_candidate_bank()), encoding="utf-8")
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")

    note = generate_note_from_evidence_bank(bank, clean, out, zotero_key="P1", citation_key="key", title="Title", client=FakeLLM(_llm_response()))

    assert len(note.evidence_links) == 3
    assert note.evidence_links[0].evidence_text == "evidence 1"
    assert note.evidence_links[0].evidence_text in _clean_context()["chunks"][0]["text"]
    assert "generated_from_evidence_candidate_bank" in note.warnings


def test_unknown_candidate_id_fails(tmp_path):
    bank = tmp_path / "bank.json"
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    bank.write_text(json.dumps(_candidate_bank()), encoding="utf-8")
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")

    with pytest.raises(LLMError):
        generate_note_from_evidence_bank(bank, clean, out, zotero_key="P1", citation_key="key", title="Title", client=FakeLLM(_llm_response(["missing"])))

    assert json.loads(out.with_suffix(".error.json").read_text(encoding="utf-8"))["error_type"] == "ValueError"


def test_less_than_three_evidence_fails(tmp_path):
    bank = tmp_path / "bank.json"
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    bank.write_text(json.dumps(_candidate_bank()), encoding="utf-8")
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")

    with pytest.raises(LLMError):
        generate_note_from_evidence_bank(bank, clean, out, zotero_key="P1", citation_key="key", title="Title", client=FakeLLM(_llm_response(["P1_ev_0001", "P1_ev_0002"])))


def test_list_text_fields_are_converted_to_markdown_text(tmp_path):
    bank = tmp_path / "bank.json"
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    data = json.loads(_llm_response())
    data["core_contribution"] = ["one", "two"]
    bank.write_text(json.dumps(_candidate_bank()), encoding="utf-8")
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")

    note = generate_note_from_evidence_bank(bank, clean, out, zotero_key="P1", citation_key="key", title="Title", client=FakeLLM(json.dumps(data)))

    assert note.core_contribution == "- one\n- two"


def test_prompt_does_not_ask_llm_for_chunk_or_evidence_text(tmp_path):
    bank = tmp_path / "bank.json"
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    fake = FakeLLM(_llm_response())
    bank.write_text(json.dumps(_candidate_bank()), encoding="utf-8")
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")

    generate_note_from_evidence_bank(bank, clean, out, zotero_key="P1", citation_key="key", title="Title", client=fake)

    assert "Do not output evidence_text, chunk_id, page_start, or page_end" in fake.prompts[0]
    assert "物流纸箱/包装箱表观缺陷检测" in fake.prompts[0]
    assert "revised_longform_note" in fake.prompts[0]
    assert "never use not_found" in fake.prompts[0]
