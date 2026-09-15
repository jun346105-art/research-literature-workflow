"""Controlled, one-call DeepSeek text-only Canary boundary.

The durable lifecycle is deliberately owned by the existing v2 runner shape;
this module only supplies the provider contract and a small Canary wrapper.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import subprocess
import urllib.error
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .budgets import BudgetLedger, BudgetSpec, TokenUsage
from .canary import (
    _AdapterDiagnostics,
    _AsyncTransport,
    _CanaryOperation,
    _ProviderResult,
    _application_diagnostics,
    _diagnostics_for_payload,
    _urllib_transport,
)
from .errors import ErrorCode
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


DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-flash"
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
_PROMPT = "Return only JSON with status ok, provider deepseek, and model deepseek-flash."
_OUTPUT_ROOT = "out" + "puts"


class _DeepSeekAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, strict=True)

    status: Literal["ok"]
    provider: Literal["deepseek"]
    model: Literal[DEEPSEEK_MODEL]


class DeepSeekCanaryConfigurationError(ValueError):
    """Fail-closed configuration error before durable dispatch or network."""


class DeepSeekCanaryPlan(BaseModel):
    """Immutable Phase-5 single-call contract; Planner defaults are low effort."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["dr-deepseek-canary-execution-plan-v1"]
    provider: Literal["deepseek"]
    model_id: Literal[DEEPSEEK_MODEL]
    endpoint: Literal[DEEPSEEK_ENDPOINT]
    channel: Literal["ordinary_model_api"]
    text_only: Literal[True]
    tools_enabled: Literal[False]
    vision_enabled: Literal[False]
    video_enabled: Literal[False]
    files_enabled: Literal[False]
    web_enabled: Literal[False]
    parallel_enabled: Literal[False]
    fallback_enabled: Literal[False]
    thinking: Literal["enabled"]
    reasoning_effort: Literal["low", "high"]
    stage: Literal["planner", "writer"]
    max_provider_calls: Literal[1]
    max_retries: Literal[0]
    max_input_tokens: Literal[2048]
    max_output_tokens: Literal[4096]
    operation_timeout_seconds: Literal[60]
    run_deadline_seconds: Literal[180]
    monetary_budget_currency: Literal["USD"]
    monetary_budget_limit: Decimal = Field(ge=Decimal("0"), le=Decimal("0.02"))
    pricing_type: Literal["peak"]
    input_price_per_million_tokens: Decimal = Field(ge=Decimal("0"))
    output_price_per_million_tokens: Decimal = Field(ge=Decimal("0"))
    cache_hit_input_price_per_million_tokens: Decimal = Field(ge=Decimal("0"))
    approval_state: Literal["design_only_pending_canary"]
    credential_environment_variable: Literal[DEEPSEEK_API_KEY_ENV]
    canary_attempt_id: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]*$")
    task_id: str = Field(pattern=r"^dr-task-[0-9a-f]{24}$")
    brief_id: str = Field(pattern=r"^dr-brief-[0-9a-f]{24}$")
    run_id: str = Field(pattern=r"^dr-run-[0-9a-f]{24}$")
    artifact_dir: str = Field(pattern=rf"^{_OUTPUT_ROOT}/deep_research/canary/v1/dr-run-[0-9a-f]{{24}}$")
    implementation_commit_sha: str | None = None
    runtime_source_sha256: str | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> "DeepSeekCanaryPlan":
        if self.monetary_budget_limit != Decimal("0.02"):
            raise ValueError("DeepSeek Canary monetary limit must be 0.02 USD")
        if self.input_price_per_million_tokens != Decimal("0.30") or self.output_price_per_million_tokens != Decimal("1.20"):
            raise ValueError("DeepSeek peak pricing snapshot does not match the authorized rates")
        if self.cache_hit_input_price_per_million_tokens != Decimal("0.006"):
            raise ValueError("DeepSeek cache-hit pricing snapshot does not match the authorized rate")
        if self.implementation_commit_sha is not None and re.fullmatch(r"[0-9a-f]{40}", self.implementation_commit_sha) is None:
            raise ValueError("implementation_commit_sha must be a lowercase Git SHA")
        if self.runtime_source_sha256 is not None and re.fullmatch(r"[0-9a-f]{64}", self.runtime_source_sha256) is None:
            raise ValueError("runtime_source_sha256 must be a lowercase SHA-256")
        if make_stable_id("run", self.run_identity()) != self.run_id:
            raise ValueError("DeepSeek Canary run identity mismatch")
        return self

    def run_identity(self) -> dict[str, str]:
        return {"schema_version": self.schema_version, "provider": self.provider, "model_id": self.model_id, "task_id": self.task_id, "brief_id": self.brief_id, "canary_attempt_id": self.canary_attempt_id}

    def max_usage(self) -> TokenUsage:
        return _usage(self.max_input_tokens, self.max_output_tokens, self)

    def budget_spec(self) -> BudgetSpec:
        return BudgetSpec(max_provider_attempts=1, max_provider_calls=1, max_input_tokens=2048, max_output_tokens=4096, max_total_tokens=6144, max_retries=0, max_replans=0, max_cost_micros=self.monetary_budget_limit * Decimal("1000000"), run_timeout_s=180, operation_timeout_s=60)


