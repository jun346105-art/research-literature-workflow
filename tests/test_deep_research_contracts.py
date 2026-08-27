from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from litflow.deep_research.contracts import (
    BriefApproval,
    BriefApprovalStatus,
    Citation,
    CitationRelation,
    ContractBundle,
    EvidenceLocator,
    EvidenceModality,
    EvidenceUnit,
    ResearchBrief,
    ResearchSubtask,
    ResearchTask,
    Source,
    SourceKind,
    Claim,
)
from litflow.deep_research.identity import canonical_json, make_stable_id
from litflow.deep_research.schema_export import render_contract_bundle_schema, write_contract_schemas


NOW = datetime(2026, 8, 27, tzinfo=UTC)
TEXT = "A verified sentence from the source."
TEXT_SHA = hashlib.sha256(TEXT.encode("utf-8")).hexdigest()


def _task() -> ResearchTask:
    return ResearchTask.create(
        original_question="What supports the method?",
        locale="en",
        constraints=("local-only",),
        deliverable_type="grounded_report",
        created_at=NOW,
    )


def _bundle() -> ContractBundle:
    task = _task()
    brief = ResearchBrief.create(
        task_id=task.task_id,
        objective="Map available support.",
        scope_inclusions=("method",),
        scope_exclusions=("web",),
        deliverable="evidence-backed outline",
        success_criteria=("every claim has evidence",),
        constraints=("no provider",),
        approval_status=BriefApprovalStatus.approved,
    )
    approval = BriefApproval.create(
        brief_id=brief.brief_id,
        task_id=task.task_id,
        status=BriefApprovalStatus.approved,
        actor="researcher",
        decided_at=NOW,
    )
    first = ResearchSubtask.create(
        task_id=task.task_id,
        question="Locate method evidence.",
        rationale="Required before synthesis.",
        expected_evidence=("verbatim method passage",),
        completion_criteria=("one source-backed evidence unit",),
    )
    second = ResearchSubtask.create(
        task_id=task.task_id,
        question="Relate evidence to the task.",
        rationale="Supports the final claim.",
        dependency_ids=(first.subtask_id,),
        expected_evidence=("linked claim",),
        completion_criteria=("citation integrity",),
    )
    source = Source.create(
        kind=SourceKind.local_pdf,
        canonical_reference="doi:10.1000/example",
        title="Example paper",
        content_sha256="a" * 64,
        language="en",
    )
    evidence = EvidenceUnit.create(
        source_id=source.source_id,
        modality=EvidenceModality.text,
        locator=EvidenceLocator(passage_id="P1:C1", page_number=1, span_start=0, span_end=len(TEXT)),
        verbatim_content=TEXT,
        language="en",
    )
    claim = Claim.create(task_id=task.task_id, text="The source supports the method.", language="en")
    citation = Citation.create(
        claim_id=claim.claim_id,
        evidence_id=evidence.evidence_id,
        relation=CitationRelation.support,
        quote=TEXT,
        quote_span_start=0,
        quote_span_end=len(TEXT),
    )
    return ContractBundle(
        task=task,
        brief=brief,
        brief_approvals=(approval,),
        subtasks=(second, first),
        sources=(source,),
        evidence_units=(evidence,),
        claims=(claim,),
        citations=(citation,),
    )


def test_contracts_construct_round_trip_and_export_stable_schema(tmp_path: Path):
    bundle = _bundle()

    assert bundle.topological_subtask_ids() == (bundle.subtasks[1].subtask_id, bundle.subtasks[0].subtask_id)
    assert ContractBundle.model_validate_json(bundle.model_dump_json()) == bundle
    assert json.loads(canonical_json({"b": "值", "a": 1})) == {"a": 1, "b": "值"}

    written = write_contract_schemas(tmp_path)
    committed = Path("docs/deep_research/contracts/v1/research_contract_bundle.schema.json")
    assert written["research_contract_bundle.schema.json"].read_bytes() == committed.read_bytes()
    assert render_contract_bundle_schema() == committed.read_text(encoding="utf-8")


