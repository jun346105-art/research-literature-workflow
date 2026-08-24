from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from litflow.llm.client import LLMCompletion
from litflow_api.mvp import DemoAssets, MvpService, create_mvp_app
from litflow.rag.qa import run_qa_v12


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _assets(tmp_path: Path) -> DemoAssets:
    tmp_path.mkdir(parents=True, exist_ok=True)
    corpus = tmp_path / "passages.jsonl"
    passages = [
        {
            "passage_id": "P1:C1",
            "paper_key": "P1",
            "citation_key": "paper1",
            "title": "Paper One",
            "year": 2024,
            "chunk_id": "C1",
            "page_start": 1,
            "page_end": 1,
            "text": "Merge-YOLO improves packaging defect detection.",
            "text_sha256": "text-sha",
            "source_context_sha256": "context-sha",
        }
    ]
    corpus.write_text("".join(json.dumps(row) + "\n" for row in passages), encoding="utf-8")
    entity = tmp_path / "entities.json"
    _write_json(entity, {"schema_version": "paper-entity-metadata-v1", "entities": [{"paper_key": "P1", "entity_name": "Merge-YOLO", "entity_type": "model", "aliases": ["Merge-YOLO"], "evidence_passage_ids": ["P1:C1"]}]})
    matrix = tmp_path / "matrix.json"
    _write_json(matrix, {"papers": [{"paper_key": "P1", "fields": {"method": []}}]})
    writing = tmp_path / "writing"
    writing.mkdir()
    _write_json(writing / "writing_author_semantic_review.json", {"m4_status": "pass_with_moderate_human_revision", "publication_ready": False})
    (writing / "method_comparison_draft_zh_author_reviewed.md").write_text("中文作者审核稿", encoding="utf-8")
    (writing / "method_comparison_draft_en_author_reviewed.md").write_text("English author-reviewed draft", encoding="utf-8")
    (writing / "sentence_evidence_ledger_author_reviewed.md").write_text("S1 -> ev_1", encoding="utf-8")
    _write_json(writing / "closure_plan.json", {"task_id": "writing_task_v1", "limitations_zh": "partial coverage"})
    return DemoAssets(corpus_path=corpus, entity_metadata_path=entity, matrix_path=matrix, writing_dir=writing, jobs_dir=tmp_path / "jobs", corpus_id="test-corpus")


def _client(tmp_path: Path, **kwargs: object) -> TestClient:
    return TestClient(create_mvp_app(MvpService(_assets(tmp_path), run_jobs_inline=True, **kwargs)))


def test_offline_health_papers_retrieval_and_demo_views(tmp_path):
    client = _client(tmp_path)
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["mode"] == "offline_demo"
    assert health.json()["corpus_identity"]["passage_count"] == 1
    assert client.get("/api/v1/papers").json()["papers"][0]["paper_key"] == "P1"
    retrieved = client.post("/api/v1/retrieve", json={"query": "Merge-YOLO", "query_language": "en"})
    assert retrieved.status_code == 200
    assert retrieved.json()["passages"][0]["passage_id"] == "P1:C1"
    assert "relevant_passage_ids" not in retrieved.text
    assert client.get("/api/v1/evidence-matrix/demo").json()["demo_artifact"] is True
    writing = client.get("/api/v1/writing/demo").json()
    assert writing["author_reviewed"] is True
    assert writing["publication_ready"] is False


def test_input_limits_and_unknown_resources_are_safe(tmp_path):
    client = _client(tmp_path)
    assert client.post("/api/v1/retrieve", json={"query": "", "query_language": "auto"}).status_code == 422
    assert client.post("/api/v1/retrieve", json={"query": "x" * 501, "query_language": "en"}).status_code == 422
    assert client.get("/api/v1/passages/unknown").status_code == 404
    assert client.get("/api/v1/jobs/unknown").status_code == 404


def test_offline_mode_does_not_construct_llm_client(tmp_path):
    calls = []
    client = _client(tmp_path, client_factory=lambda: calls.append(True))
    response = client.post("/api/v1/qa/jobs", json={"query": "Merge-YOLO", "query_language": "en"})
    assert response.status_code == 409
    assert calls == []


