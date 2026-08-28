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
    diagnostics = json.loads((tmp_path / "canary" / "adapter_diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics == {
        "contract_error_code": None,
        "application_json_valid": True,
        "cost_audit_complete": True,
        "cost_verification": "verified",
        "expected_field": None,
        "failure_stage": None,
        "http_status": 200,
        "model_identity_verified": True,
        "observed_keys": ["choices", "id", "model", "usage"],
        "observed_type": "object",
        "provider_response_confirmed": True,
        "provider_response_received": True,
        "response_json_parsed": True,
        "usage_inconsistent": False,
        "usage_reported": True,
    }
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


def test_application_contract_failure_does_not_claim_transport_or_adapter_failed(tmp_path, monkeypatch):
    from litflow.deep_research.canary import GLMCanaryPlan, GLMCanaryRunner

    async def transport(**_kwargs):
        return 200, {}, json.dumps(_response(content="not-json")).encode("utf-8")

    monkeypatch.setenv("ZHIPUAI_API_KEY", "test-token-not-a-secret")
    result = GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()
    diagnostics = json.loads((tmp_path / "canary" / "adapter_diagnostics.json").read_text(encoding="utf-8"))
    assert result.terminal == "failed"
    assert diagnostics["failure_stage"] == "application_contract"
    assert diagnostics["contract_error_code"] == "application_json_invalid"
    assert diagnostics["provider_response_received"] is True
    assert diagnostics["provider_response_confirmed"] is True
    assert diagnostics["model_identity_verified"] is True
    assert diagnostics["application_json_valid"] is False
    assert diagnostics["usage_reported"] is True


def test_missing_usage_keeps_confirmed_text_but_fails_required_cost_audit(tmp_path, monkeypatch):
    from litflow.deep_research.canary import GLMCanaryPlan, GLMCanaryRunner

    response = _response()
    response.pop("usage")

    async def transport(**_kwargs):
        return 200, {}, json.dumps(response).encode("utf-8")

    monkeypatch.setenv("ZHIPUAI_API_KEY", "test-token-not-a-secret")
    result = GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()
    diagnostics = json.loads((tmp_path / "canary" / "adapter_diagnostics.json").read_text(encoding="utf-8"))
    assert result.terminal == "failed"
    assert diagnostics["failure_stage"] == "provider_adapter_contract"
    assert diagnostics["contract_error_code"] == "usage_missing"
    assert diagnostics["provider_response_confirmed"] is True
    assert diagnostics["usage_reported"] is False
    assert diagnostics["cost_verification"] == "unavailable"
    assert diagnostics["cost_audit_complete"] is False
    assert diagnostics["application_json_valid"] is True


def test_model_identity_unverified_preserves_received_content_but_fails_canary(tmp_path, monkeypatch):
    from litflow.deep_research.canary import GLMCanaryPlan, GLMCanaryRunner

    async def transport(**_kwargs):
        return 200, {}, json.dumps({**_response(), "model": "other-model"}).encode("utf-8")

    monkeypatch.setenv("ZHIPUAI_API_KEY", "test-token-not-a-secret")
    result = GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()
    diagnostics = json.loads((tmp_path / "canary" / "adapter_diagnostics.json").read_text(encoding="utf-8"))
    assert result.terminal == "failed"
    assert diagnostics["failure_stage"] == "provider_adapter_contract"
    assert diagnostics["contract_error_code"] == "model_identity_unverified"
    assert diagnostics["provider_response_received"] is True
    assert diagnostics["model_identity_verified"] is False
    assert diagnostics["provider_response_confirmed"] is False
    assert diagnostics["application_json_valid"] is True


def test_http_error_is_a_transport_failure_with_safe_status_only(tmp_path, monkeypatch):
    from litflow.deep_research.canary import GLMCanaryPlan, GLMCanaryRunner

    async def transport(**_kwargs):
        return 401, {}, b'{"error":{"message":"not persisted"}}'

    monkeypatch.setenv("ZHIPUAI_API_KEY", "test-token-not-a-secret")
    result = GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()
    diagnostics = json.loads((tmp_path / "canary" / "adapter_diagnostics.json").read_text(encoding="utf-8"))
    assert result.error_code.value == "permanent_provider"
    assert diagnostics["failure_stage"] == "transport_contract"
    assert diagnostics["contract_error_code"] == "http_non_2xx"
    assert diagnostics["http_status"] == 401
    assert diagnostics["provider_response_received"] is True


@pytest.mark.parametrize(
    ("payload", "expected_stage", "expected_code"),
    (
        (b"not-json", "transport_contract", "response_body_not_json"),
        (json.dumps({"model": "glm-5.3-flash", "choices": [], "usage": {}}).encode("utf-8"), "provider_adapter_contract", "content_missing"),
        (json.dumps({"error": {"code": "safe-code"}}).encode("utf-8"), "provider_adapter_contract", "provider_error_envelope"),
    ),
)
def test_response_failures_are_classified_by_contract_layer(tmp_path, monkeypatch, payload, expected_stage, expected_code):
    from litflow.deep_research.canary import GLMCanaryPlan, GLMCanaryRunner

    async def transport(**_kwargs):
        return 200, {}, payload

    monkeypatch.setenv("ZHIPUAI_API_KEY", "test-token-not-a-secret")
    result = GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()
    diagnostics = json.loads((tmp_path / "canary" / "adapter_diagnostics.json").read_text(encoding="utf-8"))
    assert result.terminal == "failed"
    assert diagnostics["failure_stage"] == expected_stage
    assert diagnostics["contract_error_code"] == expected_code
    assert diagnostics["provider_response_received"] is True


def test_inconsistent_usage_is_not_repaired_and_fails_cost_audit(tmp_path, monkeypatch):
    from litflow.deep_research.canary import GLMCanaryPlan, GLMCanaryRunner

    response = _response()
    response["usage"] = {"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 20}

    async def transport(**_kwargs):
        return 200, {}, json.dumps(response).encode("utf-8")

    monkeypatch.setenv("ZHIPUAI_API_KEY", "test-token-not-a-secret")
    result = GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), tmp_path / "canary", transport=transport).execute()
    diagnostics = json.loads((tmp_path / "canary" / "adapter_diagnostics.json").read_text(encoding="utf-8"))
    assert result.terminal == "failed"
    assert diagnostics["contract_error_code"] == "usage_inconsistent"
    assert diagnostics["usage_reported"] is True
    assert diagnostics["usage_inconsistent"] is True
    assert diagnostics["cost_verification"] == "failed"
    assert diagnostics["cost_audit_complete"] is False


