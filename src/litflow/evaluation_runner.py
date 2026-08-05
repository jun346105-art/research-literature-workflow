from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from litflow.evaluation import score_evidence_note
from litflow.llm.client import LLMClient, LLMError
from litflow.llm.evidence_bank_note import generate_note_from_evidence_bank
from litflow.llm.evidence_candidates import _chunk_prompt, build_evidence_candidate_bank
from litflow.llm.models import StructuredReadingNote
from litflow.llm.structured_reader import _parse_json_response, build_llm_input


RAW_BASELINE_PROMPT_VERSION = "raw-baseline-multichunk-v1"
PROPOSED_CANDIDATE_PROMPT_VERSION = "chunk-constrained-evidence-v1"
PROPOSED_FINAL_PROMPT_VERSION = "evidence-bank-note-v1"


class FrozenInputError(ValueError):
    pass


@dataclass(frozen=True)
class FrozenPaper:
    zotero_key: str
    citation_key: str
    title: str
    clean_context_path: Path
    pdf_path: Path
    clean_context_sha256: str
    pdf_sha256: str
    quality_status: str


class EvaluationRunner:
    def __init__(
        self,
        frozen_manifest_path: Path,
        out_dir: Path,
        research_context_path: Path,
        *,
        model: str,
        temperature: float,
        client: LLMClient | None = None,
    ) -> None:
        self.frozen_manifest_path = frozen_manifest_path
        self.out_dir = out_dir
        self.research_context_path = research_context_path
        self.model = model
        self.temperature = temperature
        self.client = client

    def plan(self) -> dict[str, Any]:
        papers, research_context = self._verified_inputs()
        paper_plans = []
        for paper in papers:
            clean_context = _load_json(paper.clean_context_path)
            baseline_prompt = _raw_baseline_prompt(clean_context, research_context)
            candidate_prompts = [_chunk_prompt(chunk, research_context) for chunk in clean_context.get("chunks", [])]
            paper_plans.append(
                {
                    "zotero_key": paper.zotero_key,
                    "chunk_count": len(candidate_prompts),
                    "baseline_expected_calls": 1,
                    "proposed_candidate_expected_calls": len(candidate_prompts),
                    "proposed_final_note_expected_calls": 1,
                    "baseline_prompt_version": RAW_BASELINE_PROMPT_VERSION,
                    "baseline_prompt_char_count": len(baseline_prompt),
                    "baseline_prompt_sha256": _sha256_text(baseline_prompt),
                    "proposed_candidate_prompt_char_count": sum(len(prompt) for prompt in candidate_prompts),
                    "proposed_candidate_prompt_sha256": _sha256_text("".join(candidate_prompts)),
                    "proposed_candidate_prompt_version": PROPOSED_CANDIDATE_PROMPT_VERSION,
                    "proposed_final_prompt_version": PROPOSED_FINAL_PROMPT_VERSION,
                }
            )
        baseline_calls = len(paper_plans)
        candidate_calls = sum(item["proposed_candidate_expected_calls"] for item in paper_plans)
        final_calls = len(paper_plans)
        return {
            "role": "development_pilot",
            "manifest": str(self.frozen_manifest_path),
            "research_context": {
                "path": str(self.research_context_path),
                "char_count": len(research_context),
                "sha256": _sha256_text(research_context),
            },
            "paper_count": len(paper_plans),
            "papers": paper_plans,
            "estimated_calls": {
                "baseline_initial": baseline_calls,
                "proposed_candidate": candidate_calls,
                "proposed_final_note": final_calls,
                "minimum_total": baseline_calls + candidate_calls + final_calls,
                "maximum_with_one_baseline_retry": baseline_calls * 2 + candidate_calls + final_calls,
            },
        }

    def execute(self) -> dict[str, Any]:
        if self.client is None:
            raise LLMError("execute requires an explicitly injected LLM client")
        plan = self.plan()
        papers, research_context = self._verified_inputs()
        self.out_dir.mkdir(parents=True, exist_ok=True)
        recorder = _CallRecorder(self.model, self.temperature, self.out_dir)
        errors: list[dict[str, Any]] = []
        comparisons: list[dict[str, Any]] = []

        for paper in papers:
            clean_context = _load_json(paper.clean_context_path)
            paper_dir = self.out_dir / "papers" / paper.zotero_key
            baseline = _run_raw_baseline(
                paper,
                clean_context,
                paper_dir / "baseline",
                research_context,
                self.client,
                recorder,
                self.model,
                self.temperature,
            )
            proposed = _run_proposed(
                paper,
                paper_dir / "proposed",
                research_context,
                self.client,
                recorder,
                self.model,
                self.temperature,
            )
            comparison = {
                "zotero_key": paper.zotero_key,
                "baseline": baseline["metrics"],
                "proposed": proposed["metrics"],
            }
            comparisons.append(comparison)
            _write_json(paper_dir / "comparison.json", comparison)
            errors.extend(baseline["errors"])
            errors.extend(proposed["errors"])

        aggregate = _aggregate(comparisons, recorder.records)
        _write_json(
            self.out_dir / "run_manifest.json",
            {
                "plan": plan,
                "executed_at": _now(),
                "model": self.model,
                "temperature": self.temperature,
                **_git_metadata(self.frozen_manifest_path),
                "dirty_worktree_policy": "record_only; require a clean worktree before enabling real execution",
            },
        )
        _write_json(self.out_dir / "input_verification.json", {"verified": True, "papers": [paper.zotero_key for paper in papers]})
        _write_json(self.out_dir / "call_metrics.json", recorder.records)
        _write_json(self.out_dir / "aggregate_report.json", aggregate)
        _write_json(self.out_dir / "errors.json", errors)
        _write_manual_review_csv(self.out_dir / "manual_claim_evidence_review.csv", comparisons, papers)
        return {"plan": plan, "aggregate": aggregate, "errors": errors}

    def _verified_inputs(self) -> tuple[list[FrozenPaper], str]:
        if not self.research_context_path.is_file():
            raise FrozenInputError(f"research context file not found: {self.research_context_path}")
        payload = _load_json(self.frozen_manifest_path)
        papers = payload.get("papers")
        if not isinstance(papers, list) or len(papers) != 3:
            raise FrozenInputError("frozen manifest must contain exactly three papers")
        keys = [item.get("zotero_key") for item in papers]
        if len(set(keys)) != len(keys) or any(not key for key in keys):
            raise FrozenInputError("frozen manifest contains duplicate or missing zotero_key")
        frozen = []
        for item in papers:
            context_path = Path(item["source_clean_context_path"])
            if not context_path.is_absolute():
                context_path = _repo_root(self.frozen_manifest_path) / context_path
            pdf_path = Path(item["pdf_path"])
            if not context_path.is_file():
                raise FrozenInputError(f"clean context path not found: {context_path}")
            if not pdf_path.is_file():
                raise FrozenInputError(f"PDF path not found: {pdf_path}")
            if _sha256_file(context_path) != item.get("clean_context_sha256"):
                raise FrozenInputError(f"clean context SHA-256 mismatch: {item.get('zotero_key')}")
            if _sha256_file(pdf_path) != item.get("pdf_sha256"):
                raise FrozenInputError(f"PDF SHA-256 mismatch: {item.get('zotero_key')}")
            if item.get("quality_status") != "ready_for_llm":
                raise FrozenInputError(f"quality status is not ready_for_llm: {item.get('zotero_key')}")
            frozen.append(
                FrozenPaper(
                    zotero_key=item["zotero_key"],
                    citation_key=item.get("citation_key") or "",
                    title=item.get("title") or "",
                    clean_context_path=context_path,
                    pdf_path=pdf_path,
                    clean_context_sha256=item["clean_context_sha256"],
                    pdf_sha256=item["pdf_sha256"],
                    quality_status=item["quality_status"],
                )
            )
        return frozen, self.research_context_path.read_text(encoding="utf-8-sig")


