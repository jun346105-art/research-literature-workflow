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


@pytest.mark.parametrize(("provider", "terminal", "expected"), (("deepseek", "complete", 0), ("zhipu-bigmodel", "failed", 2), ("deepseek", "manual_review_required", 3)))
def test_paired_cli_execute_enters_shared_runner_without_transport(monkeypatch, tmp_path, provider, terminal, expected):
    from litflow.deep_research import paired_cli

    plan_path = PAIR_DIR / ("paired_deepseek_single_paper_plan.json" if provider == "deepseek" else "paired_glm_single_paper_plan.json")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    artifact = tmp_path / "artifact"
    from litflow.deep_research.paired_e2e import parse_paired_plan
    parsed_plan = parse_paired_plan(plan).model_copy(update={"artifact_dir": artifact.as_posix().replace("\\", "/")})

    # Keep plan parsing/preflight and all task/corpus loading real; replace only live-capable seams.
    monkeypatch.setattr(paired_cli, "preflight_paired_plan", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(paired_cli, "parse_paired_plan", lambda _data: parsed_plan)

    class Adapter:
        def __init__(self, *_args, **_kwargs):
            self.replies = []

        def require_credential_for_execute(self):
            return "fixture"

    class Planner:
        def __init__(self, *_args, **_kwargs):
            pass

    class Writer:
        def __init__(self, *_args, **_kwargs):
            pass

    class Result:
        run_id = parsed_plan.run_id

        def __init__(self):
            self.terminal = terminal

    class Runner:
        def __init__(self, *_args, **_kwargs):
            pass

        async def run(self, *_args, **kwargs):
            kwargs["event_path"].parent.mkdir(parents=True, exist_ok=True)
            return Result()

    monkeypatch.setattr(paired_cli, "DeepSeekStructuredAdapter", Adapter)
    monkeypatch.setattr(paired_cli, "DeepSeekStructuredPlanner", Planner)
    monkeypatch.setattr(paired_cli, "DeepSeekSingleWriter", Writer)
    monkeypatch.setattr(paired_cli, "GLMStructuredAdapter", Adapter)
    monkeypatch.setattr(paired_cli, "GLMStructuredPlanner", Planner)
    monkeypatch.setattr(paired_cli, "GLMSingleWriter", Writer)
    monkeypatch.setattr(paired_cli, "DeepResearchRunner", Runner)
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
    monkeypatch.setenv("LITFLOW_PAIRED_EXECUTE_RUN_ID", parsed_plan.run_id)
    assert paired_cli.main(["--plan", str(plan_file), "--artifact-dir", str(artifact), "--execute"]) == expected
    if expected == 0:
        assert (artifact / "provider_telemetry.json").is_file()


def test_telemetry_counts_durable_dispatches_and_confirmed_replies_only(tmp_path):
    from litflow.deep_research.paired_cli import _write_telemetry
    from litflow.deep_research.runtime_v2 import RuntimeEventType, UnifiedEventStore, create_runtime_event
    from litflow.deep_research.deepseek_e2e import DeepSeekStructuredReply
    from litflow.deep_research.budgets import TokenUsage

    plan = _plans()[0]
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    store = UnifiedEventStore(artifact / "runtime.jsonl", run_id=plan.run_id)
    first = create_runtime_event(plan.run_id, 1, RuntimeEventType.operation_dispatched, operation_id="dr-operation-" + "a" * 24, attempt_id="dr-attempt-" + "a" * 24, payload={"operation_name": "structured_planner"})
    second = create_runtime_event(plan.run_id, 2, RuntimeEventType.operation_dispatched, operation_id="dr-operation-" + "b" * 24, attempt_id="dr-attempt-" + "b" * 24, payload={"operation_name": "single_writer"}, previous_event_hash=first.event_hash)
    store.append(first)
    store.append(second)
    reply = DeepSeekStructuredReply(content="{}", usage=TokenUsage(), model_identity_verified=True, usage_reported=True, request_id_present=True, prompt_cache_hit_tokens=2, prompt_cache_miss_tokens=3, client_observed_elapsed_s=0.5)
    adapter = type("Adapter", (), {"replies": [reply]})()
    _write_telemetry(artifact, plan, adapter)
    telemetry = json.loads((artifact / "provider_telemetry.json").read_text(encoding="utf-8"))
    assert telemetry["provider_calls"] == 2 and telemetry["planner_calls"] == 1 and telemetry["writer_calls"] == 1
    assert telemetry["prompt_cache_hit_tokens"] == [2] and telemetry["client_observed_elapsed_s"] == [0.5]


def test_execute_auth_latch_precedes_host_credentials_and_network(monkeypatch, tmp_path):
    from litflow.deep_research import paired_cli

    plan_path = PAIR_DIR / "paired_deepseek_single_paper_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    artifact = tmp_path / "artifact"
    monkeypatch.setattr(paired_cli, "preflight_paired_plan", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(paired_cli, "DeepSeekStructuredAdapter", lambda *_args, **_kwargs: pytest.fail("adapter must not be constructed"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "host-key")
    monkeypatch.delenv("LITFLOW_PAIRED_EXECUTE_RUN_ID", raising=False)
    plan["artifact_dir"] = artifact.as_posix().replace("\\", "/")
    from litflow.deep_research.paired_e2e import parse_paired_plan
    parsed = parse_paired_plan(json.loads(plan_path.read_text(encoding="utf-8"))).model_copy(update={"artifact_dir": plan["artifact_dir"]})
    monkeypatch.setattr(paired_cli, "parse_paired_plan", lambda _data: parsed)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    assert paired_cli.main(["--plan", str(path), "--artifact-dir", str(artifact), "--execute"]) == 2
    assert not artifact.exists()


def test_existing_glm_attempt001_artifact_fails_closed_before_credential(monkeypatch):
    from litflow.deep_research import paired_cli

    monkeypatch.setenv("ZHIPUAI_API_KEY", "host-key")
    monkeypatch.delenv("LITFLOW_PAIRED_EXECUTE_RUN_ID", raising=False)
    monkeypatch.setattr(paired_cli, "GLMStructuredAdapter", lambda *_args, **_kwargs: pytest.fail("credential path must not be reached"))
    result = paired_cli.main(["--plan", str(PAIR_DIR / "paired_glm_single_paper_plan.json"), "--dry-run"])
    assert result == 2
