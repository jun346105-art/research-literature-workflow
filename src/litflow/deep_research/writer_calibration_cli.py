"""Dry-run boundary for the Writer-only development calibration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .writer_calibration import WriterCalibrationPlan, preflight_writer_calibration


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m litflow.deep_research.writer_calibration_cli")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = WriterCalibrationPlan.model_validate(json.loads(args.plan.read_text(encoding="utf-8")))
        preflight_writer_calibration(plan, repo_root=Path.cwd())
        if args.artifact_dir.as_posix() != plan.artifact_dir:
            raise ValueError("artifact-dir must exactly match the frozen calibration target")
        print(json.dumps({"preflight": "passed", "calibration_id": plan.calibration_id, "artifact_dir": plan.artifact_dir}, ensure_ascii=False))
        return 0
    except (ValueError, OSError):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
