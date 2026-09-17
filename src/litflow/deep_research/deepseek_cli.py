"""Explicit DeepSeek Canary command; isolated to preserve historical GLM CLI fingerprints."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .deepseek_canary import DeepSeekCanaryRunner, parse_deepseek_canary_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deepseek-canary")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = parse_deepseek_canary_plan(json.loads(args.plan.read_text(encoding="utf-8")))
        runner = DeepSeekCanaryRunner(plan, args.artifact_dir)
        if args.preflight:
            runner.preflight()
            print(json.dumps({"preflight": "passed", "run_id": runner.run_id}, ensure_ascii=False))
            return 0
        result = runner.execute()
    except (OSError, ValueError) as error:
        print(json.dumps({"terminal": "failed", "error_code": "contract_invalid", "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"terminal": result.terminal, "error_code": result.error_code.value if result.error_code else None}, ensure_ascii=False))
    return 0 if result.terminal == "complete" else 3 if result.error_code and result.error_code.value == "unknown_outcome" else 2


if __name__ == "__main__":
    raise SystemExit(main())
