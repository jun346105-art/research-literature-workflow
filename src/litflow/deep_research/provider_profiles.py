"""Small, explicit capability and retry profiles for the supported providers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ProviderName = Literal["zhipu-bigmodel", "deepseek"]
ProviderErrorClass = Literal[
    "authentication", "permission", "invalid_request", "unsupported_parameter",
    "model_not_found", "quota_or_balance", "rate_limit", "provider_overload",
    "timeout_or_network", "content_truncated", "malformed_output",
    "provider_contract_failure", "unknown",
]


@dataclass(frozen=True)
class ProviderCapabilityProfile:
    provider: ProviderName
    canonical_model: str
    base_url: str
    credential_environment_variable: str
    json_output: bool
    json_schema_output: bool
    thinking: bool
    tool_calling: bool
    strict_tool_calling: bool
    streaming: bool
    output_token_parameter: str
    usage_fields: tuple[str, ...]
    finish_reasons: tuple[str, ...]
    supported_parameters: tuple[str, ...]
    unsupported_parameters: tuple[str, ...]
    notes: tuple[str, ...]


PROVIDER_CAPABILITIES: dict[str, ProviderCapabilityProfile] = {
    "zhipu-bigmodel": ProviderCapabilityProfile(
        "zhipu-bigmodel", "glm-5.3-flash", "https://open.bigmodel.cn/api/paas/v4",
        "ZHIPUAI_API_KEY", True, True, True, True, False, True, "max_tokens",
        ("prompt_tokens", "completion_tokens", "total_tokens"),
        ("stop", "length", "tool_calls"),
        ("model", "messages", "temperature", "top_p", "thinking", "reasoning_effort", "response_format", "stream", "max_tokens"),
        ("provider-specific unknown fields",),
        ("ordinary model API; no automatic Coding Plan fallback",),
    ),
    "deepseek": ProviderCapabilityProfile(
        "deepseek", "deepseek-flash", "https://api.deepseek.com",
        "DEEPSEEK_API_KEY", True, False, True, True, False, True, "max_tokens",
        ("prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"),
        ("stop", "length", "tool_calls"),
        ("model", "messages", "thinking", "reasoning_effort", "response_format", "stream", "max_tokens"),
        ("temperature", "presence_penalty", "frequency_penalty"),
        ("thinking mode ignores temperature-like controls",),
    ),
}


def capability_profile(provider: ProviderName) -> ProviderCapabilityProfile:
    try:
        return PROVIDER_CAPABILITIES[provider]
    except KeyError as exc:
        raise ValueError(f"unsupported provider: {provider}") from exc


def classify_provider_error(*, status: int | None = None, finish_reason: str | None = None, code: str | None = None, outcome_unknown: bool = False) -> ProviderErrorClass:
    if outcome_unknown or code in {"outcome_unknown", "timeout_or_network"}:
        return "timeout_or_network"
    if finish_reason in {"length", "max_tokens"} or code in {"writer_content_truncated", "planner_content_truncated", "content_truncated"}:
        return "content_truncated"
    if status in {401}:
        return "authentication"
    if status in {402}:
        return "quota_or_balance"
    if status in {403}:
        return "permission"
    if status == 404:
        return "model_not_found"
    if status == 422:
        return "unsupported_parameter"
    if status == 400:
        return "invalid_request"
    if status == 429:
        return "rate_limit"
    if status is not None and status >= 500:
        return "provider_overload"
    if code in {"provider_response_invalid", "writer_json_invalid", "planner_json_invalid"}:
        return "malformed_output"
    if code:
        return "provider_contract_failure"
    return "unknown"


def retryable(error_class: ProviderErrorClass) -> bool:
    return error_class in {"rate_limit", "provider_overload", "timeout_or_network"}


__all__ = ["ProviderCapabilityProfile", "ProviderErrorClass", "capability_profile", "classify_provider_error", "retryable"]
