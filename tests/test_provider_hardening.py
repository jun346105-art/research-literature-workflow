from __future__ import annotations

import asyncio
import json
from pathlib import Path


def test_capability_profiles_are_explicit_and_provider_specific():
    from litflow.deep_research.provider_profiles import capability_profile

    glm = capability_profile("zhipu-bigmodel")
    deepseek = capability_profile("deepseek")
    assert glm.canonical_model == "glm-5.3-flash"
    assert deepseek.canonical_model == "deepseek-flash"
    assert glm.credential_environment_variable != deepseek.credential_environment_variable
    assert "temperature" in glm.supported_parameters
    assert "temperature" in deepseek.unsupported_parameters


def test_provider_error_classification_and_retry_boundary():
    from litflow.deep_research.provider_profiles import classify_provider_error, retryable

    assert classify_provider_error(status=401) == "authentication"
    assert classify_provider_error(status=429) == "rate_limit"
    assert classify_provider_error(status=503) == "provider_overload"
    assert classify_provider_error(finish_reason="length") == "content_truncated"
    assert retryable("rate_limit") and retryable("provider_overload") and retryable("timeout_or_network")
    assert not retryable("content_truncated") and not retryable("authentication")


def test_explicit_writer_budget_reaches_glm_request_without_credential_persistence():
    from litflow.deep_research.e2e import GLMInvocationPolicy, GLMStructuredAdapter

    captured: dict[str, object] = {}

    async def transport(**kwargs):
        captured.update(kwargs)
        return 200, {}, json.dumps({"model": "glm-5.3-flash", "choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}).encode()

    policy = GLMInvocationPolicy(planner_max_output_tokens=8192, writer_max_output_tokens=16384)
    asyncio.run(GLMStructuredAdapter(policy, transport=transport, credential="fixture").complete(prompt="offline", operation_name="glm_single_writer"))
    request = json.loads(captured["body"])
    assert request["max_tokens"] == 16384
    assert "fixture" not in captured["body"].decode()


def test_explicit_writer_budget_reaches_deepseek_request():
    from litflow.deep_research.deepseek_e2e import DeepSeekInvocationPolicy, DeepSeekStructuredAdapter

    captured: dict[str, object] = {}

    async def transport(**kwargs):
        captured.update(kwargs)
        return 200, {}, json.dumps({"model": "deepseek-flash", "choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 1}}).encode()

    policy = DeepSeekInvocationPolicy(planner_max_output_tokens=8192, writer_max_output_tokens=16384)
    asyncio.run(DeepSeekStructuredAdapter(policy, transport=transport, credential="fixture").complete(prompt="offline", operation_name="glm_single_writer"))
    request = json.loads(captured["body"])
    assert request["max_tokens"] == 16384


def test_provider_doctor_is_offline_and_rejects_stale_binding(tmp_path: Path):
    from litflow.deep_research import provider_doctor

    plan = Path("docs/deep_research/paired_e2e/paired_deepseek_single_paper_plan.attempt-003.json")
    result = provider_doctor.main(["--plan", str(plan), "--provider", "deepseek"])
    assert result == 2


def test_run_script_does_not_echo_credentials():
    script = Path("scripts/run-provider-canary.ps1").read_text(encoding="utf-8")
    assert "Read-Host" in script
    assert "Write-Output $secureKey" not in script
    assert "ZeroFreeBSTR" in script