def test_online_default_rejects_the_wrong_deployment_model_before_execution(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "wrong-model")
    client = TestClient(create_mvp_app(MvpService(_assets(tmp_path), online_enabled=True, run_jobs_inline=True)))
    response = client.post("/api/v1/qa/jobs", json={"query": "Merge-YOLO", "query_language": "en"})
    assert response.status_code == 409
    assert "deepseek-v4-flash" in response.json()["detail"]


def test_completed_fake_job_has_validated_answer_events_and_passage_anchor(tmp_path):
    def fake_executor(job_id, query, top, service):
        return {
            "execution_status": "success",
            "final_answer_status": "answered",
            "coverage_status": "complete",
            "answer_zh": "根据当前检索到的证据，可以确认：测试回答。",
            "claims": [{"subject_paper_key": "P1", "claim_text_zh": "测试回答", "citations": [{"passage_id": "P1:C1", "evidence_quote": "Merge-YOLO improves packaging defect detection.", "page_start": 1, "page_end": 1, "anchor_status": "exact_match"}]}],
            "limitations_zh": "",
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            "latency_ms": 1.0,
            "validation_summary": {"citation_membership": "pass", "quote_grounding": "pass"},
        }

    client = _client(tmp_path, online_enabled=True, qa_executor=fake_executor)
    created = client.post("/api/v1/qa/jobs", json={"query": "Merge-YOLO", "query_language": "en"})
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    result = client.get(f"/api/v1/jobs/{job_id}/result")
    assert result.status_code == 200
    assert result.json()["final_answer_status"] == "answered"
    assert "qrels" not in result.text.lower()
    event_text = client.get(f"/api/v1/jobs/{job_id}/events").text
    assert event_text.index("job_created") < event_text.index("retrieval_completed") < event_text.index("job_completed")
    passage = client.get("/api/v1/passages/P1:C1", params={"evidence_quote": "Merge-YOLO improves packaging defect detection."}).json()
    assert passage["anchor_status"] == "exact_match"
    assert "C:\\Users" not in json.dumps(passage)


def test_fake_llm_uses_existing_v12_quote_and_entity_validation(tmp_path):
    class FakeClient:
        model = "fake"

        def complete_json_with_usage(self, prompt, *, temperature):
            assert "SUPPLIED_PASSAGES" in prompt
            return LLMCompletion(
                content=json.dumps({"status": "answered", "claims": [{"subject_paper_key": "P1", "subject_entity_name": "Merge-YOLO", "claim_text_zh": "Merge-YOLO用于包装缺陷检测。", "citations": [{"passage_id": "P1:C1", "evidence_quote": "Merge-YOLO improves packaging defect detection."}]}], "limitations_zh": ""}),
                input_tokens=11,
                output_tokens=7,
                total_tokens=18,
            )

    service = MvpService(_assets(tmp_path), online_enabled=True, run_jobs_inline=True, client_factory=FakeClient)
    client = TestClient(create_mvp_app(service))
    job_id = client.post("/api/v1/qa/jobs", json={"query": "Merge-YOLO", "query_language": "en"}).json()["job_id"]
    result = client.get(f"/api/v1/jobs/{job_id}/result").json()
    assert result["execution_status"] == "success"
    assert result["claims"][0]["citations"][0]["anchor_status"] == "exact_match"
    assert result["usage"]["total_tokens"] == 18


def test_fake_translation_routes_a_new_chinese_query_without_qrels_in_llm_input(tmp_path):
    class FakeClient:
        model = "fake"

        def __init__(self):
            self.calls = 0

        def complete_json_with_usage(self, prompt, *, temperature):
            self.calls += 1
            assert "relevant_passage_ids" not in prompt
            assert "gold_evidence_summary" not in prompt
            if self.calls == 1:
                query_id = json.loads(prompt.split("INPUT:\n", 1)[1])["query_id"]
                return LLMCompletion(content=json.dumps({"query_id": query_id, "source_language": "zh", "target_language": "en", "translated_query": "Explain Merge-YOLO", "preserved_entities": ["Merge-YOLO"], "preserved_numbers_and_units": []}), input_tokens=3, output_tokens=2, total_tokens=5)
            return LLMCompletion(content=json.dumps({"status": "answered", "claims": [{"subject_paper_key": "P1", "subject_entity_name": "Merge-YOLO", "claim_text_zh": "Merge-YOLO用于包装缺陷检测。", "citations": [{"passage_id": "P1:C1", "evidence_quote": "Merge-YOLO improves packaging defect detection."}]}], "limitations_zh": ""}), input_tokens=7, output_tokens=5, total_tokens=12)

    fake = FakeClient()
    client = TestClient(create_mvp_app(MvpService(_assets(tmp_path), online_enabled=True, run_jobs_inline=True, client_factory=lambda: fake)))
    job_id = client.post("/api/v1/qa/jobs", json={"query": "请说明 Merge-YOLO", "query_language": "zh"}).json()["job_id"]
    assert client.get(f"/api/v1/jobs/{job_id}/result").json()["execution_status"] == "success"
    assert fake.calls == 2


