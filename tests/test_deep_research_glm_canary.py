from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest


def _plan() -> dict[str, object]:
    return {
        "schema_version": "dr-canary-execution-plan-v1.1",
        "provider": "zhipu-bigmodel",
        "model_id": "glm-5.3-flash",
        "endpoint": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "channel": "ordinary_model_api",
        "text_only": True,
        "tools_enabled": False,
        "vision_enabled": False,
        "video_enabled": False,
        "files_enabled": False,
        "web_enabled": False,
        "parallel_enabled": False,
        "fallback_enabled": False,
        "max_provider_calls": 1,
        "max_retries": 0,
        "max_input_tokens": 512,
        "max_output_tokens": 256,
        "operation_timeout_seconds": 30,
        "run_deadline_seconds": 45,
        "monetary_budget_currency": "CNY",
        "monetary_budget_limit": "0.01",
        "pricing_type": "promotional",
        "input_price_per_million_tokens": "0.4",
        "output_price_per_million_tokens": "1.4",
        "approval_state": "user_authorized_single_call",
        "credential_environment_variable": "ZHIPUAI_API_KEY",
    }


def _response(*, content: str = '{"status":"ok","provider":"zhipu_bigmodel","model":"glm-5.3-flash"}') -> dict[str, object]:
    return {
        "model": "glm-5.3-flash",
        "id": "request-test-1",
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19},
    }


def test_glm_runner_records_only_after_durable_reserve_and_dispatch(tmp_path, monkeypatch):
    from litflow.deep_research.canary import GLMCanaryPlan, GLMCanaryRunner

    calls: list[dict[str, object]] = []

    async def transport(*, url, headers, body, timeout_s):
        calls.append({"url": url, "headers": headers, "body": body, "timeout_s": timeout_s})
        return 200, {}, json.dumps(_response()).encode("utf-8")

    monkeypatch.setenv("ZHIPUAI_API_KEY", "test-token-not-a-secret")
    plan = GLMCanaryPlan.model_validate(_plan())
    result = GLMCanaryRunner(plan, tmp_path / "canary", transport=transport).execute()

    assert result.terminal == "complete"
    assert result.ledger.provider_calls == 1
    assert result.ledger.provider_succeeded == 1
    assert result.ledger.input_tokens == 12
    assert result.ledger.output_tokens == 7
    assert result.ledger.cost_micros == pytest.approx(Decimal("14.6"))
    assert len(calls) == 1
    request = json.loads(calls[0]["body"])
    assert request == {
        "model": "glm-5.3-flash",
        "messages": [{"role": "user", "content": "Return only JSON with status ok, provider zhipu_bigmodel, and model glm-5.3-flash."}],
        "temperature": 1,
        "top_p": 0.95,
        "max_tokens": 256,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "max",
        "response_format": {"type": "json_object"},
        "stream": False,
    }
    assert all(event.event_type.value != "operation_dispatched" for event in result.events[:4])
    assert result.events[-1].event_type.value == "lifecycle_transition"
    assert json.loads((tmp_path / "canary" / "replay_verification.json").read_text(encoding="utf-8"))["full_replay_matches"] is True
    assert len(json.loads((tmp_path / "canary" / "immutable_plan.json").read_text(encoding="utf-8"))["adapter_commit_sha"]) == 40


def test_missing_key_fails_before_durable_dispatch_and_network(tmp_path, monkeypatch):
    from litflow.deep_research.canary import CanaryConfigurationError, GLMCanaryPlan, GLMCanaryRunner

    async def forbidden_transport(**_kwargs):
        raise AssertionError("network must not be invoked")

    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
    runner = GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=forbidden_transport)
    with pytest.raises(CanaryConfigurationError, match="credential"):
        runner.execute()
    assert not (tmp_path / "canary").exists()


