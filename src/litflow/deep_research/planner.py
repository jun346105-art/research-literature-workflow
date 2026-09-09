"""Approved-brief planning boundary; planner output is always untrusted input."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import Field, ValidationError, field_validator

from .contracts import (
    BriefApproval,
    BriefApprovalStatus,
    ContractBundle,
    ContractModel,
    ResearchBrief,
    ResearchSubtask,
    ResearchTask,
)
from .identity import make_stable_id


PLANNER_DRAFT_VERSION = "dr-planner-draft-v1"
PLANNER_RESULT_VERSION = "dr-validated-research-plan-v1"


class PlannerError(ValueError):
    """Fail-closed, code-bearing planning error without runtime side effects."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


class PlannerSubtaskDraft(ContractModel):
    """Model candidate using local keys only; it cannot own a final subtask ID."""

    local_key: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    dependencies: tuple[str, ...] = ()
    expected_evidence: tuple[str, ...] = ()
    completion_criteria: tuple[str, ...] = ()

    @field_validator("local_key")
    @classmethod
    def validate_local_key(cls, value: str) -> str:
        if not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError("local_key must use letters, digits, underscores, or hyphens")
        return value

    @field_validator("dependencies")
    @classmethod
    def validate_dependencies(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("dependencies must be unique")
        if any(not item for item in value):
            raise ValueError("dependencies cannot contain blank local keys")
        return value


class PlannerDraft(ContractModel):
    """Strict, untrusted structured candidate returned by one Planner."""

    schema_version: Literal[PLANNER_DRAFT_VERSION] = PLANNER_DRAFT_VERSION
    task_id: str
    brief_id: str
    locale: str
    constraints: tuple[str, ...] = ()
    scope_inclusions: tuple[str, ...] = ()
    scope_exclusions: tuple[str, ...] = ()
    subtasks: tuple[PlannerSubtaskDraft, ...] = Field(default=(), min_length=1, max_length=8)


class ValidatedResearchPlan(ContractModel):
    """Program-owned formal plan after approval and deterministic normalization."""

    schema_version: Literal[PLANNER_RESULT_VERSION] = PLANNER_RESULT_VERSION
    plan_id: str
    task_id: str
    brief_id: str
    approval_id: str
    subtasks: tuple[ResearchSubtask, ...]
    topological_subtask_ids: tuple[str, ...]


@runtime_checkable
class Planner(Protocol):
    """Async-only boundary; implementations return untrusted structured values."""

    async def create_draft(self, *, task: ResearchTask, brief: ResearchBrief) -> object: ...


class FakePlanner:
    """Scripted offline planner fixture; it performs no tool, Web, or provider work."""

    def __init__(self, response: object):
        self._response = response
        self.calls = 0

    async def create_draft(self, *, task: ResearchTask, brief: ResearchBrief) -> object:
        self.calls += 1
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def require_approved_brief(task: ResearchTask, brief: ResearchBrief, approval: BriefApproval) -> None:
    """Validate one immutable human decision before a Planner may be invoked."""

    if brief.approval_status is BriefApprovalStatus.rejected:
        raise PlannerError("brief_rejected", "the current brief is rejected")
    if brief.approval_status is not BriefApprovalStatus.approved:
        raise PlannerError("brief_not_approved", "the current brief is not approved")
    if approval.status is not BriefApprovalStatus.approved:
        raise PlannerError("brief_not_approved", "the approval record is not approved")
    if approval.task_id != task.task_id or approval.brief_id != brief.brief_id or brief.task_id != task.task_id:
        raise PlannerError("approval_identity_mismatch", "approval must match the current task and immutable brief")


def _validate_draft_scope(task: ResearchTask, brief: ResearchBrief, draft: PlannerDraft, *, max_subtasks: int) -> None:
    if draft.task_id != task.task_id or draft.brief_id != brief.brief_id:
        raise PlannerError("planner_scope_violation", "draft must bind to the approved task and brief")
    if draft.locale != task.locale or draft.constraints != brief.constraints:
        raise PlannerError("planner_scope_violation", "draft locale and constraints must exactly preserve the brief")
    if draft.scope_inclusions != brief.scope_inclusions or draft.scope_exclusions != brief.scope_exclusions:
        raise PlannerError("planner_scope_violation", "draft scope must exactly preserve the brief")
    if not draft.subtasks:
        raise PlannerError("planner_empty", "draft must contain at least one subtask")
    if len(draft.subtasks) > max_subtasks:
        raise PlannerError("planner_contract_invalid", "draft exceeds the allowed subtask count")


def _topological_local_keys(draft: PlannerDraft) -> tuple[str, ...]:
    by_key = {item.local_key: item for item in draft.subtasks}
    if len(by_key) != len(draft.subtasks):
        raise PlannerError("planner_contract_invalid", "draft local keys must be unique")
    remaining: dict[str, set[str]] = {}
    for item in draft.subtasks:
        dependencies = set(item.dependencies)
        if item.local_key in dependencies or not dependencies.issubset(by_key):
            raise PlannerError("planner_dependency_invalid", "draft dependency must exist and cannot reference itself")
        remaining[item.local_key] = dependencies
    ordered: list[str] = []
    while remaining:
        ready = sorted(key for key, dependencies in remaining.items() if not dependencies)
        if not ready:
            raise PlannerError("planner_cycle_detected", "draft dependency cycle detected")
        for key in ready:
            ordered.append(key)
            remaining.pop(key)
        for dependencies in remaining.values():
            dependencies.difference_update(ready)
    return tuple(ordered)


def normalize_planner_draft(
    task: ResearchTask,
    brief: ResearchBrief,
    approval: BriefApproval,
    draft: PlannerDraft,
    *,
    max_subtasks: int = 8,
) -> ValidatedResearchPlan:
    """Turn one approved, untrusted draft into a program-owned formal DAG."""

    require_approved_brief(task, brief, approval)
    _validate_draft_scope(task, brief, draft, max_subtasks=max_subtasks)
    ordered_keys = _topological_local_keys(draft)
    by_key = {item.local_key: item for item in draft.subtasks}
    subtasks_by_key: dict[str, ResearchSubtask] = {}
    seen_semantics: set[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = set()
    for key in ordered_keys:
        candidate = by_key[key]
        semantic_key = (candidate.question, candidate.rationale, candidate.expected_evidence, candidate.completion_criteria)
        if semantic_key in seen_semantics:
            raise PlannerError("planner_contract_invalid", "duplicate executable subtask")
        seen_semantics.add(semantic_key)
        subtasks_by_key[key] = ResearchSubtask.create(
            task_id=task.task_id,
            question=candidate.question,
            rationale=candidate.rationale,
            dependency_ids=tuple(subtasks_by_key[dependency].subtask_id for dependency in sorted(candidate.dependencies)),
            expected_evidence=candidate.expected_evidence,
            completion_criteria=candidate.completion_criteria,
        )
    subtasks = tuple(subtasks_by_key[key] for key in ordered_keys)
    bundle = ContractBundle(task=task, brief=brief, brief_approvals=(approval,), subtasks=subtasks)
    topological_ids = bundle.topological_subtask_ids()
    plan_id = make_stable_id(
        "plan",
        {
            "task_id": task.task_id,
            "brief_id": brief.brief_id,
            "approval_id": approval.approval_id,
            "subtask_ids": list(topological_ids),
        },
    )
    return ValidatedResearchPlan(
        plan_id=plan_id,
        task_id=task.task_id,
        brief_id=brief.brief_id,
        approval_id=approval.approval_id,
        subtasks=subtasks,
        topological_subtask_ids=topological_ids,
    )


async def plan_approved_brief(
    task: ResearchTask,
    brief: ResearchBrief,
    approval: BriefApproval,
    planner: Planner,
    *,
    max_subtasks: int = 8,
) -> ValidatedResearchPlan:
    """The only B04 entry point: gate first, then call and normalize one Planner."""

    require_approved_brief(task, brief, approval)
    try:
        raw_draft = await planner.create_draft(task=task, brief=brief)
        draft = PlannerDraft.model_validate(raw_draft)
    except PlannerError:
        raise
    except (TypeError, ValidationError) as error:
        raise PlannerError("planner_contract_invalid", "planner output failed the strict draft contract") from error
    return normalize_planner_draft(task, brief, approval, draft, max_subtasks=max_subtasks)