def _run_raw_baseline(
    paper: FrozenPaper,
    clean_context: dict[str, Any],
    out_dir: Path,
    research_context: str,
    client: LLMClient,
    recorder: "_CallRecorder",
    model: str,
    temperature: float,
) -> dict[str, Any]:
    prompt = _raw_baseline_prompt(clean_context, research_context)
    initial_success = False
    raw_note: StructuredReadingNote | None = None
    errors: list[dict[str, Any]] = []
    for attempt in (1, 2):
        raw, call_id = recorder.complete(client, paper.zotero_key, "baseline_raw", None, attempt, RAW_BASELINE_PROMPT_VERSION, prompt)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"raw_response_attempt_{attempt}.txt").write_text(raw, encoding="utf-8")
        try:
            raw_note = StructuredReadingNote.model_validate(_parse_json_response(raw))
            if raw_note.zotero_key != paper.zotero_key:
                raise ValueError("raw baseline zotero_key does not match frozen input")
            initial_success = attempt == 1
            break
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            recorder.mark_invalid(call_id, type(exc).__name__)
            errors.append({"zotero_key": paper.zotero_key, "method": "baseline", "attempt": attempt, "error_type": type(exc).__name__, "error": str(exc)})
            if attempt == 2:
                _write_json(out_dir / "error.json", {"error_type": type(exc).__name__, "error": str(exc), "raw_response_artifact": f"raw_response_attempt_{attempt}.txt"})
            else:
                prompt = _raw_baseline_retry_prompt(prompt)
    if raw_note is None:
        metrics = _note_metrics(None, clean_context, initial_success=False, retry_count=1, final_success=False, calls=recorder.records, key=paper.zotero_key)
        _write_json(out_dir / "metrics.json", metrics)
        return {"metrics": metrics, "errors": errors}
    raw_note_path = out_dir / "raw_note.json"
    raw_note_path.write_text(raw_note.model_dump_json(indent=2) + "\n", encoding="utf-8")
    metrics = _note_metrics(raw_note.model_dump(), clean_context, initial_success=initial_success, retry_count=0 if initial_success else 1, final_success=True, calls=recorder.records, key=paper.zotero_key)
    _write_json(out_dir / "metrics.json", metrics)
    return {"metrics": metrics, "errors": errors}


