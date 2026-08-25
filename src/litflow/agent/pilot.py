"""Frozen M8B protocol loading and zero-provider preflight checks."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any


class AgentPilotError(ValueError):
    pass


POLICY_VERSION = "evidence-bounded-agent-policy-v1"


def load_pilot_config(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentPilotError("pilot config must be valid UTF-8 JSON") from exc
    if payload.get("schema_version") != "agent-pilot-v1":
        raise AgentPilotError("pilot config schema_version must be agent-pilot-v1")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise AgentPilotError("pilot config must contain tasks")
    ids = [task.get("task_id") for task in tasks if isinstance(task, dict)]
    if len(ids) != len(tasks) or any(not isinstance(task_id, str) or not task_id for task_id in ids) or len(set(ids)) != len(ids):
        raise AgentPilotError("pilot task IDs must be present and unique")
    ag12 = next((task for task in tasks if task["task_id"] == "AG12"), None)
    if ag12 and (ag12.get("expected_tool_calls") != 0 or ag12.get("expected_external_llm_calls") != 0):
        raise AgentPilotError("AG12 must be deterministically policy rejected without calls")
    return payload


def build_pilot_preflight(config_path: Path, corpus_path: Path, entity_metadata_path: Path) -> dict[str, Any]:
    """Build identity only. This function never creates an LLM client or loads qrels."""
    config = load_pilot_config(config_path)
    if os.environ.get("LLM_MODEL") != "deepseek-v4-flash":
        raise AgentPilotError("resolved_model must be deepseek-v4-flash")
    for path, label in ((corpus_path, "corpus"), (entity_metadata_path, "entity metadata")):
        if not path.is_file():
            raise AgentPilotError(f"{label} is missing")
    metadata = _load_json(entity_metadata_path)
    if metadata.get("schema_version") != "paper-entity-metadata-v1":
        raise AgentPilotError("invalid paper entity metadata")
    policy = {
        "policy_version": POLICY_VERSION,
        "allowlisted_tools": ["list_papers", "retrieve_evidence", "inspect_passages", "answer_grounded", "query_evidence_matrix", "stage_writing_draft"],
        "forbidden_capabilities": ["qrels", "gold", "shell", "arbitrary_file", "arbitrary_network", "zotero_write", "obsidian_write"],
    }
    return {
        "role": config.get("role"),
        "resolved_model": "deepseek-v4-flash",
        "temperature": 0,
        "thinking_mode": "disabled",
        "response_format": "json_object",
        "protocol_sha256": _sha256_file(config_path),
        "task_set_sha256": _sha256_text(json.dumps(config["tasks"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
        "policy_sha256": _sha256_text(json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
        "corpus_sha256": _sha256_file(corpus_path),
        "entity_metadata_sha256": _sha256_file(entity_metadata_path),
        "git_commit_sha": _git_sha(),
        "task_count": len(config["tasks"]),
        "qrels_or_gold_in_agent_context": False,
        "external_llm_client_constructed": False,
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentPilotError("invalid JSON input") from exc
    if not isinstance(payload, dict):
        raise AgentPilotError("JSON input must be an object")
    return payload


def _git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
