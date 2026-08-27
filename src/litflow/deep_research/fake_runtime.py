"""Deterministic, offline execution harness for B03 policy verification."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .budgets import BudgetLedger, BudgetSpec, TokenUsage
from .errors import ErrorCode
from .events import PolicyEvent, PolicyEventType, RunEvent, create_policy_event
from .identity import make_stable_id, sha256_hex
from .operations import OperationJournal, OperationKind, OperationRecord, OperationStatus
from .policies import CancellationToken, ReplanPolicy, RetryPolicy
from .state import RunState, RunStatus, transition


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        if start < 0:
            raise ValueError("clock cannot start before zero")
        self._now = float(start)

    def monotonic(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("clock cannot move backwards")
        self._now += float(seconds)


@dataclass(frozen=True)
class FakeStep:
    status: str = "success"
    content: str = "ok"
    latency_s: float = 0.0
    usage: TokenUsage = field(default_factory=TokenUsage)
    error_code: ErrorCode | None = None


@dataclass(frozen=True)
class FakeOperation:
    name: str
    kind: OperationKind
    attempts: tuple[FakeStep, ...]
    idempotent: bool = True
    side_effecting: bool = False

    @property
    def operation_id(self) -> str:
        return make_stable_id("operation", {"kind": self.kind.value, "name": self.name})


@dataclass(frozen=True)
class _Snapshot:
    scenario: str
    next_operation: int
    ledger: BudgetLedger
    journal: OperationJournal
    events: tuple[PolicyEvent, ...]
    external_call_count: int
    clock_now: float
    run_state: Any
    lifecycle_events: tuple[RunEvent, ...]
    run_deadline: float | None


@dataclass(frozen=True)
class FakeResult:
    scenario: str
    terminal: str
    error_code: ErrorCode | None
    ledger: BudgetLedger
    journal: OperationJournal
    events: tuple[PolicyEvent, ...]
    run_state: Any
    lifecycle_events: tuple[RunEvent, ...]
    external_call_count: int
    durable_boundary_count: int
    interrupted: bool = False
    _snapshot: _Snapshot | None = field(default=None, compare=False, repr=False)

    def resume(self) -> "FakeResult":
        if not self.interrupted or self._snapshot is None:
            return self
        harness = FakeExecutionHarness(self.scenario)
        return asyncio.run(harness.run_async(snapshot=self._snapshot))


class FakeProvider:
    def __init__(self, operations: tuple[FakeOperation, ...], clock: FakeClock) -> None:
        self.operations = operations
        self.clock = clock
        self.calls: list[tuple[str, str]] = []

    async def call(self, *, operation_id: str, attempt_id: str, request: Any, timeout_s: float | None = None) -> FakeStep:
        operation = next(item for item in self.operations if item.operation_id == operation_id)
        attempt_number = sum(item[0] == operation_id for item in self.calls) + 1
        if attempt_number > len(operation.attempts):
            raise AssertionError("unexpected fake provider call")
        self.calls.append((operation_id, attempt_id))
        step = operation.attempts[attempt_number - 1]
        self.clock.advance(step.latency_s)
        if timeout_s is not None and step.latency_s > timeout_s:
            return FakeStep(status="error", latency_s=0.0, usage=step.usage, error_code=ErrorCode.operation_timeout)
        return step


class FakeTool:
    def __init__(self, operations: tuple[FakeOperation, ...], clock: FakeClock) -> None:
        self.operations = operations
        self.clock = clock
        self.calls: list[tuple[str, str]] = []

    async def call(self, *, operation_id: str, attempt_id: str, request: Any, timeout_s: float | None = None) -> FakeStep:
        operation = next(item for item in self.operations if item.operation_id == operation_id)
        attempt_number = sum(item[0] == operation_id for item in self.calls) + 1
        if attempt_number > len(operation.attempts):
            raise AssertionError("unexpected fake tool call")
        self.calls.append((operation_id, attempt_id))
        step = operation.attempts[attempt_number - 1]
        self.clock.advance(step.latency_s)
        if timeout_s is not None and step.latency_s > timeout_s:
            return FakeStep(status="error", latency_s=0.0, usage=step.usage, error_code=ErrorCode.operation_timeout)
        return step


def _step(status: str = "success", *, content: str = "ok", latency: float = 0.0, input_tokens: int = 1, output_tokens: int = 1, cost_micros: str = "0", error: ErrorCode | None = None) -> FakeStep:
    return FakeStep(status=status, content=content, latency_s=latency, usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens, cost_micros=Decimal(cost_micros)), error_code=error)


def scenario_operations(name: str) -> tuple[FakeOperation, ...]:
    provider = OperationKind.provider
    tool = OperationKind.tool
    scenarios: dict[str, tuple[FakeOperation, ...]] = {
        "success_minimal": (FakeOperation("retrieve", tool, (_step(content="evidence"),)), FakeOperation("synthesize", provider, (_step(),))),
        "insufficient_evidence": (FakeOperation("retrieve", tool, (_step(content=""),)),),
        "transient_retry_success": (FakeOperation("provider", provider, (_step(status="error", error=ErrorCode.transient_provider), _step())),),
        "timeout_exhausted": (FakeOperation("slow", provider, (_step(status="error", latency=2.0, error=ErrorCode.operation_timeout), _step(status="error", latency=2.0, error=ErrorCode.operation_timeout))),),
        "cancel_before_next_call": (FakeOperation("retrieve", tool, (_step(),)), FakeOperation("synthesize", provider, (_step(),))),
        "budget_exhausted": (FakeOperation("first", tool, (_step(),)), FakeOperation("second", provider, (_step(),))),
        "single_replan_success": (FakeOperation("retrieve_initial", tool, (_step(status="abstain", content=""),)), FakeOperation("retrieve_followup", tool, (_step(content="evidence"),)), FakeOperation("synthesize", provider, (_step(),))),
        "replan_limit_exceeded": (FakeOperation("retrieve_initial", tool, (_step(status="abstain", content=""),)), FakeOperation("retrieve_followup", tool, (_step(status="abstain", content=""),))),
        "unknown_non_idempotent_outcome": (FakeOperation("write_side_effect", tool, (_step(status="unknown", error=ErrorCode.unknown_outcome),), idempotent=False, side_effecting=True),),
    }
    if name not in scenarios:
        raise ValueError(f"unknown fake scenario: {name}")
    return scenarios[name]


class FakeExecutionHarness:
    def __init__(self, scenario: str, *, spec: BudgetSpec | None = None, clock: FakeClock | None = None, token: CancellationToken | None = None) -> None:
        self.scenario = scenario
        self.operations = scenario_operations(scenario)
        self.spec = spec or (BudgetSpec(max_provider_attempts=4, max_provider_calls=0, max_tool_attempts=4, max_tool_calls=1, max_total_tokens=100, max_replans=1, run_timeout_s=10.0, operation_timeout_s=1.0) if scenario == "budget_exhausted" else BudgetSpec(max_provider_attempts=4, max_provider_calls=4, max_tool_attempts=4, max_tool_calls=4, max_total_tokens=100, max_replans=1, run_timeout_s=10.0, operation_timeout_s=1.0))
        self.clock = clock or FakeClock()
        self.token = token or CancellationToken()
        self.retry = RetryPolicy(max_attempts=2)
        self.replan = ReplanPolicy(max_replans=self.spec.max_replans)
        self.run_id = make_stable_id(
            "run",
            {
                "runtime": "dr-runtime-v1",
                "task_id": "dr-task-" + "a" * 24,
                "brief_id": "dr-brief-" + "b" * 24,
            },
        )

    async def run_async(self, *, interrupt_after: int | None = None, snapshot: _Snapshot | None = None) -> FakeResult:
        ledger = snapshot.ledger if snapshot else BudgetLedger.empty(self.spec)
        journal = snapshot.journal if snapshot else OperationJournal.empty()
        events = list(snapshot.events) if snapshot else []
        lifecycle_events = list(snapshot.lifecycle_events) if snapshot else []
        external_calls = snapshot.external_call_count if snapshot else 0
        start_index = snapshot.next_operation if snapshot else 0
        if snapshot:
            run_state = snapshot.run_state
        else:
            run_state = RunState.create(task_id="dr-task-" + "a" * 24, brief_id="dr-brief-" + "b" * 24, brief_approved=True)
            run_state, lifecycle_event = transition(run_state, RunStatus.brief_approved)
            lifecycle_events.append(lifecycle_event)
            run_state, lifecycle_event = transition(run_state, RunStatus.researching)
            lifecycle_events.append(lifecycle_event)
        run_deadline = snapshot.run_deadline if snapshot else (self.clock.monotonic() + self.spec.run_timeout_s if self.spec.run_timeout_s is not None else None)
        if snapshot:
            self.clock.advance(max(0.0, snapshot.clock_now - self.clock.monotonic()))
        provider = FakeProvider(self.operations, self.clock)
        tool = FakeTool(self.operations, self.clock)
        terminal = "complete"
        error_code: ErrorCode | None = None
        completed = 0
        for index in range(start_index, len(self.operations)):
            operation = self.operations[index]
            if self.scenario == "cancel_before_next_call" and index == 1:
                self.token.request()
            if self.token.cancelled:
                terminal, error_code = "failed", ErrorCode.cancelled
                break
            if run_deadline is not None and self.clock.monotonic() >= run_deadline:
                terminal, error_code = "failed", ErrorCode.run_deadline_exceeded
                break
            record = journal.plan(operation_id=operation.operation_id, kind=operation.kind, name=operation.name, idempotent=operation.idempotent, side_effecting=operation.side_effecting)
            if journal._current(record.operation_id) is None:
                journal = journal.add(record)
                events.append(create_policy_event(self.run_id, len(events) + 1, PolicyEventType.operation_planned, operation_id=operation.operation_id, attempt_id=record.attempt_id, operation_kind=operation.kind.value, operation_name=operation.name, operation_status=OperationStatus.planned.value, idempotent=operation.idempotent, side_effecting=operation.side_effecting, attempt_number=1, previous_event_hash=events[-1].event_hash if events else "0" * 64))
            for attempt_number, scripted in enumerate(operation.attempts, 1):
                current = journal._current(operation.operation_id)
                assert current is not None
                attempt_id = make_stable_id("attempt", {"operation_id": operation.operation_id, "attempt_number": attempt_number})
                if attempt_number > 1:
                    journal = journal._update(operation.operation_id, current.attempt_id, attempt_id=attempt_id, attempt_number=attempt_number, status=OperationStatus.planned)
                try:
                    ledger, reservation = ledger.reserve(self.spec, operation_id=operation.operation_id, attempt_id=attempt_id, kind=operation.kind, usage=scripted.usage)
                except ValueError:
                    terminal, error_code = "failed", ErrorCode.budget_exhausted
                    break
                journal = journal.start(operation.operation_id, attempt_id)
                event_type = PolicyEventType.operation_started
                events.append(create_policy_event(self.run_id, len(events) + 1, event_type, operation_id=operation.operation_id, attempt_id=attempt_id, operation_kind=operation.kind.value, operation_name=operation.name, operation_status=OperationStatus.started.value, idempotent=operation.idempotent, side_effecting=operation.side_effecting, attempt_number=attempt_number, previous_event_hash=events[-1].event_hash if events else "0" * 64))
                response = await (provider.call if operation.kind is OperationKind.provider else tool.call)(operation_id=operation.operation_id, attempt_id=attempt_id, request={"scenario": self.scenario}, timeout_s=self.spec.operation_timeout_s)
                external_calls += 1
                code = response.error_code or (ErrorCode.transient_provider if response.status == "error" else None)
                outcome = OperationStatus.succeeded if response.status in {"success", "abstain"} else OperationStatus.failed_known
                if response.status == "unknown":
                    outcome = OperationStatus.outcome_unknown
                    code = ErrorCode.unknown_outcome
                if code is ErrorCode.operation_timeout:
                    outcome = OperationStatus.failed_known
                ledger = ledger.reconcile(reservation, usage=response.usage, outcome=outcome, attempt_number=attempt_number, spec=self.spec)
                events.append(create_policy_event(self.run_id, len(events) + 1, PolicyEventType.attempt_charged, operation_id=operation.operation_id, attempt_id=attempt_id, operation_kind=operation.kind.value, operation_name=operation.name, operation_status=outcome.value, error_code=code.value if code else None, attempt_number=attempt_number, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens, cost_micros=str(response.usage.cost_micros), previous_event_hash=events[-1].event_hash))
                if outcome is OperationStatus.succeeded:
                    journal = journal.mark_succeeded(operation.operation_id, attempt_id, sha256_hex(response.content))
                    events.append(create_policy_event(self.run_id, len(events) + 1, PolicyEventType.operation_succeeded, operation_id=operation.operation_id, attempt_id=attempt_id, operation_kind=operation.kind.value, operation_name=operation.name, operation_status=outcome.value, result_sha256=sha256_hex(response.content), attempt_number=attempt_number, previous_event_hash=events[-1].event_hash))
                    completed += 1
                    break
                if outcome is OperationStatus.outcome_unknown:
                    journal = journal.mark_unknown(operation.operation_id, attempt_id, ErrorCode.unknown_outcome.value)
                    events.append(create_policy_event(self.run_id, len(events) + 1, PolicyEventType.operation_unknown, operation_id=operation.operation_id, attempt_id=attempt_id, operation_kind=operation.kind.value, operation_name=operation.name, operation_status=outcome.value, error_code=ErrorCode.unknown_outcome.value, attempt_number=attempt_number, previous_event_hash=events[-1].event_hash))
                    terminal, error_code = "failed", ErrorCode.unknown_outcome
                    break
                journal = journal.mark_failed(operation.operation_id, attempt_id, (code or ErrorCode.tool_failure).value)
                events.append(create_policy_event(self.run_id, len(events) + 1, PolicyEventType.operation_failed, operation_id=operation.operation_id, attempt_id=attempt_id, operation_kind=operation.kind.value, operation_name=operation.name, operation_status=outcome.value, error_code=(code or ErrorCode.tool_failure).value, attempt_number=attempt_number, previous_event_hash=events[-1].event_hash))
                if code is ErrorCode.operation_timeout and self.scenario == "timeout_exhausted":
                    error_code = ErrorCode.operation_timeout
                remaining_s = (run_deadline if run_deadline is not None else float("inf")) - self.clock.monotonic()
                if remaining_s <= 0:
                    terminal, error_code = "failed", ErrorCode.run_deadline_exceeded
                    break
                if code is None or not self.retry.allows(code, attempt_number=attempt_number, remaining_s=remaining_s):
                    terminal, error_code = "failed", code or ErrorCode.tool_failure
                    break
            if terminal == "failed":
                break
            if self.scenario in {"insufficient_evidence", "single_replan_success", "replan_limit_exceeded"} and index == 0:
                if self.spec.max_replans < 1:
                    terminal, error_code = "insufficient_evidence", ErrorCode.budget_exhausted
                    break
                decision = self.replan.admit(ordinal=0, old_plan_id="dr-plan-old", proposed_plan_id="dr-plan-new", reason=ErrorCode.grounding_rejected)
                if not decision.admitted:
                    terminal, error_code = "insufficient_evidence", ErrorCode.budget_exhausted
                    break
                ledger = ledger.record_replan(self.spec)
                events.append(create_policy_event(self.run_id, len(events) + 1, PolicyEventType.replan_decided, old_plan_id=decision.old_plan_id, proposed_plan_id=decision.proposed_plan_id, replan_ordinal=0, admitted=True, previous_event_hash=events[-1].event_hash))
                if self.scenario == "insufficient_evidence":
                    terminal, error_code = "insufficient_evidence", ErrorCode.grounding_rejected
                    break
            if self.scenario == "replan_limit_exceeded" and index == 1:
                terminal, error_code = "insufficient_evidence", ErrorCode.budget_exhausted
                break
            if interrupt_after is not None and completed >= interrupt_after:
                snapshot_value = _Snapshot(self.scenario, index + 1, ledger, journal, tuple(events), external_calls, self.clock.monotonic(), run_state, tuple(lifecycle_events), run_deadline)
                return FakeResult(
                    scenario=self.scenario,
                    terminal="interrupted",
                    error_code=None,
                    ledger=ledger,
                    journal=journal,
                    events=tuple(events),
                    run_state=run_state,
                    lifecycle_events=tuple(lifecycle_events),
                    external_call_count=external_calls,
                    durable_boundary_count=len(events),
                    interrupted=True,
                    _snapshot=snapshot_value,
                )
        if terminal != "failed" and error_code is None:
            if self.scenario == "insufficient_evidence":
                terminal, error_code = "insufficient_evidence", ErrorCode.grounding_rejected
            elif self.scenario == "replan_limit_exceeded":
                terminal, error_code = "insufficient_evidence", ErrorCode.budget_exhausted
            else:
                terminal = "complete"
        if run_state.status is RunStatus.researching:
            if terminal == "complete":
                run_state, lifecycle_event = transition(run_state, RunStatus.validating)
                lifecycle_events.append(lifecycle_event)
                run_state, lifecycle_event = transition(run_state, RunStatus.complete)
                lifecycle_events.append(lifecycle_event)
            else:
                target = RunStatus.insufficient_evidence if terminal == "insufficient_evidence" else RunStatus.failed
                run_state, lifecycle_event = transition(run_state, target, reason=error_code.value if error_code else None)
                lifecycle_events.append(lifecycle_event)
        return FakeResult(
            scenario=self.scenario,
            terminal=terminal,
            error_code=error_code,
            ledger=ledger,
            journal=journal,
            events=tuple(events),
            run_state=run_state,
            lifecycle_events=tuple(lifecycle_events),
            external_call_count=external_calls,
            durable_boundary_count=len(events),
        )

    def run(self, *, interrupt_after: int | None = None) -> FakeResult:
        return asyncio.run(self.run_async(interrupt_after=interrupt_after))


def run_fake_scenario(name: str, *, interrupt_after: int | None = None) -> FakeResult:
    return FakeExecutionHarness(name).run(interrupt_after=interrupt_after)