def _run_proposed(
    paper: FrozenPaper,
    out_dir: Path,
    research_context: str,
    client: LLMClient,
    recorder: "_CallRecorder",
    model: str,
    temperature: float,
) -> dict[str, Any]:
    bank_path = out_dir / "evidence_candidate_bank.json"
    report_path = out_dir / "candidate_report.json"
    clean_context = _load_json(paper.clean_context_path)
    candidate_client = _RecordingClient(
        client,
        recorder,
        paper.zotero_key,
        "proposed_candidate_chunk",
        PROPOSED_CANDIDATE_PROMPT_VERSION,
        [chunk.get("chunk_id") for chunk in clean_context.get("chunks", [])],
    )
    final_client = _RecordingClient(client, recorder, paper.zotero_key, "proposed_final_note", PROPOSED_FINAL_PROMPT_VERSION)
    errors: list[dict[str, Any]] = []
    try:
        report = build_evidence_candidate_bank(paper.clean_context_path, bank_path, report_path, client=candidate_client, research_context=research_context)
        final_path = out_dir / "final_note.json"
        note = generate_note_from_evidence_bank(
            bank_path,
            paper.clean_context_path,
            final_path,
            zotero_key=paper.zotero_key,
            citation_key=paper.citation_key,
            title=paper.title,
            client=final_client,
            research_context=research_context,
        )
        metrics = _note_metrics(note.model_dump(), clean_context, initial_success=True, retry_count=0, final_success=True, calls=recorder.records, key=paper.zotero_key)
        bank = _load_json(bank_path)
        candidates = bank.get("candidates", [])
        failures = bank.get("failures", [])
        chunks_with_candidates = len({candidate.get("chunk_id") for candidate in candidates})
        denominator = len(candidates) + len(failures)
        metrics.update(
            {
                "chunk_count": bank["metadata"].get("chunk_count", 0),
                "chunk_call_success_count": sum(record["status"] == "success" for record in recorder.records if record["zotero_key"] == paper.zotero_key and record["stage"] == "proposed_candidate_chunk"),
                "chunk_call_failure_count": sum(record["status"] != "success" for record in recorder.records if record["zotero_key"] == paper.zotero_key and record["stage"] == "proposed_candidate_chunk"),
                "chunks_with_anchored_candidate": chunks_with_candidates,
                "proposed_candidate_count": len(candidates) + len(failures),
                "anchored_candidate_count": len(candidates),
                "failed_anchor_count": len(failures),
                "candidate_anchor_rate": len(candidates) / denominator if denominator else 0,
                "chunk_evidence_coverage_rate": chunks_with_candidates / bank["metadata"].get("chunk_count", 1) if bank["metadata"].get("chunk_count", 0) else 0,
                "final_selected_evidence_count": len(note.evidence_links),
                "candidate_report_success": report.get("success", False),
            }
        )
    except Exception as exc:
        errors.append({"zotero_key": paper.zotero_key, "method": "proposed", "error_type": type(exc).__name__, "error": str(exc)})
        _write_json(out_dir / "error.json", errors[-1])
        metrics = _note_metrics(None, _load_json(paper.clean_context_path), initial_success=False, retry_count=0, final_success=False, calls=recorder.records, key=paper.zotero_key)
        metrics.update({"chunk_count": len(_load_json(paper.clean_context_path).get("chunks", [])), "chunk_call_success_count": 0, "chunk_call_failure_count": 0, "chunks_with_anchored_candidate": 0, "proposed_candidate_count": 0, "anchored_candidate_count": 0, "failed_anchor_count": 0, "candidate_anchor_rate": 0, "chunk_evidence_coverage_rate": 0, "final_selected_evidence_count": 0})
    _write_json(out_dir / "metrics.json", metrics)
    return {"metrics": metrics, "errors": errors}


