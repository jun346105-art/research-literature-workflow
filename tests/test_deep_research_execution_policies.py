from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from litflow.deep_research.budgets import BudgetLedger, BudgetSpec, TokenUsage
from litflow.deep_research.fake_runtime import run_fake_scenario
from litflow.deep_research.persistence import PolicyEventStore
from litflow.deep_research.replay import replay_policy_events
from litflow.deep_research.errors import ErrorCode, error_spec
from litflow.deep_research.operations import OperationJournal, OperationKind, OperationStatus
from litflow.deep_research.policies import CancellationToken, ReplanPolicy, RetryPolicy


def test_error_taxonomy_has_explicit_retry_and_terminal_semantics():
    assert error_spec(ErrorCode.transient_provider).retryable is True
    assert error_spec(ErrorCode.rate_limited).retryable is True
    assert error_spec(ErrorCode.contract_invalid).retryable is False
    assert error_spec(ErrorCode.unknown_outcome).retryable is False
    assert error_spec(ErrorCode.unknown_outcome).recommended_terminal == ErrorCode.unknown_outcome


def test_budget_ledger_reserves_reconciles_and_deduplicates_attempt_charge():
    spec = BudgetSpec(
        max_provider_calls=2,
        max_provider_attempts=3,
        max_total_tokens=20,
        max_cost_micros=100,
    )
    ledger = BudgetLedger.empty(spec)
    ledger, reservation = ledger.reserve(
        spec,
        operation_id="dr-operation-" + "a" * 24,
        attempt_id="dr-attempt-" + "b" * 24,
        kind=OperationKind.provider,
        usage=TokenUsage(input_tokens=4, output_tokens=0, cost_micros=Decimal("0.00")),
    )
    ledger = ledger.reconcile(
        reservation,
        usage=TokenUsage(input_tokens=4, output_tokens=6, cost_micros=Decimal("0.03")),
        outcome=OperationStatus.succeeded,
    )
    same = ledger.charge_attempt(
        spec,
        operation_id=reservation.operation_id,
        attempt_id=reservation.attempt_id,
        kind=OperationKind.provider,
        usage=TokenUsage(input_tokens=4, output_tokens=6, cost_micros=Decimal("0.03")),
        outcome=OperationStatus.succeeded,
    )
    assert same == ledger
    assert ledger.provider_calls == 1
    assert ledger.total_tokens == 10
    assert ledger.cost_micros == Decimal("0.03")
    with pytest.raises(ValueError, match="budget"):
        ledger.reserve(
            spec,
            operation_id="dr-operation-" + "c" * 24,
            attempt_id="dr-attempt-" + "d" * 24,
            kind=OperationKind.provider,
            usage=TokenUsage(input_tokens=11, output_tokens=0),
        )


def test_budget_ledger_enforces_retry_budget():
    spec = BudgetSpec(max_retries=1)
    ledger = BudgetLedger.empty(spec)
    ledger = ledger.charge_attempt(
        spec,
        operation_id="dr-operation-" + "r" * 24,
        attempt_id="dr-attempt-" + "s" * 24,
        kind=OperationKind.provider,
        usage=TokenUsage(input_tokens=1),
        outcome=OperationStatus.failed_known,
        attempt_number=1,
    )
    ledger = ledger.charge_attempt(
        spec,
        operation_id="dr-operation-" + "r" * 24,
        attempt_id="dr-attempt-" + "t" * 24,
        kind=OperationKind.provider,
        usage=TokenUsage(input_tokens=1),
        outcome=OperationStatus.failed_known,
        attempt_number=2,
    )
    assert ledger.retries == 1
    with pytest.raises(ValueError, match="retries"):
        ledger.charge_attempt(
            spec,
            operation_id="dr-operation-" + "r" * 24,
            attempt_id="dr-attempt-" + "u" * 24,
            kind=OperationKind.provider,
            usage=TokenUsage(input_tokens=1),
            outcome=OperationStatus.failed_known,
            attempt_number=3,
        )


def test_operation_journal_protects_succeeded_and_unknown_side_effects_on_resume():
    journal = OperationJournal.empty()
    record = journal.plan(
        operation_id="dr-operation-" + "1" * 24,
        kind=OperationKind.tool,
        name="write_fixture",
        idempotent=False,
        side_effecting=True,
    )
    journal = journal.add(record)
    journal = journal.start(record.operation_id, record.attempt_id)
    journal = journal.mark_unknown(record.operation_id, record.attempt_id, ErrorCode.unknown_outcome)
    assert journal.can_resume(record.operation_id) is False
    assert journal.resume_decision(record.operation_id) == "manual_review_required"

    read = journal.plan(
        operation_id="dr-operation-" + "2" * 24,
        kind=OperationKind.tool,
        name="read_fixture",
        idempotent=True,
        side_effecting=False,
    )
    journal = journal.add(read)
    journal = journal.mark_succeeded(read.operation_id, read.attempt_id)
    assert journal.can_resume(read.operation_id) is False


def test_retry_cancel_and_replan_contracts_are_bounded_and_idempotent():
    retry = RetryPolicy(max_attempts=2)
    assert retry.allows(ErrorCode.transient_provider, attempt_number=1)
    assert not retry.allows(ErrorCode.transient_provider, attempt_number=2)
    assert not retry.allows(ErrorCode.permanent_provider, attempt_number=1)

    token = CancellationToken()
    assert token.request() is True
    assert token.request() is False
    assert token.cancelled is True

    policy = ReplanPolicy(max_replans=1)
    decision = policy.admit(
        ordinal=0,
        old_plan_id="dr-plan-" + "1" * 24,
        proposed_plan_id="dr-plan-" + "2" * 24,
        reason=ErrorCode.transient_provider,
    )
    assert decision.admitted is True
    assert policy.admit(
        ordinal=1,
        old_plan_id="dr-plan-" + "2" * 24,
        proposed_plan_id="dr-plan-" + "3" * 24,
        reason=ErrorCode.transient_provider,
    ).admitted is False


def test_policy_event_store_and_replay_rebuild_ledger_and_journal(tmp_path):
    result = run_fake_scenario("single_replan_success")
    store = PolicyEventStore(tmp_path / "policy.jsonl", run_id=result.run_state.run_id)
    for event in result.events:
        store.append(event)
    loaded = store.read_all()
    ledger, journal = replay_policy_events(loaded, BudgetSpec(max_replans=1))
    assert ledger == result.ledger
    assert journal == result.journal
    raw = (tmp_path / "policy.jsonl").read_text(encoding="utf-8")
    (tmp_path / "policy.jsonl").write_text(raw.replace(result.run_state.run_id, "dr-run-tampered", 1), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError):
        store.read_all()


def test_policy_contract_schema_exports_are_byte_stable(tmp_path):
    from litflow.deep_research.schema_export import write_policy_schemas

    written = write_policy_schemas(tmp_path)
    for name, path in written.items():
        assert path.read_bytes() == (Path("docs/deep_research/policies/v1") / name).read_bytes()