def test_cli_and_api_share_the_v12_validation_result_for_the_same_raw_response(tmp_path):
    raw = json.dumps({"status": "answered", "claims": [{"subject_paper_key": "P1", "subject_entity_name": "Merge-YOLO", "claim_text_zh": "Merge-YOLO用于包装缺陷检测。", "citations": [{"passage_id": "P1:C1", "evidence_quote": "Merge-YOLO improves packaging defect detection."}]}], "limitations_zh": ""})

    class FakeClient:
        model = "fake"

        def complete_json_with_usage(self, prompt, *, temperature):
            return LLMCompletion(content=raw, input_tokens=1, output_tokens=1, total_tokens=2)

    assets = _assets(tmp_path)
    queries = tmp_path / "queries.json"
    _write_json(queries, {"queries": [{"query_id": "Q1", "query_zh": "Merge-YOLO", "query_en": "Merge-YOLO", "expected_answerable": True, "relevant_passage_ids": []}]})
    cli = run_qa_v12(assets.corpus_path, queries, tmp_path / "cli", model="fake", query_id="Q1", entity_metadata_path=assets.entity_metadata_path, client=FakeClient())
    service = MvpService(assets, online_enabled=True, run_jobs_inline=True, client_factory=FakeClient)
    api = TestClient(create_mvp_app(service))
    job_id = api.post("/api/v1/qa/jobs", json={"query": "Merge-YOLO", "query_language": "en"}).json()["job_id"]
    api_result = api.get(f"/api/v1/jobs/{job_id}/result").json()
    assert cli["results"][0].execution_status == api_result["execution_status"] == "success"
    assert cli["results"][0].claims[0]["citations"][0]["anchor_status"] == api_result["claims"][0]["citations"][0]["anchor_status"]


def test_duplicate_quote_policy_keeps_safe_metadata_and_rejects_cross_passage_matches(tmp_path):
    assets = _assets(tmp_path)
    corpus = json.loads(assets.corpus_path.read_text(encoding="utf-8").splitlines()[0])
    corpus["text"] = "Merge-YOLO supports details. Shared exact quote. Shared exact quote."
    second = {**corpus, "passage_id": "P1:C2", "chunk_id": "C2", "page_start": 2, "page_end": 2, "text": "Shared exact quote."}
    assets.corpus_path.write_text("\n".join(json.dumps(item) for item in (corpus, second)) + "\n", encoding="utf-8")
    raw = json.dumps({"status": "answered", "claims": [{"subject_paper_key": "P1", "subject_entity_name": "Merge-YOLO", "claim_text_zh": "Merge-YOLO支持细节。", "citations": [{"passage_id": "P1:C1", "evidence_quote": "Shared exact quote."}]}], "limitations_zh": ""})

    class FakeClient:
        model = "fake"

        def complete_json_with_usage(self, prompt, *, temperature):
            return LLMCompletion(content=raw)

    service = MvpService(assets, online_enabled=True, run_jobs_inline=True, client_factory=FakeClient)
    client = TestClient(create_mvp_app(service))
    job_id = client.post("/api/v1/qa/jobs", json={"query": "Merge-YOLO", "query_language": "en"}).json()["job_id"]
    result = client.get(f"/api/v1/jobs/{job_id}/result").json()
    assert result["execution_status"] == "quote_grounding_failed"
    internal = json.loads((assets.jobs_dir / job_id / "result.json").read_text(encoding="utf-8"))
    ledger = internal["quote_grounding_ledger"][0]
    assert ledger["classification"] == "matches_across_passages"
    assert ledger["ambiguity_preserved"] is False