class _RecordingClient:
    def __init__(self, client: LLMClient, recorder: "_CallRecorder", zotero_key: str, stage: str, prompt_version: str, chunk_ids: list[str | None] | None = None) -> None:
        self.client, self.recorder, self.zotero_key, self.stage, self.prompt_version = client, recorder, zotero_key, stage, prompt_version
        self.chunk_ids = iter(chunk_ids or [])

    def complete_json(self, prompt: str) -> str:
        chunk_id = next(self.chunk_ids, None) if self.stage == "proposed_candidate_chunk" else None
        return self.recorder.complete(self.client, self.zotero_key, self.stage, chunk_id, 1, self.prompt_version, prompt)[0]


class _CallRecorder:
    def __init__(self, model: str, temperature: float, artifact_root: Path) -> None:
        self.model, self.temperature, self.records = model, temperature, []
        self.artifact_root = artifact_root

    def complete(self, client: LLMClient, zotero_key: str, stage: str, chunk_id: str | None, attempt: int, prompt_version: str, prompt: str) -> tuple[str, str]:
        call_id = uuid.uuid4().hex
        started = time.perf_counter()
        record = {
            "call_id": call_id, "zotero_key": zotero_key, "stage": stage, "chunk_id": chunk_id, "attempt": attempt,
            "start_timestamp": _now(), "end_timestamp": None, "latency_ms": None, "status": "failed", "error_type": None,
            "model": self.model, "temperature": self.temperature, "prompt_version": prompt_version,
            "prompt_char_count": len(prompt), "response_char_count": None, "prompt_sha256": _sha256_text(prompt), "response_sha256": None,
            "input_tokens": None, "output_tokens": None, "total_tokens": None, "usage_status": "usage_unavailable", "estimated_cost": None,
            "raw_response_artifact": None,
        }
        try:
            response = client.complete_json(prompt)
        except Exception as exc:
            record.update({"end_timestamp": _now(), "latency_ms": round((time.perf_counter() - started) * 1000, 3), "error_type": type(exc).__name__})
            self.records.append(record)
            raise
        artifact = self.artifact_root / "calls" / f"{call_id}.response.txt"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(response, encoding="utf-8")
        record.update({"end_timestamp": _now(), "latency_ms": round((time.perf_counter() - started) * 1000, 3), "status": "success", "response_char_count": len(response), "response_sha256": _sha256_text(response), "raw_response_artifact": str(artifact.relative_to(self.artifact_root))})
        self.records.append(record)
        return response, call_id

    def mark_invalid(self, call_id: str, error_type: str) -> None:
        for record in self.records:
            if record["call_id"] == call_id:
                record.update({"status": "response_invalid", "error_type": error_type})
                return


