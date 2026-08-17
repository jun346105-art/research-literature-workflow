from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from litflow.llm.client import LLMClient, LLMError, OpenAICompatibleClient
from litflow.llm.deep_reading_models import (
    AblationRecord, DeepReadingSidecar, ExperimentRecord, MethodComponent, MetricRecord,
    NamedSetting, PaperStatedClaim, SourcedValue, ValueStatus, not_found_value,
)
from litflow.llm.evidence_registry import EvidenceRegistry, load_registry
from litflow.llm.structured_reader import _parse_json_response


DEEP_READING_PROMPT_VERSION = "deep-reading-objects-v0.3A"


def plan_deep_reading(
    candidate_bank_path: Path,
    clean_context_path: Path,
    *,
    model: str,
    context_limit_tokens: int = 1_000_000,
    max_output_tokens: int = 8192,
    safety_margin_tokens: int = 16_384,
) -> dict[str, Any]:
    registry = load_registry(candidate_bank_path, clean_context_path)
    clean = _load(clean_context_path)
    prompt = _prompt(clean, registry)
    estimated_input = (len(prompt) + 3) // 4
    required = estimated_input + max_output_tokens + safety_margin_tokens
    if required > context_limit_tokens:
        raise ValueError("deep-reading prompt exceeds configured context limit before LLM call")
    return {
        "role": "development_vertical_slice",
        "zotero_key": registry.zotero_key,
        "prompt_version": DEEP_READING_PROMPT_VERSION,
        "candidate_bank_sha256": _sha256_file(candidate_bank_path),
        "clean_context_sha256": _sha256_file(clean_context_path),
        "full_context_char_count": sum(len(chunk.get("text") or "") for chunk in clean.get("chunks", [])),
        "candidate_evidence_char_count": sum(len(record.evidence_text) for record in registry.records),
        "prompt_char_count": len(prompt),
        "prompt_sha256": _sha256_text(prompt),
        "estimated_input_tokens": estimated_input,
        "context_guard": {
            "context_limit_tokens": context_limit_tokens,
            "max_output_tokens": max_output_tokens,
            "safety_margin_tokens": safety_margin_tokens,
            "required_tokens": required,
            "within_limit": True,
            "token_estimator": "chars_div_4",
        },
        "estimated_calls": 1,
        "model": model,
    }


