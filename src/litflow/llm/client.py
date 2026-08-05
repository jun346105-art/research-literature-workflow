from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol
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
class OpenAICompatibleClient:
    base_url: str
    api_key: str
    model: str

    @classmethod
    def from_env(cls) -> OpenAICompatibleClient:
        base_url = os.environ.get("LLM_BASE_URL")
        api_key = os.environ.get("LLM_API_KEY")
        model = os.environ.get("LLM_MODEL")
        missing = [name for name, value in [("LLM_BASE_URL", base_url), ("LLM_API_KEY", api_key), ("LLM_MODEL", model)] if not value]
        if missing:
            raise LLMError(f"Missing LLM environment variables: {', '.join(missing)}")
        return cls(base_url=base_url.rstrip("/"), api_key=api_key, model=model)

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


def _usage_int(usage: object, key: str) -> int | None:
    value = usage.get(key) if isinstance(usage, dict) else None
    return value if isinstance(value, int) else None
