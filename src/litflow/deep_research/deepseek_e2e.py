"""DeepSeek structured Planner/Writer adapters for the paired single-paper design."""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .canary import _AsyncTransport, _urllib_transport
from .e2e import GLMAdapterError, GLMStructuredPlanner, GLMSingleWriter, GLMStructuredReply, _provider_diagnostics
from .budgets import BudgetSpec, TokenUsage
from .identity import canonical_json_bytes, sha256_hex


DEEPSEEK_E2E_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEEPSEEK_E2E_MODEL = "deepseek-flash"


class DeepSeekInvocationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    endpoint: Literal[DEEPSEEK_E2E_ENDPOINT] = DEEPSEEK_E2E_ENDPOINT
    model_id: Literal[DEEPSEEK_E2E_MODEL] = DEEPSEEK_E2E_MODEL
    credential_environment_variable: Literal["DEEPSEEK_API_KEY"] = "DEEPSEEK_API_KEY"
    thinking_type: Literal["enabled"] = "enabled"
    planner_reasoning_effort: Literal["low"] = "low"
    writer_reasoning_effort: Literal["high"] = "high"
    planner_max_input_tokens: Literal[2048] = 2048
    writer_max_input_tokens: Literal[4096] = 4096
    planner_max_output_tokens: Literal[4096] = 4096
    writer_max_output_tokens: Literal[4096] = 4096
    operation_timeout_seconds: Literal[60] = 60
    run_timeout_seconds: Literal[180] = 180
    max_provider_calls: Literal[2] = 2
    max_provider_attempts: Literal[2] = 2
    max_retries: Literal[0] = 0
    max_replans: Literal[1] = 1
    input_price_per_million: Decimal = Decimal("0.30")
    cache_hit_input_price_per_million: Decimal = Decimal("0.006")
    output_price_per_million: Decimal = Decimal("1.20")
    monetary_budget_limit_micros: Literal[20000] = 20000
    tools_enabled: Literal[False] = False
    vision_enabled: Literal[False] = False
    files_enabled: Literal[False] = False
    web_enabled: Literal[False] = False
    parallel_enabled: Literal[False] = False
    fallback_enabled: Literal[False] = False

    def usage(self, input_tokens: int, output_tokens: int) -> TokenUsage:
        cost = (Decimal(input_tokens) * self.input_price_per_million + Decimal(output_tokens) * self.output_price_per_million) / Decimal("1000000")
        return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens, cost_micros=cost * Decimal("1000000"))

    def reservation(self, operation: str) -> TokenUsage:
        return self.usage(self.planner_max_input_tokens if operation == "planner" else self.writer_max_input_tokens, self.planner_max_output_tokens if operation == "planner" else self.writer_max_output_tokens)

    def budget_spec(self) -> BudgetSpec:
        return BudgetSpec(max_provider_attempts=2, max_provider_calls=2, max_input_tokens=6144, max_output_tokens=8192, max_total_tokens=14336, max_retries=0, max_replans=1, max_cost_micros=Decimal("20000"), run_timeout_s=180, operation_timeout_s=60)


