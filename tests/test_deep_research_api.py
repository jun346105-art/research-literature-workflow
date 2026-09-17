from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from litflow_api.mvp import DEEP_RESEARCH_EXAMPLES, DemoAssets, MvpService, create_mvp_app
from test_mvp_api import _assets


def test_missing_frozen_artifact_fails_closed_and_sse_remains_available(tmp_path):
    client = TestClient(create_mvp_app(MvpService(_assets(tmp_path))))
    created = client.post("/api/deep-research/jobs", json={"query": next(iter(DEEP_RESEARCH_EXAMPLES))})
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    status = client.get(f"/api/deep-research/jobs/{job_id}")
    assert status.status_code == 200 and status.json()["status"] == "failed"
    result = client.get(f"/api/deep-research/jobs/{job_id}/result")
    body = result.json()
    assert body["reason"] == "demo_artifact_unavailable"
    assert body["findings"] == []
    assert body["replay"]["external_calls"] == 0
    assert body["publication_ready"] is False
    events = client.get(f"/api/deep-research/jobs/{job_id}/events")
    assert events.status_code == 200 and "offline_demo_loaded" in events.text


@pytest.mark.parametrize("query,identity", DEEP_RESEARCH_EXAMPLES.items())
def test_available_frozen_examples_keep_distinct_run_identity(tmp_path, query, identity):
    assets = replace(DemoAssets.from_repo(Path(__file__).parents[1]), jobs_dir=tmp_path / "jobs")
    artifact = assets.corpus_path.parents[2] / "outputs" / "deep_research" / "e2e" / "v1.2" / identity[0]
    if not artifact.is_dir():
        pytest.skip("optional local frozen artifact not installed")
    client = TestClient(create_mvp_app(MvpService(assets)))
    created = client.post("/api/deep-research/jobs", json={"query": query})
    result = client.get(f"/api/deep-research/jobs/{created.json()['job_id']}/result").json()
    assert result["run_id"] == identity[0]
    assert result["terminal"] in {"complete", "insufficient_evidence"}
    assert result["replay"]["external_calls"] == 0
    assert result["publication_ready"] is False
    if identity[1]:
        direct = [finding for finding in result["findings"] if finding["support_kind"] == "direct"]
        assert len(direct) == 1 and direct[0]["claim_id"] == identity[1]
        assert direct[0]["citations"]
    else:
        assert result["findings"] == []


def test_deep_research_online_mode_is_explicitly_rejected(tmp_path):
    client = TestClient(create_mvp_app(MvpService(_assets(tmp_path))))
    response = client.post("/api/deep-research/jobs", json={"query": "x", "mode": "online"})
    assert response.status_code == 409


def test_deep_research_arbitrary_question_never_reuses_fixed_report(tmp_path):
    client = TestClient(create_mvp_app(MvpService(_assets(tmp_path))))
    created = client.post("/api/deep-research/jobs", json={"query": "Which unrelated method is best for climate forecasting?"})
    result = client.get(f"/api/deep-research/jobs/{created.json()['job_id']}/result").json()
    assert result["terminal"] == "partial"
    assert result["planner"]["calls"] == result["writer"]["calls"] == 0
    assert result["findings"] == []


def test_deep_research_job_id_path_is_safe(tmp_path):
    client = TestClient(create_mvp_app(MvpService(_assets(tmp_path))))
    assert client.get("/api/deep-research/jobs/../../etc").status_code in {404, 307}
    assert client.get("/api/deep-research/jobs/not-a-demo-id").status_code == 404
