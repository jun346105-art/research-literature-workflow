"""Prepared single-agent GLM DeepResearch E2E path; offline by default."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import urllib.error
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .budgets import BudgetSpec, TokenUsage
from .canary import GLM_ENDPOINT, GLM_MODEL, _urllib_transport
from .contracts import BriefApproval, BriefApprovalStatus, ResearchBrief, ResearchTask
from .executor import LocalResearchExecutor
from .gap_replan import AssessmentContext, GapConflictAssessment, SubtaskEvidenceRequirement, assess_evidence_graph
from .identity import canonical_json_bytes, make_stable_id, sha256_hex
from .operations import OperationKind
from .planner import Planner, PlannerDraft, PlannerError, PlannerSubtaskDraft, ValidatedResearchPlan, plan_approved_brief
from .runtime_v2 import GENESIS_HASH, CoordinatedCheckpointV2, RuntimeEventEnvelope, RuntimeEventType, UnifiedEventStore, create_runtime_event, reduce_runtime_events, replay_runtime_events, write_coordinated_checkpoint
from .state import RunState, RunStatus, transition
from .writer import ReportStatus, ReportValidationResult, SingleWriterRunner, Writer, WriterError


E2E_PLAN_VERSION = "dr-glm-e2e-pilot-v1"
E2E_VERSION = "dr-single-agent-e2e-v1"
PLANNER_PROMPT_VERSION = "dr-glm-planner-prompt-v1"
WRITER_PROMPT_VERSION = "dr-glm-writer-prompt-v1"

PLANNER_PROMPT = """You propose one JSON PlannerDraft for the approved brief. Preserve task_id, brief_id, locale, constraints and scope exactly. Use only local keys for dependencies; never create formal IDs, evidence, claims, citations, tools, or final answers."""
WRITER_PROMPT = """You propose one JSON ReportDraft from the supplied Evidence View and gap/conflict summary. Cite only supplied evidence_id values with exact quotes. Never create Sources, Evidence, formal IDs, or a final publication-ready answer. Preserve disclosed uncertainty."""
_OUTPUT_ROOT = "outputs"


def runtime_source_sha256() -> str:
    """Fingerprint the minimal code that can change an E2E pilot's durable behavior."""
    paths = {
        "src/litflow/deep_research/e2e.py": Path(__file__).resolve(),
        "src/litflow/deep_research/e2e_cli.py": Path(__file__).resolve().with_name("e2e_cli.py"),
        "src/litflow/deep_research/executor.py": Path(__file__).resolve().with_name("executor.py"),
        "src/litflow/deep_research/writer.py": Path(__file__).resolve().with_name("writer.py"),
    }
    return sha256_hex(canonical_json_bytes({name: sha256_hex(path.read_bytes()) for name, path in paths.items()}))


class E2EConfigurationError(ValueError):
    pass


class E2ETerminalError(ValueError):
    """Structured E2E terminal outcome for the CLI boundary; never match text."""

    def __init__(self, error_code: str, *, outcome_unknown: bool = False):
        self.error_code, self.outcome_unknown = error_code, outcome_unknown
        super().__init__(error_code)


class PlannerResponseError(PlannerError):
    """Planner contract error carrying only redacted structural diagnostics."""

    def __init__(self, code: str, message: str, diagnostics: dict[str, object] | None = None):
        self.diagnostics = diagnostics or {}
        super().__init__(code, message)


class GLMAdapterError(ValueError):
    def __init__(self, code: str, *, outcome_unknown: bool = False, diagnostics: dict[str, object] | None = None):
        self.code, self.outcome_unknown, self.diagnostics = code, outcome_unknown, diagnostics or {}
        super().__init__(code)


