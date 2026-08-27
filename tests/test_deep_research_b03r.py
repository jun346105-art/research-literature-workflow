from __future__ import annotations

import pytest
from pathlib import Path
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum

from litflow.deep_research.budgets import BudgetSpec
from litflow.deep_research.fake_runtime import FakeClock
from litflow.deep_research.operations import OperationStatus
from litflow.deep_research.runtime_v2 import (
    CrashPoint,
    DispatchInterrupted,
    RuntimeEventType,
    UnifiedEventStore,
    CrashSafeFakeHarness,
    replay_runtime_events,
    CoordinatedCheckpointV2,
    read_coordinated_checkpoint,
)
from litflow.deep_research.policies import CancellationToken
from litflow.deep_research.identity import canonical_json_bytes, sha256_hex
from litflow.deep_research.errors import ManualInterventionRequired


def test_reserved_boundary_is_durable_and_safe_to_resume(tmp_path):
    path = tmp_path / "runtime.jsonl"
    harness = CrashSafeFakeHarness("success_minimal", path)
    with pytest.raises(DispatchInterrupted):
        harness.run(crash_at=CrashPoint.after_reserved)

    events = UnifiedEventStore(path, run_id=harness.run_id).read_all()
    assert events[-1].event_type is RuntimeEventType.operation_reserved
    recovered = replay_runtime_events(harness.initial_state, events, harness.spec)
    assert len(recovered.ledger.reservations) == 1
    assert recovered.journal.records[0].status is OperationStatus.reserved
    assert harness.provider.calls == []

    resumed = CrashSafeFakeHarness("success_minimal", path).resume()
    assert resumed.terminal == "complete"
    assert resumed.ledger.reservations == ()
    assert resumed.external_call_count == 2


def test_dispatched_boundary_replays_unknown_and_blocks_resume(tmp_path):
    path = tmp_path / "runtime.jsonl"
    harness = CrashSafeFakeHarness("unknown_non_idempotent_outcome", path)
    with pytest.raises(DispatchInterrupted):
        harness.run(crash_at=CrashPoint.after_dispatched)

    events = UnifiedEventStore(path, run_id=harness.run_id).read_all()
    recovered = replay_runtime_events(harness.initial_state, events, harness.spec)
    record = recovered.journal.records[0]
    assert record.status is OperationStatus.outcome_unknown
    assert recovered.journal.resume_decision(record.operation_id) == "manual_review_required"
    assert recovered.ledger.reservations
    assert isinstance(recovered.manual_intervention, ManualInterventionRequired)
    recovered_again = replay_runtime_events(harness.initial_state, events, harness.spec)
    assert recovered.manual_intervention == recovered_again.manual_intervention
    assert harness.provider.calls == []


def test_response_lost_after_provider_call_is_unknown_without_reexecution(tmp_path):
    path = tmp_path / "runtime.jsonl"
    harness = CrashSafeFakeHarness("unknown_non_idempotent_outcome", path)
    with pytest.raises(DispatchInterrupted):
        harness.run(crash_at=CrashPoint.after_provider_call)
    assert len(harness.tool.calls) == 1

    resumed = CrashSafeFakeHarness("unknown_non_idempotent_outcome", path).resume()
    assert resumed.error_code.value == "unknown_outcome"
    assert resumed.external_call_count == 1
    assert resumed.journal.records[0].status is OperationStatus.outcome_unknown
    assert resumed.journal.records[0].attempt_number == 1
    assert resumed.ledger.reservations
    assert resumed.ledger.retries == 0
    assert resumed.ledger.replans == 0
    assert isinstance(resumed.manual_intervention, ManualInterventionRequired)
    assert resumed.manual_intervention.snapshot == CrashSafeFakeHarness("unknown_non_idempotent_outcome", path).resume().manual_intervention.snapshot
    assert resumed.manual_intervention.snapshot.get("last_event_id")
    assert resumed.manual_intervention.snapshot["last_event_type"] == "operation_dispatched"
    assert all(not value.startswith(("C:\\", "/")) for value in resumed.manual_intervention.snapshot.values())

    before_provider, before_tool = len(harness.provider.calls), len(harness.tool.calls)
    events = UnifiedEventStore(path, run_id=harness.run_id).read_all()
    first_replay = replay_runtime_events(harness.initial_state, events, harness.spec)
    second_replay = replay_runtime_events(harness.initial_state, events, harness.spec)
    assert first_replay.manual_intervention == second_replay.manual_intervention
    assert len(harness.provider.calls) == before_provider
    assert len(harness.tool.calls) == before_tool


