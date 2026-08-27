"""Deterministic replay of previously validated lifecycle events."""
from __future__ import annotations
from decimal import Decimal
from .events import GENESIS_HASH, PolicyEvent, PolicyEventType, RunEvent
from .budgets import BudgetLedger, BudgetSpec, TokenUsage
from .errors import ErrorCode
from .operations import OperationJournal, OperationKind, OperationRecord, OperationStatus
from .persistence import Checkpoint
from .state import RunState,RunStatus,next_state

def replay_events(initial:RunState,events:tuple[RunEvent,...]|list[RunEvent])->RunState:
    state=initial
    for event in events:
        if event.run_id!=state.run_id: raise ValueError("event run_id mismatch")
        if event.sequence!=state.applied_event_count+1: raise ValueError("event sequence mismatch")
        if event.previous_event_hash!=(state.event_head or "0"*64): raise ValueError("event chain mismatch")
        if event.from_status is not state.status: raise ValueError("event from_status mismatch")
        candidate=next_state(state,event.to_status,event.terminal_reason)
        state=candidate.model_copy(update={"applied_event_count":event.sequence,"event_head":event.event_hash})
    return state
def recover_state(initial:RunState,events:tuple[RunEvent,...]|list[RunEvent],checkpoint:Checkpoint|None=None)->RunState:
    if checkpoint is None: return replay_events(initial,events)
    if checkpoint.run_id!=initial.run_id or checkpoint.applied_sequence>len(events): raise ValueError("checkpoint mismatch")
    prefix=replay_events(initial,events[:checkpoint.applied_sequence])
    if prefix!=checkpoint.state or (checkpoint.applied_sequence and checkpoint.event_head!=events[checkpoint.applied_sequence-1].event_hash): raise ValueError("checkpoint mismatch")
    return replay_events(checkpoint.state,events[checkpoint.applied_sequence:])


def replay_policy_events(events: tuple[PolicyEvent, ...] | list[PolicyEvent], spec: BudgetSpec, *, ledger: BudgetLedger | None = None, journal: OperationJournal | None = None) -> tuple[BudgetLedger, OperationJournal]:
    current_ledger = ledger or BudgetLedger.empty(spec)
    current_journal = journal or OperationJournal.empty()
    for position, event in enumerate(events, 1):
        if event.sequence != position:
            raise ValueError("policy event sequence mismatch")
        if event.previous_event_hash != (GENESIS_HASH if position == 1 else events[position - 2].event_hash):
            raise ValueError("policy event hash chain mismatch")
        if event.event_type is PolicyEventType.operation_planned:
            if not event.operation_id or not event.attempt_id or not event.operation_kind or not event.operation_name:
                raise ValueError("operation_planned event is incomplete")
            record = OperationRecord(operation_id=event.operation_id, attempt_id=event.attempt_id, kind=OperationKind(event.operation_kind), name=event.operation_name, attempt_number=event.attempt_number or 1, idempotent=event.idempotent if event.idempotent is not None else True, side_effecting=event.side_effecting if event.side_effecting is not None else False)
            if current_journal._current(record.operation_id) is None:
                current_journal = current_journal.add(record)
        elif event.event_type is PolicyEventType.operation_started:
            if event.operation_id and event.attempt_id:
                current = current_journal._current(event.operation_id)
                if current is not None and current.attempt_id != event.attempt_id:
                    current_journal = current_journal._update(event.operation_id, current.attempt_id, attempt_id=event.attempt_id, attempt_number=event.attempt_number or current.attempt_number, status=OperationStatus.planned)
                current_journal = current_journal.start(event.operation_id, event.attempt_id)
        elif event.event_type is PolicyEventType.operation_succeeded:
            if event.operation_id and event.attempt_id:
                current_journal = current_journal.mark_succeeded(event.operation_id, event.attempt_id, event.result_sha256)
        elif event.event_type is PolicyEventType.operation_failed:
            if event.operation_id and event.attempt_id:
                current_journal = current_journal.mark_failed(event.operation_id, event.attempt_id, event.error_code or ErrorCode.tool_failure.value)
        elif event.event_type is PolicyEventType.operation_unknown:
            if event.operation_id and event.attempt_id:
                current_journal = current_journal.mark_unknown(event.operation_id, event.attempt_id, event.error_code or ErrorCode.unknown_outcome.value)
        elif event.event_type is PolicyEventType.attempt_charged:
            if not event.operation_id or not event.attempt_id or not event.operation_kind or not event.operation_status:
                raise ValueError("attempt_charged event is incomplete")
            current_ledger = current_ledger.charge_attempt(spec, operation_id=event.operation_id, attempt_id=event.attempt_id, kind=event.operation_kind, usage=TokenUsage(input_tokens=event.input_tokens, output_tokens=event.output_tokens, cost_micros=Decimal(event.cost_micros)), outcome=event.operation_status, attempt_number=event.attempt_number or 1)
        elif event.event_type is PolicyEventType.replan_decided and event.admitted:
            current_ledger = current_ledger.record_replan(spec)
        elif event.event_type is PolicyEventType.elapsed_recorded and event.elapsed_s is not None:
            current_ledger = current_ledger.record_elapsed(event.elapsed_s)
    return current_ledger, current_journal
