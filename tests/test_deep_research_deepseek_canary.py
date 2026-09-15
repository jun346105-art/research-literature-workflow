from __future__ import annotations

import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError


PLAN_PATH = Path("docs/deep_research/deepseek/canary_execution_plan.attempt-001.json")


def _plan() -> dict[str, object]:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _response(*, content: str = '{"status":"ok","provider":"deepseek","model":"deepseek-flash"}', model: str = "deepseek-flash", usage: dict[str, int] | None = None) -> dict[str, object]:
    return {"model": model, "id": "deepseek-request-1", "choices": [{"message": {"reasoning_content": "private reasoning", "content": content}}], "usage": usage or {"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19, "prompt_cache_hit_tokens": 4, "prompt_cache_miss_tokens": 8}}


def test_deepseek_plan_is_immutable_and_uses_new_identity():
    from litflow.deep_research.deepseek_canary import DeepSeekCanaryPlan, DEEPSEEK_ENDPOINT, DEEPSEEK_MODEL

    plan = DeepSeekCanaryPlan.model_validate(_plan())
    assert plan.model_id == DEEPSEEK_MODEL and plan.endpoint == DEEPSEEK_ENDPOINT
    assert plan.run_id == "dr-run-0381179dd264e4f8324c3214"
    assert plan.canary_attempt_id == "deepseek-flash-text-canary-001"
    assert plan.budget_spec().max_cost_micros == Decimal("20000")
    with pytest.raises(ValidationError):
        DeepSeekCanaryPlan.model_validate({**_plan(), "model_id": "deepseek-v4-flash"})


def test_normal_response_freezes_thinking_request_and_reconciles_cost(tmp_path, monkeypatch):
    from litflow.deep_research.deepseek_canary import DeepSeekCanaryPlan, DeepSeekCanaryRunner

    captured: dict[str, object] = {}

    async def transport(**kwargs):
        captured.update(kwargs)
        return 200, {}, json.dumps(_response()).encode("utf-8")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-key-never-persist")
    result = DeepSeekCanaryRunner(DeepSeekCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()
    request = json.loads(captured["body"])
    assert result.terminal == "complete" and result.ledger.provider_calls == 1
    assert result.ledger.input_tokens == 12 and result.ledger.output_tokens == 7
    assert result.ledger.cost_micros == Decimal("10.824")
    assert request == {"model": "deepseek-flash", "messages": [{"role": "user", "content": "Return only JSON with status ok, provider deepseek, and model deepseek-flash."}], "max_tokens": 4096, "thinking": {"type": "enabled"}, "reasoning_effort": "low", "response_format": {"type": "json_object"}, "stream": False}
    persisted = "\n".join(path.read_text(encoding="utf-8") for path in (tmp_path / "canary").glob("*"))
    assert "fixture-key-never-persist" not in persisted and "reasoning_content" not in persisted and "Authorization" not in persisted
    assert json.loads((tmp_path / "canary" / "replay_verification.json").read_text(encoding="utf-8"))["provider_calls_during_replay"] == 0
    assert json.loads((tmp_path / "canary" / "immutable_plan.json").read_text(encoding="utf-8")) == _plan()


def test_missing_key_and_invalid_plan_are_pre_dispatch_zero_network(tmp_path, monkeypatch):
    from litflow.deep_research.deepseek_canary import DeepSeekCanaryConfigurationError, DeepSeekCanaryPlan, DeepSeekCanaryRunner

    async def forbidden(**_kwargs):
        raise AssertionError("network must not be invoked")

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(DeepSeekCanaryConfigurationError, match="credential"):
        DeepSeekCanaryRunner(DeepSeekCanaryPlan.model_validate(_plan()), tmp_path / "missing", transport=forbidden).execute()
    assert not (tmp_path / "missing").exists()


def test_preflight_is_read_only_and_does_not_need_key(tmp_path, monkeypatch):
    from litflow.deep_research.deepseek_canary import DeepSeekCanaryPlan, DeepSeekCanaryRunner

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("litflow.deep_research.deepseek_canary.urllib.request.urlopen", lambda *_args, **_kwargs: pytest.fail("network attempted"))
    target = tmp_path / "new-canary"
    plan = DeepSeekCanaryPlan.model_validate(_plan())
    bound = DeepSeekCanaryRunner(plan, target, transport=lambda **_kwargs: None).preflight()
    assert bound.run_id == plan.run_id and bound.implementation_commit_sha and bound.runtime_source_sha256
    assert not target.exists()


def test_live_preflight_rejects_null_binding_before_network_or_key(tmp_path, monkeypatch):
    from litflow.deep_research.deepseek_canary import DeepSeekCanaryPlan, DeepSeekCanaryRunner

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    calls: list[list[str]] = []

    def git_run(args, **kwargs):
        calls.append(args)
        if args[1:3] == ["rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(args, 0, "a" * 40, "")
        if args[1:3] == ["status", "--porcelain"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError("binding should fail before ancestor lookup")

    monkeypatch.setattr("litflow.deep_research.deepseek_canary.subprocess.run", git_run)
    monkeypatch.setattr("litflow.deep_research.deepseek_canary.urllib.request.urlopen", lambda *_args, **_kwargs: pytest.fail("network attempted"))
    plan = DeepSeekCanaryPlan.model_validate(_plan()).model_copy(update={"implementation_commit_sha": None, "runtime_source_sha256": None})
    runner = DeepSeekCanaryRunner(plan, tmp_path / "canary")
    with pytest.raises(ValueError, match="must bind"):
        runner.preflight()
    assert not (tmp_path / "canary").exists() and len(calls) == 2


def test_non_ancestor_binding_is_rejected(tmp_path, monkeypatch):
    from litflow.deep_research.deepseek_canary import DeepSeekCanaryPlan, DeepSeekCanaryRunner

    data = {**_plan(), "implementation_commit_sha": "f" * 40, "runtime_source_sha256": "0" * 64}

    def git_run(args, **kwargs):
        if args[1:3] == ["rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(args, 0, "a" * 40, "")
        if args[1:3] == ["status", "--porcelain"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 1, "", "")

    monkeypatch.setattr("litflow.deep_research.deepseek_canary.subprocess.run", git_run)
    with pytest.raises(ValueError, match="not an ancestor"):
        DeepSeekCanaryRunner(DeepSeekCanaryPlan.model_validate(data), tmp_path / "canary").preflight()
    assert not (tmp_path / "canary").exists()


def test_source_drift_is_rejected(tmp_path, monkeypatch):
    from litflow.deep_research.deepseek_canary import DeepSeekCanaryPlan, DeepSeekCanaryRunner

    data = {**_plan(), "implementation_commit_sha": "a" * 40, "runtime_source_sha256": "f" * 64}

    def git_run(args, **kwargs):
        if args[1:3] == ["rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(args, 0, "a" * 40, "")
        if args[1:3] == ["status", "--porcelain"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("litflow.deep_research.deepseek_canary.subprocess.run", git_run)
    with pytest.raises(ValueError, match="fingerprint"):
        DeepSeekCanaryRunner(DeepSeekCanaryPlan.model_validate(data), tmp_path / "canary").preflight()
    assert not (tmp_path / "canary").exists()


@pytest.mark.parametrize(
    ("change", "expected"),
    (({"prompt_cache_hit_tokens": None}, "usage_missing"), ({"prompt_cache_hit_tokens": 3}, "usage_prompt_split_inconsistent"), ({"total_tokens": 20}, "usage_total_inconsistent")),
)
def test_cache_usage_audit_is_required_and_never_repaired(tmp_path, monkeypatch, change, expected):
    from litflow.deep_research.deepseek_canary import DeepSeekCanaryPlan, DeepSeekCanaryRunner

    response = _response()
    usage = dict(response["usage"])
    for key, value in change.items():
        if value is None:
            usage.pop(key)
        else:
            usage[key] = value
    response["usage"] = usage

    async def transport(**_kwargs):
        return 200, {}, json.dumps(response).encode("utf-8")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture")
    result = DeepSeekCanaryRunner(DeepSeekCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()
    diagnostics = json.loads((tmp_path / "canary" / "adapter_diagnostics.json").read_text(encoding="utf-8"))
    assert result.terminal == "failed" and result.error_code.value == "contract_invalid"
    assert diagnostics["contract_error_code"] == expected and diagnostics["usage_reported"] is False and diagnostics["cost_audit_complete"] is False


def test_plan_commit_can_be_older_than_current_head_and_fingerprint_covers_runtime_sources():
    from litflow.deep_research.deepseek_canary import DeepSeekCanaryPlan, _runtime_source_sha256
    from litflow.deep_research.identity import canonical_json_bytes, sha256_hex

    root = Path.cwd()
    relative = ("src/litflow/deep_research/deepseek_canary.py", "src/litflow/deep_research/deepseek_cli.py", "src/litflow/deep_research/canary.py", "src/litflow/deep_research/runtime_v2.py", "src/litflow/deep_research/budgets.py", "src/litflow/deep_research/operations.py")
    expected = sha256_hex(canonical_json_bytes({name: sha256_hex((root / name).read_bytes()) for name in relative}))
    plan = DeepSeekCanaryPlan.model_validate(_plan())
    assert plan.implementation_commit_sha == "b5e93f548a52e1bc0580bcfb5742be4358136a62"
    assert plan.runtime_source_sha256 == expected == _runtime_source_sha256()


def test_cli_subprocess_preflight_is_zero_network_zero_key_and_artifact_absent(tmp_path):
    environment = dict(os.environ)
    environment.pop("DEEPSEEK_API_KEY", None)
    environment["PYTHONPATH"] = "src"
    artifact = tmp_path / "must-not-exist"
    result = subprocess.run([sys.executable, "-m", "litflow.deep_research.deepseek_cli", "--plan", str(PLAN_PATH), "--artifact-dir", str(artifact), "--preflight"], cwd=Path.cwd(), env=environment, capture_output=True, text=True, check=False)
    assert result.returncode == 0 and '"preflight": "passed"' in result.stdout
    assert not artifact.exists()


@pytest.mark.parametrize(("status", "expected"), ((400, "permanent_provider"), (401, "permanent_provider"), (403, "permanent_provider"), (429, "rate_limited"), (500, "transient_provider"), (503, "transient_provider")))
def test_http_classes_are_known_and_zero_retry(tmp_path, monkeypatch, status, expected):
    from litflow.deep_research.deepseek_canary import DeepSeekCanaryPlan, DeepSeekCanaryRunner

    calls = 0

    async def transport(**_kwargs):
        nonlocal calls
        calls += 1
        return status, {}, json.dumps({"error": {"message": "redacted"}, "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 2}}).encode()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture")
    result = DeepSeekCanaryRunner(DeepSeekCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()
    assert calls == 1 and result.error_code.value == expected and result.ledger.provider_calls == 1 and result.ledger.retries == 0
    assert result.ledger.input_tokens == 2 and result.ledger.output_tokens == 3


@pytest.mark.parametrize("failure", (TimeoutError(), ConnectionResetError()))
def test_timeout_and_reset_are_unknown_without_reexecution(tmp_path, monkeypatch, failure):
    from litflow.deep_research.deepseek_canary import DeepSeekCanaryPlan, DeepSeekCanaryRunner
    from litflow.deep_research.runtime_v2 import replay_runtime_events

    calls = 0

    async def transport(**_kwargs):
        nonlocal calls
        calls += 1
        raise failure

    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture")
    result = DeepSeekCanaryRunner(DeepSeekCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()
    assert calls == 1 and result.error_code.value == "unknown_outcome" and result.manual_intervention is not None
    replay_runtime_events(result.initial_state, result.events, result.spec)
    assert calls == 1


@pytest.mark.parametrize("payload", (b"not-json", json.dumps({"model": "deepseek-flash", "choices": []}).encode(), json.dumps({"model": "wrong", "choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 1}}).encode()))
def test_malformed_missing_usage_and_model_mismatch_are_known_failures(tmp_path, monkeypatch, payload):
    from litflow.deep_research.deepseek_canary import DeepSeekCanaryPlan, DeepSeekCanaryRunner

    async def transport(**_kwargs):
        return 200, {}, payload

    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture")
    result = DeepSeekCanaryRunner(DeepSeekCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()
    assert result.terminal == "failed" and result.error_code.value == "contract_invalid" and result.ledger.provider_calls == 1


@pytest.mark.parametrize("fail_at", (4, 5))
def test_reserve_or_dispatch_fsync_failure_prevents_network(tmp_path, monkeypatch, fail_at):
    from litflow.deep_research.deepseek_canary import DeepSeekCanaryPlan, DeepSeekCanaryRunner

    calls = 0
    fsync_calls = 0
    original = os.fsync

    def fsync(fd):
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == fail_at:
            raise OSError("durable-boundary")
        return original(fd)

    async def transport(**_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("network must not be invoked")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture")
    monkeypatch.setattr("litflow.deep_research.runtime_v2.os.fsync", fsync)
    with pytest.raises(OSError, match="durable-boundary"):
        DeepSeekCanaryRunner(DeepSeekCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()
    assert calls == 0


def test_schema_is_byte_stable_and_package_root_hides_adapter(tmp_path):
    from litflow.deep_research import DeepSeekCanaryRunner
    from litflow.deep_research.deepseek_canary import write_deepseek_canary_schema

    assert write_deepseek_canary_schema(tmp_path).read_bytes() == Path("docs/deep_research/deepseek/canary_execution_plan.schema.json").read_bytes()
    import litflow.deep_research as package
    assert hasattr(package, "DeepSeekCanaryRunner") and not hasattr(package, "_DeepSeekTextOnlyAdapter")


@pytest.mark.parametrize(("terminal", "error_code", "expected"), (("complete", None, 0), ("failed", "contract_invalid", 2), ("failed", "unknown_outcome", 3)))
def test_dedicated_cli_maps_terminals_to_0_2_3(monkeypatch, terminal, error_code, expected):
    from litflow.deep_research import deepseek_cli

    class Result:
        def __init__(self):
            self.terminal = terminal
            self.error_code = type("Error", (), {"value": error_code})() if error_code else None

    class Runner:
        run_id = "dr-run-0381179dd264e4f8324c3214"

        def __init__(self, *_args, **_kwargs):
            pass

        def execute(self):
            return Result()

        def preflight(self):
            return None

    monkeypatch.setattr(deepseek_cli, "DeepSeekCanaryRunner", Runner)
    assert deepseek_cli.main(["--plan", str(PLAN_PATH), "--artifact-dir", "unused", "--execute"]) == expected


def test_dedicated_cli_requires_execute_or_preflight(tmp_path):
    from litflow.deep_research import deepseek_cli

    with pytest.raises(SystemExit):
        deepseek_cli.main(["--plan", str(PLAN_PATH), "--artifact-dir", str(tmp_path)])
