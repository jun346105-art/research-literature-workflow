from __future__ import annotations

from fastapi.testclient import TestClient

from litflow_api.mvp import MvpService, create_mvp_app
from test_mvp_api import _assets


def test_deep_research_offline_demo_job_result_and_sse(tmp_path):
    client = TestClient(create_mvp_app(MvpService(_assets(tmp_path))))
    created = client.post("/api/deep-research/jobs", json={"query": "What does the frozen demo show?"})
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    status = client.get(f"/api/deep-research/jobs/{job_id}")
    assert status.status_code == 200 and status.json()["status"] == "complete"
    result = client.get(f"/api/deep-research/jobs/{job_id}/result")
    body = result.json()
    assert body["run_id"].startswith("dr-run-")
    assert body["replay"]["external_calls"] == 0
    assert body["publication_ready"] is False
    events = client.get(f"/api/deep-research/jobs/{job_id}/events")
    assert events.status_code == 200 and "offline_demo_loaded" in events.text


def test_deep_research_online_mode_is_explicitly_rejected(tmp_path):
    client = TestClient(create_mvp_app(MvpService(_assets(tmp_path))))
    response = client.post("/api/deep-research/jobs", json={"query": "x", "mode": "online"})
    assert response.status_code == 409


def test_deep_research_job_id_path_is_safe(tmp_path):
    client = TestClient(create_mvp_app(MvpService(_assets(tmp_path))))
    assert client.get("/api/deep-research/jobs/../../etc").status_code in {404, 307}
    assert client.get("/api/deep-research/jobs/not-a-demo-id").status_code == 404
