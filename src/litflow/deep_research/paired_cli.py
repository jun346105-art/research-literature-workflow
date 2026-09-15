"""Offline preflight/dry-run CLI for the paired provider plans."""
from __future__ import annotations

import argparse
import asyncio
import json
from decimal import Decimal
from pathlib import Path

from .budgets import BudgetSpec
from .deepseek_e2e import DeepSeekInvocationPolicy, DeepSeekSingleWriter, DeepSeekStructuredAdapter, DeepSeekStructuredPlanner
from .e2e import GLMInvocationPolicy, GLMSingleWriter, GLMStructuredAdapter, GLMStructuredPlanner, parse_e2e_pilot_plan
from .executor import LocalResearchExecutor, ReadOnlyToolRegistry
from .paired_e2e import parse_paired_plan, preflight_paired_plan
from .identity import canonical_json
from .e2e import DeepResearchRunner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paired-single-paper")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--artifact-dir", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = parse_paired_plan(json.loads(args.plan.read_text(encoding="utf-8")))
        preflight_paired_plan(plan, repo_root=Path.cwd())
        if args.execute:
            if args.artifact_dir is None or args.artifact_dir.as_posix() != plan.artifact_dir:
                raise ValueError("artifact-dir must exactly match the frozen task target")
            trusted_path = Path("docs/deep_research/e2e/v1.2/glm_e2e_pilot_plan.attempt-008.json")
            trusted = parse_e2e_pilot_plan(json.loads(trusted_path.read_text(encoding="utf-8")))
            task = next(item for item in trusted.tasks if item.task_key == "single_paper")
            if task.task_id != plan.task_id or task.brief_id != plan.brief_id or task.corpus_path != plan.corpus_path or task.corpus_sha256 != plan.corpus_sha256 or task.planner_prompt_sha256 != plan.planner_prompt_sha256 or task.writer_prompt_sha256 != plan.writer_prompt_sha256:
                raise ValueError("paired trusted task identity mismatch")
            task_contract, brief, approval = task.materialize()
            passages = [json.loads(line) for line in (Path.cwd() / plan.corpus_path).read_text(encoding="utf-8").splitlines() if line]
            if plan.provider == "deepseek":
                policy = DeepSeekInvocationPolicy()
                adapter = DeepSeekStructuredAdapter(policy)
                planner = DeepSeekStructuredPlanner(adapter, reservation_usage=policy.reservation("planner"))
                writer = DeepSeekSingleWriter(adapter, reservation_usage=policy.reservation("writer"))
                budget = policy.budget_spec()
            else:
                policy = GLMInvocationPolicy()
                adapter = GLMStructuredAdapter(policy)
                planner = GLMStructuredPlanner(adapter, reservation_usage=policy.reservation("planner"))
                writer = GLMSingleWriter(adapter, reservation_usage=policy.reservation("writer"))
                budget = BudgetSpec(max_provider_attempts=2, max_provider_calls=2, max_input_tokens=6144, max_output_tokens=8192, max_total_tokens=14336, max_retries=0, max_replans=1, max_cost_micros=Decimal("20000"), run_timeout_s=180, operation_timeout_s=60)
            adapter.require_credential_for_execute()
            runner = DeepResearchRunner(planner, LocalResearchExecutor(ReadOnlyToolRegistry(passages), budget=budget), writer, budget=budget)
            result = asyncio.run(runner.run(task_contract, brief, approval, event_path=args.artifact_dir / "runtime.jsonl", checkpoint_path=args.artifact_dir / "checkpoint.json", attempt_id=plan.attempt_id))
            telemetry = {"provider": plan.provider, "run_id": result.run_id, "planner_calls": 1, "writer_calls": 1, "client_observed_elapsed_s": [getattr(reply, "client_observed_elapsed_s", None) for reply in getattr(adapter, "replies", ())], "prompt_cache_hit_tokens": [getattr(reply, "prompt_cache_hit_tokens", None) for reply in getattr(adapter, "replies", ())], "prompt_cache_miss_tokens": [getattr(reply, "prompt_cache_miss_tokens", None) for reply in getattr(adapter, "replies", ())], "raw_persisted": False, "reasoning_persisted": False, "credential_persisted": False}
            (args.artifact_dir / "provider_telemetry.json").write_text(canonical_json(telemetry) + "\n", encoding="utf-8", newline="\n")
            print(json.dumps({"terminal": result.terminal, "provider": plan.provider, "run_id": result.run_id}, ensure_ascii=False))
            return 0 if result.terminal == "complete" else 3 if result.terminal == "manual_review_required" else 2
        print(json.dumps({"preflight": "passed", "dry_run": True, "provider": plan.provider, "run_id": plan.run_id, "artifact_dir": plan.artifact_dir}, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"terminal": "failed", "error_code": "contract_invalid", "error": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
