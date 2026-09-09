"""Explicit CLI boundary for the separately-gated GLM DeepResearch E2E pilot."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .e2e import DeepResearchRunner, E2ETerminalError, GLMSingleWriter, GLMStructuredAdapter, GLMStructuredPlanner, parse_e2e_pilot_plan, preflight_e2e_pilot
from .executor import LocalResearchExecutor, ReadOnlyToolRegistry
from .writer import WriterError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m litflow.deep_research.e2e_cli")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--task", required=True, choices=["single_paper", "cross_paper_comparison", "insufficient_evidence"])
    parser.add_argument("--artifact-dir", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = parse_e2e_pilot_plan(json.loads(args.plan.read_text(encoding="utf-8")))
        task = next(item for item in preflight_e2e_pilot(plan, repo_root=Path.cwd()) if item.task_key == args.task)
        if args.artifact_dir.as_posix() != task.artifact_dir:
            raise ValueError("artifact-dir must exactly match the frozen task target")
        if not args.execute:
            print(json.dumps({"preflight": "passed", "dry_run": bool(args.dry_run), "task": task.task_key, "run_id": task.run_id, "artifact_dir": task.artifact_dir}, ensure_ascii=False))
            return 0
        task_contract, brief, approval = task.materialize()
        passages = [json.loads(line) for line in (Path.cwd() / task.corpus_path).read_text(encoding="utf-8").splitlines() if line]
        adapter = GLMStructuredAdapter(plan.policy)
        adapter.require_credential_for_execute()
        runner = DeepResearchRunner(
            GLMStructuredPlanner(adapter, reservation_usage=plan.policy.reservation("planner")),
            LocalResearchExecutor(ReadOnlyToolRegistry(passages), budget=plan.budget_spec()),
            GLMSingleWriter(adapter, reservation_usage=plan.policy.reservation("writer")),
            budget=plan.budget_spec(),
            comparison_required=task.task_key == "cross_paper_comparison",
        )
        result = asyncio.run(runner.run(task_contract, brief, approval, event_path=args.artifact_dir / "runtime.jsonl", checkpoint_path=args.artifact_dir / "checkpoint.json", attempt_id=getattr(task, "attempt_id", None)))
        print(json.dumps({"terminal": result.terminal, "run_id": result.run_id}, ensure_ascii=False))
        return 0 if result.terminal == "complete" else 3 if result.terminal == "manual_review_required" else 2
    except E2ETerminalError as error:
        print(json.dumps({"terminal": "outcome_unknown" if error.outcome_unknown else "failed", "error_code": error.error_code}, ensure_ascii=False))
        return 3 if error.outcome_unknown else 2
    except WriterError as error:
        print(json.dumps({"terminal": "failed", "error_code": error.code, "diagnostics": error.diagnostics}, ensure_ascii=False))
        return 2
    except (ValueError, OSError) as error:
        print(json.dumps({"terminal": "failed", "error_code": type(error).__name__}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
