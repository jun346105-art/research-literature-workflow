"""Immutable hash-chained lifecycle events."""
from __future__ import annotations
from datetime import UTC,datetime
from pydantic import Field,model_validator
from .contracts import ContractModel
from .identity import canonical_json,make_stable_id,sha256_hex
from .state import RUNTIME_VERSION,RunState,RunStatus

GENESIS_HASH="0"*64
class RunEvent(ContractModel):
    runtime_version:str=Field(default=RUNTIME_VERSION,description="Runtime event version.")
    event_id:str=Field(description="Program-generated deterministic event ID.")
    run_id:str=Field(description="Owning run ID.")
    sequence:int=Field(ge=1,description="Continuous one-based event sequence.")
    from_status:RunStatus=Field(description="Prior lifecycle state.")
    to_status:RunStatus=Field(description="Next lifecycle state.")
    terminal_reason:str|None=Field(default=None,description="Terminal reason when applicable.")
    previous_event_hash:str=Field(description="Genesis or prior event hash.")
    event_hash:str=Field(description="SHA-256 of canonical event content excluding event_hash.")
    occurred_at:datetime|None=Field(default=None,description="Optional UTC audit metadata excluded from identity.")
    @model_validator(mode="after")
    def verify(self):
        payload=self._payload()
        if self.sequence==1 and self.previous_event_hash!=GENESIS_HASH: raise ValueError("previous_event_hash invalid")
        if self.event_id!=make_stable_id("event",payload): raise ValueError("event_id does not match canonical payload")
        if self.event_hash!=sha256_hex(canonical_json(payload)): raise ValueError("event_hash does not match canonical payload")
        return self
    def _payload(self): return {"runtime_version":self.runtime_version,"run_id":self.run_id,"sequence":self.sequence,"from_status":self.from_status.value,"to_status":self.to_status.value,"terminal_reason":self.terminal_reason,"previous_event_hash":self.previous_event_hash}

def create_event(state:RunState,next_state:RunState,*,occurred_at:datetime|None=None)->RunEvent:
    sequence=state.applied_event_count+1; previous=state.event_head or GENESIS_HASH
    payload={"runtime_version":RUNTIME_VERSION,"run_id":state.run_id,"sequence":sequence,"from_status":state.status.value,"to_status":next_state.status.value,"terminal_reason":next_state.terminal_reason,"previous_event_hash":previous}
    audit=occurred_at.astimezone(UTC) if occurred_at else None
    return RunEvent(event_id=make_stable_id("event",payload),run_id=state.run_id,sequence=sequence,from_status=state.status,to_status=next_state.status,terminal_reason=next_state.terminal_reason,previous_event_hash=previous,event_hash=sha256_hex(canonical_json(payload)),occurred_at=audit)
