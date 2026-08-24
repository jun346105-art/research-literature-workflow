from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from litflow.llm.client import LLMCompletion, OpenAICompatibleClient
from litflow.llm.span_mapping import map_verbatim_span
from litflow.rag.bm25 import BM25Index, load_corpus
from litflow.rag.qa import (
    CanonicalTransportError,
    QAResult,
    RawAnswerV12,
    _failed,
    _parse_v12,
    _prompt_v12,
    _verify_v12,
)
from litflow.rag.translation import TranslationResponse, build_translation_prompt


MAX_QUERY_LENGTH = 500
TOP_K = 10
SERVICE_VERSION = "m5-minimal-fastapi-ui-v1"
DEPLOYMENT_MODEL = "deepseek-v4-flash"


@dataclass(frozen=True)
class DemoAssets:
    corpus_path: Path
    entity_metadata_path: Path
    matrix_path: Path
    writing_dir: Path
    jobs_dir: Path
    corpus_id: str
    translation_cache_path: Path | None = None

    @classmethod
    def from_repo(cls, repo_root: Path) -> DemoAssets:
        return cls(
            corpus_path=repo_root / "outputs" / "rag_bm25_v1" / "passages.jsonl",
            entity_metadata_path=repo_root / "configs" / "paper_entity_metadata_v1.json",
            matrix_path=repo_root / "outputs" / "evidence_matrix_v1" / "evidence_matrix.json",
            writing_dir=repo_root / "outputs" / "m4_writing_v1" / "author_reviewed_closure_v1",
            jobs_dir=repo_root / "outputs" / "m5_fastapi_v1" / "jobs",
            corpus_id="rag_bm25_v1",
            translation_cache_path=repo_root / "outputs" / "m2a_translation" / "final_translation_freeze_v1" / "queries_machine_translated.json",
        )


class RetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    query_language: Literal["auto", "zh", "en"] = "auto"
    top_k: int = TOP_K

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be empty")
        return value

    @field_validator("top_k")
    @classmethod
    def fixed_top_k(cls, value: int) -> int:
        if value != TOP_K:
            raise ValueError("top_k is frozen at 10 for this MVP")
        return value


class QaJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    query_language: Literal["auto", "zh", "en"] = "auto"

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be empty")
        return value