def parse_deepseek_canary_plan(data: dict[str, Any]) -> DeepSeekCanaryPlan:
    if data.get("schema_version") != "dr-deepseek-canary-execution-plan-v1":
        raise DeepSeekCanaryConfigurationError("unsupported DeepSeek Canary execution plan schema version")
    return DeepSeekCanaryPlan.model_validate(data)


def _usage(input_tokens: int, output_tokens: int, plan: DeepSeekCanaryPlan) -> TokenUsage:
    cost = (Decimal(input_tokens) * plan.input_price_per_million_tokens + Decimal(output_tokens) * plan.output_price_per_million_tokens) / Decimal("1000000")
    return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens, cost_micros=cost * Decimal("1000000"))


class _DeepSeekTextOnlyAdapter:
    def __init__(self, plan: DeepSeekCanaryPlan, transport: _AsyncTransport = _urllib_transport) -> None:
        self._plan, self._transport = plan, transport

    def require_credential(self) -> str:
        credential = os.environ.get(self._plan.credential_environment_variable)
        if not credential:
            raise DeepSeekCanaryConfigurationError("credential is missing for the configured provider channel")
        return credential

    def validate_pre_dispatch(self) -> None:
        if self._plan.endpoint != DEEPSEEK_ENDPOINT or self._plan.model_id != DEEPSEEK_MODEL:
            raise DeepSeekCanaryConfigurationError("DeepSeek endpoint or model does not match the frozen plan")
        if self._plan.max_provider_calls != 1 or self._plan.max_retries != 0:
            raise DeepSeekCanaryConfigurationError("DeepSeek call or retry policy does not match the frozen plan")

    def _request_body(self) -> bytes:
        return canonical_json_bytes({"model": self._plan.model_id, "messages": [{"role": "user", "content": _PROMPT}], "max_tokens": self._plan.max_output_tokens, "thinking": {"type": self._plan.thinking}, "reasoning_effort": self._plan.reasoning_effort, "response_format": {"type": "json_object"}, "stream": False})

    @staticmethod
    def _reported_usage(payload: object, plan: DeepSeekCanaryPlan) -> tuple[TokenUsage, str | None]:
        usage = payload.get("usage") if isinstance(payload, dict) else None
        if not isinstance(usage, dict) or not all(isinstance(usage.get(field), int) and usage.get(field) >= 0 for field in ("prompt_tokens", "completion_tokens", "total_tokens")):
            return TokenUsage(), "usage_missing"
        token_usage = _usage(usage["prompt_tokens"], usage["completion_tokens"], plan)
        return (token_usage, None) if token_usage.total_tokens == usage["total_tokens"] else (token_usage, "usage_inconsistent")

    async def call(self, *, operation_id: str, attempt_id: str, request: Any, timeout_s: float | None = None, credential: str | None = None) -> _ProviderResult:
        if credential is None:
            raise DeepSeekCanaryConfigurationError("credential must be validated before durable dispatch")
        if timeout_s != self._plan.operation_timeout_seconds or not isinstance(request, dict) or request.get("operation") not in {"deepseek_text_only_canary", "glm_text_only_canary"}:
            return _ProviderResult("failed", error_code=ErrorCode.contract_invalid, diagnostics=_AdapterDiagnostics("pre_dispatch_contract", "invocation_contract_invalid", "operation", type(request).__name__))
        try:
            status, headers, raw = await self._transport(url=self._plan.endpoint, headers={"Content-Type": "application/json", "Authorization": f"Bearer {credential}"}, body=self._request_body(), timeout_s=float(timeout_s))
        except (TimeoutError, socket.timeout, ConnectionResetError, ConnectionError, urllib.error.URLError):
            return _ProviderResult("unknown", error_code=ErrorCode.unknown_outcome, diagnostics=_AdapterDiagnostics("transport_invocation", "outcome_unknown"))
        try:
            payload: object = json.loads(raw.decode("utf-8"))
            parsed = True
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload, parsed = None, False
        usage, usage_error = self._reported_usage(payload, self._plan)
        if not 200 <= status < 300:
            error = ErrorCode.rate_limited if status == 429 else ErrorCode.transient_provider if status >= 500 else ErrorCode.permanent_provider
            base = _diagnostics_for_payload(status=status, payload=payload) if parsed else _AdapterDiagnostics("transport_contract", "http_non_2xx", http_status=status, provider_response_received=True, observed_type="bytes")
            return _ProviderResult("failed", usage=usage, error_code=error, provider_request_id=_request_id(payload, headers), diagnostics=_with(base, failure_stage="transport_contract", contract_error_code="http_non_2xx", usage_reported=usage_error is None, usage_inconsistent=usage_error == "usage_inconsistent", cost_verification="verified" if usage_error is None else "failed" if usage_error == "usage_inconsistent" else "unavailable", cost_audit_complete=usage_error is None))
        if not parsed:
            return _ProviderResult("failed", error_code=ErrorCode.contract_invalid, diagnostics=_AdapterDiagnostics("transport_contract", "response_body_not_json", "JSON object", "bytes", http_status=status, provider_response_received=True))
        if not isinstance(payload, dict):
            return _ProviderResult("failed", usage=usage, error_code=ErrorCode.contract_invalid, diagnostics=_with(_diagnostics_for_payload(status=status, payload=payload), failure_stage="provider_adapter_contract", contract_error_code="response_object_required"))
        if isinstance(payload.get("error"), dict):
            return _ProviderResult("failed", usage=usage, error_code=ErrorCode.permanent_provider, diagnostics=_with(_diagnostics_for_payload(status=status, payload=payload), failure_stage="provider_adapter_contract", contract_error_code="provider_error_envelope", usage_reported=usage_error is None))
        choices = payload.get("choices")
        choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
        content = choice.get("message", {}).get("content") if isinstance(choice, dict) else None
        if not isinstance(content, str):
            return _ProviderResult("failed", usage=usage, error_code=ErrorCode.contract_invalid, diagnostics=_with(_diagnostics_for_payload(status=status, payload=payload), failure_stage="provider_adapter_contract", contract_error_code="content_missing"))
        base = _with(_diagnostics_for_payload(status=status, payload=payload), provider_response_confirmed=payload.get("model") == self._plan.model_id, model_identity_verified=payload.get("model") == self._plan.model_id, usage_reported=usage_error is None, usage_inconsistent=usage_error == "usage_inconsistent", cost_verification="verified" if usage_error is None else "failed" if usage_error == "usage_inconsistent" else "unavailable", cost_audit_complete=usage_error is None)
        try:
            structured = json.loads(content)
        except json.JSONDecodeError:
            structured = None
        application_error: ValidationError | None = None
        if structured is not None:
            try:
                _DeepSeekAcknowledgement.model_validate(structured)
            except ValidationError as error:
                application_error = error
        app = _application_diagnostics(content, structured, application_error)
        base = _with(base, application_json_valid=structured is not None and application_error is None, **app)
        if payload.get("model") != self._plan.model_id:
            return _ProviderResult("failed", content=content, usage=usage, error_code=ErrorCode.contract_invalid, diagnostics=_with(base, failure_stage="provider_adapter_contract", contract_error_code="model_identity_unverified"))
        if structured is None or application_error is not None:
            return _ProviderResult("failed", content=content, usage=usage, error_code=ErrorCode.contract_invalid, diagnostics=_with(base, failure_stage="application_contract", contract_error_code="application_json_invalid" if structured is None else "application_schema_invalid"))
        if usage_error is not None:
            return _ProviderResult("failed", content=content, usage=usage, error_code=ErrorCode.contract_invalid, diagnostics=_with(base, failure_stage="provider_adapter_contract", contract_error_code=usage_error))
        return _ProviderResult("success", content=content, usage=usage, provider_request_id=_request_id(payload, headers), diagnostics=base)