def _note_metrics(note: dict[str, Any] | None, clean_context: dict[str, Any], *, initial_success: bool, retry_count: int, final_success: bool, calls: list[dict[str, Any]], key: str) -> dict[str, Any]:
    score = score_evidence_note(note, clean_context) if note else {"evidence_links_count": 0, "pass_count": 0, "failure_count": 0, "exact_grounding_rate": 0, "failures": []}
    failures = score["failures"]
    paper_calls = [record for record in calls if record["zotero_key"] == key]
    return {
        "json_parse_success": final_success,
        "schema_valid": final_success,
        "initial_success": initial_success,
        "retry_count": retry_count,
        "final_success": final_success,
        "evidence_links_count": score["evidence_links_count"],
        "exact_grounding_pass_count": score["pass_count"],
        "exact_grounding_failure_count": score["failure_count"],
        "exact_grounding_rate": score["exact_grounding_rate"],
        "chunk_id_not_found_count": sum(item["type"] == "chunk_id_not_found" for item in failures),
        "page_range_mismatch_count": sum(item["type"] == "page_range_mismatch" for item in failures),
        "evidence_text_not_found_count": sum(item["type"] == "evidence_text_not_found" for item in failures),
        "end_to_end_success": final_success and score["failure_count"] == 0,
        "total_llm_calls": len(paper_calls),
        "failed_llm_calls": sum(record["status"] != "success" for record in paper_calls),
        "total_latency_ms": round(sum(record["latency_ms"] or 0 for record in paper_calls), 3),
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "usage_status": "usage_unavailable",
        "estimated_cost": None,
        "evidence_failures": failures,
    }


def _aggregate(comparisons: list[dict[str, Any]], records: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"paper_count": len(comparisons), "baseline": {}, "proposed": {}, "manual_metrics": "not_computed_until_manual_csv_is_filled"}
    for method in ("baseline", "proposed"):
        metrics = [item[method] for item in comparisons]
        for field in ("evidence_links_count", "exact_grounding_pass_count", "exact_grounding_failure_count", "total_llm_calls", "failed_llm_calls", "total_latency_ms"):
            result[method][field] = sum(item.get(field, 0) for item in metrics)
        links = result[method]["evidence_links_count"]
        result[method]["exact_grounding_rate"] = result[method]["exact_grounding_pass_count"] / links if links else 0
    return result


def _write_manual_review_csv(path: Path, comparisons: list[dict[str, Any]], papers: list[FrozenPaper]) -> None:
    by_key = {paper.zotero_key: paper for paper in papers}
    fields = ["run_id", "zotero_key", "method", "evidence_index", "claim", "chunk_id", "page_start", "page_end", "evidence_text", "automatic_grounding_status", "automatic_failure_type", "support_label", "needs_revision", "acceptance", "reviewer_notes"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for comparison in comparisons:
            for method in ("baseline", "proposed"):
                metrics = comparison[method]
                failures = {item["index"]: item["type"] for item in metrics["evidence_failures"]}
                note_path = path.parent / "papers" / comparison["zotero_key"] / method / ("raw_note.json" if method == "baseline" else "final_note.json")
                if not note_path.is_file():
                    continue
                for index, link in enumerate(_load_json(note_path).get("evidence_links", []), 1):
                    writer.writerow({"run_id": path.parent.name, "zotero_key": comparison["zotero_key"], "method": method, "evidence_index": index, **link, "automatic_grounding_status": "pass" if index not in failures else "fail", "automatic_failure_type": failures.get(index, ""), "support_label": "", "needs_revision": "", "acceptance": "", "reviewer_notes": ""})


def _raw_baseline_prompt(clean_context: dict[str, Any], research_context: str) -> str:
    return (
        f"Prompt version: {RAW_BASELINE_PROMPT_VERSION}\n"
        "Return one JSON object only. Use only the provided clean context and research context. Do not use external knowledge. "
        "For every evidence link, provide claim, chunk_id, page_start, page_end, and evidence_text.\n"
        f"Research context:\n{research_context}\n"
        f"Clean context:\n{json.dumps(build_llm_input(clean_context), ensure_ascii=False)}"
    )


def _raw_baseline_retry_prompt(prompt: str) -> str:
    return prompt + "\nYour previous response was not valid JSON/schema. Return corrected JSON only. This retry corrects format only; do not rely on programmatic evidence repair."


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _repo_root(path: Path) -> Path:
    for candidate in (path.parent, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    raise FrozenInputError(f"repository root not found for frozen manifest: {path}")


def _git_metadata(manifest_path: Path) -> dict[str, str | None]:
    try:
        root = _repo_root(manifest_path)
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        status = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True).stdout
        return {"git_commit_sha": commit, "git_worktree_status": "clean" if not status.strip() else "dirty"}
    except (FrozenInputError, OSError, subprocess.CalledProcessError):
        return {"git_commit_sha": None, "git_worktree_status": "unavailable"}


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
