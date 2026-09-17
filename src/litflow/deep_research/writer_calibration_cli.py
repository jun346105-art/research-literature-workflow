"""Explicit dry-run/execute boundary for the Writer-only development calibration."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .e2e import E2EConfigurationError, GLMSingleWriter, GLMStructuredAdapter
from .writer import WriterError
from .writer_calibration import WriterCalibrationPlan, WriterCalibrationRunner, build_writer_calibration_fixture, preflight_writer_calibration, write_calibration_result


def main(argv: list[str] | None = None, *, repo_root: Path | None = None, artifact_root: Path | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m litflow.deep_research.writer_calibration_cli")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    root = repo_root or Path.cwd()
    output_root = artifact_root or root
    try:
        plan = WriterCalibrationPlan.model_validate(json.loads(args.plan.read_text(encoding="utf-8")))
        preflight_writer_calibration(plan, repo_root=root, artifact_root=output_root)
        if args.artifact_dir.as_posix() != plan.artifact_dir:
            raise ValueError("artifact-dir must exactly match the frozen calibration target")
        if args.dry_run:
            print(json.dumps({"preflight": "passed", "calibration_id": plan.calibration_id, "artifact_dir": plan.artifact_dir}, ensure_ascii=False))
            return 0
        task, brief, approval, validated_plan, graph, assessment = build_writer_calibration_fixture(plan)
        adapter = GLMStructuredAdapter(plan.policy)
        adapter.require_credential_for_execute()
        artifact_dir = output_root / plan.artifact_dir
        artifact_dir.mkdir(parents=True, exist_ok=False)
        runner = WriterCalibrationRunner(GLMSingleWriter(adapter, reservation_usage=plan.policy.reservation("writer")), policy=plan.policy)
        try:
            result = asyncio.run(runner.run(task, brief, approval, validated_plan, graph, assessment, event_path=artifact_dir / "runtime.jsonl", checkpoint_path=artifact_dir / "checkpoint.json"))
        except WriterError as error:
            if (artifact_dir / "runtime.jsonl").is_file() and (artifact_dir / "checkpoint.json").is_file():
                write_calibration_result(plan, artifact_dir, error_code=error.code)
            print(json.dumps({"terminal": "failed", "error_code": error.code, "diagnostics": error.diagnostics}, ensure_ascii=False))
            return 2
        result_path = write_calibration_result(plan, artifact_dir, result=result)
        terminal = result.validation.status.value
        print(json.dumps({"terminal": terminal, "calibration_id": plan.calibration_id, "run_id": result.run_id, "artifact_dir": plan.artifact_dir, "result_artifact": result_path.relative_to(output_root).as_posix()}, ensure_ascii=False))
        return 0 if terminal == "complete" else 3 if terminal == "manual_review_required" else 2
    except E2EConfigurationError:
        print(json.dumps({"terminal": "failed", "error_code": "configuration_invalid"}, ensure_ascii=False))
        return 2
    except WriterError as error:
        print(json.dumps({"terminal": "failed", "error_code": error.code}, ensure_ascii=False))
        return 2
    except (ValueError, OSError):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