def test_local_plan_validation_fails_before_artifact_dispatch_or_transport(tmp_path, monkeypatch):
    from litflow.deep_research.canary import CanaryConfigurationError, GLMCanaryPlan, GLMCanaryRunner

    calls = 0

    async def forbidden_transport(**_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("transport must not be invoked")

    monkeypatch.setenv("ZHIPUAI_API_KEY", "test-token-not-a-secret")
    invalid_plan = GLMCanaryPlan.model_validate(_plan()).model_copy(update={"max_retries": 1})
    with pytest.raises(CanaryConfigurationError, match="retry"):
        GLMCanaryRunner(invalid_plan, tmp_path / "canary", transport=forbidden_transport).execute()
    assert calls == 0
    assert not (tmp_path / "canary").exists()


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


@pytest.mark.parametrize(("terminal", "error_code", "expected_exit"), (("failed", "contract_invalid", 2), ("failed", "unknown_outcome", 3)))
def test_cli_maps_failed_and_unknown_canary_terminals_to_nonzero_exit(tmp_path, monkeypatch, terminal, error_code, expected_exit):
    from litflow.cli import main
    import litflow.cli

    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(_plan()), encoding="utf-8")

    class Result:
        def __init__(self):
            self.terminal = terminal
            self.error_code = type("Error", (), {"value": error_code})()

    monkeypatch.setattr(litflow.cli.GLMCanaryRunner, "execute", lambda _self: Result())
    assert main(["run-glm-canary", "--plan", str(plan), "--artifact-dir", str(tmp_path / "artifact"), "--execute"]) == expected_exit


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


def _v12_plan(*, attempt_id: str = "glm-5.3-flash-text-canary-002") -> dict[str, object]:
    plan = _plan()
    plan.update(
        {
            "schema_version": "dr-canary-execution-plan-v1.2",
            "canary_attempt_id": attempt_id,
            "task_id": "dr-task-" + "c" * 24,
            "brief_id": "dr-brief-" + "d" * 24,
            "implementation_commit_sha": "a" * 40,
            "runtime_source_sha256": "b" * 64,
        }
    )
    return plan


def test_v11_plan_keeps_the_original_deterministic_run_id(tmp_path):
    from litflow.deep_research.canary import GLMCanaryPlan, GLMCanaryRunner

    runner = GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), tmp_path / "canary")
    assert runner.run_id == "dr-run-dc27b7d035bba74e18f4c7f3"


