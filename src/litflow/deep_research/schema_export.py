"""Deterministic JSON Schema export for DeepResearch domain contracts."""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import ContractBundle


SCHEMA_FILENAME = "research_contract_bundle.schema.json"


def render_contract_bundle_schema() -> str:
    """Render the primary schema with stable key ordering and formatting."""
    schema = ContractBundle.model_json_schema()
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_contract_schemas(output_dir: Path) -> dict[str, Path]:
    """Write deterministic schema files to a caller-controlled directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / SCHEMA_FILENAME
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_contract_bundle_schema())
    return {SCHEMA_FILENAME: target}


def render_planner_schemas() -> dict[str, str]:
    """Render strict Planner candidate/result schemas with stable UTF-8/LF content."""
    from .planner import PlannerDraft, ValidatedResearchPlan

    return {
        "planner_draft.schema.json": json.dumps(PlannerDraft.model_json_schema(), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        "validated_research_plan.schema.json": json.dumps(ValidatedResearchPlan.model_json_schema(), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    }


def write_planner_schemas(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name, content in render_planner_schemas().items():
        target = output_dir / name
        target.write_text(content, encoding="utf-8", newline="\n")
        written[name] = target
    return written


def write_runtime_schemas(output_dir: Path) -> dict[str, Path]:
    """Write stable runtime contract schemas without importing a runtime adapter."""
    from .events import RunEvent
    from .persistence import Checkpoint
    from .state import RunState

    output_dir.mkdir(parents=True, exist_ok=True)
    schemas = {"run_state.schema.json": RunState, "run_event.schema.json": RunEvent, "checkpoint.schema.json": Checkpoint}
    written = {}
    for name, model in schemas.items():
        target = output_dir / name
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(model.model_json_schema(), ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        written[name] = target
    return written


def write_policy_schemas(output_dir: Path) -> dict[str, Path]:
    from .budgets import BudgetLedger, BudgetSpec
    from .events import PolicyEvent
    from .operations import OperationJournal, OperationRecord
    from .policies import ReplanDecision, ReplanPolicy, RetryPolicy

    output_dir.mkdir(parents=True, exist_ok=True)
    schemas = {
        "budget_spec.schema.json": BudgetSpec,
        "budget_ledger.schema.json": BudgetLedger,
        "policy_event.schema.json": PolicyEvent,
        "operation_record.schema.json": OperationRecord,
        "operation_journal.schema.json": OperationJournal,
        "retry_policy.schema.json": RetryPolicy,
        "replan_policy.schema.json": ReplanPolicy,
        "replan_decision.schema.json": ReplanDecision,
    }
    written: dict[str, Path] = {}
    for name, model in schemas.items():
        target = output_dir / name
        target.write_text(json.dumps(model.model_json_schema(), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        written[name] = target
    return written


def write_runtime_v2_schemas(output_dir: Path) -> dict[str, Path]:
    from .runtime_v2 import CoordinatedCheckpointV2, RuntimeEventEnvelope

    output_dir.mkdir(parents=True, exist_ok=True)
    schemas = {
        "runtime_event_envelope.schema.json": RuntimeEventEnvelope,
        "coordinated_checkpoint.schema.json": CoordinatedCheckpointV2,
    }
    written: dict[str, Path] = {}
    for name, model in schemas.items():
        target = output_dir / name
        target.write_text(json.dumps(model.model_json_schema(), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        written[name] = target
    return written


def render_executor_schemas() -> dict[str, str]:
    """Render B05 offline executor contracts with the shared canonical writer."""
    from .executor import EvidenceGraph, LocalExecutorResult, LocalPassage, LocalSearchRequest, ReadPassageRequest

    schemas = {
        "local_search_request.schema.json": LocalSearchRequest,
        "read_passage_request.schema.json": ReadPassageRequest,
        "local_passage.schema.json": LocalPassage,
        "evidence_graph.schema.json": EvidenceGraph,
        "local_executor_result.schema.json": LocalExecutorResult,
    }
    return {name: json.dumps(model.model_json_schema(), ensure_ascii=False, sort_keys=True, indent=2) + "\n" for name, model in schemas.items()}


def write_executor_schemas(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name, content in render_executor_schemas().items():
        target = output_dir / name
        target.write_text(content, encoding="utf-8", newline="\n")
        written[name] = target
    return written
