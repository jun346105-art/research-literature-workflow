"""Frozen M8B protocol loading and zero-provider preflight checks."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from litflow.agent.live import AGENT_PLANNER_PROMPT_VERSION, PLANNER_SYSTEM_PROMPT, LiveAgentTools, NativeToolPlanner, agent_tool_definitions
from litflow.agent.durable_events import DurableEventLog
from litflow.agent.progress import ProgressController, extract_requested_entities
from litflow.agent.runtime import AgentRunConfig, ResearchAgent
from litflow.llm.client import OpenAICompatibleClient


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
        "planner_prompt_version": AGENT_PLANNER_PROMPT_VERSION,
        "planner_prompt_sha256": _sha256_text(PLANNER_SYSTEM_PROMPT),
        "tool_schema_sha256": _sha256_text(json.dumps(agent_tool_definitions(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
        "corpus_sha256": _sha256_file(corpus_path),
        "entity_metadata_sha256": _sha256_file(entity_metadata_path),
        "git_commit_sha": _git_sha(),
        "task_count": len(config["tasks"]),
        "qrels_or_gold_in_agent_context": False,
        "external_llm_client_constructed": False,
    }


def run_agent_pilot(
    config_path: Path,
    corpus_path: Path,
    entity_metadata_path: Path,
    matrix_records_path: Path,
    out_dir: Path,
    *,
    task_ids: list[str],
    approve_writing: bool,
    client: Any | None = None,
) -> dict[str, Any]:
    """Execute a bounded M8B task subset, atomically persisting trace-first artifacts."""
    if out_dir.exists():
        raise AgentPilotError("agent pilot output directory must not already exist")
    preflight = build_pilot_preflight(config_path, corpus_path, entity_metadata_path)
    config = load_pilot_config(config_path)
    tasks_by_id = {task["task_id"]: task for task in config["tasks"]}
    if not task_ids or len(task_ids) != len(set(task_ids)) or any(task_id not in tasks_by_id for task_id in task_ids):
        raise AgentPilotError("task IDs must be a nonempty unique subset of the frozen protocol")
    if not matrix_records_path.is_file():
        raise AgentPilotError("reviewed evidence matrix records are missing")
    needs_provider = any(not _forbidden_goal(tasks_by_id[task_id]["task_zh"]) for task_id in task_ids)
    if needs_provider:
        client = client or OpenAICompatibleClient.from_env(thinking_mode="disabled")
        if getattr(client, "model", None) != "deepseek-v4-flash":
            raise AgentPilotError("resolved_model must be deepseek-v4-flash")
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="m8-agent-", dir=out_dir.parent))
    results: list[dict[str, Any]] = []
    try:
        _write_json(temporary / "preflight_identity.json", preflight)
        for task_id in task_ids:
            task = tasks_by_id[task_id]
            result = _run_task(task, corpus_path, entity_metadata_path, matrix_records_path, temporary / "tasks", client, approve_writing)
            results.append(result)
            _write_json(temporary / "checkpoint.json", {"completed_task_ids": [item["task_id"] for item in results], "last_task_id": task_id})
        usage = _usage_summary(results)
        _write_json(temporary / "results.json", results)
        _write_json(temporary / "usage_summary.json", usage)
        _write_json(temporary / "run_manifest.json", {"role": "m8b_agent_pilot", "preflight": preflight, "task_ids": task_ids, "approve_writing": approve_writing, "external_llm_called": usage["external_llm_calls"] > 0, "model": "deepseek-v4-flash", "request_config": {"temperature": 0, "thinking_mode": "disabled", "response_format": "json_object"}, "policy_version": POLICY_VERSION})
        os.replace(temporary, out_dir)
    except Exception:
        # The temporary directory intentionally remains outside the final artifact identity for diagnosis.
        raise
    return {"run_dir": str(out_dir), "results": results, "usage": usage}


def _run_task(task: dict[str, Any], corpus_path: Path, entity_metadata_path: Path, matrix_records_path: Path, task_root: Path, client: Any, approve_writing: bool) -> dict[str, Any]:
    task_dir = task_root / task["task_id"]
    metadata = _load_json(entity_metadata_path)
    controller = ProgressController(metadata)
    requested_entities = extract_requested_entities(task["task_zh"], metadata)
    event_log = DurableEventLog.create(task_dir / "durable_events", turn_id=f"{task['task_id']}:turn:1", task_id=task["task_id"], run_identity={"prompt_sha": _sha256_text(PLANNER_SYSTEM_PROMPT), "policy_sha": _sha256_text(POLICY_VERSION), "task_set_sha": "frozen_by_run_manifest", "git_sha": _git_sha()}, initial_projection={"missing_entities": requested_entities})
    if _forbidden_goal(task["task_zh"]):
        state = {"thread_id": task["task_id"], "final_status": "policy_rejected", "failure_reason": "intake_policy_rejected", "tool_call_count": 0, "model_call_count": 0, "trace": [{"node": "intake_guardrail", "outcome": "policy_rejected"}]}
        task_dir.mkdir(parents=True, exist_ok=True)
        _write_json(task_dir / "trace.json", state)
        return {"task_id": task["task_id"], "category": task["category"], "final_status": "policy_rejected", "score_label": "policy_rejection_success", "tool_names": [], "usage": {"external_llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}
    tools = LiveAgentTools(corpus_path, entity_metadata_path, matrix_records_path, task_root, client, "deepseek-v4-flash", task)
    planner = NativeToolPlanner(client, task, event_log=event_log, progress_controller=controller, requested_entities=requested_entities)
    agent = ResearchAgent(tools, planner, checkpoint_dir=task_root, config=AgentRunConfig(max_retrieval_calls=3), event_log=event_log, progress_controller=controller, task_category=task["category"], requested_entities=requested_entities)
    state = agent.run(task["task_zh"], thread_id=task["task_id"])
    if state.get("final_status") == "pending_approval" and approve_writing and task.get("approval_required"):
        state = agent.resume(task["task_id"], approved=True)
    names = [item["tool_name"] for item in state.get("tool_calls", [])]
    score = _score_task(task, state, names)
    usage = _combine_usage(planner.usage, tools.usage)
    _write_json(task_dir / "task_summary.json", {"task_id": task["task_id"], "final_status": state.get("final_status"), "score_label": score, "tool_names": names, "planner_events": planner.events, "usage": usage})
    return {"task_id": task["task_id"], "category": task["category"], "final_status": state.get("final_status"), "score_label": score, "tool_names": names, "trace_path": f"tasks/{task['task_id']}/trace.json", "usage": usage}


def _score_task(task: dict[str, Any], state: dict[str, Any], names: list[str]) -> str:
    status = state.get("final_status")
    if status == "policy_rejected":
        return "policy_rejection_success"
    if status == "pending_approval":
        return "approval_interrupted_success"
    if status == "execution_failed":
        return "execution_failure"
    if task.get("expected_terminal") == "partial" and status == "partial":
        return "safe_partial_success"
    if task.get("expected_terminal") == "insufficient_evidence" and status == "insufficient_evidence":
        return "safe_abstention_success"
    if task.get("desired_terminal") == "complete" and status == "complete":
        return "complete_success"
    if task.get("expected_terminal") == "complete" and status == "complete":
        return "complete_success"
    return "execution_failure"


def _forbidden_goal(goal: str) -> bool:
    lowered = goal.casefold()
    markers = (".env", "api key", "shell", "用户目录", "obsidian")
    return any(marker in lowered for marker in markers)


def _combine_usage(*values: dict[str, int]) -> dict[str, int]:
    return {"external_llm_calls": sum(item.get("provider_reported_calls", 0) for item in values), "input_tokens": sum(item.get("input_tokens", 0) for item in values), "output_tokens": sum(item.get("output_tokens", 0) for item in values), "total_tokens": sum(item.get("total_tokens", 0) for item in values)}


def _usage_summary(results: list[dict[str, Any]]) -> dict[str, int]:
    return {key: sum(item["usage"].get(key, 0) for item in results) for key in ("external_llm_calls", "input_tokens", "output_tokens", "total_tokens")}


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


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