class MvpService:
    def __init__(
        self,
        assets: DemoAssets,
        *,
        online_enabled: bool = False,
        run_jobs_inline: bool = False,
        client_factory: Callable[[], Any] | None = None,
        qa_executor: Callable[[str, dict[str, Any], list[dict[str, Any]], MvpService], dict[str, Any]] | None = None,
    ) -> None:
        self.assets = assets
        self.online_enabled = online_enabled
        self.run_jobs_inline = run_jobs_inline
        self._enforce_deployment_model = client_factory is None and qa_executor is None
        self.client_factory = client_factory or (lambda: OpenAICompatibleClient.from_env(thinking_mode="disabled"))
        self.qa_executor = qa_executor or self._default_qa_executor
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def health(self) -> dict[str, Any]:
        passages = self._passages()
        return {
            "status": "ok",
            "version": SERVICE_VERSION,
            "mode": "online_qa" if self.online_enabled else "offline_demo",
            "model_availability": "enabled_by_explicit_service_mode" if self.online_enabled else "offline_no_client",
            "corpus_identity": {
                "corpus_id": self.assets.corpus_id,
                "corpus_sha256": _sha_file(self.assets.corpus_path),
                "passage_count": len(passages),
            },
        }

    def papers(self) -> dict[str, Any]:
        papers: dict[str, dict[str, Any]] = {}
        for passage in self._passages():
            item = papers.setdefault(
                passage["paper_key"],
                {
                    "paper_key": passage["paper_key"],
                    "citation_key": passage.get("citation_key"),
                    "title": passage.get("title"),
                    "year": passage.get("year"),
                    "language": passage.get("source_language", "en"),
                    "passage_count": 0,
                    "readiness_status": "frozen_demo_corpus",
                },
            )
            item["passage_count"] += 1
        return {"papers": sorted(papers.values(), key=lambda item: item["paper_key"])}

    def retrieve(self, query: str, requested_language: str, *, allow_online_translation: bool = False, job_id: str | None = None) -> dict[str, Any]:
        language = _detect_query_language(query) if requested_language == "auto" else requested_language
        retrieval_query = query
        translation_status = "not_required"
        route = "en_original_to_bm25_en"
        translation_usage: dict[str, Any] | None = None
        if language == "zh":
            cached = self._cached_translation(query)
            if cached:
                retrieval_query = cached
                translation_status = "cached_frozen_translation"
            elif allow_online_translation:
                translated, translation_usage = self._translate(query, job_id or "ad_hoc")
                retrieval_query = translated
                translation_status = "online_translation"
            else:
                return {
                    "original_query": query,
                    "query_language": language,
                    "retrieval_query": None,
                    "translation_status": "translation_unavailable_in_offline_demo",
                    "route": "zh_requires_cached_or_online_translation_before_bm25_en",
                    "passages": [],
                }
            route = "zh_machine_translation_to_bm25_en"
        passages = self._passages()
        by_id = {item["passage_id"]: item for item in passages}
        ranked = BM25Index(passages).search(retrieval_query, top_k=TOP_K)
        result_passages = [
            {
                "passage_id": item["passage_id"],
                "score": item["score"],
                "rank": item["rank"],
                "paper_key": by_id[item["passage_id"]]["paper_key"],
                "citation_key": by_id[item["passage_id"]].get("citation_key"),
                "title": by_id[item["passage_id"]].get("title"),
                "page_start": by_id[item["passage_id"]]["page_start"],
                "page_end": by_id[item["passage_id"]]["page_end"],
                "snippet": _snippet(by_id[item["passage_id"]]["text"]),
                "source_language": by_id[item["passage_id"]].get("source_language", "en"),
            }
            for item in ranked
        ]
        return {
            "original_query": query,
            "query_language": language,
            "retrieval_query": retrieval_query,
            "translation_status": translation_status,
            "route": route,
            "passages": result_passages,
            "translation_usage": translation_usage,
        }

    def create_job(self, request: QaJobRequest) -> str:
        if not self.online_enabled:
            raise PermissionError("online QA is disabled; offline demo never constructs an LLM client")
        if self._enforce_deployment_model and os.environ.get("LLM_MODEL") != DEPLOYMENT_MODEL:
            raise PermissionError(f"online QA requires LLM_MODEL={DEPLOYMENT_MODEL}")
        job_id = secrets.token_urlsafe(16)
        with self._lock:
            self._jobs[job_id] = {"job_id": job_id, "status": "queued", "events": [], "request": request.model_dump(), "result": None}
            self._event(job_id, "job_created", "queued")
            self._persist_job(job_id)
        if self.run_jobs_inline:
            self._run_job(job_id)
        else:
            threading.Thread(target=self._run_job, args=(job_id,), daemon=True).start()
        return job_id

    def job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            self._load_persisted_job(job_id)
            if job_id not in self._jobs:
                raise KeyError(job_id)
            item = self._jobs[job_id]
            return {"job_id": job_id, "status": item["status"], "result_ready": item["result"] is not None}

    def job_events(self, job_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self._load_persisted_job(job_id)
            if job_id not in self._jobs:
                raise KeyError(job_id)
            return list(self._jobs[job_id]["events"])

    def job_result(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            self._load_persisted_job(job_id)
            if job_id not in self._jobs:
                raise KeyError(job_id)
            result = self._jobs[job_id]["result"]
            if result is None:
                return {"job_id": job_id, "status": self._jobs[job_id]["status"]}
            return _public_result(result)

    def passage(self, passage_id: str, evidence_quote: str | None) -> dict[str, Any]:
        passage = next((item for item in self._passages() if item["passage_id"] == passage_id), None)
        if passage is None:
            raise KeyError(passage_id)
        anchor: dict[str, Any] = {"anchor_status": "not_requested", "start": None, "end": None}
        if evidence_quote:
            mapped = map_verbatim_span(evidence_quote, passage["text"])
            anchor = {"anchor_status": "exact_match" if mapped.method == "exact_match" else "normalized_exact_match" if mapped.status == "ok" else "anchor_failed", "start": mapped.start, "end": mapped.end, "mapper_method": mapped.method}
        return {
            "passage_id": passage["passage_id"],
            "paper_key": passage["paper_key"],
            "citation_key": passage.get("citation_key"),
            "title": passage.get("title"),
            "page_start": passage["page_start"],
            "page_end": passage["page_end"],
            "passage_text": passage["text"],
            "source_language": passage.get("source_language", "en"),
            "evidence_quote": evidence_quote,
            **anchor,
        }

    def matrix_demo(self) -> dict[str, Any]:
        return {"demo_artifact": True, "author_reviewed": True, "matrix": _load_json(self.assets.matrix_path)}

    def writing_demo(self) -> dict[str, Any]:
        review = _load_json(self.assets.writing_dir / "writing_author_semantic_review.json")
        plan = _load_json(self.assets.writing_dir / "closure_plan.json")
        return {
            "demo_artifact": True,
            "author_reviewed": True,
            "publication_ready": False,
            "writing_task": plan.get("task_id"),
            "outline": {"limitations_zh": plan.get("limitations_zh"), "limitations_en": plan.get("limitations_en")},
            "draft_zh": (self.assets.writing_dir / "method_comparison_draft_zh_author_reviewed.md").read_text(encoding="utf-8"),
            "draft_en": (self.assets.writing_dir / "method_comparison_draft_en_author_reviewed.md").read_text(encoding="utf-8"),
            "sentence_evidence_ledger": (self.assets.writing_dir / "sentence_evidence_ledger_author_reviewed.md").read_text(encoding="utf-8"),
            "m4_status": review.get("m4_status"),
            "partial_coverage_limitations": review.get("limitations_zh"),
        }

    def _run_job(self, job_id: str) -> None:
        try:
            request = self._jobs[job_id]["request"]
            self._set_status(job_id, "retrieving", "translation_started" if request["query_language"] != "en" else "translation_skipped")
            retrieval = self.retrieve(request["query"], request["query_language"], allow_online_translation=True, job_id=job_id)
            self._event(job_id, "translation_completed" if retrieval["translation_status"] != "not_required" else "translation_skipped", "retrieving")
            self._event(job_id, "retrieval_completed", "retrieving")
            top = [item for item in self._passages() if item["passage_id"] in {row["passage_id"] for row in retrieval["passages"]}]
            self._write_job_json(job_id, "retrieval.json", retrieval)
            self._set_status(job_id, "generating", "generation_started")
            result = self.qa_executor(job_id, {"query_zh": request["query"], "query_en": retrieval["retrieval_query"] if request["query_language"] == "en" else None}, top, self)
            self._event(job_id, "generation_completed", "validating")
            self._set_status(job_id, "validating", "validation_completed")
            with self._lock:
                self._jobs[job_id]["result"] = result
                self._jobs[job_id]["status"] = "completed" if result.get("execution_status") == "success" else "failed"
                self._event(job_id, "job_completed" if self._jobs[job_id]["status"] == "completed" else "job_failed", self._jobs[job_id]["status"])
                self._persist_job(job_id)
            self._write_job_json(job_id, "result.json", result)
        except Exception:
            with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id]["result"] = {"execution_status": "provider_failed"}
                    self._jobs[job_id]["status"] = "failed"
                    self._event(job_id, "job_failed", "failed")
                    self._persist_job(job_id)

    def _default_qa_executor(self, job_id: str, query: dict[str, Any], top: list[dict[str, Any]], _: MvpService) -> dict[str, Any]:
        if not top:
            return {"execution_status": "success", "final_answer_status": "insufficient_evidence", "coverage_status": "none", "answer_zh": "基于当前检索到的文献片段，证据不足，无法给出可验证回答。", "claims": [], "limitations_zh": "当前检索结果为空。", "usage": None, "latency_ms": None, "validation_summary": {"citation_membership": "not_applicable", "quote_grounding": "not_applicable"}}
        client = self.client_factory()
        if self._enforce_deployment_model and getattr(client, "model", None) != DEPLOYMENT_MODEL:
            raise RuntimeError(f"resolved model must be {DEPLOYMENT_MODEL}")
        entity_metadata = _load_json(self.assets.entity_metadata_path)
        prompt = _prompt_v12({"query_id": job_id, **query}, top, entity_metadata)
        raw_path = self._job_dir(job_id) / "raw_response_attempt_1.txt"
        started = time.perf_counter()
        raw_paths: list[str] = []
        usage: dict[str, Any] | None = None
        try:
            completion: LLMCompletion = client.complete_json_with_usage(prompt, temperature=0)
            _atomic_write_text(raw_path, completion.content)
            raw_paths = ["raw_response_attempt_1.txt"]
            usage = {"input_tokens": completion.input_tokens, "output_tokens": completion.output_tokens, "total_tokens": completion.total_tokens, "usage_status": "provider_reported" if completion.total_tokens is not None else "usage_unavailable"}
            self._write_job_json(job_id, "usage.json", usage)
            self._write_job_json(job_id, "run_manifest.json", {"service_version": SERVICE_VERSION, "prompt_version": "evidence-grounded-qa-v1.2", "prompt_sha256": _sha_text(prompt), "input_sha256": _sha_text(json.dumps({"query": query, "top_passage_ids": [item["passage_id"] for item in top]}, ensure_ascii=False, sort_keys=True)), "corpus_sha256": _sha_file(self.assets.corpus_path), "model": getattr(client, "model", None), "temperature": 0, "thinking_mode": "disabled", "response_format": {"type": "json_object"}, "external_llm_called": True})
            self._write_job_json(job_id, "checkpoint_1.json", {"raw_response_sha256": _sha_file(raw_path), "prompt_sha256": _sha_text(prompt), "input_sha256": _sha_text(json.dumps({"query": query, "top_passage_ids": [item["passage_id"] for item in top]}, ensure_ascii=False, sort_keys=True)), "corpus_sha256": _sha_file(self.assets.corpus_path)})
            passages = {item["passage_id"]: item for item in self._passages()}
            result = _verify_v12(job_id, _parse_v12(completion.content), passages, [item["passage_id"] for item in top], raw_paths, entity_metadata, {"query_id": job_id, **query})
            return {**result.model_dump(), "usage": usage, "latency_ms": round((time.perf_counter() - started) * 1000, 6), "validation_summary": {"citation_membership": "pass" if result.execution_status == "success" else "failed", "quote_grounding": "pass" if result.execution_status == "success" else "failed"}}
        except CanonicalTransportError as exc:
            result = _failed(job_id, "transport_failed", str(exc), raw_paths)
        except ValidationError as exc:
            result = _failed(job_id, "schema_failed", str(exc), raw_paths)
        except Exception as exc:
            result = _failed(job_id, "provider_failed", str(exc), raw_paths)
        return {**result.model_dump(), "usage": usage, "latency_ms": round((time.perf_counter() - started) * 1000, 6), "validation_summary": {"citation_membership": "not_checked", "quote_grounding": "not_checked"}}

    def _translate(self, query: str, query_id: str) -> tuple[str, dict[str, Any]]:
        client = self.client_factory()
        source = {"query_id": query_id, "query_zh": query}
        started = time.perf_counter()
        completion: LLMCompletion = client.complete_json_with_usage(build_translation_prompt(source), temperature=0)
        response = TranslationResponse.model_validate_json(completion.content)
        response.validate_against_query(source)
        return response.translated_query, {"input_tokens": completion.input_tokens, "output_tokens": completion.output_tokens, "total_tokens": completion.total_tokens, "latency_ms": round((time.perf_counter() - started) * 1000, 6), "usage_status": "provider_reported" if completion.total_tokens is not None else "usage_unavailable"}

    def _cached_translation(self, query: str) -> str | None:
        path = self.assets.translation_cache_path
        if path is None or not path.is_file():
            return None
        data = _load_json(path)
        items = data if isinstance(data, list) else data.get("queries", data.get("translations", []))
        if not isinstance(items, list):
            return None
        for item in items:
            source = item.get("query_zh") or item.get("source_query_zh")
            translated = item.get("translated_query") or (item.get("translation") or {}).get("translated_query") or item.get("query_en")
            if source == query and isinstance(translated, str) and translated:
                return translated
        return None

    def _passages(self) -> list[dict[str, Any]]:
        return load_corpus(self.assets.corpus_path)

    def _job_dir(self, job_id: str) -> Path:
        path = self.assets.jobs_dir / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_job_json(self, job_id: str, name: str, value: Any) -> None:
        _atomic_write_text(self._job_dir(job_id) / name, json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    def _persist_job(self, job_id: str) -> None:
        item = self._jobs[job_id]
        self._write_job_json(job_id, "job.json", {"job_id": job_id, "status": item["status"], "events": item["events"], "request": item["request"], "has_result": item["result"] is not None})

    def _set_status(self, job_id: str, status: str, event: str) -> None:
        with self._lock:
            self._jobs[job_id]["status"] = status
            self._event(job_id, event, status)
            self._persist_job(job_id)

    def _event(self, job_id: str, event_type: str, status: str) -> None:
        self._jobs[job_id]["events"].append({"event": event_type, "status": status})

    def _load_persisted_job(self, job_id: str) -> None:
        if job_id in self._jobs or not re.fullmatch(r"[A-Za-z0-9_-]{16,}", job_id):
            return
        directory = self.assets.jobs_dir / job_id
        job_path = directory / "job.json"
        if not job_path.is_file():
            return
        payload = _load_json(job_path)
        if payload.get("job_id") != job_id or not isinstance(payload.get("events"), list) or not isinstance(payload.get("request"), dict):
            return
        result_path = directory / "result.json"
        self._jobs[job_id] = {
            "job_id": job_id,
            "status": payload.get("status"),
            "events": payload["events"],
            "request": payload["request"],
            "result": _load_json(result_path) if result_path.is_file() else None,
        }


def create_mvp_app(service: MvpService | None = None) -> FastAPI:
    if service is None:
        repo_root = Path(__file__).resolve().parents[2]
        service = MvpService(DemoAssets.from_repo(repo_root), online_enabled=os.environ.get("LITFLOW_ONLINE_QA") == "1")
    app = FastAPI(title="LitFlow MVP", version=SERVICE_VERSION, description="Local evidence-grounded research copilot MVP.")
    static_dir = Path(__file__).with_name("static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/api/v1/health")
    def health() -> dict[str, Any]:
        return service.health()

    @app.get("/api/v1/papers")
    def papers() -> dict[str, Any]:
        return service.papers()

    @app.post("/api/v1/retrieve")
    def retrieve(request: RetrieveRequest) -> dict[str, Any]:
        return service.retrieve(request.query, request.query_language)

    @app.post("/api/v1/qa/jobs", status_code=202)
    def create_job(request: QaJobRequest) -> dict[str, str]:
        try:
            return {"job_id": service.create_job(request)}
        except PermissionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/jobs/{job_id}")
    def job(job_id: str) -> dict[str, Any]:
        try:
            return service.job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

    @app.get("/api/v1/jobs/{job_id}/events")
    def events(job_id: str) -> StreamingResponse:
        try:
            items = service.job_events(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc
        def stream() -> Any:
            for item in items:
                yield f"event: {item['event']}\ndata: {json.dumps({'status': item['status']})}\n\n"
        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/v1/jobs/{job_id}/result")
    def result(job_id: str) -> dict[str, Any]:
        try:
            return service.job_result(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

    @app.get("/api/v1/passages/{passage_id}")
    def passage(passage_id: str, evidence_quote: str | None = Query(default=None, max_length=1000)) -> dict[str, Any]:
        try:
            return service.passage(passage_id, evidence_quote)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="passage not found") from exc

    @app.get("/api/v1/evidence-matrix/demo")
    def matrix_demo() -> dict[str, Any]:
        return service.matrix_demo()

    @app.get("/api/v1/writing/demo")
    def writing_demo() -> dict[str, Any]:
        return service.writing_demo()

    return app


def _public_result(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("execution_status") != "success":
        return {"execution_status": result.get("execution_status"), "final_answer_status": None, "user_message": "系统暂时无法生成经过验证的回答，请稍后重试。", "validation_summary": result.get("validation_summary", {})}
    fields = ("execution_status", "final_answer_status", "coverage_status", "answer_zh", "claims", "limitations_zh", "coverage_ledger", "usage", "latency_ms", "validation_summary")
    return {field: result.get(field) for field in fields}


def _detect_query_language(query: str) -> Literal["zh", "en"]:
    return "zh" if any("\u4e00" <= char <= "\u9fff" for char in query) else "en"


def _snippet(text: str) -> str:
    return text[:500] + ("..." if len(text) > 500 else "")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _atomic_write_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
