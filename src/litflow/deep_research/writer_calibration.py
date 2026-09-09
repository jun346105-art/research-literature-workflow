"""Bounded Writer-only development calibration; no Planner or retrieval calls."""

from __future__ import annotations

import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .e2e import GLMInvocationPolicy, _write_json_artifact, runtime_source_sha256
from .writer import OfflineWriterResult, SingleWriterRunner, Writer
from .contracts import BriefApproval, BriefApprovalStatus, EvidenceLocator, EvidenceModality, EvidenceUnit, ResearchBrief, ResearchSubtask, ResearchTask, Source, SourceKind
from .executor import EvidenceGraph, EvidenceGraphEdge
from .gap_replan import GapConflictAssessment
from .identity import make_stable_id, sha256_hex
from .planner import ValidatedResearchPlan


CALIBRATION_VERSION = "dr-writer-calibration-v1"
_OUTPUT_ROOT = "outputs"


class WriterCalibrationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[CALIBRATION_VERSION] = CALIBRATION_VERSION
    calibration_id: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]*$")
    fixture_id: Literal["single_paper_evidence_graph_v1"] = "single_paper_evidence_graph_v1"
    implementation_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    runtime_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy: GLMInvocationPolicy = GLMInvocationPolicy()
    max_provider_calls: Literal[1] = 1
    max_retries: Literal[0] = 0
    run_id: str | None = Field(default=None, pattern=r"^dr-run-[0-9a-f]{24}$")
    artifact_dir: str = Field(pattern=rf"^{_OUTPUT_ROOT}/deep_research/writer_calibration/v1/dr-calibration-[0-9a-f]{{24}}$")


def calibration_run_id(plan: WriterCalibrationPlan) -> str:
    return make_stable_id("run", {"schema_version": plan.schema_version, "provider": "zhipu-bigmodel", "model_id": plan.policy.model_id, "calibration_id": plan.calibration_id, "fixture_id": plan.fixture_id})


def preflight_writer_calibration(plan: WriterCalibrationPlan, *, repo_root: Path, artifact_root: Path | None = None) -> None:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, capture_output=True, text=True).stdout.strip()
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", plan.implementation_commit_sha, head], cwd=repo_root, check=False)
    if ancestor.returncode != 0 or plan.runtime_source_sha256 != runtime_source_sha256():
        raise ValueError("Writer calibration implementation binding mismatch")
    expected_run_id = calibration_run_id(plan)
    if plan.run_id is not None and plan.run_id != expected_run_id:
        raise ValueError("Writer calibration run identity mismatch")
    if plan.artifact_dir and ((artifact_root or repo_root) / plan.artifact_dir).exists():
        raise ValueError("Writer calibration artifact directory must not already exist")


def build_writer_calibration_fixture(plan: WriterCalibrationPlan) -> tuple[ResearchTask, ResearchBrief, BriefApproval, ValidatedResearchPlan, EvidenceGraph, GapConflictAssessment]:
    """Create the deterministic single-paper fixture without Planner or retrieval calls."""
    now = datetime(2026, 9, 10, tzinfo=UTC)
    task = ResearchTask.create("Which local evidence supports the calibration claim?", "en", ("local-only",), "grounded_report", now)
    brief = ResearchBrief.create(task.task_id, "Produce a grounded calibration report.", ("calibration",), ("web",), "grounded report", ("one verbatim quote",), task.constraints, BriefApprovalStatus.approved)
    approval = BriefApproval.create(brief.brief_id, task.task_id, BriefApprovalStatus.approved, "offline-calibration", now)
    subtask = ResearchSubtask.create(task.task_id, "Read the supplied local calibration evidence.", "The Writer must cite the fixture evidence.", expected_evidence=("verbatim quote",), completion_criteria=("one grounded claim",))
    plan_id = make_stable_id("plan", {"task_id": task.task_id, "brief_id": brief.brief_id, "approval_id": approval.approval_id, "subtask_ids": [subtask.subtask_id]})
    validated_plan = ValidatedResearchPlan(plan_id=plan_id, task_id=task.task_id, brief_id=brief.brief_id, approval_id=approval.approval_id, subtasks=(subtask,), topological_subtask_ids=(subtask.subtask_id,))
    run_id = plan.run_id or calibration_run_id(plan)
    text = "The calibration fixture preserves a grounded local passage."
    source = Source.create(SourceKind.passage_corpus, "calibration://single-paper-evidence-graph-v1", "Writer calibration fixture", hashlib.sha256(text.encode("utf-8")).hexdigest(), "en")
    evidence = EvidenceUnit.create(source.source_id, EvidenceModality.text, EvidenceLocator(passage_id="CAL:P1", page_number=1, span_start=0, span_end=len(text)), text, "en", {"chunk_id": "CAL_P1", "evidence_type": "text"})
    edges = tuple(sorted((EvidenceGraphEdge(run_id=run_id, relation="subtask_retrieved_source", from_id=subtask.subtask_id, to_id=source.source_id), EvidenceGraphEdge(run_id=run_id, relation="source_contains_evidence", from_id=source.source_id, to_id=evidence.evidence_id), EvidenceGraphEdge(run_id=run_id, relation="evidence_supports_subtask", from_id=evidence.evidence_id, to_id=subtask.subtask_id)), key=lambda item: (item.relation, item.from_id, item.to_id)))
    graph = EvidenceGraph(run_id=run_id, task_id=task.task_id, plan_id=plan_id, subtasks=(subtask,), sources=(source,), evidence_units=(evidence,), edges=edges)
    assessment = GapConflictAssessment(assessment_id=make_stable_id("assessment", {"run_id": run_id, "gap_ids": [], "conflict_ids": []}), run_id=run_id)
    return task, brief, approval, validated_plan, graph, assessment


