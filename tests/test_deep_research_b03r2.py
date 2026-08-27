from __future__ import annotations

from pathlib import Path
import os

import pytest

import litflow.deep_research as deep_research
from litflow.deep_research.runtime_v2 import (
    CoordinatedCheckpointV2,
    CrashSafeFakeHarness,
    RuntimeEventType,
    UnifiedEventStore,
    reduce_runtime_events,
    replay_runtime_events,
)


def _write_prefix(path: Path, run_id: str, events: tuple, end: int) -> None:
    store = UnifiedEventStore(path, run_id=run_id)
    for event in events[:end]:
        store.append(event)


@pytest.mark.parametrize("scenario", ("success_minimal", "transient_retry_success", "single_replan_success", "unknown_non_idempotent_outcome"))
def test_every_durable_prefix_checkpoint_tail_matches_full_replay(tmp_path, scenario):
    full = CrashSafeFakeHarness(scenario, tmp_path / f"{scenario}.jsonl").run()
    expected = replay_runtime_events(full.initial_state, full.events, full.spec)
    prefixes = [(), *[full.events[:index] for index in range(1, len(full.events) + 1)]]

    for prefix in prefixes:
        reduced = reduce_runtime_events(full.initial_state, prefix, full.spec)
        checkpoint = CoordinatedCheckpointV2.from_result(reduced)
        recovered = replay_runtime_events(full.initial_state, full.events, full.spec, checkpoint=checkpoint)
        assert recovered == expected


def test_dispatched_prefix_success_tail_has_no_unknown_or_duplicate_charge(tmp_path):
    full = CrashSafeFakeHarness("success_minimal", tmp_path / "run.jsonl").run()
    index = next(index for index, event in enumerate(full.events, 1) if event.event_type is RuntimeEventType.operation_dispatched)
    checkpoint = CoordinatedCheckpointV2.from_result(reduce_runtime_events(full.initial_state, full.events[:index], full.spec))

    recovered = replay_runtime_events(full.initial_state, full.events, full.spec, checkpoint=checkpoint)
    assert recovered == replay_runtime_events(full.initial_state, full.events, full.spec)
    assert all(record.status.value != "outcome_unknown" for record in recovered.journal.records)
    assert len(recovered.ledger.charges) == len(full.ledger.charges)


@pytest.mark.parametrize("field", ("schema_version", "run_id", "stream_sequence", "stream_head", "run_state_hash", "ledger_hash", "journal_hash"))
def test_model_copy_checkpoint_tampering_is_rejected(tmp_path, field):
    full = CrashSafeFakeHarness("success_minimal", tmp_path / "run.jsonl").run()
    checkpoint = full.checkpoint
    assert checkpoint is not None
    replacements = {
        "schema_version": "not-runtime-v2",
        "run_id": "dr-run-" + "f" * 24,
        "stream_sequence": checkpoint.stream_sequence + 1,
        "stream_head": "f" * 64,
        "run_state_hash": "f" * 64,
        "ledger_hash": "f" * 64,
        "journal_hash": "f" * 64,
    }
    with pytest.raises(ValueError):
        replay_runtime_events(full.initial_state, full.events, full.spec, checkpoint=checkpoint.model_copy(update={field: replacements[field]}))


@pytest.mark.parametrize("event_type", (RuntimeEventType.operation_failed, RuntimeEventType.retry_scheduled, RuntimeEventType.operation_reserved))
def test_retry_prefixes_resume_with_one_deterministic_next_attempt(tmp_path, event_type):
    complete = CrashSafeFakeHarness("transient_retry_success", tmp_path / "complete.jsonl").run()
    end = next(index for index, event in enumerate(complete.events, 1) if event.event_type is event_type)
    path = tmp_path / f"{event_type.value}.jsonl"
    _write_prefix(path, complete.run_id, complete.events, end)

    resumed = CrashSafeFakeHarness("transient_retry_success", path).resume()
    dispatched = [event for event in resumed.events if event.event_type is RuntimeEventType.operation_dispatched]
    assert resumed.terminal == "complete"
    assert len(dispatched) == 2
    assert dispatched[0].operation_id == dispatched[1].operation_id
    assert dispatched[0].attempt_id != dispatched[1].attempt_id
    assert len(resumed.ledger.charges) == 2


def test_retry_dispatched_prefix_is_unknown_and_never_reexecuted(tmp_path):
    complete = CrashSafeFakeHarness("transient_retry_success", tmp_path / "complete.jsonl").run()
    end = next(index for index, event in enumerate(complete.events, 1) if event.event_type is RuntimeEventType.operation_dispatched and event.attempt_id != complete.events[4].attempt_id)
    path = tmp_path / "retry_dispatched.jsonl"
    _write_prefix(path, complete.run_id, complete.events, end)
    resumed = CrashSafeFakeHarness("transient_retry_success", path).resume()
    assert resumed.error_code.value == "unknown_outcome"
    assert resumed.journal.records[0].status.value == "outcome_unknown"


