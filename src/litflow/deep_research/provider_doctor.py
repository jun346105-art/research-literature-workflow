"""Offline provider/plan contract doctor; never reads credential values."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .paired_e2e import parse_paired_plan, preflight_paired_plan
from .provider_profiles import capability_profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="litflow-provider-doctor")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--provider", choices=("zhipu-bigmodel", "deepseek"))
    args = parser.parse_args(argv)
    try:
        plan = parse_paired_plan(json.loads(args.plan.read_text(encoding="utf-8")))
        if args.provider and args.provider != plan.provider:
            raise ValueError("provider does not match plan")
        profile = capability_profile(plan.provider)
        if plan.model_id != profile.canonical_model or not plan.endpoint.startswith(profile.base_url) or plan.credential_environment_variable != profile.credential_environment_variable:
            raise ValueError("provider capability profile mismatch")
        preflight_paired_plan(plan, repo_root=Path.cwd())
        print(json.dumps({"doctor": "passed", "provider": plan.provider, "model": plan.model_id, "base_url": profile.base_url, "credential_environment_variable": profile.credential_environment_variable, "planner_max_output_tokens": plan.planner_max_output_tokens, "writer_max_output_tokens": plan.writer_max_output_tokens, "retryable_errors": ["rate_limit", "provider_overload", "timeout_or_network"], "credential_value_read": False, "network_called": False}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"doctor": "failed", "error": str(error), "credential_value_read": False, "network_called": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
