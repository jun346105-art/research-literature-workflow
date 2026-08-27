"""Append-only JSONL storage and derived atomic checkpoints."""
from __future__ import annotations
import os,json,tempfile
from pathlib import Path
from pydantic import Field,model_validator
from .contracts import ContractModel
from .identity import canonical_json,sha256_hex
from .events import GENESIS_HASH, PolicyEvent, RunEvent
from .state import RunState,RUNTIME_VERSION

class EventStore:
    def __init__(self,path:Path,*,run_id:str): self.path,self.run_id=path,run_id
    def read_all(self)->list[RunEvent]:
        if not self.path.exists(): return []
        data=self.path.read_bytes()
        if data and not data.endswith(b"\n"): raise ValueError("event JSONL has an incomplete final line")
        events=[]
        for line in data.decode("utf-8").splitlines():
            try: events.append(RunEvent.model_validate_json(line))
            except Exception as exc: raise ValueError("event JSONL is invalid JSON") from exc
        self._verify(events); return events
    def append(self,event:RunEvent)->None:
        events=self.read_all()
        if event.run_id!=self.run_id: raise ValueError("event run_id mismatch")
        if any(item.event_id==event.event_id for item in events): raise ValueError("duplicate event")
        self._verify(events+[event])
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open("a",encoding="utf-8",newline="\n") as h: h.write(canonical_json(event.model_dump(mode="json"))+"\n"); h.flush(); os.fsync(h.fileno())
    def _verify(self,events:list[RunEvent])->None:
        previous="0"*64
        for index,event in enumerate(events,1):
            if event.run_id!=self.run_id: raise ValueError("event run_id mismatch")
            if event.sequence!=index: raise ValueError("event sequence is not continuous")
            if event.previous_event_hash!=previous: raise ValueError("event hash chain mismatch")
            previous=event.event_hash

class Checkpoint(ContractModel):
    runtime_version:str=Field(default=RUNTIME_VERSION,description="Runtime checkpoint version.")
    run_id:str=Field(description="Owning run ID.")
    applied_sequence:int=Field(ge=0,description="Last applied event sequence.")
    event_head:str=Field(description="Hash at applied sequence or genesis.")
    state:RunState=Field(description="Derived state snapshot.")
    state_hash:str=Field(description="Canonical state SHA-256.")
    @model_validator(mode="after")
    def verify(self):
        if self.state.run_id!=self.run_id or self.state.applied_event_count!=self.applied_sequence or self.state.event_head!=(None if self.applied_sequence==0 else self.event_head): raise ValueError("checkpoint state mismatch")
        if self.state_hash!=sha256_hex(canonical_json(self.state.model_dump(mode="json"))): raise ValueError("checkpoint state_hash mismatch")
        return self
    @classmethod
    def from_state(cls,run_id:str,sequence:int,head:str,state:RunState)->"Checkpoint": return cls(run_id=run_id,applied_sequence=sequence,event_head=head,state=state,state_hash=sha256_hex(canonical_json(state.model_dump(mode="json"))))

def write_checkpoint(path:Path,checkpoint:Checkpoint)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",encoding="utf-8",newline="\n",dir=path.parent,delete=False) as h:
        temp=Path(h.name); h.write(canonical_json(checkpoint.model_dump(mode="json"))+"\n"); h.flush(); os.fsync(h.fileno())
    try: os.replace(temp,path)
    except Exception:
        temp.unlink(missing_ok=True); raise
def read_checkpoint(path:Path)->Checkpoint: return Checkpoint.model_validate_json(path.read_text(encoding="utf-8"))


class PolicyEventStore:
    """Append-only JSONL store for policy facts, separate from B02 lifecycle events."""
    def __init__(self, path: Path, *, run_id: str) -> None:
        self.path, self.run_id = path, run_id

    def read_all(self) -> list[PolicyEvent]:
        if not self.path.exists():
            return []
        data = self.path.read_bytes()
        if data and not data.endswith(b"\n"):
            raise ValueError("policy event JSONL has an incomplete final line")
        events: list[PolicyEvent] = []
        for line in data.decode("utf-8").splitlines():
            try:
                events.append(PolicyEvent.model_validate_json(line))
            except Exception as exc:
                raise ValueError("policy event JSONL is invalid JSON") from exc
        self._verify(events)
        return events

    def append(self, event: PolicyEvent) -> None:
        events = self.read_all()
        if event.run_id != self.run_id:
            raise ValueError("policy event run_id mismatch")
        if any(item.event_id == event.event_id for item in events):
            raise ValueError("duplicate policy event")
        self._verify(events + [event])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(event.model_dump(mode="json")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _verify(self, events: list[PolicyEvent]) -> None:
        previous = GENESIS_HASH
        for index, event in enumerate(events, 1):
            if event.run_id != self.run_id or event.sequence != index:
                raise ValueError("policy event sequence/run mismatch")
            if event.previous_event_hash != previous:
                raise ValueError("policy event hash chain mismatch")
            previous = event.event_hash
