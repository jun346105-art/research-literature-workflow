"""Stable operation and attempt journal contracts."""
from __future__ import annotations

from enum import Enum

from pydantic import Field

from .contracts import ContractModel
from .identity import make_stable_id


class OperationKind(str, Enum):
    provider = "provider"
    tool = "tool"


class OperationStatus(str, Enum):
    planned = "planned"
    reserved = "reserved"
    started = "started"
    succeeded = "succeeded"
    failed_known = "failed_known"
    outcome_unknown = "outcome_unknown"
    cancelled_before_dispatch = "cancelled_before_dispatch"


class OperationRecord(ContractModel):
    operation_id: str
    attempt_id: str
    kind: OperationKind
    name: str = Field(min_length=1)
    attempt_number: int = Field(default=1, ge=1)
    status: OperationStatus = OperationStatus.planned
    idempotent: bool
    side_effecting: bool
    error_code: str | None = None
    result_sha256: str | None = None


class OperationJournal(ContractModel):
    records: tuple[OperationRecord, ...] = ()

    @classmethod
    def empty(cls) -> "OperationJournal":
        return cls()

    def plan(self, *, operation_id: str | None = None, kind: OperationKind, name: str, idempotent: bool, side_effecting: bool) -> OperationRecord:
        if operation_id is None:
            operation_id = make_stable_id("operation", {"kind": kind.value, "name": name})
        existing = self._current(operation_id)
        if existing is not None:
            return existing
        attempt_id = make_stable_id("attempt", {"operation_id": operation_id, "attempt_number": 1})
        record = OperationRecord(operation_id=operation_id, attempt_id=attempt_id, kind=kind, name=name, idempotent=idempotent, side_effecting=side_effecting)
        return record

    def add(self, record: OperationRecord) -> "OperationJournal":
        if self._current(record.operation_id) is not None:
            raise ValueError("operation already planned")
        return self.model_copy(update={"records": self.records + (record,)})

    def plan_and_add(self, *, operation_id: str | None = None, kind: OperationKind, name: str, idempotent: bool, side_effecting: bool) -> tuple["OperationJournal", OperationRecord]:
        record = self.plan(operation_id=operation_id, kind=kind, name=name, idempotent=idempotent, side_effecting=side_effecting)
        return self if self._current(record.operation_id) is not None else self.add(record), record

    def _current(self, operation_id: str) -> OperationRecord | None:
        for item in reversed(self.records):
            if item.operation_id == operation_id:
                return item
        return None

    def _update(self, operation_id: str, current_attempt_id: str, **changes: object) -> "OperationJournal":
        current = self._current(operation_id)
        if current is None or current.attempt_id != current_attempt_id:
            raise ValueError("unknown operation attempt")
        updated = current.model_copy(update=changes)
        records = tuple(updated if item is current else item for item in self.records)
        return self.model_copy(update={"records": records})

    def start(self, operation_id: str, attempt_id: str) -> "OperationJournal":
        current = self._current(operation_id)
        if current is None or current.attempt_id != attempt_id:
            raise ValueError("unknown operation attempt")
        if current.status not in {OperationStatus.planned, OperationStatus.reserved}:
            raise ValueError("operation is not dispatchable")
        return self._update(operation_id, attempt_id, status=OperationStatus.started)

    def reserve(self, operation_id: str, attempt_id: str) -> "OperationJournal":
        current = self._current(operation_id)
        if current is None or current.attempt_id != attempt_id:
            raise ValueError("unknown operation attempt")
        if current.status is OperationStatus.reserved:
            return self
        if current.status is not OperationStatus.planned:
            raise ValueError("operation is not reservable")
        return self._update(operation_id, attempt_id, status=OperationStatus.reserved)

    def mark_succeeded(self, operation_id: str, attempt_id: str, result_sha256: str | None = None) -> "OperationJournal":
        return self._update(operation_id, attempt_id, status=OperationStatus.succeeded, result_sha256=result_sha256, error_code=None)

    def mark_failed(self, operation_id: str, attempt_id: str, error_code: str) -> "OperationJournal":
        return self._update(operation_id, attempt_id, status=OperationStatus.failed_known, error_code=error_code)

    def mark_unknown(self, operation_id: str, attempt_id: str, error_code: str) -> "OperationJournal":
        return self._update(operation_id, attempt_id, status=OperationStatus.outcome_unknown, error_code=error_code)

    def cancel_before_dispatch(self, operation_id: str, attempt_id: str) -> "OperationJournal":
        current = self._current(operation_id)
        if current is None or current.attempt_id != attempt_id or current.status is not OperationStatus.planned:
            raise ValueError("operation is already dispatched")
        return self._update(operation_id, attempt_id, status=OperationStatus.cancelled_before_dispatch)

    def can_resume(self, operation_id: str) -> bool:
        current = self._current(operation_id)
        if current is None:
            raise ValueError("unknown operation")
        if current.status in {OperationStatus.succeeded, OperationStatus.cancelled_before_dispatch}:
            return False
        if current.status is OperationStatus.outcome_unknown and (current.side_effecting or not current.idempotent):
            return False
        return current.status in {OperationStatus.planned, OperationStatus.reserved, OperationStatus.failed_known}

    def resume_decision(self, operation_id: str) -> str:
        current = self._current(operation_id)
        if current is None:
            raise ValueError("unknown operation")
        if current.status is OperationStatus.outcome_unknown:
            return "manual_review_required"
        if current.status is OperationStatus.started:
            return "manual_review_required"
        if current.status in {OperationStatus.succeeded, OperationStatus.cancelled_before_dispatch}:
            return "do_not_execute"
        return "retry_allowed"