def test_v12_plan_derives_stable_distinct_run_ids_from_attempt_identity(tmp_path):
    from litflow.deep_research.canary import GLMCanaryPlanV12, GLMCanaryRunner

    first = GLMCanaryRunner(GLMCanaryPlanV12.model_validate(_v12_plan()), tmp_path / "first")
    same = GLMCanaryRunner(GLMCanaryPlanV12.model_validate(_v12_plan()), tmp_path / "same")
    other = GLMCanaryRunner(
        GLMCanaryPlanV12.model_validate(_v12_plan(attempt_id="glm-5.3-flash-text-canary-003")),
        tmp_path / "other",
    )

    assert first.run_id == same.run_id
    assert first.run_id != other.run_id
    assert first.run_id.startswith("dr-run-")


def test_v12_parser_rejects_missing_attempt_identity_and_accepts_v11():
    from litflow.deep_research.canary import CanaryConfigurationError, GLMCanaryPlan, GLMCanaryPlanV12, parse_glm_canary_plan

    assert isinstance(parse_glm_canary_plan(_plan()), GLMCanaryPlan)
    assert isinstance(parse_glm_canary_plan(_v12_plan()), GLMCanaryPlanV12)
    invalid = _v12_plan()
    invalid.pop("canary_attempt_id")
    with pytest.raises((CanaryConfigurationError, ValueError)):
        parse_glm_canary_plan(invalid)


def test_v12_preflight_rejects_non_ancestor_implementation_or_source_fingerprint(tmp_path, monkeypatch):
    import subprocess

    from litflow.deep_research.canary import CanaryConfigurationError, GLMCanaryPlanV12, GLMCanaryRunner

    plan = GLMCanaryPlanV12.model_validate(_v12_plan())

    def git_result(args, **_kwargs):
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(args, 0, "c" * 40 + "\n", "")
        if args[:3] == ["git", "merge-base", "--is-ancestor"]:
            return subprocess.CompletedProcess(args, 1, "", "")
        raise AssertionError(args)

    monkeypatch.setattr("litflow.deep_research.canary.subprocess.run", git_result)
    runner = GLMCanaryRunner(plan, tmp_path / "canary", transport=lambda **_kwargs: None)
    with pytest.raises(CanaryConfigurationError, match="ancestor"):
        runner.preflight()


def test_v12_preflight_rejects_runtime_source_fingerprint_drift(tmp_path, monkeypatch):
    import subprocess

    from litflow.deep_research.canary import CanaryConfigurationError, GLMCanaryPlanV12, GLMCanaryRunner

    plan = GLMCanaryPlanV12.model_validate(_v12_plan())

    def git_result(args, **_kwargs):
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(args, 0, "c" * 40 + "\n", "")
        if args[:3] == ["git", "merge-base", "--is-ancestor"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(args)

    monkeypatch.setattr("litflow.deep_research.canary.subprocess.run", git_result)
    monkeypatch.setattr("litflow.deep_research.canary._runtime_source_sha256", lambda: "f" * 64)
    runner = GLMCanaryRunner(plan, tmp_path / "canary", transport=lambda **_kwargs: None)
    with pytest.raises(CanaryConfigurationError, match="fingerprint"):
        runner.preflight()


def test_preflight_rejects_an_existing_artifact_directory_without_reading_a_credential(tmp_path, monkeypatch):
    from litflow.deep_research.canary import CanaryConfigurationError, GLMCanaryPlan, GLMCanaryRunner

    artifact_dir = tmp_path / "canary"
    artifact_dir.mkdir()
    runner = GLMCanaryRunner(GLMCanaryPlan.model_validate(_plan()), artifact_dir, transport=lambda **_kwargs: None)
    monkeypatch.setattr(runner, "_bind_execution_plan", lambda: runner.plan)
    with pytest.raises(CanaryConfigurationError, match="already exist"):
        runner.preflight()


def test_v12_execution_plan_schema_is_byte_stable(tmp_path):
    from litflow.deep_research.canary import write_glm_canary_schema_v12

    written = write_glm_canary_schema_v12(tmp_path)
    committed = Path("docs/deep_research/canary/v1.2/canary_execution_plan.schema.json")
    assert written.read_bytes() == committed.read_bytes()


def test_committed_v12_plan_has_a_new_deterministic_run_identity_without_a_credential(tmp_path):
    from litflow.deep_research.canary import GLMCanaryPlanV12, GLMCanaryRunner, parse_glm_canary_plan

    plan_path = Path("docs/deep_research/canary/v1.2/canary_execution_plan.example.json")
    plan = parse_glm_canary_plan(json.loads(plan_path.read_text(encoding="utf-8")))
    assert isinstance(plan, GLMCanaryPlanV12)
    runner = GLMCanaryRunner(plan, tmp_path / "second-canary", transport=lambda **_kwargs: None)
    assert runner.run_id == "dr-run-e195b665d03ebf536d0bc63d"
    assert runner.run_id != "dr-run-dc27b7d035bba74e18f4c7f3"
    assert runner.preflight() == plan
