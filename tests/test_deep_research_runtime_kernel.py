from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from litflow.deep_research.events import RunEvent, create_event
from litflow.deep_research.persistence import Checkpoint, EventStore, read_checkpoint, write_checkpoint
from litflow.deep_research.replay import replay_events, recover_state
from litflow.deep_research.state import RunStatus, RunState, TransitionError, transition


NOW = datetime(2026, 8, 27, tzinfo=UTC)


def _state() -> RunState:
    return RunState.create(task_id="dr-task-" + "a" * 24, brief_id="dr-brief-" + "b" * 24, brief_approved=True)


def _events() -> tuple[RunState, list[RunEvent]]:
    state = _state()
    events = []
    for target in (RunStatus.brief_approved, RunStatus.researching, RunStatus.validating, RunStatus.complete):
        next_state, event = transition(state, target, occurred_at=NOW)
        events.append(event)
        state = next_state
    return state, events


def test_state_machine_happy_paths_terminal_guards_and_unapproved_guard():
    state = _state()
    assert state.status is RunStatus.brief_pending
    with pytest.raises(TransitionError, match="approved brief"):
        transition(RunState.create(task_id=state.task_id, brief_id=state.brief_id, brief_approved=False), RunStatus.brief_approved)
    with pytest.raises(TransitionError, match="illegal"):
        transition(state, RunStatus.complete)
    final, _ = _events()
    with pytest.raises(TransitionError, match="terminal"):
        transition(final, RunStatus.failed)


def test_event_identity_hash_chain_and_round_trip_reject_tampering():
    state = _state()
    next_state, event = transition(state, RunStatus.brief_approved, occurred_at=NOW)
    assert event.run_id == state.run_id and event.sequence == 1
    assert RunEvent.model_validate_json(event.model_dump_json()) == event
    assert create_event(state, next_state, occurred_at=NOW) == event
    with pytest.raises(ValidationError, match="event_hash"):
        event.model_validate({**event.model_dump(), "event_hash": "0" * 64})


def test_event_store_append_only_validation_and_prefix_replay(tmp_path: Path):
    final, events = _events()
    store = EventStore(tmp_path / "events.jsonl", run_id=final.run_id)
    for event in events:
        store.append(event)
    loaded = store.read_all()
    assert replay_events(_state(), loaded) == final
    for index in range(len(events) + 1):
        assert replay_events(_state(), loaded[:index]).applied_event_count == index
    with pytest.raises(ValueError, match="duplicate"):
        store.append(events[-1])
    (tmp_path / "events.jsonl").write_text((tmp_path / "events.jsonl").read_text(encoding="utf-8") + '{"bad"', encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="JSON"):
        store.read_all()


def test_replay_rejects_tamper_gap_reorder_and_cross_run():
    _final, events = _events()
    with pytest.raises(ValueError, match="sequence"):
        replay_events(_state(), (events[1],))
    with pytest.raises(ValueError, match="sequence"):
        replay_events(_state(), (events[1], events[0]))
    with pytest.raises(ValueError, match="run_id"):
        replay_events(_state().model_copy(update={"run_id": "dr-run-" + "c" * 24}), events)
    with pytest.raises(ValidationError):
        events[0].model_validate({**events[0].model_dump(), "previous_event_hash": "f" * 64})


def test_checkpoint_round_trip_tail_replay_and_mismatch_rejection(tmp_path: Path, monkeypatch):
    final, events = _events()
    checkpoint = Checkpoint.from_state(events[0].run_id, events[0].sequence, events[0].event_hash, replay_events(_state(), events[:1]))
    path = tmp_path / "checkpoint.json"
    write_checkpoint(path, checkpoint)
    assert read_checkpoint(path) == checkpoint
    assert recover_state(_state(), events, checkpoint) == final
    with pytest.raises(ValueError, match="checkpoint"):
        recover_state(_state(), events, checkpoint.model_copy(update={"event_head": "0" * 64}))
    original = path.read_bytes()
    import litflow.deep_research.persistence as persistence
    monkeypatch.setattr(persistence.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("replace failed")))
    with pytest.raises(OSError):
        write_checkpoint(path, checkpoint)
    assert path.read_bytes() == original


def test_runtime_modules_are_offline_and_schema_exports_are_stable(tmp_path: Path):
    from litflow.deep_research.schema_export import write_runtime_schemas

    written = write_runtime_schemas(tmp_path)
    for name, path in written.items():
        committed = Path("docs/deep_research/runtime/v1") / name
        assert path.read_bytes() == committed.read_bytes()
    text = "\n".join(path.read_text(encoding="utf-8") for path in Path("src/litflow/deep_research").glob("*.py"))
    for forbidden in ("litflow.agent", "langgraph", "fastapi", "httpx", "numpy", "torch", "transformers", "outputs/"):
        assert forbidden not in text
