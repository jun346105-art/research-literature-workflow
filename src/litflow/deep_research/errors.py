"""Structured execution error taxonomy for the offline policy layer."""
from __future__ import annotations

from enum import Enum

from pydantic import Field

from .contracts import ContractModel


class ErrorCode(str, Enum):
    transient_provider = "transient_provider"
    rate_limited = "rate_limited"
    operation_timeout = "operation_timeout"
    run_deadline_exceeded = "run_deadline_exceeded"
    budget_exhausted = "budget_exhausted"
    cancelled = "cancelled"
    contract_invalid = "contract_invalid"
    grounding_rejected = "grounding_rejected"
    permanent_provider = "permanent_provider"
    tool_failure = "tool_failure"
    unknown_outcome = "unknown_outcome"
    internal_invariant_violation = "internal_invariant_violation"


class ErrorSpec(ContractModel):
    code: ErrorCode
    retryable: bool
    counts_as_call: bool
    can_replan: bool
    recommended_terminal: ErrorCode
    automatic_recovery: bool


_SPECS = {
    ErrorCode.transient_provider: ErrorSpec(code=ErrorCode.transient_provider, retryable=True, counts_as_call=True, can_replan=True, recommended_terminal=ErrorCode.transient_provider, automatic_recovery=True),
    ErrorCode.rate_limited: ErrorSpec(code=ErrorCode.rate_limited, retryable=True, counts_as_call=True, can_replan=True, recommended_terminal=ErrorCode.rate_limited, automatic_recovery=True),
    ErrorCode.operation_timeout: ErrorSpec(code=ErrorCode.operation_timeout, retryable=True, counts_as_call=True, can_replan=True, recommended_terminal=ErrorCode.operation_timeout, automatic_recovery=True),
    ErrorCode.run_deadline_exceeded: ErrorSpec(code=ErrorCode.run_deadline_exceeded, retryable=False, counts_as_call=False, can_replan=False, recommended_terminal=ErrorCode.run_deadline_exceeded, automatic_recovery=False),
    ErrorCode.budget_exhausted: ErrorSpec(code=ErrorCode.budget_exhausted, retryable=False, counts_as_call=False, can_replan=False, recommended_terminal=ErrorCode.budget_exhausted, automatic_recovery=False),
    ErrorCode.cancelled: ErrorSpec(code=ErrorCode.cancelled, retryable=False, counts_as_call=False, can_replan=False, recommended_terminal=ErrorCode.cancelled, automatic_recovery=False),
    ErrorCode.contract_invalid: ErrorSpec(code=ErrorCode.contract_invalid, retryable=False, counts_as_call=True, can_replan=False, recommended_terminal=ErrorCode.contract_invalid, automatic_recovery=False),
    ErrorCode.grounding_rejected: ErrorSpec(code=ErrorCode.grounding_rejected, retryable=False, counts_as_call=True, can_replan=True, recommended_terminal=ErrorCode.grounding_rejected, automatic_recovery=False),
    ErrorCode.permanent_provider: ErrorSpec(code=ErrorCode.permanent_provider, retryable=False, counts_as_call=True, can_replan=False, recommended_terminal=ErrorCode.permanent_provider, automatic_recovery=False),
    ErrorCode.tool_failure: ErrorSpec(code=ErrorCode.tool_failure, retryable=False, counts_as_call=True, can_replan=True, recommended_terminal=ErrorCode.tool_failure, automatic_recovery=False),
    ErrorCode.unknown_outcome: ErrorSpec(code=ErrorCode.unknown_outcome, retryable=False, counts_as_call=True, can_replan=False, recommended_terminal=ErrorCode.unknown_outcome, automatic_recovery=False),
    ErrorCode.internal_invariant_violation: ErrorSpec(code=ErrorCode.internal_invariant_violation, retryable=False, counts_as_call=False, can_replan=False, recommended_terminal=ErrorCode.internal_invariant_violation, automatic_recovery=False),
}


def error_spec(code: ErrorCode | str) -> ErrorSpec:
    return _SPECS[ErrorCode(code)]


class ExecutionFailure(ContractModel):
    code: ErrorCode
    message: str = Field(min_length=1)
    retryable: bool | None = None
    attempt_number: int = Field(default=1, ge=1)

    def policy(self) -> ErrorSpec:
        return error_spec(self.code)


class ManualInterventionRequired(ContractModel):
    """Stable, redacted diagnostic for an operation with an unknown outcome."""

    code: ErrorCode = ErrorCode.unknown_outcome
    run_id: str
    operation_id: str
    attempt_id: str
    last_event_id: str
    status: str = "outcome_unknown"
    reservation_present: bool = True
    snapshot: dict[str, str] = Field(default_factory=dict)
