"""Pure DeepResearch lifecycle state and transition guards."""
from __future__ import annotations
from enum import Enum
from pydantic import Field
from .contracts import CONTRACT_VERSION, ContractModel
from .identity import make_stable_id

RUNTIME_VERSION = "dr-runtime-v1"

class RunStatus(str, Enum):
    brief_pending="brief_pending"; brief_approved="brief_approved"; researching="researching"; validating="validating"; complete="complete"; insufficient_evidence="insufficient_evidence"; failed="failed"

TERMINAL=frozenset({RunStatus.complete,RunStatus.insufficient_evidence,RunStatus.failed})
ALLOWED={RunStatus.brief_pending:{RunStatus.brief_approved},RunStatus.brief_approved:{RunStatus.researching,RunStatus.failed},RunStatus.researching:{RunStatus.validating,RunStatus.insufficient_evidence,RunStatus.failed},RunStatus.validating:{RunStatus.complete,RunStatus.insufficient_evidence,RunStatus.failed}}

class TransitionError(ValueError): pass

class RunState(ContractModel):
    runtime_version: str=Field(default=RUNTIME_VERSION,description="Runtime kernel version.")
    run_id: str=Field(description="Program-generated deterministic run ID.")
    task_id: str=Field(description="Referenced B01 task ID.")
    brief_id: str=Field(description="Referenced B01 brief ID.")
    brief_approved: bool=Field(description="Verified brief approval reference state.")
    status: RunStatus=Field(default=RunStatus.brief_pending,description="Explicit lifecycle status.")
    applied_event_count: int=Field(default=0,ge=0,description="Applied durable event count.")
    event_head: str|None=Field(default=None,description="Last durable event hash.")
    terminal_reason: str|None=Field(default=None,description="Structured terminal reason label.")
    @classmethod
    def create(cls,task_id:str,brief_id:str,brief_approved:bool)->"RunState":
        return cls(run_id=make_stable_id("run",{"runtime":RUNTIME_VERSION,"task_id":task_id,"brief_id":brief_id}),task_id=task_id,brief_id=brief_id,brief_approved=brief_approved)

def next_state(state:RunState,target:RunStatus,reason:str|None=None)->RunState:
    if state.status in TERMINAL: raise TransitionError("terminal state is absorbing")
    if target not in ALLOWED.get(state.status,set()): raise TransitionError("illegal lifecycle transition")
    if target is RunStatus.brief_approved and not state.brief_approved: raise TransitionError("brief approval requires an approved brief")
    if target in TERMINAL and not reason: reason=target.value
    return state.model_copy(update={"status":target,"terminal_reason":reason if target in TERMINAL else None})

def transition(state:RunState,target:RunStatus,*,occurred_at=None,reason:str|None=None):
    """Validate in memory before constructing the one corresponding event."""
    provisional=next_state(state,target,reason)
    from .events import create_event
    event=create_event(state,provisional,occurred_at=occurred_at)
    return provisional.model_copy(update={"applied_event_count":event.sequence,"event_head":event.event_hash}),event
