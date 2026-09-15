from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


PAIR_DIR = Path("docs/deep_research/paired_e2e")


def _plans():
    from litflow.deep_research.paired_e2e import parse_paired_plan
    return [parse_paired_plan(json.loads(path.read_text(encoding="utf-8"))) for path in sorted(PAIR_DIR.glob("paired_*plan.json"))]


def test_paired_plans_share_inputs_but_have_distinct_runs_and_native_prices():
    plans = _plans()
    assert {plan.provider for plan in plans} == {"deepseek", "zhipu-bigmodel"}
    assert len({plan.run_id for plan in plans}) == 2
    assert len({plan.artifact_dir for plan in plans}) == 2
    assert len({plan.task_id for plan in plans}) == 1 and len({plan.brief_id for plan in plans}) == 1
    assert len({plan.corpus_sha256 for plan in plans}) == 1 and len({plan.planner_prompt_sha256 for plan in plans}) == 1 and len({plan.writer_prompt_sha256 for plan in plans}) == 1 and len({plan.task_input_sha256 for plan in plans}) == 1
    assert {plan.monetary_budget_currency for plan in plans} == {"CNY", "USD"}


def test_paired_plans_preflight_offline_and_artifacts_absent():
    from litflow.deep_research.paired_e2e import paired_runtime_source_sha256, preflight_paired_plan

    assert paired_runtime_source_sha256()
    for plan in _plans():
        preflight_paired_plan(plan, repo_root=Path.cwd())
        assert not (Path.cwd() / plan.artifact_dir).exists()


def test_paired_cli_dry_run_preflight_uses_no_key_or_network(tmp_path):
    env = dict(os.environ)
    env.pop("DEEPSEEK_API_KEY", None)
    env.pop("ZHIPUAI_API_KEY", None)
    env["PYTHONPATH"] = "src"
    for path in sorted(PAIR_DIR.glob("paired_*plan.json")):
        result = subprocess.run([sys.executable, "-m", "litflow.deep_research.paired_cli", "--plan", str(path), "--dry-run"], cwd=Path.cwd(), env=env, capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        assert not (Path.cwd() / json.loads(path.read_text())["artifact_dir"]).exists()
