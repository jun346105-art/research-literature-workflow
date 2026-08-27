from __future__ import annotations

import asyncio

from litflow.deep_research.budgets import BudgetSpec
from litflow.deep_research.errors import ErrorCode
from litflow.deep_research.fake_runtime import FakeClock, FakeExecutionHarness, run_fake_scenario
from litflow.deep_research.operations import OperationStatus
from litflow.deep_research.replay import replay_events
from litflow.deep_research.state import RunState


def test_fake_clock_and_scripted_provider_are_deterministic():
    clock = FakeClock()
    clock.advance(1.25)
    assert clock.monotonic() == 1.25
    first = run_fake_scenario("success_minimal")
    second = run_fake_scenario("success_minimal")
    assert first == second
    assert first.terminal == "complete"
    assert first.external_call_count == 2


def test_run_deadline_is_relative_to_injected_clock_origin():
    harness = FakeExecutionHarness(
        "success_minimal",
        spec=BudgetSpec(run_timeout_s=1.0, operation_timeout_s=1.0),
        clock=FakeClock(start=100.0),
    )
    result = harness.run()
    assert result.terminal == "complete"


def test_fake_scenarios_cover_abstain_retry_timeout_cancel_budget_and_unknown():
    assert run_fake_scenario("insufficient_evidence").terminal == "insufficient_evidence"
    retry = run_fake_scenario("transient_retry_success")
    assert retry.terminal == "complete"
    assert retry.ledger.retries == 1
    timeout = run_fake_scenario("timeout_exhausted")
    assert timeout.error_code is ErrorCode.operation_timeout
    assert timeout.terminal == "failed"
    cancel = run_fake_scenario("cancel_before_next_call")
    assert cancel.error_code is ErrorCode.cancelled
    assert cancel.external_call_count == 1
    budget = run_fake_scenario("budget_exhausted")
    assert budget.error_code is ErrorCode.budget_exhausted
    unknown = run_fake_scenario("unknown_non_idempotent_outcome")
    assert unknown.error_code is ErrorCode.unknown_outcome
    assert unknown.journal.resume_decision(unknown.journal.records[0].operation_id) == "manual_review_required"


def test_replan_is_bounded_and_does_not_reset_ledger():
    success = run_fake_scenario("single_replan_success")
    assert success.terminal == "complete"
    assert success.ledger.replans == 1
    exhausted = run_fake_scenario("replan_limit_exceeded")
    assert exhausted.terminal == "insufficient_evidence"
    assert exhausted.error_code is ErrorCode.budget_exhausted
    assert exhausted.ledger.replans == 1


def test_resume_at_each_boundary_matches_uninterrupted_result():
    expected = run_fake_scenario("single_replan_success")
    for boundary in range(expected.durable_boundary_count + 1):
        resumed = run_fake_scenario("single_replan_success", interrupt_after=boundary)
        if resumed.interrupted:
            resumed = resumed.resume()
        assert resumed.terminal == expected.terminal
        assert resumed.ledger == expected.ledger
        assert resumed.journal == expected.journal
        assert resumed.external_call_count == expected.external_call_count


def test_async_entrypoint_does_not_reexecute_unknown_side_effect():
    harness = FakeExecutionHarness("unknown_non_idempotent_outcome")
    result = asyncio.run(harness.run_async())
    assert result.error_code is ErrorCode.unknown_outcome
    assert result.journal.records[0].status is OperationStatus.outcome_unknown


def test_full_lifecycle_replay_matches_resumed_final_state():
    expected = run_fake_scenario("single_replan_success")
    initial = RunState.create(
        task_id="dr-task-" + "a" * 24,
        brief_id="dr-brief-" + "b" * 24,
        brief_approved=True,
    )
    recovered = replay_events(initial, expected.lifecycle_events)
    assert recovered == expected.run_state

    resumed = run_fake_scenario("single_replan_success", interrupt_after=1).resume()
    assert resumed.run_state == expected.run_state
    assert resumed.ledger == expected.ledger
    assert resumed.journal == expected.journal
