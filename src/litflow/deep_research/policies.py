"""Bounded retry, cancellation, deadline and controlled-replan policies."""
from __future__ import annotations

from .contracts import ContractModel
from .errors import ErrorCode, error_spec


class RetryPolicy(ContractModel):
    policy_version: str = "dr-policies-v1"
    max_attempts: int = 1
    retryable_errors: tuple[ErrorCode, ...] = (ErrorCode.transient_provider, ErrorCode.rate_limited, ErrorCode.operation_timeout)
    backoff_seconds: tuple[float, ...] = ()

    def allows(self, code: ErrorCode | str, *, attempt_number: int, cancelled: bool = False, remaining_s: float | None = None) -> bool:
        if cancelled or attempt_number >= self.max_attempts:
            return False
        error = ErrorCode(code)
        if error not in self.retryable_errors or not error_spec(error).retryable:
            return False
        delay = self.delay_for(attempt_number)
        return remaining_s is None or remaining_s >= delay

    def delay_for(self, attempt_number: int) -> float:
        if attempt_number <= 0:
            raise ValueError("attempt_number must be positive")
        index = attempt_number - 1
        return self.backoff_seconds[index] if index < len(self.backoff_seconds) else 0.0


class CancellationToken:
    def __init__(self) -> None:
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def request(self) -> bool:
        if self._cancelled:
            return False
        self._cancelled = True
        return True

    def raise_if_cancelled(self) -> None:
        if self._cancelled:
            raise RuntimeError(ErrorCode.cancelled.value)


class ReplanDecision(ContractModel):
    admitted: bool
    ordinal: int
    reason: ErrorCode
    old_plan_id: str
    proposed_plan_id: str
    rejected_reason: str | None = None


class ReplanPolicy(ContractModel):
    policy_version: str = "dr-policies-v1"
    max_replans: int = 1

    def admit(self, *, ordinal: int, old_plan_id: str, proposed_plan_id: str, reason: ErrorCode | str) -> ReplanDecision:
        code = ErrorCode(reason)
        if ordinal >= self.max_replans:
            return ReplanDecision(admitted=False, ordinal=ordinal, reason=code, old_plan_id=old_plan_id, proposed_plan_id=proposed_plan_id, rejected_reason="replan_limit_exceeded")
        if old_plan_id == proposed_plan_id:
            return ReplanDecision(admitted=False, ordinal=ordinal, reason=code, old_plan_id=old_plan_id, proposed_plan_id=proposed_plan_id, rejected_reason="plan_unchanged")
        return ReplanDecision(admitted=True, ordinal=ordinal, reason=code, old_plan_id=old_plan_id, proposed_plan_id=proposed_plan_id)
