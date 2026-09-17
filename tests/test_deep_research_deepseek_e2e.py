from __future__ import annotations

import asyncio
import json
from decimal import Decimal

import pytest


def _usage(hit=4, miss=8, completion=7, total=19):
    return {"prompt_tokens": hit + miss, "completion_tokens": completion, "total_tokens": total, "prompt_cache_hit_tokens": hit, "prompt_cache_miss_tokens": miss}


def _payload(content="{}", model="deepseek-flash", usage=None):
    return {"model": model, "id": "request", "choices": [{"message": {"reasoning_content": "must not persist", "content": content}}], "usage": usage or _usage()}


def test_deepseek_structured_adapter_freezes_stage_request_and_cache_cost():
    from litflow.deep_research.deepseek_e2e import DeepSeekInvocationPolicy, DeepSeekStructuredAdapter

    captured = {}

    async def transport(**kwargs):
        captured.update(kwargs)
        return 200, {}, json.dumps(_payload()).encode()

    adapter = DeepSeekStructuredAdapter(DeepSeekInvocationPolicy(), transport=transport, credential="fixture")
    reply = asyncio.run(adapter.complete(prompt="offline", operation_name="glm_structured_planner"))
    request = json.loads(captured["body"])
    assert reply.prompt_cache_hit_tokens == 4 and reply.prompt_cache_miss_tokens == 8 and reply.client_observed_elapsed_s > 0
    assert reply.usage.cost_micros == Decimal("10.824")
    assert request["model"] == "deepseek-flash" and request["reasoning_effort"] == "low" and request["max_tokens"] == 4096
    assert request["thinking"] == {"type": "enabled"} and request["stream"] is False
    assert "temperature" not in request and "top_p" not in request and "tools" not in request and "fixture" not in captured["body"].decode()


def test_deepseek_writer_stage_uses_high_reasoning():
    from litflow.deep_research.deepseek_e2e import DeepSeekInvocationPolicy, DeepSeekStructuredAdapter

    captured = {}

    async def transport(**kwargs):
        captured.update(kwargs)
        return 200, {}, json.dumps(_payload()).encode()

    asyncio.run(DeepSeekStructuredAdapter(DeepSeekInvocationPolicy(), transport=transport, credential="fixture").complete(prompt="offline", operation_name="glm_single_writer"))
    request = json.loads(captured["body"])
    assert request["reasoning_effort"] == "high" and request["max_tokens"] == 4096


@pytest.mark.parametrize("failure", (TimeoutError(), ConnectionResetError()))
def test_deepseek_structured_unknown_has_elapsed_and_no_retry(failure):
    from litflow.deep_research.deepseek_e2e import DeepSeekInvocationPolicy, DeepSeekStructuredAdapter

    async def transport(**_kwargs):
        raise failure

    from litflow.deep_research.e2e import GLMAdapterError
    with pytest.raises(GLMAdapterError, match="outcome_unknown") as error:
        asyncio.run(DeepSeekStructuredAdapter(DeepSeekInvocationPolicy(), transport=transport, credential="fixture").complete(prompt="offline", operation_name="glm_structured_planner"))
    assert error.value.outcome_unknown and error.value.diagnostics["client_observed_elapsed_s"] > 0


@pytest.mark.parametrize("usage", ({"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19, "prompt_cache_hit_tokens": 4}, {**_usage(), "prompt_cache_hit_tokens": 3}, {**_usage(), "total_tokens": 20}))
def test_deepseek_structured_usage_fail_closed(usage):
    from litflow.deep_research.deepseek_e2e import DeepSeekInvocationPolicy, DeepSeekStructuredAdapter
    from litflow.deep_research.e2e import GLMAdapterError

    async def transport(**_kwargs):
        return 200, {}, json.dumps(_payload(usage=usage)).encode()

    with pytest.raises(GLMAdapterError, match="provider_response_invalid"):
        asyncio.run(DeepSeekStructuredAdapter(DeepSeekInvocationPolicy(), transport=transport, credential="fixture").complete(prompt="offline", operation_name="glm_structured_planner"))


def test_deepseek_policy_matches_paired_budget():
    from litflow.deep_research.deepseek_e2e import DeepSeekInvocationPolicy

    policy = DeepSeekInvocationPolicy()
    spec = policy.budget_spec()
    assert spec.max_provider_calls == 2 and spec.max_provider_attempts == 2 and spec.max_retries == 0 and spec.max_replans == 1
    assert spec.operation_timeout_s == 60 and spec.run_timeout_s == 180 and spec.max_cost_micros == Decimal("20000")
    assert policy.reservation("planner").total_tokens == 6144 and policy.reservation("writer").total_tokens == 8192