def test_success_event_replays_without_duplicate_call_or_charge(tmp_path):
    path = tmp_path / "runtime.jsonl"
    first = CrashSafeFakeHarness("success_minimal", path).run()
    store = UnifiedEventStore(path, run_id=first.run_id)
    events = store.read_all()
    replayed = replay_runtime_events(first.initial_state, events, first.spec)
    assert replayed.run_state == first.run_state
    assert replayed.ledger == first.ledger
    assert replayed.journal == first.journal
    assert sum(event.event_type is RuntimeEventType.operation_succeeded for event in events) == 2


def test_terminal_lifecycle_is_after_operation_accounting(tmp_path):
    result = CrashSafeFakeHarness("success_minimal", tmp_path / "runtime.jsonl").run()
    terminal_index = max(index for index, event in enumerate(result.events) if event.event_type is RuntimeEventType.lifecycle_transition and event.payload["to_status"] == "complete")
    last_success_index = max(index for index, event in enumerate(result.events) if event.event_type is RuntimeEventType.operation_succeeded)
    assert terminal_index > last_success_index


def test_success_before_checkpoint_resume_does_not_repeat_call_or_charge(tmp_path):
    path = tmp_path / "runtime.jsonl"
    harness = CrashSafeFakeHarness("success_minimal", path)
    with pytest.raises(DispatchInterrupted):
        harness.run(crash_at=CrashPoint.after_success_before_checkpoint)
    resumed = CrashSafeFakeHarness("success_minimal", path).resume()
    assert resumed.terminal == "complete"
    assert resumed.external_call_count == 2
    assert resumed.ledger.provider_calls == 1
    assert resumed.ledger.tool_calls == 1


def test_checkpoint_tail_replay_and_tamper_fail_closed(tmp_path):
    path = tmp_path / "runtime.jsonl"
    first = CrashSafeFakeHarness("success_minimal", path).run()
    store = UnifiedEventStore(path, run_id=first.run_id)
    events = store.read_all()
    checkpoint = first.checkpoint
    assert checkpoint is not None
    prefix_length = next(index for index, event in enumerate(events, 1) if event.event_type is RuntimeEventType.operation_succeeded)
    prefix = replay_runtime_events(first.initial_state, events[:prefix_length], first.spec)
    prefix_checkpoint = CoordinatedCheckpointV2.from_result(prefix)
    recovered = replay_runtime_events(first.initial_state, events, first.spec, checkpoint=prefix_checkpoint)
    assert recovered.run_state == first.run_state
    assert recovered.ledger == first.ledger
    assert recovered.journal == first.journal
    assert recovered.stream_sequence == first.checkpoint.stream_sequence
    assert recovered.stream_head == first.checkpoint.stream_head

    tampered = events[1].model_copy(update={"stream_sequence": 99})
    with pytest.raises(ValueError):
        replay_runtime_events(first.initial_state, [events[0], tampered, *events[2:]], first.spec)
    tampered_payload = events[1].model_copy(update={"payload": {**events[1].payload, "tampered": True}})
    with pytest.raises(ValueError):
        replay_runtime_events(first.initial_state, [events[0], tampered_payload, *events[2:]], first.spec)
    tampered_previous = events[1].model_copy(update={"previous_event_hash": "f" * 64})
    with pytest.raises(ValueError):
        replay_runtime_events(first.initial_state, [events[0], tampered_previous, *events[2:]], first.spec)
    assert read_coordinated_checkpoint(path.with_suffix(".checkpoint.json")) == checkpoint


def test_unknown_event_duplicate_and_cross_run_fail_closed(tmp_path):
    path = tmp_path / "runtime.jsonl"
    first = CrashSafeFakeHarness("success_minimal", path).run()
    store = UnifiedEventStore(path, run_id=first.run_id)
    events = store.read_all()
    with pytest.raises(ValueError):
        store.append(events[0])
    foreign = events[-1].model_copy(update={"run_id": "dr-run-" + "f" * 24})
    with pytest.raises(ValueError):
        UnifiedEventStore(path, run_id=foreign.run_id).read_all()
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace('"event_type":"lifecycle_transition"', '"event_type":"not_known"', 1), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError):
        store.read_all()


def test_runtime_v2_schemas_are_byte_stable(tmp_path):
    from litflow.deep_research.schema_export import write_runtime_v2_schemas

    written = write_runtime_v2_schemas(tmp_path)
    for name, path in written.items():
        assert path.read_bytes() == (Path("docs/deep_research/runtime/v2") / name).read_bytes()