@pytest.mark.parametrize(
    ("status", "expected"),
    ((400, "permanent_provider"), (401, "permanent_provider"), (403, "permanent_provider"), (429, "rate_limited"), (500, "transient_provider"), (503, "transient_provider")),
)
def test_http_failures_are_known_and_never_retried(tmp_path, monkeypatch, status, expected):
    from litflow.deep_research.canary import GLMCanaryPlan, GLMCanaryRunner

    calls = 0

    async def transport(**_kwargs):
        nonlocal calls
        calls += 1
        return status, {}, b'{"error":{"message":"redacted"}}'

    monkeypatch.setenv("ZHIPUAI_API_KEY", "test-token-not-a-secret")
    result = GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()
    assert calls == 1
    assert result.error_code.value == expected
    assert result.ledger.provider_calls == 1
    assert result.ledger.retries == 0


@pytest.mark.parametrize("failure", (TimeoutError(), ConnectionResetError()))
def test_transport_ambiguity_is_unknown_and_never_reexecuted(tmp_path, monkeypatch, failure):
    from litflow.deep_research.canary import GLMCanaryPlan, GLMCanaryRunner
    from litflow.deep_research.runtime_v2 import replay_runtime_events

    calls = 0

    async def transport(**_kwargs):
        nonlocal calls
        calls += 1
        raise failure

    monkeypatch.setenv("ZHIPUAI_API_KEY", "test-token-not-a-secret")
    runner = GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport)
    result = runner.execute()
    replayed = replay_runtime_events(result.initial_state, result.events, result.spec)
    assert calls == 1
    assert result.error_code.value == "unknown_outcome"
    assert result.manual_intervention is not None
    assert result.ledger.reservations
    assert replayed.manual_intervention == result.manual_intervention
    assert calls == 1


@pytest.mark.parametrize(
    "payload",
    (b"not json", json.dumps({"model": "glm-5.3-flash", "choices": [], "usage": {}}).encode("utf-8"), json.dumps({"model": "glm-5.3-flash", "choices": [{"message": {"content": "{}"}}]}).encode("utf-8"), json.dumps({**_response(), "model": "other-model"}).encode("utf-8")),
)
def test_bad_response_is_known_contract_failure(tmp_path, monkeypatch, payload):
    from litflow.deep_research.canary import GLMCanaryPlan, GLMCanaryRunner

    async def transport(**_kwargs):
        return 200, {}, payload

    monkeypatch.setenv("ZHIPUAI_API_KEY", "test-token-not-a-secret")
    result = GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()
    assert result.error_code.value == "contract_invalid"
    assert result.ledger.provider_calls == 1


def test_fsync_failure_prevents_adapter_invocation(tmp_path, monkeypatch):
    import os

    from litflow.deep_research.canary import GLMCanaryPlan, GLMCanaryRunner

    calls = 0
    real_fsync = os.fsync

    def fail_at_reserved_or_dispatched(fd):
        nonlocal calls
        calls += 1
        if calls in {4, 5}:
            raise OSError("durable failure")
        real_fsync(fd)

    async def transport(**_kwargs):
        raise AssertionError("network must not be invoked")

    monkeypatch.setenv("ZHIPUAI_API_KEY", "test-token-not-a-secret")
    monkeypatch.setattr("litflow.deep_research.runtime_v2.os.fsync", fail_at_reserved_or_dispatched)
    with pytest.raises(OSError, match="durable failure"):
        GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()


def test_package_root_only_exposes_controlled_canary_runner():
    import litflow.deep_research as deep_research

    assert hasattr(deep_research, "GLMCanaryRunner")
    assert not hasattr(deep_research, "GLMTextOnlyAdapter")
    assert not hasattr(deep_research, "_OperationInvoker")