def test_ids_are_deterministic_prefixed_and_change_with_semantic_input():
    first = make_stable_id("task", {"question": "same", "constraints": ["x"]})
    second = make_stable_id("task", {"constraints": ["x"], "question": "same"})
    changed = make_stable_id("task", {"question": "changed", "constraints": ["x"]})

    assert first == second
    assert first != changed
    assert first.startswith("dr-task-")
    assert len(first.rsplit("-", 1)[1]) == 24


def test_strict_models_reject_extra_blank_naive_datetime_and_private_path():
    with pytest.raises(ValidationError, match="extra_forbidden"):
        _task().model_validate({**_task().model_dump(mode="json"), "extra": True})
    with pytest.raises(ValidationError):
        ResearchTask.create("  ", "en", (), "grounded_report", NOW)
    with pytest.raises(ValidationError):
        ResearchTask.create("question", "en", (), "grounded_report", datetime(2026, 8, 27))
    with pytest.raises(ValidationError):
        Source.create(SourceKind.local_pdf, "C:\\private\\paper.pdf", "paper", "a" * 64, "en")


def test_brief_approval_semantics_require_auditable_record():
    task = _task()
    brief = ResearchBrief.create(task.task_id, "objective", (), (), "report", ("criterion",), (), BriefApprovalStatus.approved)
    with pytest.raises(ValidationError, match="approval"):
        ContractBundle(task=task, brief=brief)


def test_bundle_rejects_missing_dependency_self_cycle_and_cross_task_references():
    bundle = _bundle()
    first, second = bundle.subtasks[1], bundle.subtasks[0]
    with pytest.raises(ValidationError, match="dependency"):
        ContractBundle(task=bundle.task, brief=bundle.brief, brief_approvals=bundle.brief_approvals, subtasks=(first.model_copy(update={"dependency_ids": ("dr-subtask-missing",)}),))
    with pytest.raises(ValidationError, match="self dependency"):
        ContractBundle(task=bundle.task, brief=bundle.brief, brief_approvals=bundle.brief_approvals, subtasks=(first.model_copy(update={"dependency_ids": (first.subtask_id,)}),))
    with pytest.raises(ValidationError, match="cycle"):
        ContractBundle(task=bundle.task, brief=bundle.brief, brief_approvals=bundle.brief_approvals, subtasks=(first.model_copy(update={"dependency_ids": (second.subtask_id,)}), second))
    with pytest.raises(ValidationError, match="same task"):
        ContractBundle(task=bundle.task, brief=bundle.brief.model_copy(update={"task_id": "dr-task-" + "0" * 24}), brief_approvals=bundle.brief_approvals)


def test_bundle_rejects_broken_references_span_hash_and_locator_modality():
    bundle = _bundle()
    evidence = bundle.evidence_units[0]
    with pytest.raises(ValidationError, match="evidence_id"):
        ContractBundle(task=bundle.task, brief=bundle.brief, brief_approvals=bundle.brief_approvals, evidence_units=(evidence,), claims=bundle.claims, citations=(bundle.citations[0].model_copy(update={"evidence_id": "dr-evidence-" + "0" * 24}),))
    with pytest.raises(ValidationError, match="quote"):
        ContractBundle(task=bundle.task, brief=bundle.brief, brief_approvals=bundle.brief_approvals, sources=bundle.sources, evidence_units=(evidence,), claims=bundle.claims, citations=(bundle.citations[0].model_copy(update={"quote": "wrong"}),))
    with pytest.raises(ValidationError, match="content_sha256"):
        ContractBundle(task=bundle.task, brief=bundle.brief, brief_approvals=bundle.brief_approvals, sources=bundle.sources, evidence_units=(evidence.model_copy(update={"content_sha256": "b" * 64}),), claims=bundle.claims, citations=bundle.citations)
    with pytest.raises(ValidationError, match="text modality"):
        EvidenceUnit.create(source_id=bundle.sources[0].source_id, modality=EvidenceModality.text, locator=EvidenceLocator(page_number=1, bbox=(0.0, 0.0, 1.0, 1.0), coordinate_space="pdf_points"), verbatim_content=TEXT, language="en")


def test_domain_contract_modules_do_not_import_runtime_or_provider_dependencies():
    root = Path("src/litflow/deep_research")
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    for forbidden in ("langgraph", "fastapi", "httpx", "numpy", "torch", "transformers", "litflow.agent", "litflow.rag", "litflow.llm"):
        assert forbidden not in text
