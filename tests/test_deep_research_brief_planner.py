from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from litflow.deep_research.contracts import BriefApproval, BriefApprovalStatus, ResearchBrief, ResearchTask
from litflow.deep_research.planner import (
    FakePlanner,
    PlannerDraft,
    PlannerError,
    PlannerSubtaskDraft,
    normalize_planner_draft,
    plan_approved_brief,
)
from litflow.deep_research.schema_export import render_planner_schemas, write_planner_schemas


NOW = datetime(2026, 8, 28, tzinfo=UTC)


def _inputs(status: BriefApprovalStatus = BriefApprovalStatus.approved):
    task = ResearchTask.create(
        original_question="What evidence supports the method?",
        locale="en",
        constraints=("local-only", "2020-2026"),
        deliverable_type="grounded_report",
        created_at=NOW,
    )
    brief = ResearchBrief.create(
        task.task_id,
        "Map method evidence.",
        ("method",),
        ("web",),
        "evidence-backed outline",
        ("source-backed support",),
        ("local-only", "2020-2026"),
        status,
    )
    approval = BriefApproval.create(brief.brief_id, task.task_id, status, "human-reviewer", NOW)
    return task, brief, approval


def _draft(task: ResearchTask, brief: ResearchBrief) -> PlannerDraft:
    return PlannerDraft(
        task_id=task.task_id,
        brief_id=brief.brief_id,
        locale=task.locale,
        constraints=brief.constraints,
        scope_inclusions=brief.scope_inclusions,
        scope_exclusions=brief.scope_exclusions,
        subtasks=(
            PlannerSubtaskDraft(
                local_key="support",
                question="Locate method evidence.",
                rationale="Required by the brief.",
                expected_evidence=("verbatim method passage",),
                completion_criteria=("one source-backed evidence unit",),
            ),
            PlannerSubtaskDraft(
                local_key="relation",
                question="Relate the evidence to the task.",
                rationale="Connects evidence to the objective.",
                dependencies=("support",),
                expected_evidence=("linked support",),
                completion_criteria=("dependency completed",),
            ),
        ),
    )


def test_approved_brief_calls_fake_planner_once_and_normalizes_a_stable_dag():
    task, brief, approval = _inputs()
    planner = FakePlanner(_draft(task, brief))

    first = asyncio.run(plan_approved_brief(task, brief, approval, planner))
    second = normalize_planner_draft(task, brief, approval, _draft(task, brief))

    assert planner.calls == 1
    assert first == second
    assert first.topological_subtask_ids == tuple(item.subtask_id for item in first.subtasks)
    assert all(item.task_id == task.task_id for item in first.subtasks)
    assert first.plan_id.startswith("dr-plan-")


@pytest.mark.parametrize(
    ("brief_status", "approval_update", "code"),
    [
        (BriefApprovalStatus.draft, {}, "brief_not_approved"),
        (BriefApprovalStatus.rejected, {}, "brief_rejected"),
        (BriefApprovalStatus.approved, {"brief_id": "dr-brief-" + "0" * 24}, "approval_identity_mismatch"),
    ],
)
def test_unapproved_or_mismatched_approval_never_calls_planner(brief_status, approval_update, code):
    task, brief, approval = _inputs(brief_status)
    planner = FakePlanner(_draft(task, brief))
    if approval_update:
        approval = approval.model_copy(update=approval_update)

    with pytest.raises(PlannerError, match=code):
        asyncio.run(plan_approved_brief(task, brief, approval, planner))
    assert planner.calls == 0


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda value: value.model_copy(update={"subtasks": value.subtasks + (value.subtasks[0],)}), "planner_contract_invalid"),
        (lambda value: value.model_copy(update={"subtasks": (value.subtasks[0].model_copy(update={"dependencies": ("missing",)}),)}), "planner_dependency_invalid"),
        (lambda value: value.model_copy(update={"subtasks": (value.subtasks[0].model_copy(update={"dependencies": ("relation",)}), value.subtasks[1])}), "planner_cycle_detected"),
        (lambda value: value.model_copy(update={"subtasks": ()}), "planner_empty"),
        (lambda value: value.model_copy(update={"constraints": ("web",)}), "planner_scope_violation"),
    ],
)
def test_untrusted_draft_invalid_shapes_fail_closed(mutate, code):
    task, brief, approval = _inputs()
    with pytest.raises(PlannerError, match=code):
        normalize_planner_draft(task, brief, approval, mutate(_draft(task, brief)))


def test_draft_rejects_unknown_evidence_claim_citation_and_final_answer_fields():
    task, brief, _ = _inputs()
    data = _draft(task, brief).model_dump(mode="json")
    data["final_answer"] = "not allowed"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        PlannerDraft.model_validate(data)


def test_planner_rejects_malformed_output_and_never_writes_evidence_or_answers():
    task, brief, approval = _inputs()
    planner = FakePlanner({"task_id": task.task_id, "brief_id": brief.brief_id, "schema_version": "wrong"})

    with pytest.raises(PlannerError, match="planner_contract_invalid"):
        asyncio.run(plan_approved_brief(task, brief, approval, planner))
    assert planner.calls == 1


def test_draft_schema_version_is_fixed_and_normalization_is_input_order_independent():
    task, brief, approval = _inputs()
    draft = _draft(task, brief)
    with pytest.raises(ValidationError):
        PlannerDraft.model_validate({**draft.model_dump(mode="json"), "schema_version": "other"})

    reordered = draft.model_copy(update={"subtasks": tuple(reversed(draft.subtasks))})
    assert normalize_planner_draft(task, brief, approval, draft) == normalize_planner_draft(task, brief, approval, reordered)


def test_planner_schemas_are_stable_and_match_committed_files(tmp_path: Path):
    written = write_planner_schemas(tmp_path)
    committed = Path("docs/deep_research/planner/v1")
    for name, target in written.items():
        assert target.read_bytes() == (committed / name).read_bytes()
    assert render_planner_schemas() == {name: (committed / name).read_text(encoding="utf-8") for name in written}
