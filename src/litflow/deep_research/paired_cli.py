"""Offline preflight/dry-run CLI for the paired provider plans."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from .deepseek_e2e import DeepSeekInvocationPolicy, DeepSeekSingleWriter, DeepSeekStructuredAdapter, DeepSeekStructuredPlanner
from .e2e import GLMInvocationPolicy, GLMSingleWriter, GLMStructuredAdapter, GLMStructuredPlanner, parse_e2e_pilot_plan
from .e2e import E2ETerminalError
from .executor import LocalResearchExecutor, ReadOnlyToolRegistry
from .paired_e2e import parse_paired_plan, preflight_paired_plan
from .identity import canonical_json
from .e2e import DeepResearchRunner
from .executor import ExecutorError
from .writer import WriterError
from .runtime_v2 import RuntimeEventType, UnifiedEventStore


AUTH_ENVIRONMENT_VARIABLE = "LITFLOW_PAIRED_EXECUTE_RUN_ID"


def _write_telemetry(artifact_dir: Path | None, plan, adapter) -> None:
    if artifact_dir is None or not artifact_dir.is_dir():
        return
    event_path = artifact_dir / "runtime.jsonl"
    events = UnifiedEventStore(event_path, run_id=plan.run_id).read_all() if event_path.is_file() else []
    dispatches = [event for event in events if event.event_type is RuntimeEventType.operation_dispatched]
    provider_dispatches = [event for event in dispatches if event.payload.get("operation_kind") == "provider" or event.payload.get("operation_name") in {"structured_planner", "single_writer"}]
    tool_dispatches = [event for event in dispatches if event.payload.get("operation_kind") == "tool" or event.payload.get("operation_name") not in {"structured_planner", "single_writer"}]
    replies = list(getattr(adapter, "replies", ()))
    elapsed = [getattr(reply, "client_observed_elapsed_s", None) for reply in replies if getattr(reply, "client_observed_elapsed_s", None) is not None]
    if not elapsed:
        elapsed = [event.payload.get("elapsed_s") for event in events if event.event_type is RuntimeEventType.elapsed_recorded and event.payload.get("elapsed_s") is not None]
    telemetry = {
        "provider": plan.provider,
        "run_id": plan.run_id,
        "planner_max_input_tokens": plan.planner_max_input_tokens,
        "planner_max_output_tokens": plan.planner_max_output_tokens,
        "writer_max_input_tokens": plan.writer_max_input_tokens,
        "writer_max_output_tokens": plan.writer_max_output_tokens,
        "planner_reasoning_effort": plan.planner_reasoning_effort,
        "writer_reasoning_effort": plan.writer_reasoning_effort,
        "provider_calls": len(provider_dispatches),
        "planner_calls": sum(event.payload.get("operation_name") == "structured_planner" for event in provider_dispatches),
        "writer_calls": sum(event.payload.get("operation_name") == "single_writer" for event in provider_dispatches),
        "tool_calls": len(tool_dispatches),
        "client_observed_elapsed_s": elapsed,
        "prompt_cache_hit_tokens": [reply.prompt_cache_hit_tokens for reply in replies],
        "prompt_cache_miss_tokens": [reply.prompt_cache_miss_tokens for reply in replies],
        "raw_persisted": False,
        "reasoning_persisted": False,
        "credential_persisted": False,
        "authorization_persisted": False,
    }
    (artifact_dir / "provider_telemetry.json").write_text(canonical_json(telemetry) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paired-single-paper")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--artifact-dir", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    adapter = None
    plan = None
    try:
        plan = parse_paired_plan(json.loads(args.plan.read_text(encoding="utf-8")))
        preflight_paired_plan(plan, repo_root=Path.cwd())
        if args.execute:
            if args.artifact_dir is None or args.artifact_dir.as_posix() != plan.artifact_dir:
                raise ValueError("artifact-dir must exactly match the frozen task target")
            if os.environ.get(AUTH_ENVIRONMENT_VARIABLE) != plan.run_id:
                raise ValueError("one-time paired execution authorization is missing or does not match the plan run_id")
            trusted_path = Path("docs/deep_research/e2e/v1.2/glm_e2e_pilot_plan.attempt-008.json")
            trusted = parse_e2e_pilot_plan(json.loads(trusted_path.read_text(encoding="utf-8")))
            task = next(item for item in trusted.tasks if item.task_key == "single_paper")
            if task.task_id != plan.task_id or task.brief_id != plan.brief_id or task.corpus_path != plan.corpus_path or task.corpus_sha256 != plan.corpus_sha256 or task.planner_prompt_sha256 != plan.planner_prompt_sha256 or task.writer_prompt_sha256 != plan.writer_prompt_sha256:
                raise ValueError("paired trusted task identity mismatch")
            task_contract, brief, approval = task.materialize()
            passages = [json.loads(line) for line in (Path.cwd() / plan.corpus_path).read_text(encoding="utf-8").splitlines() if line]
            if plan.provider == "deepseek":
                policy = DeepSeekInvocationPolicy(planner_max_input_tokens=plan.planner_max_input_tokens, writer_max_input_tokens=plan.writer_max_input_tokens, planner_max_output_tokens=plan.planner_max_output_tokens, writer_max_output_tokens=plan.writer_max_output_tokens)
                adapter = DeepSeekStructuredAdapter(policy)
                adapter.require_credential_for_execute()
                planner = DeepSeekStructuredPlanner(adapter, reservation_usage=policy.reservation("planner"))
                writer = DeepSeekSingleWriter(adapter, reservation_usage=policy.reservation("writer"))
                budget = policy.budget_spec()
            else:
                policy = GLMInvocationPolicy(planner_max_input_tokens=plan.planner_max_input_tokens, writer_max_input_tokens=plan.writer_max_input_tokens, planner_max_output_tokens=plan.planner_max_output_tokens, writer_max_output_tokens=plan.writer_max_output_tokens)
                adapter = GLMStructuredAdapter(policy)
                adapter.require_credential_for_execute()
                planner = GLMStructuredPlanner(adapter, reservation_usage=policy.reservation("planner"))
                writer = GLMSingleWriter(adapter, reservation_usage=policy.reservation("writer"))
                budget = policy.budget_spec()
            runner = DeepResearchRunner(planner, LocalResearchExecutor(ReadOnlyToolRegistry(passages), budget=budget), writer, budget=budget)
            result = asyncio.run(runner.run(task_contract, brief, approval, event_path=args.artifact_dir / "runtime.jsonl", checkpoint_path=args.artifact_dir / "checkpoint.json", attempt_id=plan.attempt_id))
            _write_telemetry(args.artifact_dir, plan, adapter)
            print(json.dumps({"terminal": result.terminal, "provider": plan.provider, "run_id": result.run_id}, ensure_ascii=False))
            return 0 if result.terminal == "complete" else 3 if result.terminal == "manual_review_required" else 2
        print(json.dumps({"preflight": "passed", "dry_run": True, "provider": plan.provider, "run_id": plan.run_id, "artifact_dir": plan.artifact_dir}, ensure_ascii=False))
        return 0
    except E2ETerminalError as error:
        _write_telemetry(args.artifact_dir, plan, adapter)
        print(json.dumps({"terminal": "outcome_unknown" if error.outcome_unknown else "failed", "error_code": error.error_code, "diagnostics": error.diagnostics}, ensure_ascii=False))
        return 3 if error.outcome_unknown else 2
    except (WriterError, ExecutorError) as error:
        _write_telemetry(args.artifact_dir, plan, adapter)
        print(json.dumps({"terminal": "failed", "error_code": error.code, "diagnostics": error.diagnostics}, ensure_ascii=False))
        return 2
    except (OSError, ValueError) as error:
        _write_telemetry(args.artifact_dir, plan, adapter)
        print(json.dumps({"terminal": "failed", "error_code": "contract_invalid", "error": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