def test_cancel_before_dispatch_is_durable_and_has_zero_calls(tmp_path):
    token = CancellationToken()
    token.request()
    harness = CrashSafeFakeHarness("success_minimal", tmp_path / "runtime.jsonl", token=token)
    result = harness.run()
    assert result.error_code.value == "cancelled"
    assert result.external_call_count == 0
    assert result.journal.records[0].status is OperationStatus.cancelled_before_dispatch
    assert any(event.event_type is RuntimeEventType.operation_cancelled for event in result.events)


def test_elapsed_backoff_and_effective_timeout_use_fake_clock():
    spec = BudgetSpec(run_timeout_s=5.0, operation_timeout_s=5.0)
    harness = CrashSafeFakeHarness(
        "transient_retry_success",
        None,
        spec=spec,
        clock=FakeClock(),
        backoff_seconds=(2.0,),
    )
    result = harness.run()
    assert result.terminal == "complete"
    assert result.ledger.elapsed_s >= 2.0
    assert any(event.event_type is RuntimeEventType.elapsed_recorded for event in result.events)
    assert result.effective_timeout_samples[0] == 5.0
    assert result.effective_timeout_samples[1] == 3.0
    dispatched = [event for event in result.events if event.event_type is RuntimeEventType.operation_dispatched]
    assert len(dispatched) == 2
    assert dispatched[0].operation_id == dispatched[1].operation_id
    assert dispatched[0].attempt_id != dispatched[1].attempt_id
    assert result.ledger.retries == 1
    assert any(event.event_type is RuntimeEventType.retry_scheduled for event in result.events)


@pytest.mark.parametrize(
    ("scenario", "terminal", "replans"),
    (("single_replan_success", "complete", 1), ("replan_limit_exceeded", "insufficient_evidence", 1), ("insufficient_evidence", "insufficient_evidence", 1)),
)
def test_replan_facts_are_unified_and_replayable(tmp_path, scenario, terminal, replans):
    result = CrashSafeFakeHarness(scenario, tmp_path / f"{scenario}.jsonl").run()
    assert result.terminal == terminal
    assert result.ledger.replans == replans
    assert any(event.event_type is RuntimeEventType.replan_decided for event in result.events)
    assert replay_runtime_events(result.initial_state, result.events, result.spec).ledger == result.ledger


def test_canonical_json_bytes_normalizes_order_datetime_decimal_and_enum():
    class Mode(str, Enum):
        safe = "safe"

    left = {"b": Decimal("1E+2"), "a": Mode.safe, "at": datetime(2025, 1, 1, tzinfo=UTC)}
    right = {"at": datetime(2025, 1, 1, 0, 0, tzinfo=UTC), "a": "safe", "b": Decimal("100")}
    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert sha256_hex(canonical_json_bytes(left)) == sha256_hex(canonical_json_bytes(right))
    assert b'"b":"100"' in canonical_json_bytes(left)
    assert b"2025-01-01T00:00:00Z" in canonical_json_bytes(left)


def test_canonical_json_bytes_rejects_non_utc_nan_and_unsupported_values():
    with pytest.raises((ValueError, TypeError)):
        canonical_json_bytes({"at": datetime(2025, 1, 1, tzinfo=timezone(timedelta(hours=1)))})
    with pytest.raises((ValueError, TypeError)):
        canonical_json_bytes({"number": float("nan")})
    with pytest.raises((ValueError, TypeError)):
        canonical_json_bytes({"number": float("inf")})
    with pytest.raises(TypeError):
        canonical_json_bytes({"object": object()})


def test_event_hash_is_independent_of_jsonl_line_ending_and_schema_roundtrip(tmp_path):
    from litflow.deep_research.runtime_v2 import RuntimeEventType, RuntimeEventEnvelope, create_runtime_event

    created = create_runtime_event("dr-run-" + "a" * 24, 1, RuntimeEventType.run_started, payload={"message": "中文"})
    assert RuntimeEventEnvelope.model_validate_json(created.model_dump_json()) == created
    assert sha256_hex(canonical_json_bytes(created._payload())) == created.event_hash
    assert sha256_hex(canonical_json_bytes(created._payload()) + b"\n") != created.event_hash

    path = tmp_path / "events.jsonl"
    path.write_bytes(canonical_json_bytes(created.model_dump(mode="json")) + b"\r\n")
    assert UnifiedEventStore(path, run_id=created.run_id).read_all() == [created]
