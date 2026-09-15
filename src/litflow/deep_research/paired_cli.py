"""Offline preflight/dry-run CLI for the paired provider plans."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .paired_e2e import parse_paired_plan, preflight_paired_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paired-single-paper")
    parser.add_argument("--plan", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = parse_paired_plan(json.loads(args.plan.read_text(encoding="utf-8")))
        preflight_paired_plan(plan, repo_root=Path.cwd())
        if args.execute:
            raise ValueError("paired execute requires the separately authorized live E2E session")
        print(json.dumps({"preflight": "passed", "dry_run": True, "provider": plan.provider, "run_id": plan.run_id, "artifact_dir": plan.artifact_dir}, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"terminal": "failed", "error_code": "contract_invalid", "error": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
