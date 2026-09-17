"""Immutable, replay-friendly execution budgets and ledger."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import Field, model_validator

from .contracts import ContractModel
from .errors import ErrorCode

if TYPE_CHECKING:
    from .operations import OperationKind, OperationStatus


class TokenUsage(ContractModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost_micros: Decimal = Field(default=Decimal("0"), ge=0)

    @model_validator(mode="before")
    @classmethod
    def normalize_total(cls, values: object) -> object:
        if not isinstance(values, dict):
            return values
        data = dict(values)
        expected = int(data.get("input_tokens", 0)) + int(data.get("output_tokens", 0))
        supplied = data.get("total_tokens", 0)
        if supplied not in (0, expected):
            raise ValueError("total_tokens must equal input_tokens + output_tokens")
        data["total_tokens"] = expected
        return data


class BudgetSpec(ContractModel):
    policy_version: str = "dr-policies-v1"
    max_provider_attempts: int | None = Field(default=None, ge=0)
    max_provider_calls: int | None = Field(default=None, ge=0)
    max_tool_attempts: int | None = Field(default=None, ge=0)
    max_tool_calls: int | None = Field(default=None, ge=0)
    max_input_tokens: int | None = Field(default=None, ge=0)
    max_output_tokens: int | None = Field(default=None, ge=0)
    max_total_tokens: int | None = Field(default=None, ge=0)
    max_retries: int | None = Field(default=None, ge=0)
    max_replans: int = Field(default=0, ge=0)
    max_cost_micros: Decimal | None = Field(default=None, ge=0)
    run_timeout_s: float | None = Field(default=None, gt=0)
    operation_timeout_s: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_deadlines(self) -> "BudgetSpec":
        if self.operation_timeout_s is not None and self.run_timeout_s is not None and self.operation_timeout_s > self.run_timeout_s:
            raise ValueError("operation timeout cannot exceed run timeout")
        return self


class BudgetReservation(ContractModel):
    operation_id: str
    attempt_id: str
    kind: str
    usage: TokenUsage


class BudgetCharge(ContractModel):
    operation_id: str
    attempt_id: str
    kind: str
    outcome: str
    usage: TokenUsage
    attempt_number: int = Field(default=1, ge=1)


class BudgetLedger(ContractModel):
    policy_version: str = "dr-policies-v1"
    provider_attempts: int = Field(default=0, ge=0)
    provider_calls: int = Field(default=0, ge=0)
    provider_succeeded: int = Field(default=0, ge=0)
    tool_attempts: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    tool_succeeded: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    retries: int = Field(default=0, ge=0)
    replans: int = Field(default=0, ge=0)
    elapsed_s: float = Field(default=0, ge=0)
    cost_micros: Decimal = Field(default=Decimal("0"), ge=0)
    reservations: tuple[BudgetReservation, ...] = ()
    charges: tuple[BudgetCharge, ...] = ()

    @classmethod
    def empty(cls, spec: BudgetSpec | None = None) -> "BudgetLedger":
        return cls(policy_version=spec.policy_version if spec else "dr-policies-v1")

    def _reserved_tokens(self) -> int:
        return sum(item.usage.total_tokens for item in self.reservations)

    def _check(self, spec: BudgetSpec, kind: str, usage: TokenUsage, *, include_reservation: bool = True) -> None:
        provider = kind == "provider"
        attempts = self.provider_attempts if provider else self.tool_attempts
        calls = self.provider_calls if provider else self.tool_calls
        max_attempts = spec.max_provider_attempts if provider else spec.max_tool_attempts
        max_calls = spec.max_provider_calls if provider else spec.max_tool_calls
        reserved_calls = len([item for item in self.reservations if item.kind == kind]) if include_reservation else 0
        if max_attempts is not None and attempts + reserved_calls + 1 > max_attempts:
            raise ValueError("budget exhausted: attempts")
        if max_calls is not None and calls + reserved_calls + 1 > max_calls:
            raise ValueError("budget exhausted: calls")
        if spec.max_input_tokens is not None and self.input_tokens + usage.input_tokens > spec.max_input_tokens:
            raise ValueError("budget exhausted: input tokens")
        if spec.max_output_tokens is not None and self.output_tokens + usage.output_tokens > spec.max_output_tokens:
            raise ValueError("budget exhausted: output tokens")
        if spec.max_total_tokens is not None and self.total_tokens + self._reserved_tokens() + usage.total_tokens > spec.max_total_tokens:
            raise ValueError("budget exhausted: total tokens")
        if spec.max_cost_micros is not None and self.cost_micros + usage.cost_micros > spec.max_cost_micros:
            raise ValueError("budget exhausted: cost")

    def reserve(self, spec: BudgetSpec, *, operation_id: str, attempt_id: str, kind: "OperationKind", usage: TokenUsage) -> tuple["BudgetLedger", BudgetReservation]:
        existing = next((item for item in self.reservations if item.attempt_id == attempt_id), None)
        if existing is not None:
            if existing.usage != usage or existing.operation_id != operation_id:
                raise ValueError("conflicting budget reservation")
            return self, existing
        if any(item.attempt_id == attempt_id for item in self.charges):
            raise ValueError("attempt already charged")
        kind_value = kind.value
        self._check(spec, kind_value, usage)
        reservation = BudgetReservation(operation_id=operation_id, attempt_id=attempt_id, kind=kind_value, usage=usage)
        return self.model_copy(update={"reservations": self.reservations + (reservation,)}), reservation

    def reconcile(self, reservation: BudgetReservation, *, usage: TokenUsage, outcome: "OperationStatus | str", attempt_number: int = 1, spec: BudgetSpec | None = None) -> "BudgetLedger":
        if not any(item.attempt_id == reservation.attempt_id for item in self.reservations):
            return self.charge_attempt(spec or BudgetSpec(), operation_id=reservation.operation_id, attempt_id=reservation.attempt_id, kind=reservation.kind, usage=usage, outcome=outcome, attempt_number=attempt_number)
        remaining = tuple(item for item in self.reservations if item.attempt_id != reservation.attempt_id)
        base = self.model_copy(update={"reservations": remaining})
        return base.charge_attempt(spec or BudgetSpec(), operation_id=reservation.operation_id, attempt_id=reservation.attempt_id, kind=reservation.kind, usage=usage, outcome=outcome, attempt_number=attempt_number)

    def charge_attempt(self, spec: BudgetSpec, *, operation_id: str, attempt_id: str, kind: "OperationKind | str", usage: TokenUsage, outcome: "OperationStatus | str", attempt_number: int = 1) -> "BudgetLedger":
        kind_value = kind.value if hasattr(kind, "value") else str(kind)
        existing = next((item for item in self.charges if item.attempt_id == attempt_id), None)
        charge = BudgetCharge(operation_id=operation_id, attempt_id=attempt_id, kind=kind_value, outcome=outcome.value if hasattr(outcome, "value") else str(outcome), usage=usage, attempt_number=attempt_number)
        if existing is not None:
            if existing != charge:
                raise ValueError("conflicting duplicate charge")
            return self
        if spec.max_retries is not None and self.retries + max(0, attempt_number - 1) > spec.max_retries:
            raise ValueError("budget exhausted: retries")
        self._check(spec, kind_value, usage, include_reservation=False)
        provider = kind_value == "provider"
        succeeded = charge.outcome == "succeeded"
        updates = {
            "provider_attempts": self.provider_attempts + (1 if provider else 0),
            "provider_calls": self.provider_calls + (1 if provider else 0),
            "provider_succeeded": self.provider_succeeded + (1 if provider and succeeded else 0),
            "tool_attempts": self.tool_attempts + (0 if provider else 1),
            "tool_calls": self.tool_calls + (0 if provider else 1),
            "tool_succeeded": self.tool_succeeded + (1 if not provider and succeeded else 0),
            "input_tokens": self.input_tokens + usage.input_tokens,
            "output_tokens": self.output_tokens + usage.output_tokens,
            "total_tokens": self.total_tokens + usage.total_tokens,
            "retries": self.retries + max(0, attempt_number - 1),
            "cost_micros": self.cost_micros + usage.cost_micros,
            "charges": self.charges + (charge,),
        }
        return self.model_copy(update=updates)

    def record_replan(self, spec: BudgetSpec) -> "BudgetLedger":
        if self.replans >= spec.max_replans:
            raise ValueError("budget exhausted: replans")
        return self.model_copy(update={"replans": self.replans + 1})

    def record_elapsed(self, seconds: float) -> "BudgetLedger":
        if seconds < 0:
            raise ValueError("elapsed time cannot be negative")
        return self.model_copy(update={"elapsed_s": max(self.elapsed_s, seconds)})
