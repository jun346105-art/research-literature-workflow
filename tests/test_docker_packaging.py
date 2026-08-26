from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_dockerfile_is_pinned_nonroot_and_does_not_copy_private_artifacts():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.13.1-slim-bookworm" in text
    assert "USER litflow" in text
    assert "HEALTHCHECK" in text
    assert "PYTHONPATH=/app/src" in text
    assert "COPY src ./src" in text
    assert "COPY outputs" not in text
    assert "COPY .git" not in text


def test_compose_defaults_to_loopback_offline_and_has_explicit_online_profile():
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert '"127.0.0.1:${LITFLOW_PORT:-8015}:8000"' in text
    assert "LITFLOW_ONLINE_QA: \"0\"" in text
    assert "litflow-online:" in text
    assert "profiles: [\"online\"]" in text
    assert "LLM_API_KEY: ${LLM_API_KEY:-}" in text
    assert "Online QA requires LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL." in text
    assert "litflow_jobs:" in text
    assert "litflow-online-init:" in text
    assert "condition: service_completed_successfully" in text
    assert "target: /app/outputs" in text
    assert "read_only: true" in text


def test_runtime_lock_and_ignore_rules_are_present():
    lock = (ROOT / "requirements.runtime.lock").read_text(encoding="utf-8")
    assert "fastapi==" in lock and "pydantic==" in lock and "uvicorn==" in lock
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    for item in (".env", "outputs/", ".git/", "tests/", "*.pdf"):
        assert item in ignored
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    runtime_names = {item.split("=", 1)[0].split("<", 1)[0].split(">", 1)[0].lower() for item in project["dependencies"]}
    lock_names = {line.split("==", 1)[0].lower() for line in (ROOT / "requirements.runtime.lock").read_text(encoding="utf-8").splitlines() if line}

    assert runtime_names <= lock_names
    assert "numpy>=2.5" in project["dependencies"]
    assert "numpy==2.5.2" in (ROOT / "requirements.runtime.lock").read_text(encoding="utf-8")
    assert project["optional-dependencies"]["test"] == ["PyMuPDF==1.28.2"]
    assert "pymupdf" not in lock_names
    assert "torch" not in runtime_names
    assert "transformers" not in runtime_names


def test_docker_demo_docs_keep_online_opt_in_and_no_private_paths():
    text = (ROOT / "docs" / "DOCKER_DEMO.md").read_text(encoding="utf-8")
    assert "docker compose up --build" in text
    assert "docker compose --profile online up --build litflow-online" in text
    assert "Offline Demo" in text and "Online QA" in text
    assert "DEMO_SCRIPT.md" in text
    assert "9/17" in text and "0.7157" in text and "5/6" in text
    assert "C:" + "\\Users" not in text and "D:/" + "论文写作" not in text