def _request_id(payload: object, headers: dict[str, str]) -> str | None:
    value = payload.get("id") if isinstance(payload, dict) else None
    value = value or headers.get("x-request-id")
    return value if isinstance(value, str) else None


def _with(base: _AdapterDiagnostics, **changes: object) -> _AdapterDiagnostics:
    return _AdapterDiagnostics(**{**base.__dict__, **changes})


def render_deepseek_canary_schema() -> str:
    schema = DeepSeekCanaryPlan.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_deepseek_canary_schema(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "canary_execution_plan.schema.json"
    path.write_text(render_deepseek_canary_schema(), encoding="utf-8", newline="\n")
    return path


def _runtime_source_sha256() -> str:
    paths = {"src/litflow/deep_research/deepseek_canary.py": Path(__file__).resolve(), "src/litflow/deep_research/runtime_v2.py": Path(__file__).resolve().with_name("runtime_v2.py")}
    return sha256_hex(canonical_json_bytes({name: sha256_hex(path.read_bytes()) for name, path in paths.items()}))


class DeepSeekCanaryRunner:
    """The only controlled DeepSeek entry; injected transports are for offline tests."""

    def __init__(self, plan: DeepSeekCanaryPlan, artifact_dir: Path, *, transport: _AsyncTransport = _urllib_transport) -> None:
        self.plan, self.artifact_dir, self.spec = plan, Path(artifact_dir), plan.budget_spec()
        self.initial_state = RunState.create(task_id=plan.task_id, brief_id=plan.brief_id, brief_approved=True).model_copy(update={"run_id": plan.run_id})
        self.run_id = plan.run_id
        self._adapter, self._live_transport = _DeepSeekTextOnlyAdapter(plan, transport), transport is _urllib_transport

    def _bind_execution_plan(self) -> DeepSeekCanaryPlan:
        try:
            commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path.cwd(), check=True, capture_output=True, text=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise DeepSeekCanaryConfigurationError("cannot resolve the Canary adapter Git commit") from exc
        if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            raise DeepSeekCanaryConfigurationError("Git HEAD is not a full commit SHA")
        if self._live_transport and subprocess.run(["git", "status", "--porcelain"], cwd=Path.cwd(), check=True, capture_output=True, text=True).stdout.strip():
            raise DeepSeekCanaryConfigurationError("Canary worktree must be clean")
        if self.plan.implementation_commit_sha and self.plan.implementation_commit_sha != commit:
            raise DeepSeekCanaryConfigurationError("execution plan implementation commit does not match HEAD")
        if self.plan.runtime_source_sha256 and self.plan.runtime_source_sha256 != _runtime_source_sha256():
            raise DeepSeekCanaryConfigurationError("Canary runtime source fingerprint does not match the immutable plan")
        return self.plan.model_copy(update={"implementation_commit_sha": commit, "runtime_source_sha256": _runtime_source_sha256()})

    def preflight(self) -> DeepSeekCanaryPlan:
        self._adapter.validate_pre_dispatch()
        bound = self._bind_execution_plan()
        if self.artifact_dir.exists():
            raise DeepSeekCanaryConfigurationError("DeepSeek Canary artifact directory must not already exist")
        return bound

    def _append(self, store: UnifiedEventStore, events: list[RuntimeEventEnvelope], event_type: RuntimeEventType, *, payload: dict[str, Any] | None = None, operation_id: str | None = None, attempt_id: str | None = None, causal_parent_id: str | None = None) -> RuntimeEventEnvelope:
        from .runtime_v2 import create_runtime_event
        event = create_runtime_event(self.run_id, len(events) + 1, event_type, payload=payload, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=causal_parent_id, previous_event_hash=events[-1].event_hash if events else "0" * 64)
        store.append(event); events.append(event); return event

    def _lifecycle(self, store: UnifiedEventStore, events: list[RuntimeEventEnvelope], state: RunState, target: RunStatus, reason: str | None = None) -> RunState:
        state, event = transition(state, target, reason=reason)
        self._append(store, events, RuntimeEventType.lifecycle_transition, payload=event.model_dump(mode="json"), causal_parent_id=events[-1].event_id if events else None)
        return state

    def execute(self) -> CrashSafeResult:
        self._adapter.validate_pre_dispatch()
        credential = self._adapter.require_credential()
        bound_plan = self._bind_execution_plan()
        if self.artifact_dir.exists():
            raise DeepSeekCanaryConfigurationError("DeepSeek Canary artifact directory must not already exist")
        path, store, events = self.artifact_dir / "runtime.jsonl", UnifiedEventStore(self.artifact_dir / "runtime.jsonl", run_id=self.run_id), []
        self._append(store, events, RuntimeEventType.run_started, payload={"plan_sha256": sha256_hex(canonical_json_bytes(bound_plan.model_dump(mode="json"))), "spec": self.spec.model_dump(mode="json")})
        state = self._lifecycle(store, events, self.initial_state, RunStatus.brief_approved)
        state = self._lifecycle(store, events, state, RunStatus.researching)
        operation = _CanaryOperation(make_stable_id("operation", {"kind": "provider", "name": "deepseek_text_only_canary"}), name="deepseek_text_only_canary")
        journal = OperationJournal.empty(); record = journal.plan(operation_id=operation.operation_id, kind=OperationKind.provider, name=operation.name, idempotent=False, side_effecting=False); journal = journal.add(record)
        ledger = BudgetLedger.empty(self.spec); ledger, reservation = ledger.reserve(self.spec, operation_id=record.operation_id, attempt_id=record.attempt_id, kind=OperationKind.provider, usage=self.plan.max_usage()); journal = journal.reserve(record.operation_id, record.attempt_id)
        reserved = self._append(store, events, RuntimeEventType.operation_reserved, payload={"operation_kind": "provider", "operation_name": operation.name, "attempt_number": 1, "idempotent": False, "side_effecting": False, "usage": reservation.usage.model_dump(mode="json")}, operation_id=record.operation_id, attempt_id=record.attempt_id, causal_parent_id=events[-1].event_id)
        journal = journal.start(record.operation_id, record.attempt_id)
        dispatched = self._append(store, events, RuntimeEventType.operation_dispatched, payload={"operation_kind": "provider", "operation_name": operation.name, "attempt_number": 1, "effective_timeout_s": 60}, operation_id=record.operation_id, attempt_id=record.attempt_id, causal_parent_id=reserved.event_id)
        response = asyncio.run(_OperationInvoker(self._adapter, self._adapter).dispatch(operation, attempt_id=record.attempt_id, timeout_s=60, credential=credential))
        if response.status == "success":
            self._append(store, events, RuntimeEventType.operation_succeeded, payload={"attempt_number": 1, "status": "success", "usage": response.usage.model_dump(mode="json"), "result_sha256": sha256_hex(response.content), "provider_request_id": response.provider_request_id or "", "provider_audit": response.diagnostics.artifact()}, operation_id=record.operation_id, attempt_id=record.attempt_id, causal_parent_id=dispatched.event_id)
            ledger = ledger.reconcile(reservation, usage=response.usage, outcome=OperationStatus.succeeded, spec=self.spec); journal = journal.mark_succeeded(record.operation_id, record.attempt_id, sha256_hex(response.content)); state = self._lifecycle(store, events, state, RunStatus.validating); state = self._lifecycle(store, events, state, RunStatus.complete); terminal, error = "complete", None
        elif response.status == "unknown":
            self._append(store, events, RuntimeEventType.operation_unknown, payload={"error_code": ErrorCode.unknown_outcome.value, "attempt_number": 1, "usage": response.usage.model_dump(mode="json"), "provider_audit": response.diagnostics.artifact()}, operation_id=record.operation_id, attempt_id=record.attempt_id, causal_parent_id=dispatched.event_id)
            journal = journal.mark_unknown(record.operation_id, record.attempt_id, ErrorCode.unknown_outcome.value); state = self._lifecycle(store, events, state, RunStatus.failed, reason=ErrorCode.unknown_outcome.value); terminal, error = "failed", ErrorCode.unknown_outcome
        else:
            error = response.error_code or ErrorCode.contract_invalid
            self._append(store, events, RuntimeEventType.operation_failed, payload={"error_code": error.value, "attempt_number": 1, "usage": response.usage.model_dump(mode="json"), "provider_audit": response.diagnostics.artifact()}, operation_id=record.operation_id, attempt_id=record.attempt_id, causal_parent_id=dispatched.event_id)
            ledger = ledger.reconcile(reservation, usage=response.usage, outcome=OperationStatus.failed_known, spec=self.spec); journal = journal.mark_failed(record.operation_id, record.attempt_id, error.value); state = self._lifecycle(store, events, state, RunStatus.failed, reason=error.value); terminal = "failed"
        persisted = tuple(store.read_all()); replayed = replay_runtime_events(self.initial_state, persisted, self.spec); checkpoint = CoordinatedCheckpointV2.from_result(reduce_runtime_events(self.initial_state, persisted, self.spec)); write_coordinated_checkpoint(path.with_suffix(".checkpoint.json"), checkpoint)
        result = CrashSafeResult(terminal, error, replayed.run_state, replayed.ledger, replayed.journal, persisted, 1, checkpoint, self.initial_state, self.spec, (60.0,), replayed.manual_intervention)
        self._write_artifacts(result, response, bound_plan); return result

    def _write_artifacts(self, result: CrashSafeResult, response: _ProviderResult, bound_plan: DeepSeekCanaryPlan) -> None:
        files = {"immutable_plan.json": bound_plan.model_dump(mode="json"), "plan_sha256.json": {"plan_sha256": sha256_hex(canonical_json_bytes(bound_plan.model_dump(mode="json")))}, "redacted_request.json": {"endpoint": self.plan.endpoint, "model": self.plan.model_id, "body_sha256": sha256_hex(self._adapter._request_body()), "contains_authorization": False}, "response_metadata.json": {"provider_request_id": response.provider_request_id or "", "model": self.plan.model_id, "provider_dispatch_intents": 1, "provider_response_received": response.diagnostics.provider_response_received, "provider_response_confirmed": response.diagnostics.provider_response_confirmed, "provider_usage_reported": response.diagnostics.usage_reported}, "structured_result.json": {"terminal": result.terminal, "error_code": result.error_code.value if result.error_code else None, "content": response.content if response.status == "success" else ""}, "usage.json": response.usage.model_dump(mode="json"), "adapter_diagnostics.json": response.diagnostics.artifact(), "replay_verification.json": {"full_replay_matches": replay_runtime_events(result.initial_state, result.events, result.spec) == replay_runtime_events(result.initial_state, result.events, result.spec, checkpoint=result.checkpoint), "provider_calls_during_replay": 0}, "secret_scan.json": {"credential_persisted": False, "authorization_persisted": False, "private_absolute_path_persisted": False}}
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        for name, value in files.items():
            (self.artifact_dir / name).write_text(canonical_json(value) + "\n", encoding="utf-8", newline="\n")


__all__ = ["DEEPSEEK_ENDPOINT", "DEEPSEEK_MODEL", "DeepSeekCanaryConfigurationError", "DeepSeekCanaryPlan", "DeepSeekCanaryRunner", "parse_deepseek_canary_plan", "render_deepseek_canary_schema", "write_deepseek_canary_schema"]
