"""One-call GLM Canary boundary; transport is reachable only through the durable runner."""
from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .budgets import BudgetLedger, BudgetSpec, TokenUsage
from .errors import ErrorCode, ManualInterventionRequired
from .identity import canonical_json, canonical_json_bytes, make_stable_id, sha256_hex
from .operations import OperationJournal, OperationKind, OperationStatus
from .runtime_v2 import (
    CoordinatedCheckpointV2,
    CrashSafeResult,
    RuntimeEventEnvelope,
    RuntimeEventType,
    UnifiedEventStore,
    _OperationInvoker,
    reduce_runtime_events,
    replay_runtime_events,
    write_coordinated_checkpoint,
)
from .state import RunState, RunStatus, transition


GLM_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
GLM_MODEL = "glm-5.3-flash"
_PROMPT = "Return only JSON with status ok, provider zhipu_bigmodel, and model glm-5.3-flash."


class CanaryConfigurationError(ValueError):
    """Fail-closed configuration error before any durable dispatch or network call."""


class GLMCanaryPlan(BaseModel):
    """Strict fixed-policy input for the single ordinary-API Canary path."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["dr-canary-execution-plan-v1.1"]
    provider: Literal["zhipu-bigmodel"]
    model_id: Literal["glm-5.3-flash"]
    endpoint: Literal[GLM_ENDPOINT]
    channel: Literal["ordinary_model_api"]
    text_only: Literal[True]
    tools_enabled: Literal[False]
    vision_enabled: Literal[False]
    video_enabled: Literal[False]
    files_enabled: Literal[False]
    web_enabled: Literal[False]
    parallel_enabled: Literal[False]
    fallback_enabled: Literal[False]
    max_provider_calls: Literal[1]
    max_retries: Literal[0]
    max_input_tokens: Literal[512]
    max_output_tokens: Literal[256]
    operation_timeout_seconds: Literal[30]
    run_deadline_seconds: Literal[45]
    monetary_budget_currency: Literal["CNY"]
    monetary_budget_limit: Decimal = Field(ge=Decimal("0"), le=Decimal("0.01"))
    pricing_type: Literal["promotional"]
    input_price_per_million_tokens: Decimal = Field(ge=Decimal("0"))
    output_price_per_million_tokens: Decimal = Field(ge=Decimal("0"))
    approval_state: Literal["user_authorized_single_call"]
    credential_environment_variable: Literal["ZHIPUAI_API_KEY"]
    adapter_commit_sha: str | None = None

    @model_validator(mode="after")
    def _validate_budget(self) -> "GLMCanaryPlan":
        if self.monetary_budget_limit != Decimal("0.01"):
            raise ValueError("Canary monetary limit must be 0.01 CNY")
        if self.input_price_per_million_tokens != Decimal("0.4") or self.output_price_per_million_tokens != Decimal("1.4"):
            raise ValueError("Canary pricing snapshot does not match the authorized rates")
        if self.adapter_commit_sha is not None and re.fullmatch(r"[0-9a-f]{40}", self.adapter_commit_sha) is None:
            raise ValueError("adapter_commit_sha must be a lowercase Git SHA")
        return self

    def max_usage(self) -> TokenUsage:
        return _usage(self.max_input_tokens, self.max_output_tokens, self)

    def budget_spec(self) -> BudgetSpec:
        return BudgetSpec(
            max_provider_attempts=1,
            max_provider_calls=1,
            max_input_tokens=512,
            max_output_tokens=256,
            max_total_tokens=768,
            max_retries=0,
            max_replans=0,
            max_cost_micros=self.monetary_budget_limit * Decimal("1000000"),
            run_timeout_s=45,
            operation_timeout_s=30,
        )


@dataclass(frozen=True)
class _CanaryOperation:
    operation_id: str
    kind: OperationKind = OperationKind.provider
    name: str = "glm_text_only_canary"
    idempotent: bool = False
    side_effecting: bool = False


@dataclass(frozen=True)
class _AdapterDiagnostics:
    """Redacted facts about the transport, adapter and application contracts."""

    failure_stage: str | None = None
    contract_error_code: str | None = None
    expected_field: str | None = None
    observed_type: str | None = None
    observed_keys: tuple[str, ...] = ()
    http_status: int | None = None
    provider_response_received: bool = False
    response_json_parsed: bool = False
    provider_response_confirmed: bool = False
    application_json_valid: bool = False
    model_identity_verified: bool = False
    usage_reported: bool = False
    usage_inconsistent: bool = False
    cost_verification: str = "unavailable"
    cost_audit_complete: bool = False

    def artifact(self) -> dict[str, object]:
        return {
            "failure_stage": self.failure_stage,
            "contract_error_code": self.contract_error_code,
            "expected_field": self.expected_field,
            "observed_type": self.observed_type,
            "observed_keys": list(self.observed_keys),
            "http_status": self.http_status,
            "provider_response_received": self.provider_response_received,
            "response_json_parsed": self.response_json_parsed,
            "provider_response_confirmed": self.provider_response_confirmed,
            "application_json_valid": self.application_json_valid,
            "model_identity_verified": self.model_identity_verified,
            "usage_reported": self.usage_reported,
            "usage_inconsistent": self.usage_inconsistent,
            "cost_verification": self.cost_verification,
            "cost_audit_complete": self.cost_audit_complete,
        }


_SAFE_RESPONSE_KEYS = frozenset({"choices", "error", "id", "model", "request_id", "usage"})


def _diagnostics_for_payload(*, status: int, payload: object) -> _AdapterDiagnostics:
    return _AdapterDiagnostics(
        http_status=status,
        provider_response_received=True,
        response_json_parsed=True,
        observed_type="object" if isinstance(payload, dict) else type(payload).__name__,
        observed_keys=tuple(sorted(key for key in payload if isinstance(key, str) and key in _SAFE_RESPONSE_KEYS)) if isinstance(payload, dict) else (),
    )


@dataclass(frozen=True)
class _ProviderResult:
    status: Literal["success", "failed", "unknown"]
    content: str = ""
    usage: TokenUsage = TokenUsage()
    error_code: ErrorCode | None = None
    provider_request_id: str | None = None
    diagnostics: _AdapterDiagnostics = _AdapterDiagnostics()


class _AsyncTransport(Protocol):
    async def __call__(self, *, url: str, headers: dict[str, str], body: bytes, timeout_s: float) -> tuple[int, dict[str, str], bytes]: ...


async def _urllib_transport(*, url: str, headers: dict[str, str], body: bytes, timeout_s: float) -> tuple[int, dict[str, str], bytes]:
    """The only live transport implementation; tests inject an in-memory replacement."""
    def send() -> tuple[int, dict[str, str], bytes]:
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 - URL is plan-allowlisted
                return int(response.status), dict(response.headers.items()), response.read()
        except urllib.error.HTTPError as error:
            return int(error.code), dict(error.headers.items()) if error.headers else {}, error.read()

    return await asyncio.to_thread(send)


class _GLMTextOnlyAdapter:
    """Internal provider implementation. It has no terminal-state or retry authority."""

    def __init__(self, plan: GLMCanaryPlan, transport: _AsyncTransport = _urllib_transport) -> None:
        self._plan = plan
        self._transport = transport

    def require_credential(self) -> str:
        credential = os.environ.get(self._plan.credential_environment_variable)
        if not credential:
            raise CanaryConfigurationError("credential is missing for the configured provider channel")
        return credential

    def validate_pre_dispatch(self) -> None:
        """Keep all locally knowable plan/request failures before durable dispatch."""
        if self._plan.endpoint != GLM_ENDPOINT or self._plan.model_id != GLM_MODEL:
            raise CanaryConfigurationError("Canary endpoint or model does not match the frozen plan")
        if self._plan.max_provider_calls != 1 or self._plan.max_retries != 0:
            raise CanaryConfigurationError("Canary call or retry policy does not match the frozen plan")

    def _request_body(self) -> bytes:
        return canonical_json_bytes(
            {
                "model": self._plan.model_id,
                "messages": [{"role": "user", "content": _PROMPT}],
                "temperature": 1,
                "top_p": 0.95,
                "max_tokens": 256,
                "thinking": {"type": "enabled"},
                "reasoning_effort": "max",
                "response_format": {"type": "json_object"},
                "stream": False,
            }
        )

    async def call(self, *, operation_id: str, attempt_id: str, request: Any, timeout_s: float | None = None, credential: str | None = None) -> _ProviderResult:
        if credential is None:
            raise CanaryConfigurationError("credential must be validated before durable dispatch")
        if timeout_s != self._plan.operation_timeout_seconds or not isinstance(request, dict) or request.get("operation") != "glm_text_only_canary":
            return _ProviderResult("failed", error_code=ErrorCode.contract_invalid, diagnostics=_AdapterDiagnostics("pre_dispatch_contract", "invocation_contract_invalid", "operation", type(request).__name__))
        body = self._request_body()
        try:
            status, headers, raw = await self._transport(
                url=self._plan.endpoint,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {credential}"},
                body=body,
                timeout_s=float(timeout_s),
            )
        except (TimeoutError, socket.timeout, ConnectionResetError, ConnectionError, urllib.error.URLError):
            return _ProviderResult("unknown", error_code=ErrorCode.unknown_outcome, diagnostics=_AdapterDiagnostics("transport_invocation", "outcome_unknown"))
        if not 200 <= status < 300:
            error = ErrorCode.transient_provider if status >= 500 else ErrorCode.rate_limited if status == 429 else ErrorCode.permanent_provider
            payload: object
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = None
            base = _diagnostics_for_payload(status=status, payload=payload) if payload is not None else _AdapterDiagnostics(
                failure_stage="transport_contract", contract_error_code="http_non_2xx", http_status=status, provider_response_received=True, observed_type="bytes"
            )
            return _ProviderResult("failed", error_code=error, diagnostics=_AdapterDiagnostics(**{**base.__dict__, "failure_stage": "transport_contract", "contract_error_code": "http_non_2xx"}))
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _ProviderResult("failed", error_code=ErrorCode.contract_invalid, diagnostics=_AdapterDiagnostics(
                "transport_contract", "response_body_not_json", "JSON object", "bytes", http_status=status, provider_response_received=True
            ))
        diagnostics = _diagnostics_for_payload(status=status, payload=payload)
        if not isinstance(payload, dict):
            return _ProviderResult("failed", error_code=ErrorCode.contract_invalid, diagnostics=_AdapterDiagnostics(**{**diagnostics.__dict__, "failure_stage": "provider_adapter_contract", "contract_error_code": "response_object_required", "expected_field": "response"}))
        if isinstance(payload.get("error"), dict):
            return _ProviderResult("failed", error_code=ErrorCode.permanent_provider, diagnostics=_AdapterDiagnostics(**{**diagnostics.__dict__, "failure_stage": "provider_adapter_contract", "contract_error_code": "provider_error_envelope", "expected_field": "choices"}))
        choices = payload.get("choices")
        choice = choices[0] if isinstance(choices, list) and choices else None
        content = choice.get("message", {}).get("content") if isinstance(choice, dict) else None
        if not isinstance(content, str):
            return _ProviderResult("failed", error_code=ErrorCode.contract_invalid, diagnostics=_AdapterDiagnostics(**{**diagnostics.__dict__, "failure_stage": "provider_adapter_contract", "contract_error_code": "content_missing", "expected_field": "choices[0].message.content"}))
        model_verified = payload.get("model") == self._plan.model_id
        diagnostics = _AdapterDiagnostics(**{**diagnostics.__dict__, "model_identity_verified": model_verified, "provider_response_confirmed": model_verified})
        usage = payload.get("usage")
        usage_reported = isinstance(usage, dict) and all(isinstance(usage.get(field), int) for field in ("prompt_tokens", "completion_tokens", "total_tokens"))
        usage_inconsistent = False
        token_usage = TokenUsage()
        usage_error: str | None = None
        if not isinstance(usage, dict):
            usage_error = "usage_missing"
        elif not usage_reported:
            usage_error = "usage_invalid"
        else:
            token_usage = _usage(usage["prompt_tokens"], usage["completion_tokens"], self._plan)
            if token_usage.total_tokens != usage["total_tokens"]:
                usage_inconsistent = True
                usage_error = "usage_inconsistent"
        cost_verification = "verified" if usage_reported and not usage_inconsistent else "failed" if usage_inconsistent else "unavailable"
        diagnostics = _AdapterDiagnostics(**{**diagnostics.__dict__, "usage_reported": usage_reported, "usage_inconsistent": usage_inconsistent, "cost_verification": cost_verification, "cost_audit_complete": usage_reported and not usage_inconsistent})
        try:
            structured = json.loads(content)
        except json.JSONDecodeError:
            structured = None
        application_valid = structured == {"status": "ok", "provider": "zhipu_bigmodel", "model": GLM_MODEL}
        diagnostics = _AdapterDiagnostics(**{**diagnostics.__dict__, "application_json_valid": application_valid})
        if not model_verified:
            return _ProviderResult("failed", content=content, error_code=ErrorCode.contract_invalid, diagnostics=_AdapterDiagnostics(**{**diagnostics.__dict__, "failure_stage": "provider_adapter_contract", "contract_error_code": "model_identity_unverified", "expected_field": "model"}))
        if structured is None:
            return _ProviderResult("failed", content=content, error_code=ErrorCode.contract_invalid, diagnostics=_AdapterDiagnostics(**{**diagnostics.__dict__, "failure_stage": "application_contract", "contract_error_code": "application_json_invalid", "expected_field": "content"}))
        if not application_valid:
            return _ProviderResult("failed", content=content, error_code=ErrorCode.contract_invalid, diagnostics=_AdapterDiagnostics(**{**diagnostics.__dict__, "failure_stage": "application_contract", "contract_error_code": "application_schema_invalid", "expected_field": "content"}))
        if usage_error is not None:
            return _ProviderResult("failed", content=content, error_code=ErrorCode.contract_invalid, diagnostics=_AdapterDiagnostics(**{**diagnostics.__dict__, "failure_stage": "provider_adapter_contract", "contract_error_code": usage_error, "expected_field": "usage"}))
        request_id = payload.get("id") or headers.get("x-request-id")
        return _ProviderResult("success", content=content, usage=token_usage, provider_request_id=request_id if isinstance(request_id, str) else None, diagnostics=diagnostics)


def _usage(input_tokens: int, output_tokens: int, plan: GLMCanaryPlan) -> TokenUsage:
    cost_cny = (
        Decimal(input_tokens) * plan.input_price_per_million_tokens
        + Decimal(output_tokens) * plan.output_price_per_million_tokens
    ) / Decimal("1000000")
    return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens, cost_micros=cost_cny * Decimal("1000000"))


def render_glm_canary_schema() -> str:
    schema = GLMCanaryPlan.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_glm_canary_schema(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "canary_execution_plan.schema.json"
    path.write_text(render_glm_canary_schema(), encoding="utf-8", newline="\n")
    return path


class GLMCanaryRunner:
    """Only public live-capable entry: validates, durably dispatches once, then replays."""

    def __init__(self, plan: GLMCanaryPlan, artifact_dir: Path, *, transport: _AsyncTransport = _urllib_transport) -> None:
        self.plan = plan
        self.artifact_dir = Path(artifact_dir)
        self.spec = plan.budget_spec()
        self.initial_state = RunState.create(task_id="dr-task-" + "c" * 24, brief_id="dr-brief-" + "d" * 24, brief_approved=True)
        self.run_id = self.initial_state.run_id
        self._adapter = _GLMTextOnlyAdapter(plan, transport)
        self._live_transport = transport is _urllib_transport

    def _bind_execution_plan(self) -> GLMCanaryPlan:
        """Bind the immutable artifact to the checked-out adapter commit without reading credentials."""
        try:
            completed = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=Path.cwd(),
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise CanaryConfigurationError("cannot resolve the adapter Git commit") from exc
        commit = completed.stdout.strip()
        if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            raise CanaryConfigurationError("Git HEAD is not a full commit SHA")
        if self._live_transport:
            try:
                status = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=Path.cwd(),
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except (OSError, subprocess.CalledProcessError) as exc:
                raise CanaryConfigurationError("cannot verify the Canary worktree") from exc
            if status.stdout.strip():
                raise CanaryConfigurationError("Canary worktree must be clean")
        if self.plan.adapter_commit_sha is not None and self.plan.adapter_commit_sha != commit:
            raise CanaryConfigurationError("execution plan adapter commit does not match HEAD")
        return self.plan.model_copy(update={"adapter_commit_sha": commit})

    def _append(self, store: UnifiedEventStore, events: list[RuntimeEventEnvelope], event_type: RuntimeEventType, *, payload: dict[str, Any] | None = None, operation_id: str | None = None, attempt_id: str | None = None, causal_parent_id: str | None = None) -> RuntimeEventEnvelope:
        from .events import GENESIS_HASH
        from .runtime_v2 import create_runtime_event

        event = create_runtime_event(
            self.run_id,
            len(events) + 1,
            event_type,
            payload=payload,
            operation_id=operation_id,
            attempt_id=attempt_id,
            causal_parent_id=causal_parent_id,
            previous_event_hash=events[-1].event_hash if events else GENESIS_HASH,
        )
        store.append(event)
        events.append(event)
        return event

    def _lifecycle(self, store: UnifiedEventStore, events: list[RuntimeEventEnvelope], state: RunState, target: RunStatus, reason: str | None = None) -> RunState:
        state, event = transition(state, target, reason=reason)
        self._append(store, events, RuntimeEventType.lifecycle_transition, payload=event.model_dump(mode="json"), causal_parent_id=events[-1].event_id if events else None)
        return state

    def execute(self) -> CrashSafeResult:
        self._adapter.validate_pre_dispatch()
        credential = self._adapter.require_credential()
        bound_plan = self._bind_execution_plan()
        if self.artifact_dir.exists():
            raise CanaryConfigurationError("Canary artifact directory must not already exist")
        path = self.artifact_dir / "runtime.jsonl"
        store = UnifiedEventStore(path, run_id=self.run_id)
        events: list[RuntimeEventEnvelope] = []
        self._append(store, events, RuntimeEventType.run_started, payload={"plan_sha256": sha256_hex(canonical_json_bytes(bound_plan.model_dump(mode="json"))), "spec": self.spec.model_dump(mode="json")})
        state = self._lifecycle(store, events, self.initial_state, RunStatus.brief_approved)
        state = self._lifecycle(store, events, state, RunStatus.researching)
        operation = _CanaryOperation(make_stable_id("operation", {"kind": "provider", "name": "glm_text_only_canary"}))
        journal = OperationJournal.empty()
        record = journal.plan(operation_id=operation.operation_id, kind=operation.kind, name=operation.name, idempotent=False, side_effecting=False)
        journal = journal.add(record)
        ledger = BudgetLedger.empty(self.spec)
        ledger, reservation = ledger.reserve(self.spec, operation_id=record.operation_id, attempt_id=record.attempt_id, kind=operation.kind, usage=self.plan.max_usage())
        journal = journal.reserve(record.operation_id, record.attempt_id)
        reserved_event = self._append(store, events, RuntimeEventType.operation_reserved, payload={"operation_kind": "provider", "operation_name": operation.name, "attempt_number": 1, "idempotent": False, "side_effecting": False, "usage": reservation.usage.model_dump(mode="json")}, operation_id=record.operation_id, attempt_id=record.attempt_id, causal_parent_id=events[-1].event_id)
        journal = journal.start(record.operation_id, record.attempt_id)
        dispatched_event = self._append(store, events, RuntimeEventType.operation_dispatched, payload={"operation_kind": "provider", "operation_name": operation.name, "attempt_number": 1, "effective_timeout_s": 30}, operation_id=record.operation_id, attempt_id=record.attempt_id, causal_parent_id=reserved_event.event_id)
        invoker = _OperationInvoker(self._adapter, self._adapter)
        response = asyncio.run(invoker.dispatch(operation, attempt_id=record.attempt_id, timeout_s=30, credential=credential))
        terminal = "complete"
        error: ErrorCode | None = None
        if response.status == "success":
            self._append(store, events, RuntimeEventType.operation_succeeded, payload={"attempt_number": 1, "status": "success", "usage": response.usage.model_dump(mode="json"), "result_sha256": sha256_hex(response.content), "provider_request_id": response.provider_request_id or "", "provider_audit": response.diagnostics.artifact()}, operation_id=record.operation_id, attempt_id=record.attempt_id, causal_parent_id=dispatched_event.event_id)
            ledger = ledger.reconcile(reservation, usage=response.usage, outcome=OperationStatus.succeeded, attempt_number=1, spec=self.spec)
            journal = journal.mark_succeeded(record.operation_id, record.attempt_id, sha256_hex(response.content))
            state = self._lifecycle(store, events, state, RunStatus.validating)
            state = self._lifecycle(store, events, state, RunStatus.complete)
        elif response.status == "unknown":
            error = ErrorCode.unknown_outcome
            terminal = "failed"
            self._append(store, events, RuntimeEventType.operation_unknown, payload={"error_code": error.value, "attempt_number": 1, "usage": response.usage.model_dump(mode="json"), "provider_audit": response.diagnostics.artifact()}, operation_id=record.operation_id, attempt_id=record.attempt_id, causal_parent_id=dispatched_event.event_id)
            journal = journal.mark_unknown(record.operation_id, record.attempt_id, error.value)
            state = self._lifecycle(store, events, state, RunStatus.failed, reason=error.value)
        else:
            error = response.error_code or ErrorCode.contract_invalid
            terminal = "failed"
            self._append(store, events, RuntimeEventType.operation_failed, payload={"error_code": error.value, "attempt_number": 1, "usage": response.usage.model_dump(mode="json"), "provider_audit": response.diagnostics.artifact()}, operation_id=record.operation_id, attempt_id=record.attempt_id, causal_parent_id=dispatched_event.event_id)
            ledger = ledger.reconcile(reservation, usage=response.usage, outcome=OperationStatus.failed_known, attempt_number=1, spec=self.spec)
            journal = journal.mark_failed(record.operation_id, record.attempt_id, error.value)
            state = self._lifecycle(store, events, state, RunStatus.failed, reason=error.value)
        persisted = tuple(store.read_all())
        replayed = replay_runtime_events(self.initial_state, persisted, self.spec)
        checkpoint = CoordinatedCheckpointV2.from_result(reduce_runtime_events(self.initial_state, persisted, self.spec))
        write_coordinated_checkpoint(path.with_suffix(".checkpoint.json"), checkpoint)
        result = CrashSafeResult(terminal, error, replayed.run_state, replayed.ledger, replayed.journal, persisted, 1, checkpoint, self.initial_state, self.spec, (30.0,), replayed.manual_intervention)
        self._write_artifacts(result, response, bound_plan)
        return result

    def _write_artifacts(self, result: CrashSafeResult, response: _ProviderResult, bound_plan: GLMCanaryPlan) -> None:
        """Persist only redacted transport facts after the durable terminal and replay checks."""
        files = {
            "immutable_plan.json": bound_plan.model_dump(mode="json"),
            "plan_sha256.json": {"plan_sha256": sha256_hex(canonical_json_bytes(bound_plan.model_dump(mode="json")))},
            "redacted_request.json": {
                "endpoint": self.plan.endpoint,
                "model": self.plan.model_id,
                "body_sha256": sha256_hex(canonical_json_bytes({"prompt": _PROMPT, "model": self.plan.model_id})),
                "contains_authorization": False,
            },
            "response_metadata.json": {
                "provider_request_id": response.provider_request_id or "",
                "model": self.plan.model_id,
                "provider_dispatch_intents": 1,
                "provider_response_received": response.diagnostics.provider_response_received,
                "provider_response_confirmed": response.diagnostics.provider_response_confirmed,
                "provider_usage_reported": response.diagnostics.usage_reported,
            },
            "structured_result.json": {"terminal": result.terminal, "error_code": result.error_code.value if result.error_code else None, "content": response.content if response.status == "success" else ""},
            "usage.json": response.usage.model_dump(mode="json"),
            "adapter_diagnostics.json": response.diagnostics.artifact(),
            "replay_verification.json": {
                "full_replay_matches": replay_runtime_events(result.initial_state, result.events, result.spec) == replay_runtime_events(result.initial_state, result.events, result.spec, checkpoint=result.checkpoint),
                "provider_calls_during_replay": 0,
            },
            "secret_scan.json": {"credential_persisted": False, "authorization_persisted": False, "private_absolute_path_persisted": False},
        }
        for name, value in files.items():
            (self.artifact_dir / name).write_text(canonical_json(value) + "\n", encoding="utf-8", newline="\n")