def test_partial_answer_and_safe_abstention_are_exposed_as_distinct_outcomes(tmp_path):
    partial = {"execution_status": "success", "final_answer_status": "partial_answer", "coverage_status": "partial", "answer_zh": "部分回答", "claims": [], "limitations_zh": "缺少TPMN", "coverage_ledger": {"uncovered_entities": [{"entity_name": "TPMN"}], "coverage_status": "partial"}, "usage": None, "latency_ms": 1, "validation_summary": {}}
    client = _client(tmp_path, online_enabled=True, qa_executor=lambda *_: partial)
    job_id = client.post("/api/v1/qa/jobs", json={"query": "Merge-YOLO", "query_language": "en"}).json()["job_id"]
    assert client.get(f"/api/v1/jobs/{job_id}/result").json()["final_answer_status"] == "partial_answer"
    abstention = {"execution_status": "success", "final_answer_status": "insufficient_evidence", "coverage_status": "none", "answer_zh": "证据不足", "claims": [], "limitations_zh": "", "usage": None, "latency_ms": 1, "validation_summary": {}}
    client = _client(tmp_path / "second", online_enabled=True, qa_executor=lambda *_: abstention)
    job_id = client.post("/api/v1/qa/jobs", json={"query": "unknown", "query_language": "en"}).json()["job_id"]
    assert client.get(f"/api/v1/jobs/{job_id}/result").json()["final_answer_status"] == "insufficient_evidence"


def test_failed_execution_never_exposes_an_answer(tmp_path):
    client = _client(tmp_path, online_enabled=True, qa_executor=lambda *_: {"execution_status": "quote_grounding_failed", "error": "bad quote"})
    job_id = client.post("/api/v1/qa/jobs", json={"query": "Merge-YOLO", "query_language": "en"}).json()["job_id"]
    result = client.get(f"/api/v1/jobs/{job_id}/result").json()
    assert result["execution_status"] == "quote_grounding_failed"
    assert result["final_answer_status"] is None
    assert "answer_zh" not in result
    assert "job_failed" in client.get(f"/api/v1/jobs/{job_id}/events").text


def test_static_ui_is_served(tmp_path):
    client = _client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert "LitFlow" in response.text
    assert 'rel="icon" href="data:,"' in response.text
    assert 'id="citation-drawer"' in response.text


def test_workbench_shell_exposes_accessible_state_and_inspector_regions(tmp_path):
    client = _client(tmp_path)
    markup = client.get("/").text
    for required in (
        "Calm Research Workbench",
        'id="evidence-inspector"',
        'aria-live="polite"',
        'id="original-query"',
        'data-view="matrix"',
        'data-view="writing"',
        'id="inspector-close"',
        'Recovered job / 已恢复历史任务',
    ):
        assert required in markup
    script = (Path(__file__).parents[1] / "src" / "litflow_api" / "static" / "app.js").read_text(encoding="utf-8")
    assert "EventSource" in script
    assert "openInspector" in script
    style = (Path(__file__).parents[1] / "src" / "litflow_api" / "static" / "style.css").read_text(encoding="utf-8")
    assert "@media (max-width: 1279px)" in style
    assert "@media (max-width: 767px)" in style
    assert ".passage-block { max-height: 48vh; overflow: auto; }" in style


def test_completed_job_is_reloadable_from_its_file_backed_artifact(tmp_path):
    completed = {"execution_status": "success", "final_answer_status": "insufficient_evidence", "coverage_status": "none", "answer_zh": "证据不足", "claims": [], "limitations_zh": "", "usage": None, "latency_ms": 1, "validation_summary": {}}
    assets = _assets(tmp_path)
    first = TestClient(create_mvp_app(MvpService(assets, online_enabled=True, run_jobs_inline=True, qa_executor=lambda *_: completed)))
    job_id = first.post("/api/v1/qa/jobs", json={"query": "unknown", "query_language": "en"}).json()["job_id"]
    second = TestClient(create_mvp_app(MvpService(assets)))
    assert second.get(f"/api/v1/jobs/{job_id}/result").json()["final_answer_status"] == "insufficient_evidence"
