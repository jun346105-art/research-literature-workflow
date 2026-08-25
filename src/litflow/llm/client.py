from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    def complete_json(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class LLMCompletion:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class LLMToolCompletion(LLMCompletion):
    tool_calls: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class OpenAICompatibleClient:
    base_url: str
    api_key: str
    model: str
    thinking_mode: str | None = None

    @classmethod
    def from_env(cls, *, thinking_mode: str | None = None) -> OpenAICompatibleClient:
        base_url = os.environ.get("LLM_BASE_URL")
        api_key = os.environ.get("LLM_API_KEY")
        model = os.environ.get("LLM_MODEL")
        missing = [name for name, value in [("LLM_BASE_URL", base_url), ("LLM_API_KEY", api_key), ("LLM_MODEL", model)] if not value]
        if missing:
            raise LLMError(f"Missing LLM environment variables: {', '.join(missing)}")
        if thinking_mode not in (None, "enabled", "disabled"):
            raise LLMError("thinking_mode must be enabled or disabled")
        return cls(base_url=base_url.rstrip("/"), api_key=api_key, model=model, thinking_mode=thinking_mode)

    def complete_json(self, prompt: str) -> str:
        return self.complete_json_with_usage(prompt).content

    def complete_json_with_usage(
        self,
        prompt: str,
        *,
        temperature: float = 0,
        max_output_tokens: int | None = None,
    ) -> LLMCompletion:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        if max_output_tokens is not None:
            payload["max_tokens"] = max_output_tokens
        if self.thinking_mode is not None:
            payload["thinking"] = {"type": self.thinking_mode}
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise LLMError(f"LLM API HTTP {exc.code}") from exc
        except URLError as exc:
            raise LLMError("LLM API unavailable") from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM API response did not contain choices[0].message.content") from exc
        usage = data.get("usage") if isinstance(data, dict) else None
        return LLMCompletion(
            content=content,
            input_tokens=_usage_int(usage, "prompt_tokens"),
            output_tokens=_usage_int(usage, "completion_tokens"),
            total_tokens=_usage_int(usage, "total_tokens"),
        )

    def complete_tools_with_usage(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        temperature: float = 0,
        max_output_tokens: int | None = None,
    ) -> LLMToolCompletion:
        """Call the provider's OpenAI-compatible native function-tool interface."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": temperature,
        }
        if max_output_tokens is not None:
            payload["max_tokens"] = max_output_tokens
        if self.thinking_mode is not None:
            payload["thinking"] = {"type": self.thinking_mode}
        data = self._post(payload)
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM API response did not contain choices[0].message") from exc
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls")
        if tool_calls is not None and not isinstance(tool_calls, list):
            raise LLMError("LLM API tool_calls must be a list")
        usage = data.get("usage") if isinstance(data, dict) else None
        return LLMToolCompletion(
            content=content,
            tool_calls=tool_calls,
            input_tokens=_usage_int(usage, "prompt_tokens"),
            output_tokens=_usage_int(usage, "completion_tokens"),
            total_tokens=_usage_int(usage, "total_tokens"),
        )

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise LLMError(f"LLM API HTTP {exc.code}") from exc
        except URLError as exc:
            raise LLMError("LLM API unavailable") from exc
        if not isinstance(data, dict):
            raise LLMError("LLM API response must be an object")
        return data


def _usage_int(usage: object, key: str) -> int | None:
    value = usage.get(key) if isinstance(usage, dict) else None
    return value if isinstance(value, int) else None