def test_artifacts_redact_credential_and_do_not_persist_private_paths(tmp_path, monkeypatch):
    from litflow.deep_research.canary import GLMCanaryPlan, GLMCanaryRunner

    secret = "test-token-do-not-persist"

    async def transport(**_kwargs):
        return 200, {}, json.dumps(_response()).encode("utf-8")

    monkeypatch.setenv("ZHIPUAI_API_KEY", secret)
    GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()
    persisted = "\n".join(path.read_text(encoding="utf-8") for path in (tmp_path / "canary").glob("*"))
    assert secret not in persisted
    assert "Authorization" not in persisted
    assert str(tmp_path) not in persisted


def test_cli_requires_explicit_execute_and_never_accepts_a_key_argument(tmp_path, monkeypatch):
    from litflow.cli import main
    import litflow.cli

    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(_plan()), encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["run-glm-canary", "--plan", str(plan), "--artifact-dir", str(tmp_path / "artifact")])
    with pytest.raises(SystemExit):
        main(["run-glm-canary", "--plan", str(plan), "--artifact-dir", str(tmp_path / "artifact"), "--api-key", "not-accepted"])

    class Result:
        terminal = "complete"
        error_code = None

    monkeypatch.setattr(litflow.cli.GLMCanaryRunner, "execute", lambda _self: Result())
    assert main(["run-glm-canary", "--plan", str(plan), "--artifact-dir", str(tmp_path / "artifact"), "--execute"]) == 0


def test_default_transport_is_network_denied_before_missing_key_dispatch(tmp_path, monkeypatch):
    from litflow.deep_research.canary import GLMCanaryPlan, GLMCanaryRunner

    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
    monkeypatch.setattr("litflow.deep_research.canary.urllib.request.urlopen", lambda *_args, **_kwargs: pytest.fail("network attempted"))
    with pytest.raises(Exception, match="credential"):
        GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), tmp_path / "canary").execute()
    assert not (tmp_path / "canary").exists()


def test_execution_plan_schema_is_byte_stable(tmp_path):
    from litflow.deep_research.canary import write_glm_canary_schema

    written = write_glm_canary_schema(tmp_path)
    committed = Path("docs/deep_research/canary/v1.1/canary_execution_plan.schema.json")
    assert written.read_bytes() == committed.read_bytes()


@pytest.mark.parametrize(
    ("field", "value"),
    (("model_id", "glm-5.3-flash[1m]"), ("endpoint", "https://open.bigmodel.cn/api/coding/paas/v4"), ("max_provider_calls", 2), ("max_retries", 1), ("tools_enabled", True), ("monetary_budget_limit", "0.02")),
)
def test_execution_plan_rejects_forbidden_canary_expansion(field, value):
    from litflow.deep_research.canary import GLMCanaryPlan

    invalid = _plan()
    invalid[field] = value
    with pytest.raises(ValueError):
        GLMCanaryPlan.model_validate(invalid)


def test_committed_execution_example_parses_and_matches_the_frozen_plan():
    from litflow.deep_research.canary import GLMCanaryPlan

    example = json.loads(Path("docs/deep_research/canary/v1.1/canary_execution_plan.example.json").read_text(encoding="utf-8"))
    assert GLMCanaryPlan.model_validate(example).model_dump(exclude={"adapter_commit_sha"}) == GLMCanaryPlan.model_validate(_plan()).model_dump(exclude={"adapter_commit_sha"})


def test_live_transport_refuses_a_dirty_worktree_before_dispatch(tmp_path, monkeypatch):
    import subprocess

    from litflow.deep_research.canary import CanaryConfigurationError, GLMCanaryPlan, GLMCanaryRunner

    def git_result(args, **_kwargs):
        if args[-1] == "HEAD":
            return subprocess.CompletedProcess(args, 0, "a" * 40 + "\n", "")
        return subprocess.CompletedProcess(args, 0, " M src/litflow/deep_research/canary.py\n", "")

    monkeypatch.setattr("litflow.deep_research.canary.subprocess.run", git_result)
    runner = GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), tmp_path / "canary")
    with pytest.raises(CanaryConfigurationError, match="worktree"):
        runner._bind_execution_plan()
