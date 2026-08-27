"""Deterministic replay of previously validated lifecycle events."""
from __future__ import annotations
from .events import RunEvent
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