def write_calibration_result(plan: WriterCalibrationPlan, artifact_dir: Path, *, result: OfflineWriterResult | None = None, error_code: str | None = None) -> Path:
    """Persist only structured Writer result/diagnostics; never raw response or credentials."""
    from .runtime_v2 import RuntimeEventType, UnifiedEventStore

    run_id = plan.run_id or calibration_run_id(plan)
    events = UnifiedEventStore(artifact_dir / "runtime.jsonl", run_id=run_id).read_all()
    terminal_event = next((event for event in reversed(events) if event.event_type in {RuntimeEventType.operation_succeeded, RuntimeEventType.operation_failed, RuntimeEventType.operation_unknown} and event.payload.get("operation_name") == "single_writer"), None)
    payload = terminal_event.payload if terminal_event is not None else {}
    terminal = result.validation.status.value if result is not None else ("manual_review_required" if terminal_event is not None and terminal_event.event_type is RuntimeEventType.operation_unknown else "failed")
    summary: dict[str, object] = {"schema_version": "dr-writer-calibration-result-v1", "calibration_id": plan.calibration_id, "run_id": run_id, "terminal": terminal, "error_code": error_code or payload.get("error_code"), "provider_calls": sum(1 for event in events if event.event_type is RuntimeEventType.operation_dispatched and event.payload.get("operation_name") == "single_writer"), "planner_calls": 0, "tool_calls": 0, "usage": payload.get("usage", result.ledger.model_dump(mode="json") if result is not None else {}), "diagnostics": payload.get("diagnostics", {}), "elapsed_s": next((event.payload.get("elapsed_s") for event in reversed(events) if event.event_type is RuntimeEventType.elapsed_recorded), None), "draft": payload.get("draft"), "validation": result.validation.model_dump(mode="json") if result is not None else payload.get("validation"), "replayed": bool(result.resumed) if result is not None else False, "artifact_files": {"runtime.jsonl": {"sha256": sha256_hex((artifact_dir / "runtime.jsonl").read_bytes()), "bytes": (artifact_dir / "runtime.jsonl").stat().st_size}, "checkpoint.json": {"sha256": sha256_hex((artifact_dir / "checkpoint.json").read_bytes()), "bytes": (artifact_dir / "checkpoint.json").stat().st_size}}}
    return _write_json_artifact(artifact_dir / "calibration_result.json", summary) and artifact_dir / "calibration_result.json"


class WriterCalibrationRunner:
    """Injects one Writer into the shared B07 runner; no Planner/Tool path exists here."""

    def __init__(self, writer: Writer, *, policy: GLMInvocationPolicy):
        self._writer, self._policy = writer, policy

    async def run(self, task: ResearchTask, brief: ResearchBrief, approval: BriefApproval, plan: ValidatedResearchPlan, graph: EvidenceGraph, assessment: GapConflictAssessment, *, event_path: Path, checkpoint_path: Path) -> OfflineWriterResult:
        return await SingleWriterRunner(self._writer, budget=self._policy_budget(), reservation_usage=self._policy.reservation("writer")).run(task, brief, approval, plan, graph, assessment, event_path=event_path, checkpoint_path=checkpoint_path)

    def _policy_budget(self):
        from .budgets import BudgetSpec

        return BudgetSpec(max_provider_attempts=1, max_provider_calls=1, max_input_tokens=self._policy.writer_max_input_tokens, max_output_tokens=self._policy.writer_max_output_tokens, max_total_tokens=self._policy.writer_max_input_tokens + self._policy.writer_max_output_tokens, max_retries=0, max_replans=0, max_cost_micros=self._policy.monetary_budget_limit_micros, run_timeout_s=self._policy.run_timeout_seconds, operation_timeout_s=self._policy.operation_timeout_seconds)