@pytest.mark.parametrize("boundary", ("success", "decision", "reserved"))
def test_replan_prefixes_resume_without_losing_or_duplicating_replan(tmp_path, boundary):
    complete = CrashSafeFakeHarness("single_replan_success", tmp_path / "complete.jsonl").run()
    matching = {
        "success": lambda event: event.event_type is RuntimeEventType.operation_succeeded,
        "decision": lambda event: event.event_type is RuntimeEventType.replan_decided,
        "reserved": lambda event: event.event_type is RuntimeEventType.operation_reserved and event.payload["operation_name"] == "retrieve_followup",
        "dispatched": lambda event: event.event_type is RuntimeEventType.operation_dispatched and event.payload["operation_name"] == "retrieve_followup",
    }
    end = next(index for index, event in enumerate(complete.events, 1) if matching[boundary](event))
    path = tmp_path / f"{boundary}.jsonl"
    _write_prefix(path, complete.run_id, complete.events, end)

    resumed = CrashSafeFakeHarness("single_replan_success", path).resume()
    assert resumed.terminal == "complete"
    assert resumed.ledger.replans == 1
    assert sum(event.event_type is RuntimeEventType.replan_decided for event in resumed.events) == 1


def test_replan_dispatched_prefix_is_unknown_and_never_reexecuted(tmp_path):
    complete = CrashSafeFakeHarness("single_replan_success", tmp_path / "complete.jsonl").run()
    end = next(index for index, event in enumerate(complete.events, 1) if event.event_type is RuntimeEventType.operation_dispatched and event.payload["operation_name"] == "retrieve_followup")
    path = tmp_path / "replan_dispatched.jsonl"
    _write_prefix(path, complete.run_id, complete.events, end)
    resumed = CrashSafeFakeHarness("single_replan_success", path).resume()
    assert resumed.error_code.value == "unknown_outcome"
    assert resumed.journal.records[-1].status.value == "outcome_unknown"


def test_package_root_does_not_export_uncontrolled_dispatcher():
    assert not hasattr(deep_research, "CrashSafeDispatcher")
    with pytest.raises(ImportError):
        exec("from litflow.deep_research import CrashSafeDispatcher", {})


def test_public_fake_runtime_entry_durably_records_reserve_and_dispatch(tmp_path):
    result = CrashSafeFakeHarness("success_minimal", tmp_path / "run.jsonl").run()
    event_types = {event.event_type for event in result.events}
    assert RuntimeEventType.operation_reserved in event_types
    assert RuntimeEventType.operation_dispatched in event_types


@pytest.mark.parametrize("failing_fsync", (4, 5))
def test_reserve_or_dispatch_fsync_failure_prevents_external_call(tmp_path, monkeypatch, failing_fsync):
    calls = 0
    real_fsync = os.fsync

    def fail_boundary(fd: int) -> None:
        nonlocal calls
        calls += 1
        if calls == failing_fsync:
            raise OSError("injected durable-boundary failure")
        real_fsync(fd)

    monkeypatch.setattr("litflow.deep_research.runtime_v2.os.fsync", fail_boundary)
    harness = CrashSafeFakeHarness("success_minimal", tmp_path / "run.jsonl")
    with pytest.raises(OSError, match="durable-boundary"):
        harness.run()
    assert harness.provider.calls == []
    assert harness.tool.calls == []


def test_cancelled_stream_prefixes_checkpoint_tail_match_full_replay(tmp_path):
    from litflow.deep_research.policies import CancellationToken

    token = CancellationToken()
    token.request()
    full = CrashSafeFakeHarness("success_minimal", tmp_path / "cancelled.jsonl", token=token).run()
    expected = replay_runtime_events(full.initial_state, full.events, full.spec)
    for end in range(len(full.events) + 1):
        checkpoint = CoordinatedCheckpointV2.from_result(
            reduce_runtime_events(full.initial_state, full.events[:end], full.spec)
        )
        assert replay_runtime_events(full.initial_state, full.events, full.spec, checkpoint=checkpoint) == expected


def test_replan_limit_remains_fail_closed_after_resume(tmp_path):
    result = CrashSafeFakeHarness("replan_limit_exceeded", tmp_path / "run.jsonl").run()
    assert result.terminal == "insufficient_evidence"
    assert result.ledger.replans == 1
    assert result.error_code.value == "budget_exhausted"