def extract_deep_reading_objects(
    candidate_bank_path: Path,
    clean_context_path: Path,
    output_path: Path,
    *,
    client: LLMClient | None = None,
    model: str = "unconfigured",
    context_limit_tokens: int = 1_000_000,
    max_output_tokens: int = 8192,
    safety_margin_tokens: int = 16_384,
    resume: bool = False,
    thinking_mode: str | None = "disabled",
) -> DeepReadingSidecar:
    plan = plan_deep_reading(
        candidate_bank_path,
        clean_context_path,
        model=model,
        context_limit_tokens=context_limit_tokens,
        max_output_tokens=max_output_tokens,
        safety_margin_tokens=safety_margin_tokens,
    )
    run_dir = output_path.parent
    identity = _sha256_text(json.dumps({"plan": plan, "git": _git_metadata()}, sort_keys=True))
    checkpoint_path = run_dir / "checkpoint.json"
    if (run_dir / "run_manifest.json").exists() and not resume:
        raise LLMError("deep-reading run directory already exists; use --resume only for the same identity")
    registry = load_registry(candidate_bank_path, clean_context_path)
    clean = _load(clean_context_path)
    prompt = _prompt(clean, registry)
    raw_path = run_dir / "raw_response.txt"
    if resume and checkpoint_path.is_file():
        checkpoint = _load(checkpoint_path)
        if checkpoint.get("identity_sha256") != identity or not raw_path.is_file() or _sha256_file(raw_path) != checkpoint.get("response_sha256"):
            raise LLMError("deep-reading checkpoint identity or response SHA-256 mismatch")
        raw_response = raw_path.read_text(encoding="utf-8")
        usage = {"status": "resumed", "input_tokens": None, "output_tokens": None, "total_tokens": None, "latency_ms": 0}
    else:
        client = client or OpenAICompatibleClient.from_env(thinking_mode=thinking_mode)
        if isinstance(client, OpenAICompatibleClient) and model != client.model:
            raise LLMError("--model must match LLM_MODEL when deep-reading execute is used")
        started = time.perf_counter()
        complete_with_usage = getattr(client, "complete_json_with_usage", None)
        if callable(complete_with_usage):
            completion = complete_with_usage(prompt, temperature=0, max_output_tokens=max_output_tokens)
            raw_response = completion.content
            usage = {"status": "provider_reported" if completion.total_tokens is not None else "usage_unavailable", "input_tokens": completion.input_tokens, "output_tokens": completion.output_tokens, "total_tokens": completion.total_tokens, "latency_ms": round((time.perf_counter() - started) * 1000, 3)}
        else:
            raw_response = client.complete_json(prompt)
            usage = {"status": "usage_unavailable", "input_tokens": None, "output_tokens": None, "total_tokens": None, "latency_ms": round((time.perf_counter() - started) * 1000, 3)}
        _atomic_write(raw_path, raw_response)
        _atomic_write(checkpoint_path, json.dumps({"identity_sha256": identity, "response_sha256": _sha256_file(raw_path), "prompt_sha256": plan["prompt_sha256"]}, indent=2) + "\n")
    try:
        payload = _parse_json_response(raw_response)
        sidecar = _assemble(payload, clean, registry, _sha256_file(candidate_bank_path))
    except Exception as exc:
        _write_error(output_path, raw_response, exc)
        raise LLMError(f"LLM returned invalid deep-reading objects; raw response saved to {output_path.with_suffix('.error.json')}") from exc
    _atomic_write(output_path, sidecar.model_dump_json(indent=2) + "\n")
    _atomic_write(run_dir / "evidence_registry.json", json.dumps([record.model_dump() for record in sidecar.evidence_registry], ensure_ascii=False, indent=2) + "\n")
    _atomic_write(run_dir / "anchor_failure_ledger.json", json.dumps(_failure_ledger(sidecar), ensure_ascii=False, indent=2) + "\n")
    _atomic_write(run_dir / "validation_report.json", json.dumps(_validation_report(sidecar), ensure_ascii=False, indent=2) + "\n")
    _atomic_write(run_dir / "usage.json", json.dumps(usage, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(run_dir / "run_manifest.json", json.dumps({"run_id": run_dir.name, "plan": plan, "identity_sha256": identity, "git": _git_metadata(), "request_config": {"thinking_mode": thinking_mode, "response_format": {"type": "json_object"}}, "resume": resume}, ensure_ascii=False, indent=2) + "\n")
    return sidecar


def _prompt(clean: dict[str, Any], registry: EvidenceRegistry) -> str:
    schema = {
        "paper_stated_claims": [{"claim_kind": "", "statement": _raw_value(), "scope": _raw_value()}],
        "method_components": [{"name": _raw_value(), "architecture_stage": _raw_value(), "operation_type": _raw_value(), "insertion_point": _raw_value(), "input_description": _raw_value(), "operation_description": _raw_value(), "output_description": _raw_value(), "addressed_problem": _raw_value(), "author_claimed_effect": _raw_value(), "stated_design_motivation": _raw_value()}],
        "experiment_records": [{"experiment_kind": "", "task": _raw_value(), "dataset": _raw_value(), "split": _raw_value(), "training_settings": [{"name": "", "value": _raw_value()}], "hardware": _raw_value(), "input_size": _raw_value(), "optimizer": _raw_value(), "metrics": [{"name": "", "value": _raw_value(), "unit": _raw_value()}], "comparison_target": _raw_value()}],
        "ablation_records": [{"ablation_design": _raw_value(), "baseline": _raw_value(), "variant": _raw_value(), "changed_components": _raw_value(), "metrics": [{"name": "", "value": _raw_value(), "unit": _raw_value()}], "comparison_conditions": _raw_value(), "interpretation": _raw_value()}],
    }
    evidence = [record.model_dump() for record in registry.records]
    chunks = [{key: chunk.get(key) for key in ("chunk_id", "page_start", "page_end", "section_guess", "text")} for chunk in clean.get("chunks", [])]
    return (
        "Extract only paper-stated deep-reading objects. Return JSON only.\n"
        "Use existing_evidence_ids when provided evidence supports a field. For a new source, provide quote_hints with declared chunk_id and a short contiguous quote_hint.\n"
        "Never state a value without existing_evidence_ids or quote_hints. If no support is found in the supplied context, use status not_found_in_available_context with value null.\n"
        "Do not infer, do not use external knowledge, do not claim a component insertion point unless it is stated.\n"
        "A full-model comparison is not a single-component ablation.\n"
        f"Schema: {json.dumps(schema, ensure_ascii=False)}\n"
        f"Existing evidence registry: {json.dumps(evidence, ensure_ascii=False)}\n"
        f"Full clean context: {json.dumps(chunks, ensure_ascii=False)}"
    )


def _raw_value() -> dict[str, Any]:
    return {"value": None, "status": "not_found_in_available_context", "existing_evidence_ids": [], "quote_hints": [], "raw_value": None, "warnings": []}


def _assemble(payload: dict[str, Any], clean: dict[str, Any], registry: EvidenceRegistry, bank_sha: str) -> DeepReadingSidecar:
    metadata = clean.get("metadata", {})
    key = metadata.get("zotero_key") or registry.zotero_key
    warnings: list[str] = []
    components = [_component(item, registry, key, index, warnings) for index, item in enumerate(payload.get("method_components", []), 1)]
    claims = [_claim(item, registry, key, index, warnings) for index, item in enumerate(payload.get("paper_stated_claims", []), 1)]
    experiments = [_experiment(item, registry, key, index, warnings) for index, item in enumerate(payload.get("experiment_records", []), 1)]
    ablations = [_ablation(item, registry, key, index, warnings) for index, item in enumerate(payload.get("ablation_records", []), 1)]
    return DeepReadingSidecar(
        zotero_key=key,
        citation_key=metadata.get("citation_key"),
        title=metadata.get("title") or "",
        candidate_bank_sha256=bank_sha,
        evidence_registry=registry.records,
        paper_stated_claims=claims,
        method_components=components,
        experiment_records=experiments,
        ablation_records=ablations,
        warnings=warnings,
    )


def _value(raw: Any, registry: EvidenceRegistry, warnings: list[str]) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    status = raw.get("status", ValueStatus.not_found)
    allowed = {ValueStatus.stated, ValueStatus.not_found, ValueStatus.not_applicable, "stated", "not_found_in_available_context", "not_applicable"}
    if status not in allowed:
        raise ValueError(f"unsupported sourced-value status: {status}")
    if status != ValueStatus.stated and status != "stated":
        return not_found_value() if status == ValueStatus.not_found or status == "not_found_in_available_context" else {"value": None, "status": ValueStatus.not_applicable, "evidence_ids": [], "raw_value": None, "warnings": []}
    evidence_ids = list(raw.get("existing_evidence_ids") or [])
    errors: list[str] = []
    known = {record.evidence_id for record in registry.records}
    if any(item not in known or not item.startswith(f"{registry.zotero_key}_") for item in evidence_ids):
        raise ValueError("invalid or cross-paper existing evidence id")
    for quote in raw.get("quote_hints") or []:
        evidence_id, error = registry.add_quote(str(quote.get("chunk_id") or ""), str(quote.get("quote_hint") or ""))
        if evidence_id:
            evidence_ids.append(evidence_id)
        else:
            errors.append(error or "evidence_anchor_not_found")
    if raw.get("value") is None or not evidence_ids or errors:
        warning = f"field downgraded to not_found_in_available_context: {','.join(errors or ['missing_value_or_evidence'])}"
        warnings.append(warning)
        return {"value": None, "status": ValueStatus.not_found, "evidence_ids": [], "raw_value": raw.get("raw_value"), "warnings": [warning]}
    return {"value": raw.get("value"), "status": ValueStatus.stated, "evidence_ids": evidence_ids, "raw_value": raw.get("raw_value"), "warnings": list(raw.get("warnings") or [])}


def _claim(raw: dict[str, Any], registry: EvidenceRegistry, key: str, index: int, warnings: list[str]) -> PaperStatedClaim:
    return PaperStatedClaim(claim_id=f"{key}:claim:{index:04d}", claim_kind=str(raw.get("claim_kind") or "other"), statement=_value(raw.get("statement"), registry, warnings), scope=_value(raw.get("scope"), registry, warnings))


def _component(raw: dict[str, Any], registry: EvidenceRegistry, key: str, index: int, warnings: list[str]) -> MethodComponent:
    names = ("name", "architecture_stage", "operation_type", "insertion_point", "input_description", "operation_description", "output_description", "addressed_problem", "author_claimed_effect", "stated_design_motivation")
    values = {name: _value(raw.get(name), registry, warnings) for name in names}
    return MethodComponent(component_id=f"{key}:component:{index:04d}", **values)


def _metric(raw: dict[str, Any], registry: EvidenceRegistry, warnings: list[str]) -> MetricRecord:
    return MetricRecord(name=str(raw.get("name") or "unknown"), value=_value(raw.get("value"), registry, warnings), unit=_value(raw.get("unit"), registry, warnings))


def _experiment(raw: dict[str, Any], registry: EvidenceRegistry, key: str, index: int, warnings: list[str]) -> ExperimentRecord:
    settings = [NamedSetting(name=str(item.get("name") or "unknown"), value=_value(item.get("value"), registry, warnings)) for item in raw.get("training_settings", [])]
    return ExperimentRecord(experiment_id=f"{key}:experiment:{index:04d}", experiment_kind=str(raw.get("experiment_kind") or "other"), task=_value(raw.get("task"), registry, warnings), dataset=_value(raw.get("dataset"), registry, warnings), split=_value(raw.get("split"), registry, warnings), training_settings=settings, hardware=_value(raw.get("hardware"), registry, warnings), input_size=_value(raw.get("input_size"), registry, warnings), optimizer=_value(raw.get("optimizer"), registry, warnings), metrics=[_metric(item, registry, warnings) for item in raw.get("metrics", [])], comparison_target=_value(raw.get("comparison_target"), registry, warnings))


def _ablation(raw: dict[str, Any], registry: EvidenceRegistry, key: str, index: int, warnings: list[str]) -> AblationRecord:
    return AblationRecord(ablation_id=f"{key}:ablation:{index:04d}", ablation_design=_value(raw.get("ablation_design"), registry, warnings), baseline=_value(raw.get("baseline"), registry, warnings), variant=_value(raw.get("variant"), registry, warnings), changed_components=_value(raw.get("changed_components"), registry, warnings), metrics=[_metric(item, registry, warnings) for item in raw.get("metrics", [])], comparison_conditions=_value(raw.get("comparison_conditions"), registry, warnings), interpretation=_value(raw.get("interpretation"), registry, warnings))


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_error(output_path: Path, raw_response: str, error: Exception) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.with_suffix(".error.json").write_text(json.dumps({"error_type": type(error).__name__, "error": str(error), "raw_response": raw_response}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _failure_ledger(sidecar: DeepReadingSidecar) -> dict[str, Any]:
    failures = []
    for path, value in _walk_values(sidecar):
        if value.status == ValueStatus.not_found and value.warnings:
            failures.append({"field_path": path, "status": value.status, "warnings": value.warnings})
    return {"count": len(failures), "failures": failures}


def _validation_report(sidecar: DeepReadingSidecar) -> dict[str, Any]:
    values = [value for _, value in _walk_values(sidecar)]
    stated = [value for value in values if value.status == ValueStatus.stated]
    return {"schema_valid": True, "method_component_count": len(sidecar.method_components), "experiment_record_count": len(sidecar.experiment_records), "ablation_record_count": len(sidecar.ablation_records), "stated_field_count": len(stated), "stated_fields_with_evidence": sum(bool(value.evidence_ids) for value in stated), "not_found_field_count": sum(value.status == ValueStatus.not_found for value in values)}


def _walk_values(value: Any, prefix: str = "") -> list[tuple[str, SourcedValue[Any]]]:
    from pydantic import BaseModel

    if isinstance(value, SourcedValue):
        return [(prefix, value)]
    if isinstance(value, BaseModel):
        return [item for field in type(value).model_fields for item in _walk_values(getattr(value, field), f"{prefix}.{field}".strip("."))]
    if isinstance(value, list):
        return [item for index, child in enumerate(value) for item in _walk_values(child, f"{prefix}[{index}]")]
    return []


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _git_metadata() -> dict[str, str | None]:
    try:
        root = Path.cwd()
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        return {"git_commit_sha": commit, "git_worktree_status": "dirty" if dirty else "clean"}
    except subprocess.CalledProcessError:
        return {"git_commit_sha": None, "git_worktree_status": "unavailable"}