class GLMInvocationPolicy(BaseModel):
    """Shared, ordinary-model, text-only provider contract for Planner and Writer."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    endpoint: Literal[GLM_ENDPOINT] = GLM_ENDPOINT
    model_id: Literal[GLM_MODEL] = GLM_MODEL
    credential_environment_variable: Literal["ZHIPUAI_API_KEY"] = "ZHIPUAI_API_KEY"
    temperature: Literal[1] = 1
    top_p: Literal[0.95] = 0.95
    thinking_type: Literal["enabled"] = "enabled"
    reasoning_effort: Literal["max"] = "max"
    max_input_tokens: int = Field(default=512, ge=1, le=512)
    max_output_tokens: int = Field(default=256, ge=1, le=256)
    operation_timeout_seconds: Literal[30] = 30
    max_retries: Literal[0] = 0
    input_price_per_million_micros: Literal[400000] = 400000
    output_price_per_million_micros: Literal[1400000] = 1400000
    monetary_budget_limit_micros: Literal[10000] = 10000
    tools_enabled: Literal[False] = False
    vision_enabled: Literal[False] = False
    video_enabled: Literal[False] = False
    files_enabled: Literal[False] = False
    web_enabled: Literal[False] = False
    parallel_enabled: Literal[False] = False
    fallback_enabled: Literal[False] = False

    def reservation(self) -> TokenUsage:
        return self.usage(self.max_input_tokens, self.max_output_tokens)

    def usage(self, input_tokens: int, output_tokens: int) -> TokenUsage:
        cost = (
            Decimal(input_tokens) * Decimal(self.input_price_per_million_micros)
            + Decimal(output_tokens) * Decimal(self.output_price_per_million_micros)
        ) / Decimal("1000000")
        return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens, cost_micros=cost)


class GLME2EPilotTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    task_key: Literal["single_paper", "cross_paper_comparison", "insufficient_evidence"]
    task_id: str = Field(pattern=r"^dr-task-[0-9a-f]{24}$")
    brief_id: str = Field(pattern=r"^dr-brief-[0-9a-f]{24}$")
    original_question: str = Field(min_length=1)
    locale: Literal["en"] = "en"
    constraints: list[str]
    deliverable_type: Literal["grounded_report"] = "grounded_report"
    created_at: str = Field(min_length=20)
    brief_objective: str = Field(min_length=1)
    scope_inclusions: list[str]
    scope_exclusions: list[str]
    brief_deliverable: Literal["grounded report"] = "grounded report"
    success_criteria: list[str]
    approval_actor: str = Field(min_length=1)
    approval_decided_at: str = Field(min_length=20)
    implementation_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    runtime_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_terminal: Literal["complete", "partial", "insufficient_evidence"]
    acceptance_metrics: list[
        Literal[
            "terminal_status",
            "evidence_citation_quote_grounding",
            "unsupported_claim_count",
            "abstention_correctness",
            "provider_attempts_responses",
            "tokens_cost",
            "latency",
            "replay_zero_calls",
            "secret_scan",
        ]
    ]
    corpus_path: str = Field(pattern=rf"^{_OUTPUT_ROOT}/rag_bm25_v1/[a-z0-9_.-]+$")
    corpus_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    planner_prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    writer_prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    max_planner_calls: Literal[1] = 1
    max_writer_calls: Literal[1] = 1
    max_replans: Literal[1] = 1
    artifact_dir: str = Field(pattern=rf"^{_OUTPUT_ROOT}/deep_research/e2e/v1/dr-run-[0-9a-f]{{24}}$")
    run_id: str = Field(pattern=r"^dr-run-[0-9a-f]{24}$")

    @field_validator("created_at", "approval_decided_at")
    @classmethod
    def require_utc_timestamp(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("pilot timestamp must be ISO-8601 UTC") from error
        if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError("pilot timestamp must be UTC")
        return value

    def materialize(self) -> tuple[ResearchTask, ResearchBrief, BriefApproval]:
        created_at = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        decided_at = datetime.fromisoformat(self.approval_decided_at.replace("Z", "+00:00"))
        task = ResearchTask.create(self.original_question, self.locale, tuple(self.constraints), self.deliverable_type, created_at)
        brief = ResearchBrief.create(task.task_id, self.brief_objective, tuple(self.scope_inclusions), tuple(self.scope_exclusions), self.brief_deliverable, tuple(self.success_criteria), tuple(self.constraints), BriefApprovalStatus.approved)
        approval = BriefApproval.create(brief.brief_id, task.task_id, BriefApprovalStatus.approved, self.approval_actor, decided_at)
        if task.task_id != self.task_id or brief.brief_id != self.brief_id:
            raise E2EConfigurationError("pilot task or brief identity mismatch")
        if DeepResearchRunner.run_id(task, brief, attempt_id=self._attempt_id()) != self.run_id:
            raise E2EConfigurationError("pilot deterministic run identity mismatch")
        return task, brief, approval

    def _attempt_id(self) -> str | None:
        return None

    @model_validator(mode="after")
    def require_complete_acceptance_set(self) -> "GLME2EPilotTask":
        required = {
            "terminal_status", "evidence_citation_quote_grounding", "unsupported_claim_count",
            "abstention_correctness", "provider_attempts_responses", "tokens_cost", "latency",
            "replay_zero_calls", "secret_scan",
        }
        if set(self.acceptance_metrics) != required or len(self.acceptance_metrics) != len(required):
            raise ValueError("pilot task must freeze every required acceptance metric exactly once")
        return self


class GLME2EPilotAttemptTask(GLME2EPilotTask):
    """v1.1 immutable attempt identity; v1 task/run identity remains untouched."""

    attempt_id: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]*$")

    def _attempt_id(self) -> str:
        return self.attempt_id


class GLME2EPilotPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[E2E_PLAN_VERSION] = E2E_PLAN_VERSION
    provider: Literal["zhipu-bigmodel"] = "zhipu-bigmodel"
    channel: Literal["ordinary_model_api"] = "ordinary_model_api"
    policy: GLMInvocationPolicy = GLMInvocationPolicy()
    tasks: list[GLME2EPilotTask]

    def budget_spec(self) -> BudgetSpec:
        return BudgetSpec(max_provider_attempts=2, max_provider_calls=2, max_tool_attempts=64, max_tool_calls=64, max_input_tokens=1024, max_output_tokens=512, max_total_tokens=1536, max_retries=0, max_replans=1, max_cost_micros=Decimal(self.policy.monetary_budget_limit_micros), run_timeout_s=90, operation_timeout_s=30)


class GLME2EPilotAttemptPlan(GLME2EPilotPlan):
    """v1.1 plan revision that binds a new execution attempt without rewriting v1."""

    schema_version: Literal["dr-glm-e2e-pilot-v1.1"] = "dr-glm-e2e-pilot-v1.1"
    tasks: list[GLME2EPilotAttemptTask]


E2EPilotPlan = GLME2EPilotPlan | GLME2EPilotAttemptPlan


def parse_e2e_pilot_plan(data: dict[str, object]) -> E2EPilotPlan:
    if data.get("schema_version") == E2E_PLAN_VERSION:
        return GLME2EPilotPlan.model_validate(data)
    if data.get("schema_version") == "dr-glm-e2e-pilot-v1.1":
        return GLME2EPilotAttemptPlan.model_validate(data)
    raise E2EConfigurationError("unsupported GLM E2E pilot schema version")


class GLMStructuredReply(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    content: str
    usage: TokenUsage
    model_identity_verified: bool
    usage_reported: bool
    request_id_present: bool
    http_status: int | None = None
    response_received: bool = True
    response_json_parsed: bool = True
    finish_reason: str | None = None
    content_length: int = 0
    content_sha256: str | None = None
    observed_type: str = "object"
    observed_keys: tuple[str, ...] = ()


_SAFE_PROVIDER_KEYS = frozenset({"choices", "error", "id", "model", "request_id", "usage"})


def _provider_shape(payload: object) -> tuple[str, tuple[str, ...]]:
    if not isinstance(payload, dict):
        return type(payload).__name__, ()
    return "object", tuple(sorted(key for key in payload if isinstance(key, str) and key in _SAFE_PROVIDER_KEYS))


def _provider_diagnostics(*, status: int | None, received: bool, parsed: bool, payload: object = None, failure_stage: str, error_code: str, content: str | None = None, finish_reason: str | None = None, model_identity_verified: bool = False, usage_reported: bool = False) -> dict[str, object]:
    observed_type, observed_keys = _provider_shape(payload)
    return {
        "failure_stage": failure_stage,
        "contract_error_code": error_code,
        "http_status": status,
        "response_received": received,
        "response_json_parsed": parsed,
        "model_identity_verified": model_identity_verified,
        "usage_reported": usage_reported,
        "finish_reason": finish_reason,
        "content_length": len(content) if content is not None else 0,
        "content_sha256": sha256_hex(content.encode("utf-8")) if content is not None else None,
        "observed_type": observed_type,
        "observed_keys": list(observed_keys),
    }


@runtime_checkable
class StructuredGLMClient(Protocol):
    async def complete(self, *, prompt: str, operation_name: str) -> GLMStructuredReply: ...


class GLMStructuredAdapter:
    """Shared ordinary-model transport client; no durable-state or retry authority."""

    def __init__(self, policy: GLMInvocationPolicy, *, transport: Any = _urllib_transport, credential: str | None = None) -> None:
        self._policy, self._transport, self._credential_override = policy, transport, credential

    def require_credential_for_execute(self) -> str:
        credential = self._credential_override or os.environ.get(self._policy.credential_environment_variable)
        if not credential:
            raise E2EConfigurationError("credential missing for ordinary-model API")
        return credential

    async def complete(self, *, prompt: str, operation_name: str) -> GLMStructuredReply:
        """This method is reachable only from an explicit future execute path."""
        credential = self.require_credential_for_execute()
        body = canonical_json_bytes({"model": self._policy.model_id, "messages": [{"role": "user", "content": prompt}], "temperature": self._policy.temperature, "top_p": self._policy.top_p, "max_tokens": self._policy.max_output_tokens, "thinking": {"type": self._policy.thinking_type}, "reasoning_effort": self._policy.reasoning_effort, "response_format": {"type": "json_object"}, "stream": False})
        try:
            status, headers, raw = await self._transport(url=self._policy.endpoint, headers={"Content-Type": "application/json", "Authorization": f"Bearer {credential}"}, body=body, timeout_s=float(self._policy.operation_timeout_seconds))
        except (TimeoutError, socket.timeout, ConnectionError, ConnectionResetError, urllib.error.URLError) as error:
            raise GLMAdapterError("outcome_unknown", outcome_unknown=True, diagnostics=_provider_diagnostics(status=None, received=False, parsed=False, failure_stage="transport", error_code="outcome_unknown")) from error
        if not 200 <= status < 300:
            try:
                error_payload = json.loads(raw.decode("utf-8"))
                parsed = True
            except (UnicodeDecodeError, json.JSONDecodeError):
                error_payload, parsed = None, False
            raise GLMAdapterError("transport_failure", diagnostics=_provider_diagnostics(status=status, received=True, parsed=parsed, payload=error_payload, failure_stage="transport", error_code="transport_failure"))
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GLMAdapterError("provider_response_invalid", diagnostics=_provider_diagnostics(status=status, received=True, parsed=False, failure_stage="provider_response", error_code="provider_response_invalid")) from error
        if not isinstance(payload, dict) or isinstance(payload.get("error"), dict):
            raise GLMAdapterError("provider_response_invalid", diagnostics=_provider_diagnostics(status=status, received=True, parsed=True, payload=payload, failure_stage="provider_response", error_code="provider_response_invalid"))
        choices = payload.get("choices")
        content = choices[0].get("message", {}).get("content") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
        if not isinstance(content, str):
            raise GLMAdapterError("provider_response_invalid", diagnostics=_provider_diagnostics(status=status, received=True, parsed=True, payload=payload, failure_stage="provider_response", error_code="provider_response_invalid"))
        finish_reason = choices[0].get("finish_reason") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
        if finish_reason is not None and not isinstance(finish_reason, str):
            finish_reason = None
        if payload.get("model") != self._policy.model_id:
            raise GLMAdapterError("provider_response_invalid", diagnostics=_provider_diagnostics(status=status, received=True, parsed=True, payload=payload, failure_stage="provider_response", error_code="provider_response_invalid", content=content, finish_reason=finish_reason))
        usage = payload.get("usage")
        if not isinstance(usage, dict) or not all(isinstance(usage.get(field), int) for field in ("prompt_tokens", "completion_tokens", "total_tokens")):
            raise GLMAdapterError("provider_response_invalid", diagnostics=_provider_diagnostics(status=status, received=True, parsed=True, payload=payload, failure_stage="provider_response", error_code="provider_response_invalid", content=content, finish_reason=finish_reason, model_identity_verified=True))
        token_usage = self._policy.usage(usage["prompt_tokens"], usage["completion_tokens"])
        if token_usage.total_tokens != usage["total_tokens"]:
            raise GLMAdapterError("provider_response_invalid", diagnostics=_provider_diagnostics(status=status, received=True, parsed=True, payload=payload, failure_stage="provider_response", error_code="provider_response_invalid", content=content, finish_reason=finish_reason, model_identity_verified=True))
        observed_type, observed_keys = _provider_shape(payload)
        return GLMStructuredReply(content=content, usage=token_usage, model_identity_verified=True, usage_reported=True, request_id_present=isinstance(payload.get("id") or headers.get("x-request-id"), str), http_status=status, finish_reason=finish_reason, content_length=len(content), content_sha256=sha256_hex(content.encode("utf-8")), observed_type=observed_type, observed_keys=observed_keys)


class GLMStructuredPlanner:
    """Real-provider-capable Planner adapter; formal Plan IDs remain program-owned."""

    def __init__(self, client: StructuredGLMClient, *, reservation_usage: TokenUsage | None = None) -> None:
        self._client, self.last_usage, self.reservation_usage = client, TokenUsage(), reservation_usage or TokenUsage()

    async def create_draft(self, *, task: ResearchTask, brief: ResearchBrief) -> object:
        prompt = f"{PLANNER_PROMPT}\nApproved brief: {json.dumps(brief.model_dump(mode='json'), ensure_ascii=False, sort_keys=True)}"
        try:
            reply = await self._client.complete(prompt=prompt, operation_name="glm_structured_planner")
            self.last_usage = reply.usage
            diagnostics = _provider_diagnostics_from_reply(reply)
            if reply.finish_reason in {"length", "max_tokens"}:
                raise PlannerResponseError("planner_content_truncated", "Planner response ended at the output limit", diagnostics)
            return _parse_planner_object_with_diagnostics(reply.content, diagnostics=diagnostics)
        except GLMAdapterError as error:
            raise PlannerResponseError(error.code, "GLM Planner provider response was not admissible", error.diagnostics) from error


class GLMSingleWriter:
    """Real-provider-capable Writer adapter; final report ownership remains in B07."""

    def __init__(self, client: StructuredGLMClient, *, reservation_usage: TokenUsage | None = None) -> None:
        self._client, self.last_usage, self.reservation_usage = client, TokenUsage(), reservation_usage or TokenUsage()

    async def create_draft(self, **kwargs: object) -> object:
        graph = kwargs["graph"]
        assessment = kwargs["assessment"]
        prompt = f"{WRITER_PROMPT}\nEvidence view: {json.dumps(graph.model_dump(mode='json'), ensure_ascii=False, sort_keys=True)}\nAssessment: {json.dumps(assessment.model_dump(mode='json'), ensure_ascii=False, sort_keys=True)}"
        try:
            reply = await self._client.complete(prompt=prompt, operation_name="glm_single_writer")
            self.last_usage = reply.usage
            return json.loads(reply.content)
        except (json.JSONDecodeError, GLMAdapterError) as error:
            raise WriterError("outcome_unknown" if isinstance(error, GLMAdapterError) and error.outcome_unknown else "writer_contract_invalid", "GLM Writer response is not an admissible draft") from error


def _parse_planner_object(content: str) -> dict[str, object]:
    """Ignore one harmless JSON fence but reject program-controlled identities."""
    return _parse_planner_object_with_diagnostics(content, diagnostics={})


def _provider_diagnostics_from_reply(reply: GLMStructuredReply) -> dict[str, object]:
    return {
        "failure_stage": "planner_application",
        "contract_error_code": None,
        "http_status": reply.http_status,
        "response_received": reply.response_received,
        "response_json_parsed": reply.response_json_parsed,
        "model_identity_verified": reply.model_identity_verified,
        "usage_reported": reply.usage_reported,
        "finish_reason": reply.finish_reason,
        "content_length": reply.content_length,
        "content_sha256": reply.content_sha256,
        "observed_type": reply.observed_type,
        "observed_keys": list(reply.observed_keys),
    }


def _parse_planner_object_with_diagnostics(content: str, *, diagnostics: dict[str, object]) -> dict[str, object]:
    """Ignore one harmless JSON fence but reject program-controlled identities."""
    normalized = content.strip()
    if normalized.startswith("```") and normalized.endswith("```"):
        lines = normalized.splitlines()
        normalized = "\n".join(lines[1:-1]).strip()
    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError as error:
        raise PlannerResponseError("planner_json_invalid", "GLM Planner response is not JSON", {**diagnostics, "failure_stage": "planner_json", "contract_error_code": "planner_json_invalid"}) from error
    if not isinstance(payload, dict):
        raise PlannerResponseError("planner_json_invalid", "GLM Planner response must be an object", {**diagnostics, "failure_stage": "planner_json", "contract_error_code": "planner_json_invalid"})
    forbidden = {"plan_id", "subtask_id", "evidence_id", "claim_id", "citation_id", "sources", "evidence_units", "final_answer"}
    if forbidden.intersection(payload):
        raise PlannerResponseError("planner_schema_invalid", "GLM Planner attempted to own a program-controlled field", {**diagnostics, "failure_stage": "planner_schema", "contract_error_code": "planner_schema_invalid"})
    result = {key: payload[key] for key in PlannerDraft.model_fields if key in payload}
    subtasks = result.get("subtasks")
    if isinstance(subtasks, list):
        normalized: list[object] = []
        for candidate in subtasks:
            if not isinstance(candidate, dict) or forbidden.intersection(candidate):
                raise PlannerResponseError("planner_schema_invalid", "GLM Planner subtask is invalid", {**diagnostics, "failure_stage": "planner_schema", "contract_error_code": "planner_schema_invalid"})
            normalized.append({key: candidate[key] for key in PlannerSubtaskDraft.model_fields if key in candidate})
        result["subtasks"] = normalized
    try:
        validated = PlannerDraft.model_validate(result)
    except ValidationError as error:
        first = error.errors(include_input=False)[0]
        location = ".".join(str(part) for part in first.get("loc", ())) or "root"
        raise PlannerResponseError("planner_schema_invalid", "GLM Planner draft failed schema validation", {**diagnostics, "failure_stage": "planner_schema", "contract_error_code": "planner_schema_invalid", "pydantic_error_type": str(first.get("type")), "pydantic_error_location": location}) from error
    return validated.model_dump(mode="json")


class DeepResearchE2EResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    terminal: Literal["complete", "partial", "insufficient_evidence", "manual_review_required"]
    plan: ValidatedResearchPlan
    validation: ReportValidationResult | None = None
    resumed: bool = False


class DeepResearchRunner:
    """One injected single-agent composition; it creates no new runtime or Event Store."""

    def __init__(self, planner: Planner, executor: LocalResearchExecutor, writer: Writer, *, budget: BudgetSpec, requirements: tuple[SubtaskEvidenceRequirement, ...] = ()) -> None:
        self._planner, self._executor, self._writer, self._budget, self._requirements = planner, executor, writer, budget, requirements

    @staticmethod
    def run_id(task: ResearchTask, brief: ResearchBrief, *, attempt_id: str | None = None) -> str:
        identity: dict[str, str] = {"runtime": E2E_VERSION, "task_id": task.task_id, "brief_id": brief.brief_id}
        if attempt_id is not None:
            identity["attempt_id"] = attempt_id
        return make_stable_id("run", identity)

    @staticmethod
    def _append(store: UnifiedEventStore, events: list[RuntimeEventEnvelope], event_type: RuntimeEventType, payload: dict[str, Any], *, operation_id: str | None = None, attempt_id: str | None = None, causal_parent_id: str | None = None) -> RuntimeEventEnvelope:
        event = create_runtime_event(store.run_id, len(events) + 1, event_type, payload=payload, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=causal_parent_id, previous_event_hash=events[-1].event_hash if events else GENESIS_HASH)
        store.append(event); events.append(event); return event

    def _lifecycle(self, store: UnifiedEventStore, events: list[RuntimeEventEnvelope], state: RunState, target: RunStatus, reason: str | None = None) -> RunState:
        state, lifecycle = transition(state, target, reason=reason)
        self._append(store, events, RuntimeEventType.lifecycle_transition, lifecycle.model_dump(mode="json"), causal_parent_id=events[-1].event_id)
        return state

    @staticmethod
    def _planner_error_code(code: str) -> str:
        return {
            "planner_contract_invalid": "planner_schema_invalid",
            "planner_scope_violation": "planner_scope_invalid",
            "planner_cycle_detected": "planner_dependency_invalid",
            "content_missing": "provider_response_invalid",
            "provider_error_envelope": "provider_response_invalid",
            "model_identity_unverified": "provider_response_invalid",
            "usage_missing": "provider_response_invalid",
        }.get(code, code)

    async def run(self, task: ResearchTask, brief: ResearchBrief, approval: BriefApproval, *, event_path: Path, checkpoint_path: Path, attempt_id: str | None = None) -> DeepResearchE2EResult:
        if brief.approval_status is not BriefApprovalStatus.approved:
            raise E2EConfigurationError("approved brief is required")
        run_id = self.run_id(task, brief, attempt_id=attempt_id)
        initial = RunState(run_id=run_id, task_id=task.task_id, brief_id=brief.brief_id, brief_approved=True)
        store = UnifiedEventStore(event_path, run_id=run_id)
        events = store.read_all()
        plan_event = next((event for event in events if event.event_type is RuntimeEventType.operation_succeeded and event.payload.get("operation_name") == "structured_planner"), None)
        report_event = next((event for event in events if event.event_type is RuntimeEventType.operation_succeeded and event.payload.get("operation_name") == "single_writer"), None)
        if report_event is not None and plan_event is not None:
            plan = ValidatedResearchPlan.model_validate(plan_event.payload["validated_plan"])
            validation = ReportValidationResult.model_validate(report_event.payload["validation"])
            return DeepResearchE2EResult(run_id=run_id, terminal=validation.status.value, plan=plan, validation=validation, resumed=True)
        if events and plan_event is not None:
            raise E2EConfigurationError("incomplete durable run requires manual review; no component is re-invoked")
        if events:
            replayed = replay_runtime_events(initial, events, self._budget)
            if replayed.manual_intervention is not None:
                raise E2EConfigurationError("outcome_unknown requires manual review")
            raise E2EConfigurationError("unexpected nonempty E2E stream")
        self._append(store, events, RuntimeEventType.run_started, {"e2e_version": E2E_VERSION, "spec": self._budget.model_dump(mode="json")})
        state = self._lifecycle(store, events, initial, RunStatus.brief_approved)
        state = self._lifecycle(store, events, state, RunStatus.researching)
        operation_id = make_stable_id("operation", {"run_id": run_id, "operation": "structured_planner"})
        attempt_id = make_stable_id("attempt", {"operation_id": operation_id, "attempt_number": 1})
        reserved_usage = getattr(self._planner, "reservation_usage", TokenUsage())
        reserved = self._append(store, events, RuntimeEventType.operation_reserved, {"operation_kind": OperationKind.provider.value, "operation_name": "structured_planner", "attempt_number": 1, "idempotent": False, "side_effecting": True, "usage": reserved_usage.model_dump(mode="json")}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=events[-1].event_id)
        reduce_runtime_events(initial, events, self._budget)
        dispatched = self._append(store, events, RuntimeEventType.operation_dispatched, {"operation_kind": OperationKind.provider.value, "operation_name": "structured_planner", "attempt_number": 1, "effective_timeout_s": self._budget.operation_timeout_s}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=reserved.event_id)
        try:
            plan = await plan_approved_brief(task, brief, approval, self._planner)
        except PlannerError as error:
            code = self._planner_error_code(error.code)
            kind = RuntimeEventType.operation_unknown if error.code == "outcome_unknown" else RuntimeEventType.operation_failed
            diagnostics = getattr(error, "diagnostics", {})
            self._append(store, events, kind, {"operation_name": "structured_planner", "error_code": code, "attempt_number": 1, "usage": TokenUsage().model_dump(mode="json"), "diagnostics": diagnostics}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=dispatched.event_id)
            state = self._lifecycle(store, events, state, RunStatus.failed, code)
            write_coordinated_checkpoint(checkpoint_path, CoordinatedCheckpointV2.from_result(replay_runtime_events(initial, events, self._budget)))
            raise E2ETerminalError(code, outcome_unknown=error.code == "outcome_unknown") from error
        usage = getattr(self._planner, "last_usage", TokenUsage())
        self._append(store, events, RuntimeEventType.operation_succeeded, {"operation_name": "structured_planner", "attempt_number": 1, "usage": usage.model_dump(mode="json"), "result_sha256": sha256_hex(canonical_json_bytes(plan.model_dump(mode="json"))), "validated_plan": plan.model_dump(mode="json")}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=dispatched.event_id)
        write_coordinated_checkpoint(checkpoint_path, CoordinatedCheckpointV2.from_result(replay_runtime_events(initial, events, self._budget)))
        execution = await self._executor.execute(task, brief, approval, plan, event_path=event_path, checkpoint_path=checkpoint_path, run_id=run_id)
        assessment = await assess_evidence_graph(execution.evidence_graph, self._requirements, AssessmentContext(completed_subtask_ids=tuple(item.subtask_id for item in plan.subtasks)))
        writer_result = await SingleWriterRunner(self._writer, budget=self._budget, reservation_usage=getattr(self._writer, "reservation_usage", TokenUsage())).run(task, brief, approval, plan, execution.evidence_graph, assessment, event_path=event_path, checkpoint_path=checkpoint_path)
        return DeepResearchE2EResult(run_id=run_id, terminal=writer_result.validation.status.value, plan=plan, validation=writer_result.validation)


def prompt_hashes() -> dict[str, str]:
    return {"planner": sha256_hex(PLANNER_PROMPT.encode("utf-8")), "writer": sha256_hex(WRITER_PROMPT.encode("utf-8"))}


def render_e2e_pilot_schema() -> str:
    schema = GLME2EPilotPlan.model_json_schema(); schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def render_e2e_pilot_attempt_schema() -> str:
    schema = GLME2EPilotAttemptPlan.model_json_schema(); schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_e2e_pilot_schema(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "glm_e2e_pilot.schema.json"
    path.write_text(render_e2e_pilot_schema(), encoding="utf-8", newline="\n")
    return path


def write_e2e_pilot_attempt_schema(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "glm_e2e_pilot.schema.json"
    path.write_text(render_e2e_pilot_attempt_schema(), encoding="utf-8", newline="\n")
    return path


def preflight_e2e_pilot(plan: E2EPilotPlan, *, repo_root: Path, git_root: Path | None = None) -> tuple[GLME2EPilotTask, ...]:
    """Read-only plan/artifact/corpus verification; it never reads a credential or transports."""
    hashes = prompt_hashes()
    git_root = git_root or Path.cwd()
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=git_root, check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise E2EConfigurationError("cannot resolve E2E implementation Git identity") from error
    if len(plan.tasks) != 3 or {item.task_key for item in plan.tasks} != {"single_paper", "cross_paper_comparison", "insufficient_evidence"}:
        raise E2EConfigurationError("pilot must freeze exactly the three authorized task categories")
    ids = [item.run_id for item in plan.tasks]
    if len(ids) != len(set(ids)):
        raise E2EConfigurationError("pilot run identities must be unique")
    for item in plan.tasks:
        item.materialize()
        try:
            ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", item.implementation_commit_sha, head], cwd=git_root, check=False, capture_output=True)
        except OSError as error:
            raise E2EConfigurationError("cannot verify E2E implementation ancestor") from error
        if ancestor.returncode != 0 or item.runtime_source_sha256 != runtime_source_sha256():
            raise E2EConfigurationError("E2E implementation binding mismatch")
        if item.planner_prompt_sha256 != hashes["planner"] or item.writer_prompt_sha256 != hashes["writer"]:
            raise E2EConfigurationError("pilot prompt fingerprint mismatch")
        corpus = repo_root / item.corpus_path
        if not corpus.is_file() or sha256_hex(corpus.read_bytes()) != item.corpus_sha256:
            raise E2EConfigurationError("frozen corpus identity mismatch")
        artifact = repo_root / item.artifact_dir
        if artifact.exists():
            raise E2EConfigurationError("pilot artifact directory must not already exist")
    return tuple(plan.tasks)