class DeepSeekStructuredAdapter:
    """Transport-only adapter; Planner/Writer and durable state remain shared."""

    def __init__(self, policy: DeepSeekInvocationPolicy, *, transport: _AsyncTransport = _urllib_transport, credential: str | None = None) -> None:
        self._policy, self._transport, self._credential_override = policy, transport, credential

    def require_credential_for_execute(self) -> str:
        credential = self._credential_override or os.environ.get(self._policy.credential_environment_variable)
        if not credential:
            raise ValueError("credential missing for DeepSeek structured E2E")
        return credential

    async def complete(self, *, prompt: str, operation_name: str) -> GLMStructuredReply:
        credential = self.require_credential_for_execute()
        planner = operation_name == "glm_structured_planner"
        max_tokens = self._policy.planner_max_output_tokens if planner else self._policy.writer_max_output_tokens
        reasoning = self._policy.planner_reasoning_effort if planner else self._policy.writer_reasoning_effort
        body = canonical_json_bytes({"model": self._policy.model_id, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "thinking": {"type": self._policy.thinking_type}, "reasoning_effort": reasoning, "response_format": {"type": "json_object"}, "stream": False})
        started = time.monotonic()
        try:
            status, headers, raw = await self._transport(url=self._policy.endpoint, headers={"Content-Type": "application/json", "Authorization": f"Bearer {credential}"}, body=body, timeout_s=float(self._policy.operation_timeout_seconds))
        except (TimeoutError, socket.timeout, ConnectionResetError, ConnectionError, urllib.error.URLError) as error:
            raise GLMAdapterError("outcome_unknown", outcome_unknown=True, diagnostics={**_provider_diagnostics(status=None, received=False, parsed=False, failure_stage="transport", error_code="outcome_unknown"), "client_observed_elapsed_s": max(0.000001, time.monotonic() - started)}) from error
        elapsed = max(0.000001, time.monotonic() - started)
        try:
            payload = json.loads(raw.decode("utf-8"))
            parsed = True
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GLMAdapterError("provider_response_invalid", diagnostics={**_provider_diagnostics(status=status, received=True, parsed=False, failure_stage="provider_response", error_code="provider_response_invalid"), "client_observed_elapsed_s": elapsed}) from error
        if not 200 <= status < 300 or not isinstance(payload, dict) or isinstance(payload.get("error"), dict):
            raise GLMAdapterError("transport_failure" if status >= 300 else "provider_response_invalid", diagnostics={**_provider_diagnostics(status=status, received=True, parsed=parsed, payload=payload, failure_stage="transport" if status >= 300 else "provider_response", error_code="transport_failure" if status >= 300 else "provider_response_invalid"), "client_observed_elapsed_s": elapsed})
        choices = payload.get("choices")
        choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
        content = choice.get("message", {}).get("content") if isinstance(choice, dict) else None
        usage = payload.get("usage")
        fields = ("prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens")
        if not isinstance(content, str) or not isinstance(usage, dict) or not all(type(usage.get(field)) is int and usage.get(field) >= 0 for field in fields) or usage["prompt_tokens"] != usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"] or usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]:
            raise GLMAdapterError("provider_response_invalid", diagnostics={"failure_stage": "provider_response", "contract_error_code": "usage_or_content_invalid", "usage_reported": False, "client_observed_elapsed_s": elapsed})
        cost = (Decimal(usage["prompt_cache_miss_tokens"]) * self._policy.input_price_per_million + Decimal(usage["prompt_cache_hit_tokens"]) * self._policy.cache_hit_input_price_per_million + Decimal(usage["completion_tokens"]) * self._policy.output_price_per_million) / Decimal("1000000")
        token_usage = TokenUsage(input_tokens=usage["prompt_tokens"], output_tokens=usage["completion_tokens"], cost_micros=cost * Decimal("1000000"))
        if payload.get("model") != self._policy.model_id:
            raise GLMAdapterError("provider_response_invalid", diagnostics={"failure_stage": "provider_response", "contract_error_code": "model_identity_unverified", "usage_reported": True, "client_observed_elapsed_s": elapsed}, usage=token_usage)
        return GLMStructuredReply(content=content, usage=token_usage, model_identity_verified=True, usage_reported=True, request_id_present=isinstance(payload.get("id") or headers.get("x-request-id"), str), http_status=status, finish_reason=choice.get("finish_reason") if isinstance(choice.get("finish_reason"), str) else None, content_length=len(content), content_sha256=sha256_hex(content.encode("utf-8")), observed_type="object", observed_keys=tuple(sorted(key for key in payload if key in {"choices", "error", "id", "model", "request_id", "usage"})), prompt_cache_hit_tokens=usage["prompt_cache_hit_tokens"], prompt_cache_miss_tokens=usage["prompt_cache_miss_tokens"], client_observed_elapsed_s=elapsed)


class DeepSeekStructuredPlanner(GLMStructuredPlanner):
    pass


class DeepSeekSingleWriter(GLMSingleWriter):
    pass


__all__ = ["DEEPSEEK_E2E_ENDPOINT", "DEEPSEEK_E2E_MODEL", "DeepSeekInvocationPolicy", "DeepSeekStructuredAdapter", "DeepSeekStructuredPlanner", "DeepSeekSingleWriter"]
