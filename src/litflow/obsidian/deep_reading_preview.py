from __future__ import annotations

from pathlib import Path

from litflow.llm.deep_reading_models import DeepReadingSidecar, SourcedValue, ValueStatus


def preview_deep_reading_objects(sidecar_path: Path, output_path: Path) -> None:
    sidecar = DeepReadingSidecar.model_validate_json(sidecar_path.read_text(encoding="utf-8-sig"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render(sidecar), encoding="utf-8")


def _render(sidecar: DeepReadingSidecar) -> str:
    lines = [f"# Deep Reading Preview: {sidecar.title}", "", "> Author-stated objects only. No analytical inference is included.", "", "## Research Problem"]
    lines.extend(_line(item.statement, item.claim_id) for item in sidecar.paper_stated_claims)
    lines.extend(["", "## Method Components", "", "| Component | Stage | Operation | Addressed Problem | Evidence |", "|---|---|---|---|---|"])
    for item in sidecar.method_components:
        lines.append(f"| {_text(item.name)} | {_text(item.architecture_stage)} | {_text(item.operation_type)} | {_text(item.addressed_problem)} | {_evidence(item.name)} |")
    lines.extend(["", "## Experiments", "", "| Task | Dataset | Split | Optimizer | Evidence |", "|---|---|---|---|---|"])
    for item in sidecar.experiment_records:
        lines.append(f"| {_text(item.task)} | {_text(item.dataset)} | {_text(item.split)} | {_text(item.optimizer)} | {_evidence(item.dataset)} |")
    lines.extend(["", "## Ablations", "", "| Design | Baseline | Variant | Metrics | Evidence |", "|---|---|---|---|---|"])
    for item in sidecar.ablation_records:
        metric = "; ".join(f"{record.name}: {_text(record.value)} {_text(record.unit)}" for record in item.metrics)
        lines.append(f"| {_text(item.ablation_design)} | {_text(item.baseline)} | {_text(item.variant)} | {metric} | {_evidence(item.baseline)} |")
    lines.extend(["", "## Missing Information"])
    missing = [value for value in _values(sidecar) if value.status == ValueStatus.not_found]
    lines.extend(f"- not_found_in_available_context: {value.raw_value or 'field not supported by supplied context'}" for value in missing) or lines.append("- None")
    return "\n".join(lines) + "\n"


def _text(value: SourcedValue[object]) -> str:
    return str(value.value) if value.status == ValueStatus.stated else value.status.value


def _evidence(value: SourcedValue[object]) -> str:
    return ", ".join(f"`{item}`" for item in value.evidence_ids) or "-"


def _line(value: SourcedValue[str], object_id: str) -> str:
    return f"- {object_id}: {_text(value)} ({_evidence(value)})"


def _values(value: object) -> list[SourcedValue[object]]:
    from pydantic import BaseModel

    if isinstance(value, SourcedValue):
        return [value]
    if isinstance(value, BaseModel):
        return [item for field in type(value).model_fields for item in _values(getattr(value, field))]
    if isinstance(value, list):
        return [item for child in value for item in _values(child)]
    return []
