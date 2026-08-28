"""Crash-safe, single-stream runtime facts for the B03R repair batch."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import Field, model_validator

from .budgets import BudgetLedger, BudgetReservation, BudgetSpec, TokenUsage
from .contracts import ContractModel
from .errors import ErrorCode, ManualInterventionRequired
from .events import GENESIS_HASH, RunEvent
from .fake_runtime import FakeClock, FakeProvider, FakeTool, scenario_operations
from .identity import canonical_json, canonical_json_bytes, make_stable_id, sha256_hex
from .operations import OperationJournal, OperationKind, OperationRecord, OperationStatus
from .policies import CancellationToken, ReplanPolicy, RetryPolicy
from .replay import replay_events
from .state import RunState, RunStatus, transition


class RuntimeEventType(str, Enum):
    run_started = "run_started"
    lifecycle_transition = "lifecycle_transition"
    operation_reserved = "operation_reserved"
    operation_dispatched = "operation_dispatched"
    operation_succeeded = "operation_succeeded"
    operation_failed = "operation_failed"
    operation_unknown = "operation_unknown"
    operation_cancelled = "operation_cancelled"
    retry_scheduled = "retry_scheduled"
    replan_decided = "replan_decided"
    elapsed_recorded = "elapsed_recorded"


class RuntimeEventEnvelope(ContractModel):
    schema_version: Literal["dr-runtime-v2"] = "dr-runtime-v2"
    event_id: str
    run_id: str
    stream_sequence: int = Field(ge=1)
    event_type: RuntimeEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    operation_id: str | None = None
    attempt_id: str | None = None
    causal_parent_id: str | None = None
    previous_event_hash: str
    event_hash: str

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "stream_sequence": self.stream_sequence,
            "event_type": self.event_type.value,
            "payload": self.payload,
            "operation_id": self.operation_id,
            "attempt_id": self.attempt_id,
            "causal_parent_id": self.causal_parent_id,
            "previous_event_hash": self.previous_event_hash,
        }

    @model_validator(mode="after")
    def verify(self) -> "RuntimeEventEnvelope":
        payload = self._payload()
        if self.stream_sequence == 1 and self.previous_event_hash != GENESIS_HASH:
            raise ValueError("runtime event genesis mismatch")
        if self.event_id != make_stable_id("runtime", payload):
            raise ValueError("runtime event_id mismatch")
        if self.event_hash != sha256_hex(canonical_json_bytes(payload)):
            raise ValueError("runtime event_hash mismatch")
        return self


def create_runtime_event(
    run_id: str,
    stream_sequence: int,
    event_type: RuntimeEventType,
    *,
    payload: dict[str, Any] | None = None,
    operation_id: str | None = None,
    attempt_id: str | None = None,
    causal_parent_id: str | None = None,
    previous_event_hash: str = GENESIS_HASH,
) -> RuntimeEventEnvelope:
    normalized_payload = json.loads(canonical_json(payload or {}))
    values = {
        "schema_version": "dr-runtime-v2",
        "run_id": run_id,
        "stream_sequence": stream_sequence,
        "event_type": event_type.value,
        "payload": normalized_payload,
        "operation_id": operation_id,
        "attempt_id": attempt_id,
        "causal_parent_id": causal_parent_id,
        "previous_event_hash": previous_event_hash,
    }
    return RuntimeEventEnvelope(
        event_id=make_stable_id("runtime", values),
        event_hash=sha256_hex(canonical_json_bytes(values)),
        run_id=run_id,
        stream_sequence=stream_sequence,
        event_type=event_type,
        payload=normalized_payload,
        operation_id=operation_id,
        attempt_id=attempt_id,
        causal_parent_id=causal_parent_id,
        previous_event_hash=previous_event_hash,
    )


class UnifiedEventStore:
    """Append-only physical stream with one sequence and one authoritative head."""

    def __init__(self, path: Path, *, run_id: str) -> None:
        self.path, self.run_id = Path(path), run_id

    def read_all(self) -> list[RuntimeEventEnvelope]:
        if not self.path.exists():
            return []
        raw = self.path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raise ValueError("runtime event stream has an incomplete final line")
        events: list[RuntimeEventEnvelope] = []
        for line in raw.decode("utf-8").splitlines():
            try:
                events.append(RuntimeEventEnvelope.model_validate_json(line))
            except Exception as exc:
                raise ValueError("runtime event stream is invalid") from exc
        self._verify(events)
        return events

    def append(self, event: RuntimeEventEnvelope) -> None:
        events = self.read_all()
        if event.run_id != self.run_id:
            raise ValueError("runtime event run_id mismatch")
        if any(item.event_id == event.event_id for item in events):
            raise ValueError("duplicate runtime event")
        self._verify(events + [event])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(event.model_dump(mode="json")) + "\n")
            handle.flush()
            import os

            os.fsync(handle.fileno())

    def _verify(self, events: list[RuntimeEventEnvelope]) -> None:
        previous = GENESIS_HASH
        for sequence, event in enumerate(events, 1):
            if event.run_id != self.run_id or event.stream_sequence != sequence:
                raise ValueError("runtime event sequence/run mismatch")
            if event.previous_event_hash != previous:
                raise ValueError("runtime event hash chain mismatch")
            previous = event.event_hash


def _model_hash(model: ContractModel) -> str:
    return sha256_hex(canonical_json_bytes(model.model_dump(mode="json")))


class CoordinatedCheckpointV2(ContractModel):
    schema_version: Literal["dr-runtime-v2"] = "dr-runtime-v2"
    run_id: str
    stream_sequence: int = Field(ge=0)
    stream_head: str
    run_state: RunState
    run_state_hash: str
    ledger: BudgetLedger
    ledger_hash: str
    journal: OperationJournal
    journal_hash: str

    @model_validator(mode="after")
    def verify(self) -> "CoordinatedCheckpointV2":
        expected_head = GENESIS_HASH if self.stream_sequence == 0 else self.stream_head
        if self.run_state.run_id != self.run_id or self.ledger_hash != _model_hash(self.ledger) or self.journal_hash != _model_hash(self.journal):
            raise ValueError("coordinated checkpoint identity/hash mismatch")
        if self.run_state_hash != _model_hash(self.run_state):
            raise ValueError("coordinated checkpoint run state hash mismatch")
        if self.stream_sequence == 0 and expected_head != GENESIS_HASH:
            raise ValueError("coordinated checkpoint genesis mismatch")
        return self

    @classmethod
    def from_result(cls, result: "RuntimeReplayResult") -> "CoordinatedCheckpointV2":
        return cls(
            run_id=result.run_state.run_id,
            stream_sequence=result.stream_sequence,
            stream_head=result.stream_head,
            run_state=result.run_state,
            run_state_hash=_model_hash(result.run_state),
            ledger=result.ledger,
            ledger_hash=_model_hash(result.ledger),
            journal=result.journal,
            journal_hash=_model_hash(result.journal),
        )


def write_coordinated_checkpoint(path: Path, checkpoint: CoordinatedCheckpointV2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical_json(checkpoint.model_dump(mode="json")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def read_coordinated_checkpoint(path: Path) -> CoordinatedCheckpointV2:
    return CoordinatedCheckpointV2.model_validate_json(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class RuntimeReplayResult:
    run_state: RunState
    ledger: BudgetLedger
    journal: OperationJournal
    stream_sequence: int
    stream_head: str
    manual_intervention: ManualInterventionRequired | None = None


def _reservation(ledger: BudgetLedger, attempt_id: str) -> BudgetReservation:
    for item in ledger.reservations:
        if item.attempt_id == attempt_id:
            return item
    raise ValueError("missing durable reservation")


def _reduce_slice(
    initial: RunState,
    events: list[RuntimeEventEnvelope],
    spec: BudgetSpec,
    *,
    ledger: BudgetLedger | None = None,
    journal: OperationJournal | None = None,
    base_sequence: int = 0,
    base_head: str = GENESIS_HASH,
) -> RuntimeReplayResult:
    state = initial
    current_ledger = ledger or BudgetLedger.empty(spec)
    current_journal = journal or OperationJournal.empty()
    for event in events:
        if event.event_type is RuntimeEventType.run_started:
            continue
        if event.event_type is RuntimeEventType.lifecycle_transition:
            lifecycle = RunEvent.model_validate(event.payload)
            state = replay_events(state, [lifecycle])
            continue
        payload = event.payload
        if event.event_type is RuntimeEventType.operation_reserved:
            if not event.operation_id or not event.attempt_id:
                raise ValueError("reserved event identity missing")
            kind = OperationKind(payload["operation_kind"])
            record = OperationRecord(
                operation_id=event.operation_id,
                attempt_id=event.attempt_id,
                kind=kind,
                name=str(payload["operation_name"]),
                attempt_number=int(payload.get("attempt_number", 1)),
                idempotent=bool(payload["idempotent"]),
                side_effecting=bool(payload["side_effecting"]),
            )
            current = current_journal._current(record.operation_id)
            if current is None:
                current_journal = current_journal.add(record)
            elif current.attempt_id != record.attempt_id:
                current_journal = current_journal._update(
                    record.operation_id,
                    current.attempt_id,
                    attempt_id=record.attempt_id,
                    attempt_number=record.attempt_number,
                    status=OperationStatus.planned,
                    error_code=None,
                    result_sha256=None,
                )
            current_ledger, _ = current_ledger.reserve(
                spec,
                operation_id=record.operation_id,
                attempt_id=record.attempt_id,
                kind=kind,
                usage=TokenUsage.model_validate(payload["usage"]),
            )
            current_journal = current_journal.reserve(record.operation_id, record.attempt_id)
        elif event.event_type is RuntimeEventType.operation_dispatched:
            if not event.operation_id or not event.attempt_id:
                raise ValueError("dispatched event identity missing")
            current_journal = current_journal.start(event.operation_id, event.attempt_id)
        elif event.event_type in {RuntimeEventType.operation_succeeded, RuntimeEventType.operation_failed, RuntimeEventType.operation_unknown}:
            if not event.operation_id or not event.attempt_id:
                raise ValueError("outcome event identity missing")
            reservation = _reservation(current_ledger, event.attempt_id)
            usage = TokenUsage.model_validate(payload.get("usage", reservation.usage.model_dump(mode="json")))
            if event.event_type is RuntimeEventType.operation_unknown:
                current_journal = current_journal.mark_unknown(event.operation_id, event.attempt_id, str(payload.get("error_code", "unknown_outcome")))
            else:
                outcome = OperationStatus.succeeded if event.event_type is RuntimeEventType.operation_succeeded else OperationStatus.failed_known
                current_ledger = current_ledger.reconcile(reservation, usage=usage, outcome=outcome, attempt_number=int(payload.get("attempt_number", 1)), spec=spec)
                if outcome is OperationStatus.succeeded:
                    current_journal = current_journal.mark_succeeded(event.operation_id, event.attempt_id, payload.get("result_sha256"))
                else:
                    current_journal = current_journal.mark_failed(event.operation_id, event.attempt_id, str(payload.get("error_code", "tool_failure")))
        elif event.event_type is RuntimeEventType.operation_cancelled:
            if not event.operation_id or not event.attempt_id:
                raise ValueError("cancel event identity missing")
            if current_journal._current(event.operation_id) is None:
                current_journal = current_journal.add(
                    OperationRecord(
                        operation_id=event.operation_id,
                        attempt_id=event.attempt_id,
                        kind=OperationKind(payload["operation_kind"]),
                        name=str(payload["operation_name"]),
                        attempt_number=int(payload.get("attempt_number", 1)),
                        idempotent=bool(payload.get("idempotent", True)),
                        side_effecting=bool(payload.get("side_effecting", False)),
                    )
                )
            current_journal = current_journal.cancel_before_dispatch(event.operation_id, event.attempt_id)
        elif event.event_type is RuntimeEventType.retry_scheduled:
            if not event.operation_id or not event.attempt_id:
                raise ValueError("retry event identity missing")
            if int(payload["next_attempt_number"]) < 2:
                raise ValueError("retry event attempt number invalid")
        elif event.event_type is RuntimeEventType.replan_decided:
            if bool(payload["admitted"]):
                current_ledger = current_ledger.record_replan(spec)
        elif event.event_type is RuntimeEventType.elapsed_recorded:
            current_ledger = current_ledger.record_elapsed(float(payload["elapsed_s"]))
        else:
            raise ValueError(f"unsupported runtime event type: {event.event_type}")

    head = events[-1].event_hash if events else base_head
    return RuntimeReplayResult(state, current_ledger, current_journal, base_sequence + len(events), head)


def _validate_runtime_events(initial: RunState, events: list[RuntimeEventEnvelope]) -> None:
    previous = GENESIS_HASH
    for sequence, event in enumerate(events, 1):
        try:
            RuntimeEventEnvelope.model_validate(event.model_dump(mode="json"))
        except Exception as exc:
            raise ValueError("runtime event envelope validation failed") from exc
        if event.run_id != initial.run_id or event.stream_sequence != sequence or event.previous_event_hash != previous:
            raise ValueError("runtime stream sequence/hash mismatch")
        previous = event.event_hash


def reduce_runtime_events(
    initial: RunState,
    events: tuple[RuntimeEventEnvelope, ...] | list[RuntimeEventEnvelope],
    spec: BudgetSpec,
) -> RuntimeReplayResult:
    """Reduce only durable facts; a prefix never infers a missing outcome."""
    ordered = list(events)
    _validate_runtime_events(initial, ordered)
    return _reduce_slice(initial, ordered, spec)


def _manual_intervention(initial: RunState, record: OperationRecord, events: list[RuntimeEventEnvelope]) -> ManualInterventionRequired:
    last_event = next((event for event in reversed(events) if event.operation_id == record.operation_id and event.attempt_id == record.attempt_id), None)
    if last_event is None:
        raise ValueError("unknown operation has no causal event")
    return ManualInterventionRequired(
        run_id=initial.run_id,
        operation_id=record.operation_id,
        attempt_id=record.attempt_id,
        last_event_id=last_event.event_id,
        reservation_present=True,
        snapshot={
            "operation_id": record.operation_id,
            "attempt_id": record.attempt_id,
            "last_event_id": last_event.event_id,
            "last_event_type": last_event.event_type.value,
            "causal_parent_id": last_event.causal_parent_id or "",
            "stream_sequence": str(last_event.stream_sequence),
        },
    )


def _finalize_stream_end(initial: RunState, reduced: RuntimeReplayResult, events: list[RuntimeEventEnvelope]) -> RuntimeReplayResult:
    """Derive the conservative view only after the complete authoritative stream ends."""
    journal = reduced.journal
    manual: ManualInterventionRequired | None = None
    for record in tuple(journal.records):
        if record.status is OperationStatus.started:
            _reservation(reduced.ledger, record.attempt_id)
            journal = journal.mark_unknown(record.operation_id, record.attempt_id, "unknown_outcome")
            record = journal._current(record.operation_id)
            assert record is not None
            manual = _manual_intervention(initial, record, events)
        elif record.status is OperationStatus.outcome_unknown:
            manual = _manual_intervention(initial, record, events)
    return RuntimeReplayResult(reduced.run_state, reduced.ledger, journal, reduced.stream_sequence, reduced.stream_head, manual)


def replay_runtime_events(
    initial: RunState,
    events: tuple[RuntimeEventEnvelope, ...] | list[RuntimeEventEnvelope],
    spec: BudgetSpec,
    *,
    checkpoint: CoordinatedCheckpointV2 | None = None,
) -> RuntimeReplayResult:
    ordered = list(events)
    _validate_runtime_events(initial, ordered)
    if checkpoint is None:
        return _finalize_stream_end(initial, _reduce_slice(initial, ordered, spec), ordered)
    try:
        checkpoint = CoordinatedCheckpointV2.model_validate(checkpoint.model_dump(mode="json"))
    except Exception as exc:
        raise ValueError("coordinated checkpoint validation failed") from exc
    if checkpoint.run_id != initial.run_id or checkpoint.stream_sequence > len(ordered):
        raise ValueError("coordinated checkpoint mismatch")
    prefix = _reduce_slice(initial, ordered[: checkpoint.stream_sequence], spec)
    if prefix.stream_head != checkpoint.stream_head or prefix.run_state != checkpoint.run_state or prefix.ledger != checkpoint.ledger or prefix.journal != checkpoint.journal:
        raise ValueError("coordinated checkpoint content mismatch")
    reduced = _reduce_slice(
        prefix.run_state,
        ordered[checkpoint.stream_sequence :],
        spec,
        ledger=prefix.ledger,
        journal=prefix.journal,
        base_sequence=checkpoint.stream_sequence,
        base_head=checkpoint.stream_head,
    )
    return _finalize_stream_end(initial, reduced, ordered)


class CrashPoint(str, Enum):
    after_reserved = "after_reserved"
    after_dispatched = "after_dispatched"
    after_provider_call = "after_provider_call"
    after_success_before_checkpoint = "after_success_before_checkpoint"


class DispatchInterrupted(RuntimeError):
    pass


@dataclass(frozen=True)
class CrashSafeResult:
    terminal: str
    error_code: ErrorCode | None
    run_state: RunState
    ledger: BudgetLedger
    journal: OperationJournal
    events: tuple[RuntimeEventEnvelope, ...]
    external_call_count: int
    checkpoint: CoordinatedCheckpointV2 | None
    initial_state: RunState
    spec: BudgetSpec
    effective_timeout_samples: tuple[float, ...] = ()
    manual_intervention: ManualInterventionRequired | None = None

    @property
    def run_id(self) -> str:
        return self.run_state.run_id


class _InvocationTarget(Protocol):
    async def call(self, *, operation_id: str, attempt_id: str, request: Any, timeout_s: float | None = None, **kwargs: Any) -> Any: ...


class _OperationInvoker:
    """Internal call primitive; CrashSafeFakeHarness owns the durable protocol."""

    def __init__(self, provider: _InvocationTarget, tool: _InvocationTarget) -> None:
        self.provider, self.tool = provider, tool

    async def dispatch(self, operation: Any, *, attempt_id: str, timeout_s: float, **kwargs: Any) -> Any:
        caller = self.provider.call if operation.kind is OperationKind.provider else self.tool.call
        return await caller(
            operation_id=operation.operation_id,
            attempt_id=attempt_id,
            request={"operation": operation.name},
            timeout_s=timeout_s,
            **kwargs,
        )


class CrashSafeFakeHarness:
    """The only formal B03R Fake execution path; provider/tool calls occur inside dispatch."""

    def __init__(self, scenario: str, path: Path | None = None, *, spec: BudgetSpec | None = None, clock: Any | None = None, token: CancellationToken | None = None, backoff_seconds: tuple[float, ...] = ()) -> None:
        self.scenario = scenario
        self.operations = scenario_operations(scenario)
        self.spec = spec or BudgetSpec(max_provider_attempts=4, max_provider_calls=4, max_tool_attempts=4, max_tool_calls=4, max_total_tokens=100, max_replans=1, run_timeout_s=10.0, operation_timeout_s=1.0)
        self.clock = clock or FakeClock()
        self.token = token or CancellationToken()
        self.retry = RetryPolicy(max_attempts=2, backoff_seconds=backoff_seconds)
        self.replan = ReplanPolicy(max_replans=self.spec.max_replans)
        self.initial_state = RunState.create(task_id="dr-task-" + "a" * 24, brief_id="dr-brief-" + "b" * 24, brief_approved=True)
        self.run_id = self.initial_state.run_id
        self.provider = FakeProvider(self.operations, self.clock)
        self.tool = FakeTool(self.operations, self.clock)
        self._invoker = _OperationInvoker(self.provider, self.tool)
        self._tempdir = tempfile.TemporaryDirectory() if path is None else None
        self.path = Path(path) if path is not None else Path(self._tempdir.name) / "runtime.jsonl"

    def _append(self, store: UnifiedEventStore, events: list[RuntimeEventEnvelope], event_type: RuntimeEventType, *, payload: dict[str, Any] | None = None, operation_id: str | None = None, attempt_id: str | None = None, causal_parent_id: str | None = None) -> RuntimeEventEnvelope:
        event = create_runtime_event(self.run_id, len(events) + 1, event_type, payload=payload, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=causal_parent_id, previous_event_hash=events[-1].event_hash if events else GENESIS_HASH)
        store.append(event)
        events.append(event)
        return event

    def _lifecycle(self, store: UnifiedEventStore, events: list[RuntimeEventEnvelope], state: RunState, target: RunStatus, reason: str | None = None) -> RunState:
        next_state, lifecycle = transition(state, target, reason=reason)
        self._append(store, events, RuntimeEventType.lifecycle_transition, payload=lifecycle.model_dump(mode="json"), causal_parent_id=events[-1].event_id if events else None)
        return next_state

    def _elapsed(self, store: UnifiedEventStore, events: list[RuntimeEventEnvelope], origin: float, *, backoff_s: float = 0.0) -> float:
        elapsed = max(0.0, self.clock.monotonic() - origin)
        self._append(store, events, RuntimeEventType.elapsed_recorded, payload={"elapsed_s": elapsed, "backoff_s": backoff_s})
        return elapsed

    def run(self, *, crash_at: CrashPoint | None = None) -> CrashSafeResult:
        store = UnifiedEventStore(self.path, run_id=self.run_id)
        events = store.read_all()
        if events:
            started = next((event for event in events if event.event_type is RuntimeEventType.run_started), None)
            if started and started.payload.get("spec"):
                self.spec = BudgetSpec.model_validate(started.payload["spec"])
                self.replan = ReplanPolicy(max_replans=self.spec.max_replans)
            if started and started.payload.get("backoff_seconds") is not None:
                self.retry = RetryPolicy(max_attempts=2, backoff_seconds=tuple(float(item) for item in started.payload["backoff_seconds"]))
            origin = float(started.payload.get("clock_origin", self.clock.monotonic())) if started else self.clock.monotonic()
            deadline = float(started.payload["run_deadline"]) if started and started.payload.get("run_deadline") is not None else None
            persisted_elapsed = max((float(event.payload.get("elapsed_s", 0.0)) for event in events if event.event_type is RuntimeEventType.elapsed_recorded), default=0.0)
            target_clock = origin + persisted_elapsed
            if self.clock.monotonic() < target_clock:
                self.clock.advance(target_clock - self.clock.monotonic())
        else:
            origin = self.clock.monotonic()
            deadline = origin + self.spec.run_timeout_s if self.spec.run_timeout_s is not None else None
            self._append(store, events, RuntimeEventType.run_started, payload={"clock_origin": origin, "run_deadline": deadline, "spec": self.spec.model_dump(mode="json"), "backoff_seconds": list(self.retry.backoff_seconds)})
        replayed = replay_runtime_events(self.initial_state, events, self.spec)
        state, ledger, journal = replayed.run_state, replayed.ledger, replayed.journal
        if not events or state.status is RunStatus.brief_pending:
            state = self._lifecycle(store, events, state, RunStatus.brief_approved)
            state = self._lifecycle(store, events, state, RunStatus.researching)
        effective_samples: list[float] = []
        terminal = "complete"
        error_code = None
        for operation in self.operations:
            current = journal._current(operation.operation_id)
            if current and current.status is OperationStatus.succeeded:
                succeeded = next(
                    (
                        event
                        for event in reversed(events)
                        if event.event_type is RuntimeEventType.operation_succeeded
                        and event.operation_id == operation.operation_id
                        and event.attempt_id == current.attempt_id
                    ),
                    None,
                )
                needs_replan = bool(succeeded) and (
                    succeeded.payload.get("status") == "abstain"
                    or (self.scenario == "insufficient_evidence" and not succeeded.payload.get("result_sha256"))
                )
                decision_exists = any(
                    event.event_type is RuntimeEventType.replan_decided
                    and event.causal_parent_id == (succeeded.event_id if succeeded else None)
                    for event in events
                )
                if needs_replan and not decision_exists:
                    decision = self.replan.admit(
                        ordinal=ledger.replans,
                        old_plan_id="dr-plan-old" if ledger.replans == 0 else "dr-plan-new",
                        proposed_plan_id="dr-plan-new" if ledger.replans == 0 else "dr-plan-final",
                        reason="grounding_rejected",
                    )
                    self._append(
                        store,
                        events,
                        RuntimeEventType.replan_decided,
                        payload=decision.model_dump(mode="json"),
                        causal_parent_id=succeeded.event_id,
                    )
                    if not decision.admitted:
                        terminal, error_code = "insufficient_evidence", "budget_exhausted"
                        break
                    ledger = ledger.record_replan(self.spec)
                    if self.scenario == "insufficient_evidence":
                        terminal, error_code = "insufficient_evidence", "grounding_rejected"
                        break
                continue
            if current and current.status is OperationStatus.outcome_unknown:
                terminal, error_code = "failed", "unknown_outcome"
                break
            if current and current.status is OperationStatus.started:
                terminal, error_code = "failed", "unknown_outcome"
                break
            if self.token.cancelled:
                if current is None:
                    record = journal.plan(operation_id=operation.operation_id, kind=operation.kind, name=operation.name, idempotent=operation.idempotent, side_effecting=operation.side_effecting)
                    journal = journal.add(record)
                    journal = journal.cancel_before_dispatch(record.operation_id, record.attempt_id)
                    self._append(store, events, RuntimeEventType.operation_cancelled, payload={"operation_kind": operation.kind.value, "operation_name": operation.name, "attempt_number": 1, "idempotent": operation.idempotent, "side_effecting": operation.side_effecting}, operation_id=record.operation_id, attempt_id=record.attempt_id)
                terminal, error_code = "failed", "cancelled"
                break
            if deadline is not None and self.clock.monotonic() >= deadline:
                terminal, error_code = "failed", "run_deadline_exceeded"
                break
            if current and current.status is OperationStatus.failed_known:
                remaining = (deadline - self.clock.monotonic()) if deadline is not None else None
                if not current.error_code or not self.retry.allows(current.error_code, attempt_number=current.attempt_number, remaining_s=remaining, cancelled=self.token.cancelled):
                    terminal, error_code = "failed", current.error_code or "tool_failure"
                    break
                next_attempt_number = current.attempt_number + 1
                next_attempt = make_stable_id("attempt", {"operation_id": operation.operation_id, "attempt_number": next_attempt_number})
                schedule = next(
                    (
                        event
                        for event in events
                        if event.event_type is RuntimeEventType.retry_scheduled
                        and event.operation_id == operation.operation_id
                        and event.attempt_id == current.attempt_id
                        and event.payload.get("next_attempt_id") == next_attempt
                    ),
                    None,
                )
                if schedule is None:
                    delay = self.retry.delay_for(current.attempt_number)
                    self._append(
                        store,
                        events,
                        RuntimeEventType.retry_scheduled,
                        payload={
                            "error_code": current.error_code,
                            "backoff_s": delay,
                            "next_attempt_id": next_attempt,
                            "next_attempt_number": next_attempt_number,
                        },
                        operation_id=operation.operation_id,
                        attempt_id=current.attempt_id,
                    )
                    self.clock.advance(delay)
                    self._elapsed(store, events, origin, backoff_s=delay)
                else:
                    delay = float(schedule.payload.get("backoff_s", 0.0))
                    schedule_index = events.index(schedule)
                    backoff_recorded = any(
                        event.event_type is RuntimeEventType.elapsed_recorded
                        and event.stream_sequence > schedule.stream_sequence
                        and float(event.payload.get("backoff_s", 0.0)) == delay
                        for event in events[schedule_index + 1 :]
                    )
                    if not backoff_recorded and delay:
                        self.clock.advance(delay)
                        self._elapsed(store, events, origin, backoff_s=delay)
                next_usage = operation.attempts[next_attempt_number - 1].usage
                ledger, _ = ledger.reserve(
                    self.spec,
                    operation_id=operation.operation_id,
                    attempt_id=next_attempt,
                    kind=operation.kind,
                    usage=next_usage,
                )
                journal = journal._update(
                    operation.operation_id,
                    current.attempt_id,
                    attempt_id=next_attempt,
                    attempt_number=next_attempt_number,
                    status=OperationStatus.reserved,
                    error_code=None,
                    result_sha256=None,
                )
                if not any(event.event_type is RuntimeEventType.operation_reserved and event.attempt_id == next_attempt for event in events):
                    self._append(
                        store,
                        events,
                        RuntimeEventType.operation_reserved,
                        payload={
                            "operation_kind": operation.kind.value,
                            "operation_name": operation.name,
                            "attempt_number": next_attempt_number,
                            "idempotent": operation.idempotent,
                            "side_effecting": operation.side_effecting,
                            "usage": next_usage.model_dump(mode="json"),
                        },
                        operation_id=operation.operation_id,
                        attempt_id=next_attempt,
                    )
                current = journal._current(operation.operation_id)
            if current is None:
                record = journal.plan(operation_id=operation.operation_id, kind=operation.kind, name=operation.name, idempotent=operation.idempotent, side_effecting=operation.side_effecting)
                journal = journal.add(record)
                usage = operation.attempts[0].usage
                ledger, _ = ledger.reserve(self.spec, operation_id=record.operation_id, attempt_id=record.attempt_id, kind=operation.kind, usage=usage)
                journal = journal.reserve(record.operation_id, record.attempt_id)
                self._append(store, events, RuntimeEventType.operation_reserved, payload={"operation_kind": operation.kind.value, "operation_name": operation.name, "attempt_number": 1, "idempotent": operation.idempotent, "side_effecting": operation.side_effecting, "usage": usage.model_dump(mode="json")}, operation_id=record.operation_id, attempt_id=record.attempt_id, causal_parent_id=events[-1].event_id if events else None)
                current = record.model_copy(update={"status": OperationStatus.reserved})
                if crash_at is CrashPoint.after_reserved:
                    raise DispatchInterrupted("interrupted after durable reservation")
            for attempt_number, scripted in enumerate(operation.attempts, current.attempt_number if current else 1):
                current = journal._current(operation.operation_id)
                if current is None:
                    raise ValueError("operation journal lost current record")
                attempt_id = make_stable_id("attempt", {"operation_id": operation.operation_id, "attempt_number": attempt_number})
                if attempt_number > current.attempt_number:
                    journal = journal._update(operation.operation_id, current.attempt_id, attempt_id=attempt_id, attempt_number=attempt_number, status=OperationStatus.planned)
                else:
                    attempt_id = current.attempt_id
                reservation = _reservation(ledger, attempt_id)
                remaining = (deadline - self.clock.monotonic()) if deadline is not None else float("inf")
                if remaining <= 0:
                    terminal, error_code = "failed", "run_deadline_exceeded"
                    break
                configured = self.spec.operation_timeout_s if self.spec.operation_timeout_s is not None else remaining
                effective_timeout = min(configured, remaining)
                effective_samples.append(effective_timeout)
                journal = journal.start(operation.operation_id, attempt_id)
                parent = next((item.event_id for item in reversed(events) if item.operation_id == operation.operation_id and item.attempt_id == attempt_id), None)
                dispatched_event = self._append(store, events, RuntimeEventType.operation_dispatched, payload={"operation_kind": operation.kind.value, "operation_name": operation.name, "attempt_number": attempt_number, "effective_timeout_s": effective_timeout}, operation_id=operation.operation_id, attempt_id=attempt_id, causal_parent_id=parent)
                if crash_at is CrashPoint.after_dispatched:
                    raise DispatchInterrupted("interrupted after durable dispatch")
                response = asyncio.run(self._invoker.dispatch(operation, attempt_id=attempt_id, timeout_s=effective_timeout))
                if crash_at is CrashPoint.after_provider_call:
                    raise DispatchInterrupted("interrupted after provider/tool call")
                usage = response.usage
                if response.status == "unknown":
                    self._append(store, events, RuntimeEventType.operation_unknown, payload={"error_code": "unknown_outcome", "attempt_number": attempt_number, "usage": usage.model_dump(mode="json")}, operation_id=operation.operation_id, attempt_id=attempt_id, causal_parent_id=dispatched_event.event_id)
                    journal = journal.mark_unknown(operation.operation_id, attempt_id, "unknown_outcome")
                    terminal, error_code = "failed", "unknown_outcome"
                    self._elapsed(store, events, origin)
                    break
                if response.status in {"success", "abstain"}:
                    succeeded_event = self._append(store, events, RuntimeEventType.operation_succeeded, payload={"attempt_number": attempt_number, "status": response.status, "usage": usage.model_dump(mode="json"), "result_sha256": sha256_hex(response.content)}, operation_id=operation.operation_id, attempt_id=attempt_id, causal_parent_id=dispatched_event.event_id)
                    ledger = ledger.reconcile(reservation, usage=usage, outcome=OperationStatus.succeeded, attempt_number=attempt_number, spec=self.spec)
                    journal = journal.mark_succeeded(operation.operation_id, attempt_id, sha256_hex(response.content))
                    self._elapsed(store, events, origin)
                    if crash_at is CrashPoint.after_success_before_checkpoint:
                        raise DispatchInterrupted("interrupted after success event")
                    needs_replan = response.status == "abstain" or (self.scenario == "insufficient_evidence" and not response.content)
                    if needs_replan and self.scenario in {"insufficient_evidence", "single_replan_success", "replan_limit_exceeded"}:
                        decision = self.replan.admit(
                            ordinal=ledger.replans,
                            old_plan_id="dr-plan-old" if ledger.replans == 0 else "dr-plan-new",
                            proposed_plan_id="dr-plan-new" if ledger.replans == 0 else "dr-plan-final",
                            reason="grounding_rejected",
                        )
                        self._append(
                            store,
                            events,
                            RuntimeEventType.replan_decided,
                            payload=decision.model_dump(mode="json"),
                            causal_parent_id=succeeded_event.event_id,
                        )
                        if not decision.admitted:
                            terminal, error_code = "insufficient_evidence", "budget_exhausted"
                            break
                        ledger = ledger.record_replan(self.spec)
                        if self.scenario == "insufficient_evidence":
                            terminal, error_code = "insufficient_evidence", "grounding_rejected"
                            break
                    break
                code = response.error_code.value if response.error_code else "tool_failure"
                self._append(store, events, RuntimeEventType.operation_failed, payload={"error_code": code, "attempt_number": attempt_number, "usage": usage.model_dump(mode="json")}, operation_id=operation.operation_id, attempt_id=attempt_id, causal_parent_id=dispatched_event.event_id)
                ledger = ledger.reconcile(reservation, usage=usage, outcome=OperationStatus.failed_known, attempt_number=attempt_number, spec=self.spec)
                journal = journal.mark_failed(operation.operation_id, attempt_id, code)
                self._elapsed(store, events, origin)
                if not self.retry.allows(code, attempt_number=attempt_number, remaining_s=(deadline - self.clock.monotonic()) if deadline is not None else None, cancelled=self.token.cancelled):
                    terminal, error_code = "failed", code
                    break
                delay = self.retry.delay_for(attempt_number)
                if deadline is not None and self.clock.monotonic() + delay >= deadline:
                    terminal, error_code = "failed", "run_deadline_exceeded"
                    break
                next_attempt_number = attempt_number + 1
                next_attempt = make_stable_id("attempt", {"operation_id": operation.operation_id, "attempt_number": next_attempt_number})
                self._append(
                    store,
                    events,
                    RuntimeEventType.retry_scheduled,
                    payload={
                        "error_code": code,
                        "backoff_s": delay,
                        "next_attempt_id": next_attempt,
                        "next_attempt_number": next_attempt_number,
                    },
                    operation_id=operation.operation_id,
                    attempt_id=attempt_id,
                )
                self.clock.advance(delay)
                self._elapsed(store, events, origin, backoff_s=delay)
                if attempt_number + 1 <= len(operation.attempts):
                    next_usage = operation.attempts[attempt_number].usage
                    ledger, _ = ledger.reserve(self.spec, operation_id=operation.operation_id, attempt_id=next_attempt, kind=operation.kind, usage=next_usage)
                    journal = journal._update(operation.operation_id, attempt_id, attempt_id=next_attempt, attempt_number=attempt_number + 1, status=OperationStatus.reserved)
                    self._append(
                        store,
                        events,
                        RuntimeEventType.operation_reserved,
                        payload={
                            "operation_kind": operation.kind.value,
                            "operation_name": operation.name,
                            "attempt_number": attempt_number + 1,
                            "idempotent": operation.idempotent,
                            "side_effecting": operation.side_effecting,
                            "usage": next_usage.model_dump(mode="json"),
                        },
                        operation_id=operation.operation_id,
                        attempt_id=next_attempt,
                    )
            if terminal != "complete":
                break
        if terminal == "complete":
            if state.status is RunStatus.researching:
                state = self._lifecycle(store, events, state, RunStatus.validating)
                state = self._lifecycle(store, events, state, RunStatus.complete)
        elif terminal == "insufficient_evidence":
            if state.status is RunStatus.researching:
                state = self._lifecycle(store, events, state, RunStatus.insufficient_evidence, reason=str(error_code))
        else:
            if state.status is RunStatus.researching:
                state = self._lifecycle(store, events, state, RunStatus.failed, reason=str(error_code))
        final_events = tuple(store.read_all())
        replayed = replay_runtime_events(self.initial_state, final_events, self.spec)
        checkpoint = CoordinatedCheckpointV2.from_result(reduce_runtime_events(self.initial_state, final_events, self.spec))
        write_coordinated_checkpoint(self.path.with_suffix(".checkpoint.json"), checkpoint)
        typed_error = ErrorCode(error_code) if error_code is not None else None
        return CrashSafeResult(terminal, typed_error, replayed.run_state, replayed.ledger, replayed.journal, final_events, sum(item.event_type is RuntimeEventType.operation_dispatched for item in final_events), checkpoint, self.initial_state, self.spec, tuple(effective_samples), replayed.manual_intervention)

    def resume(self) -> CrashSafeResult:
        return CrashSafeFakeHarness(self.scenario, self.path, spec=self.spec, backoff_seconds=self.retry.backoff_seconds).run()
