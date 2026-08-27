"""Immutable hash-chained lifecycle events."""
from __future__ import annotations
from datetime import UTC,datetime
from enum import Enum
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


class PolicyEventType(str, Enum):
    operation_planned = "operation_planned"
    operation_started = "operation_started"
    operation_succeeded = "operation_succeeded"
    operation_failed = "operation_failed"
    operation_unknown = "operation_unknown"
    operation_cancelled = "operation_cancelled"
    attempt_charged = "attempt_charged"
    replan_decided = "replan_decided"
    elapsed_recorded = "elapsed_recorded"


class PolicyEvent(ContractModel):
    """Strict policy fact event; lifecycle RunEvent remains unchanged."""
    policy_version: str = "dr-policies-v1"
    event_id: str
    run_id: str
    sequence: int = Field(ge=1)
    event_type: PolicyEventType
    operation_id: str | None = None
    attempt_id: str | None = None
    operation_kind: str | None = None
    operation_name: str | None = None
    operation_status: str | None = None
    result_sha256: str | None = None
    idempotent: bool | None = None
    side_effecting: bool | None = None
    error_code: str | None = None
    attempt_number: int | None = Field(default=None, ge=1)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_micros: str = "0"
    old_plan_id: str | None = None
    proposed_plan_id: str | None = None
    replan_ordinal: int | None = Field(default=None, ge=0)
    admitted: bool | None = None
    rejected_reason: str | None = None
    elapsed_s: float | None = Field(default=None, ge=0)
    previous_event_hash: str
    event_hash: str

    def _payload(self) -> dict[str, object]:
        data = self.model_dump(mode="json")
        data.pop("contract_version", None)
        data.pop("event_id", None)
        data.pop("event_hash", None)
        data.pop("previous_event_hash", None)
        return data | {"previous_event_hash": self.previous_event_hash}

    @model_validator(mode="after")
    def verify(self) -> "PolicyEvent":
        payload = self._payload()
        if self.sequence == 1 and self.previous_event_hash != GENESIS_HASH:
            raise ValueError("previous_event_hash invalid")
        if self.event_id != make_stable_id("policy", payload):
            raise ValueError("policy event_id mismatch")
        if self.event_hash != sha256_hex(canonical_json(payload)):
            raise ValueError("policy event_hash mismatch")
        return self


def create_policy_event(run_id: str, sequence: int, event_type: PolicyEventType, *, previous_event_hash: str = GENESIS_HASH, **fields: object) -> PolicyEvent:
    defaults = {
        "operation_id": None, "attempt_id": None, "operation_kind": None, "operation_name": None,
        "operation_status": None, "result_sha256": None, "idempotent": None, "side_effecting": None, "error_code": None, "attempt_number": None, "input_tokens": 0,
        "output_tokens": 0, "cost_micros": "0", "old_plan_id": None, "proposed_plan_id": None,
        "replan_ordinal": None, "admitted": None, "rejected_reason": None, "elapsed_s": None,
    }
    values = {**defaults, **fields}
    payload = {"policy_version": "dr-policies-v1", "run_id": run_id, "sequence": sequence, "event_type": event_type.value, **values, "previous_event_hash": previous_event_hash}
    return PolicyEvent(event_id=make_stable_id("policy", payload), event_hash=sha256_hex(canonical_json(payload)), previous_event_hash=previous_event_hash, run_id=run_id, sequence=sequence, event_type=event_type, **values)
