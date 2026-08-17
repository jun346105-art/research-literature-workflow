from __future__ import annotations

import re
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


T = TypeVar("T")
ID_PATTERN = re.compile(r"^[A-Za-z0-9]+:(claim|component|experiment|ablation):\d{4}$")


class ValueStatus(str, Enum):
    stated = "stated"
    not_found = "not_found_in_available_context"
    not_applicable = "not_applicable"


class ArchitectureStage(str, Enum):
    backbone = "backbone"
    neck = "neck"
    head = "head"
    preprocessing = "preprocessing"
    postprocessing = "postprocessing"
    unknown = "unknown"


class OperationType(str, Enum):
    convolution = "convolution"
    attention = "attention"
    fusion = "fusion"
    upsampling = "upsampling"
    loss = "loss"
    geometric = "geometric"
    other = "other"


class AblationDesign(str, Enum):
    single_component = "single_component"
    cumulative_components = "cumulative_components"
    full_model_comparison = "full_model_comparison"
    unclear = "unclear"


class SourcedValue(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")
    value: T | None = None
    status: ValueStatus
    evidence_ids: list[str] = Field(default_factory=list)
    raw_value: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status(self):
        if self.status == ValueStatus.stated and (self.value is None or not self.evidence_ids):
            raise ValueError("stated value requires a value and evidence_ids")
        if self.status != ValueStatus.stated and (self.value is not None or self.evidence_ids):
            raise ValueError("non-stated value cannot contain a value or evidence_ids")
        return self


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    origin: str
    chunk_id: str
    page_start: int
    page_end: int
    span_start: int
    span_end: int
    evidence_text: str
    evidence_sha256: str
    anchor_method: str


class PaperStatedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_id: str
    claim_kind: str
    statement: SourcedValue[str]
    scope: SourcedValue[str]


class MethodComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component_id: str
    name: SourcedValue[str]
    architecture_stage: SourcedValue[ArchitectureStage]
    architecture_stage_raw: str | None = None
    operation_type: SourcedValue[OperationType]
    operation_type_raw: str | None = None
    insertion_point: SourcedValue[str]
    input_description: SourcedValue[str]
    operation_description: SourcedValue[str]
    output_description: SourcedValue[str]
    addressed_problem: SourcedValue[str]
    author_claimed_effect: SourcedValue[str]
    stated_design_motivation: SourcedValue[str]


class NamedSetting(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    value: SourcedValue[str]


class MetricRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    value: SourcedValue[float]
    unit: SourcedValue[str]


class ExperimentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiment_id: str
    experiment_kind: str
    task: SourcedValue[str]
    dataset: SourcedValue[str]
    split: SourcedValue[str]
    training_settings: list[NamedSetting] = Field(default_factory=list)
    hardware: SourcedValue[str]
    input_size: SourcedValue[str]
    optimizer: SourcedValue[str]
    metrics: list[MetricRecord] = Field(default_factory=list)
    comparison_target: SourcedValue[str]


class AblationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ablation_id: str
    ablation_design: SourcedValue[AblationDesign]
    baseline: SourcedValue[str]
    variant: SourcedValue[str]
    changed_components: SourcedValue[list[str]]
    metrics: list[MetricRecord] = Field(default_factory=list)
    comparison_conditions: SourcedValue[str]
    interpretation: SourcedValue[str]


class DeepReadingSidecar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "v0.3A"
    zotero_key: str
    citation_key: str | None = None
    title: str
    candidate_bank_sha256: str
    evidence_registry: list[EvidenceRecord]
    paper_stated_claims: list[PaperStatedClaim] = Field(default_factory=list)
    method_components: list[MethodComponent] = Field(default_factory=list)
    experiment_records: list[ExperimentRecord] = Field(default_factory=list)
    ablation_records: list[AblationRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_cross_references(self):
        evidence_ids = {item.evidence_id for item in self.evidence_registry}
        component_ids = {item.component_id for item in self.method_components}
        for object_id in _object_ids(self):
            if not ID_PATTERN.match(object_id) or not object_id.startswith(f"{self.zotero_key}:"):
                raise ValueError(f"invalid or cross-paper object id: {object_id}")
        for value in _sourced_values(self):
            unknown = set(value.evidence_ids) - evidence_ids
            if unknown:
                raise ValueError(f"unknown or cross-paper evidence ids: {sorted(unknown)}")
        for record in self.ablation_records:
            components = record.changed_components.value or []
            unknown = set(components) - component_ids
            if unknown:
                raise ValueError(f"ablation references unknown components: {sorted(unknown)}")
        return self


def not_found_value() -> dict[str, Any]:
    return {"value": None, "status": ValueStatus.not_found, "evidence_ids": [], "raw_value": None, "warnings": []}


def _object_ids(sidecar: DeepReadingSidecar) -> list[str]:
    return [item.claim_id for item in sidecar.paper_stated_claims] + [item.component_id for item in sidecar.method_components] + [item.experiment_id for item in sidecar.experiment_records] + [item.ablation_id for item in sidecar.ablation_records]


def _sourced_values(value: Any) -> list[SourcedValue[Any]]:
    if isinstance(value, SourcedValue):
        return [value]
    if isinstance(value, BaseModel):
        return [item for field in type(value).model_fields for item in _sourced_values(getattr(value, field))]
    if isinstance(value, list):
        return [item for child in value for item in _sourced_values(child)]
    return []
