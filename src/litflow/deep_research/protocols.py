"""Minimal provider/tool/clock protocols used by the fake runtime only."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .budgets import TokenUsage


class Clock(Protocol):
    def monotonic(self) -> float: ...


class Sleeper(Protocol):
    async def sleep(self, seconds: float) -> None: ...


@dataclass(frozen=True)
class ProviderResponse:
    status: str
    content: str = ""
    usage: TokenUsage = TokenUsage()


@dataclass(frozen=True)
class ToolResponse:
    status: str
    content: str = ""
    usage: TokenUsage = TokenUsage()


class Provider(Protocol):
    async def call(self, *, operation_id: str, attempt_id: str, request: Any, timeout_s: float | None = None) -> ProviderResponse: ...


class Tool(Protocol):
    name: str
    read_only: bool
    idempotent: bool
    side_effecting: bool

    async def call(self, *, operation_id: str, attempt_id: str, request: Any, timeout_s: float | None = None) -> ToolResponse: ...
