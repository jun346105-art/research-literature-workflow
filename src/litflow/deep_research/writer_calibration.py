"""Bounded Writer-only development calibration; no Planner or retrieval calls."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .e2e import GLMInvocationPolicy, runtime_source_sha256
from .writer import OfflineWriterResult, SingleWriterRunner, Writer
from .contracts import BriefApproval, ResearchBrief, ResearchTask
from .executor import EvidenceGraph
from .gap_replan import GapConflictAssessment
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
    artifact_dir: str = Field(pattern=rf"^{_OUTPUT_ROOT}/deep_research/writer_calibration/v1/dr-calibration-[0-9a-f]{{24}}$")


def preflight_writer_calibration(plan: WriterCalibrationPlan, *, repo_root: Path) -> None:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, capture_output=True, text=True).stdout.strip()
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", plan.implementation_commit_sha, head], cwd=repo_root, check=False)
    if ancestor.returncode != 0 or plan.runtime_source_sha256 != runtime_source_sha256():
        raise ValueError("Writer calibration implementation binding mismatch")
    if plan.artifact_dir and (repo_root / plan.artifact_dir).exists():
        raise ValueError("Writer calibration artifact directory must not already exist")


class WriterCalibrationRunner:
    """Injects one Writer into the shared B07 runner; no Planner/Tool path exists here."""

    def __init__(self, writer: Writer, *, policy: GLMInvocationPolicy):
        self._writer, self._policy = writer, policy

    async def run(self, task: ResearchTask, brief: ResearchBrief, approval: BriefApproval, plan: ValidatedResearchPlan, graph: EvidenceGraph, assessment: GapConflictAssessment, *, event_path: Path, checkpoint_path: Path) -> OfflineWriterResult:
        return await SingleWriterRunner(self._writer, budget=self._policy_budget(), reservation_usage=self._policy.reservation("writer")).run(task, brief, approval, plan, graph, assessment, event_path=event_path, checkpoint_path=checkpoint_path)

    def _policy_budget(self):
        from .budgets import BudgetSpec

        return BudgetSpec(max_provider_attempts=1, max_provider_calls=1, max_input_tokens=self._policy.writer_max_input_tokens, max_output_tokens=self._policy.writer_max_output_tokens, max_total_tokens=self._policy.writer_max_input_tokens + self._policy.writer_max_output_tokens, max_retries=0, max_replans=0, max_cost_micros=self._policy.monetary_budget_limit_micros, run_timeout_s=self._policy.run_timeout_seconds, operation_timeout_s=self._policy.operation_timeout_seconds)
