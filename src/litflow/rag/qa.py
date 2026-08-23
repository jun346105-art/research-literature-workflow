from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from litflow.llm.client import LLMError, OpenAICompatibleClient
from litflow.llm.span_mapping import map_verbatim_span
from litflow.rag.bm25 import BM25Index, _percentile, _sha256_file, load_corpus
from litflow.rag.qrels import load_queries


QA_PROMPT_VERSION = "evidence-grounded-qa-v1"
QA_V11_PROMPT_VERSION = "evidence-grounded-qa-v1.1"
SAFE_INSUFFICIENT_ZH = "基于当前检索到的文献片段，证据不足，无法给出可验证回答。"
SAFE_EXECUTION_FAILURE_ZH = "系统暂时无法生成经过验证的回答，请稍后重试。"


class RawCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passage_id: str
    evidence_quote: str


class RawClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_text_zh: str
    citations: list[RawCitation] = Field(default_factory=list)


class RawAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["answered", "insufficient_evidence"]
    claims: list[RawClaim] = Field(default_factory=list)
    limitations_zh: str = ""

    @model_validator(mode="after")
    def validate_answer_contract(self):
        if self.status == "answered" and not self.claims:
            raise ValueError("answered requires at least one claim")
        if self.status == "answered" and any(not claim.citations for claim in self.claims):
            raise ValueError("every answered claim requires a citation")
        if self.status == "insufficient_evidence" and self.claims:
            raise ValueError("insufficient_evidence requires empty claims")
        return self


class RawClaimV11(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_paper_key: str
    claim_text_zh: str
    citations: list[RawCitation] = Field(default_factory=list)


class RawAnswerV11(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["answered", "insufficient_evidence"]
    claims: list[RawClaimV11] = Field(default_factory=list)
    limitations_zh: str

    @model_validator(mode="after")
    def validate_answer_contract(self):
        if self.status == "answered" and not self.claims:
            raise ValueError("answered requires at least one claim")
        if self.status == "answered" and any(not claim.citations for claim in self.claims):
            raise ValueError("every answered claim requires a citation")
        if self.status == "insufficient_evidence" and self.claims:
            raise ValueError("insufficient_evidence requires empty claims")
        return self


class VerifiedCitation(BaseModel):
    passage_id: str
    evidence_quote: str
    page_start: int
    page_end: int
    anchor_status: Literal["exact_match", "normalized_exact_match"]
    mapper_method: str


class QAResult(BaseModel):
    query_id: str
    answer_status: Literal["answered", "insufficient_evidence"]
    execution_status: Literal["success", "provider_failed", "parse_failed", "transport_failed", "schema_failed", "answer_domain_failed", "citation_validation_failed", "quote_grounding_failed"]
    answer_zh: str
    claims: list[dict[str, Any]] = Field(default_factory=list)
    limitations_zh: str = ""
    retrieval_qrels_miss: bool | None = None
    semantic_evidence_absent: bool = False
    semantic_review_status: Literal["pending_author_review", "not_applicable"] = "not_applicable"
    raw_response_artifacts: list[str] = Field(default_factory=list)
    validation_error: str | None = None


def plan_qa(corpus_path: Path, queries_path: Path, *, model: str, top_k: int = 10) -> dict[str, Any]:
    passages, queries = load_corpus(corpus_path), load_queries(queries_path)
    if top_k != 10:
        raise ValueError("MVP QA is frozen at top_k=10")
    return {"role": "evidence_grounded_qa", "corpus_sha256": _sha256_file(corpus_path), "queries_sha256": _sha256_file(queries_path), "query_count": len(queries), "top_k": top_k, "prompt_version": QA_PROMPT_VERSION, "model": model, "minimum_calls": len(queries), "maximum_calls_with_parse_schema_retry": len(queries) * 2, "passage_count": len(passages)}


def _select_query(queries: list[dict[str, Any]], query_id: str) -> dict[str, Any]:
    selected = [query for query in queries if query["query_id"] == query_id]
    if len(selected) != 1:
        raise ValueError("query_id must identify exactly one frozen query")
    return selected[0]


def plan_qa_v11(corpus_path: Path, queries_path: Path, *, model: str, query_id: str, top_k: int = 10) -> dict[str, Any]:
    passages, queries = load_corpus(corpus_path), load_queries(queries_path)
    if top_k != 10:
        raise ValueError("MVP QA is frozen at top_k=10")
    query = _select_query(queries, query_id)
    by_id = {passage["passage_id"]: passage for passage in passages}
    top = [by_id[item["passage_id"]] for item in BM25Index(passages).search(query["query_zh"], top_k=top_k)]
    prompt = _prompt_v11(query, top)
    input_identity = {
        "query_id": query_id,
        "query_sha256": _sha256_text(json.dumps(query, ensure_ascii=False, sort_keys=True)),
        "top_passage_ids": [passage["passage_id"] for passage in top],
    }
    return {
        "role": "evidence_grounded_qa_v11_canary",
        "corpus_sha256": _sha256_file(corpus_path),
        "queries_sha256": _sha256_file(queries_path),
        "selected_query_sha256": input_identity["query_sha256"],
        "query_id": query_id,
        "query_count": 1,
        "top_k": top_k,
        "top_passage_ids": input_identity["top_passage_ids"],
        "prompt_version": QA_V11_PROMPT_VERSION,
        "prompt_sha256": _sha256_text(prompt),
        "input_sha256": _sha256_text(json.dumps(input_identity, ensure_ascii=False, sort_keys=True)),
        "model": model,
        "minimum_calls": 1,
        "maximum_calls": 1,
        "retry_enabled": False,
        "passage_count": len(passages),
    }


def run_qa_v11(corpus_path: Path, queries_path: Path, run_dir: Path, *, model: str, query_id: str, top_k: int = 10, client: Any | None = None) -> dict[str, Any]:
    if run_dir.exists():
        raise LLMError("QA v1.1 canary output directory must not already exist")
    plan = plan_qa_v11(corpus_path, queries_path, model=model, query_id=query_id, top_k=top_k)
    passages, queries = load_corpus(corpus_path), load_queries(queries_path)
    query = _select_query(queries, query_id)
    by_id = {passage["passage_id"]: passage for passage in passages}
    top = [by_id[item["passage_id"]] for item in BM25Index(passages).search(query["query_zh"], top_k=top_k)]
    top_ids = [passage["passage_id"] for passage in top]
    prompt = _prompt_v11(query, top)
    identity = _sha256_text(json.dumps({**plan, "git_commit_sha": _git_sha()}, sort_keys=True))
    query_dir = run_dir / "queries" / query_id
    raw_path = query_dir / "raw_response_attempt_1.txt"
    run_dir.mkdir(parents=True, exist_ok=False)
    _write_json(run_dir / "preflight_identity.json", {**plan, "git_commit_sha": _git_sha(), "identity_sha256": identity})
    _write_json(run_dir / "run_manifest.json", {"plan": plan, "identity_sha256": identity, "git_commit_sha": _git_sha(), "request_config": {"temperature": 0, "thinking_mode": "disabled", "response_format": {"type": "json_object"}}, "external_llm_called": True, "retry_enabled": False})
    _write_json(run_dir / "retrieval" / f"{query_id}.json", top_ids)
    client = client or OpenAICompatibleClient.from_env(thinking_mode="disabled")
    if isinstance(client, OpenAICompatibleClient) and client.model != model:
        raise LLMError("--model must match LLM_MODEL when QA execute is used")
    raw_paths: list[str] = []
    try:
        started = time.perf_counter()
        completion = client.complete_json_with_usage(prompt, temperature=0)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(completion.content, encoding="utf-8")
        raw_paths.append(str(raw_path.relative_to(run_dir)))
        _write_json(query_dir / "usage_attempt_1.json", {"input_tokens": completion.input_tokens, "output_tokens": completion.output_tokens, "total_tokens": completion.total_tokens, "usage_status": "provider_reported" if completion.total_tokens is not None else "usage_unavailable", "model": model, "latency_ms": round((time.perf_counter() - started) * 1000, 6), "temperature": 0, "thinking_mode": "disabled", "response_format": {"type": "json_object"}, "prompt_sha256": plan["prompt_sha256"], "input_sha256": plan["input_sha256"], "git_commit_sha": _git_sha()})
        _write_json(query_dir / "checkpoint_1.json", {"identity_sha256": identity, "raw_sha256": _sha256_file(raw_path), "prompt_sha256": plan["prompt_sha256"], "input_sha256": plan["input_sha256"]})
        parsed = _parse_v11(completion.content)
        result = _verify_v11(query_id, parsed, by_id, top_ids, raw_paths)
    except CanonicalTransportError as exc:
        status = "parse_failed" if str(exc).startswith("raw JSON parse failed") else "transport_failed"
        result = _failed(query_id, status, str(exc), raw_paths)
    except ValidationError as exc:
        status = "answer_domain_failed" if any(error.get("loc") == () for error in exc.errors()) else "schema_failed"
        result = _failed(query_id, status, str(exc), raw_paths)
    except Exception as exc:
        result = _failed(query_id, "provider_failed", str(exc), raw_paths)
    _write_json(run_dir / "validation_report.json", {"query_id": query_id, "execution_status": result.execution_status, "answer_status": result.answer_status, "validation_error": result.validation_error, "canonical_transport_required": True, "subject_paper_key_required": True, "citation_top10_required": True, "quote_grounding_required": True})
    _write_json(run_dir / "results.json", [result.model_dump()])
    (run_dir / "rendered_answer.md").write_text(result.answer_zh + "\n", encoding="utf-8")
    return {"plan": plan, "results": [result]}


def run_qa(corpus_path: Path, queries_path: Path, run_dir: Path, *, model: str, top_k: int = 10, resume: bool = False, client: Any | None = None) -> dict[str, Any]:
    plan = plan_qa(corpus_path, queries_path, model=model, top_k=top_k)
    if run_dir.exists() and (run_dir / "run_manifest.json").exists() and not resume:
        raise LLMError("QA run directory already exists; use --resume for the same identity")
    client = client or OpenAICompatibleClient.from_env(thinking_mode="disabled")
    if isinstance(client, OpenAICompatibleClient) and client.model != model:
        raise LLMError("--model must match LLM_MODEL when QA execute is used")
    passages, queries = load_corpus(corpus_path), load_queries(queries_path)
    by_id = {passage["passage_id"]: passage for passage in passages}
    retriever = BM25Index(passages)
    identity = _sha256_text(json.dumps({**plan, "git": _git_sha()}, sort_keys=True))
    run_dir.mkdir(parents=True, exist_ok=True)
    results = []
    signatures: list[str] = []
    stop_reason = None
    for position, query in enumerate(queries):
        top = retriever.search(query["query_zh"], top_k=top_k)
        result = _run_query(query, top, by_id, run_dir, client, model, identity, resume)
        results.append(result)
        signature = f"{result.execution_status}:{result.validation_error or ''}"
        if position == 0 and result.execution_status in {"parse_failed", "transport_failed", "schema_failed"}:
            stop_reason = "canary_failed"
            break
        if result.execution_status != "success":
            signatures.append(signature)
            if len(signatures) >= 2 and signatures[-1] == signatures[-2]:
                stop_reason = "repeated_structural_error"
                break
    _write_json(run_dir / "run_manifest.json", {"plan": plan, "identity_sha256": identity, "git_commit_sha": _git_sha(), "request_config": {"thinking_mode": "disabled", "response_format": {"type": "json_object"}}, "resume": resume, "canary_gate": True, "structural_circuit_breaker": True, "stop_reason": stop_reason})
    _write_json(run_dir / "results.json", [item.model_dump() for item in results])
    return {"plan": plan, "results": results}


def evaluate_qa(run_dir: Path, corpus_path: Path, queries_path: Path, out_path: Path) -> dict[str, Any]:
    results = {item["query_id"]: QAResult.model_validate(item) for item in _load_json(run_dir / "results.json")}
    queries, passages = load_queries(queries_path), {item["passage_id"]: item for item in load_corpus(corpus_path)}
    rows = []
    for query in queries:
        result = results[query["query_id"]]
        gold = set(query.get("relevant_passage_ids", []))
        cited = {citation["passage_id"] for claim in result.claims for citation in claim["citations"]}
        retrieval = set(_load_json(run_dir / "retrieval" / f"{query['query_id']}.json"))
        miss = bool(query["expected_answerable"] and not (retrieval & gold))
        result.retrieval_qrels_miss = miss
        rows.append({"query_id": query["query_id"], "expected_answerable": query["expected_answerable"], "answer_status": result.answer_status, "execution_status": result.execution_status, "retrieval_qrels_miss": miss, "cited_gold_passage_hit": bool(cited & gold), "citation_valid": all(citation["passage_id"] in passages for claim in result.claims for citation in claim["citations"]), "quote_grounded": result.execution_status == "success"})
    answerable = [row for row in rows if row["expected_answerable"]]
    no_answer = [row for row in rows if not row["expected_answerable"]]
    answered = [row for row in rows if row["answer_status"] == "answered" and row["execution_status"] == "success"]
    usage = [item for path in (run_dir / "queries").glob("*/usage_attempt_*.json") for item in [_load_json(path)]]
    latencies = [item["latency_ms"] for item in usage]
    report = {"label": "human_reviewed_pilot_qrels_v1", "schema_valid_rate": _rate([row["execution_status"] not in {"parse_failed", "schema_failed"} for row in rows]), "answered_count": sum(row["answer_status"] == "answered" for row in rows), "insufficient_evidence_count": sum(row["answer_status"] == "insufficient_evidence" and row["execution_status"] == "success" for row in rows), "execution_failure_count": sum(row["execution_status"] != "success" for row in rows), "citation_id_validity": _rate([row["citation_valid"] for row in answered]), "strict_quote_grounding_rate": _rate([row["quote_grounded"] for row in answered]), "claim_citation_coverage": _rate([row["citation_valid"] for row in answered]), "cited_gold_passage_hit_rate": _rate([row["cited_gold_passage_hit"] for row in answerable if row["answer_status"] == "answered" and row["execution_status"] == "success"]), "retrieval_hit_conditional_answer_rate": _rate([row["answer_status"] == "answered" for row in answerable if not row["retrieval_qrels_miss"] and row["execution_status"] == "success"]), "end_to_end_grounded_success_rate": _rate([row["answer_status"] == "answered" and row["execution_status"] == "success" and row["citation_valid"] for row in answerable]), "no_answer_abstention_accuracy": _rate([row["answer_status"] == "insufficient_evidence" and row["execution_status"] == "success" for row in no_answer]), "false_answer_count": sum(row["answer_status"] == "answered" for row in no_answer), "call_count": len(usage), "token_usage": {"input": sum(item.get("input_tokens") or 0 for item in usage), "output": sum(item.get("output_tokens") or 0 for item in usage), "total": sum(item.get("total_tokens") or 0 for item in usage)}, "latency_ms": {"p50": _percentile(latencies, .5), "p95": _percentile(latencies, .95)}, "per_query": rows}
    _write_json(out_path, report)
    return report


def _run_query(query: dict[str, Any], top: list[dict[str, Any]], passages: dict[str, dict[str, Any]], run_dir: Path, client: OpenAICompatibleClient, model: str, identity: str, resume: bool) -> QAResult:
    query_dir = run_dir / "queries" / query["query_id"]
    retrieval_ids = [item["passage_id"] for item in top]
    _write_json(run_dir / "retrieval" / f"{query['query_id']}.json", retrieval_ids)
    prompt = _prompt(query, [passages[item] for item in retrieval_ids])
    raw_paths = []
    for attempt in (1, 2):
        checkpoint = query_dir / f"checkpoint_{attempt}.json"
        raw_path = query_dir / f"raw_response_attempt_{attempt}.txt"
        if resume and checkpoint.is_file() and raw_path.is_file() and _load_json(checkpoint).get("identity_sha256") == identity:
            raw = raw_path.read_text(encoding="utf-8")
        else:
            try:
                started = time.perf_counter()
                completion = client.complete_json_with_usage(prompt, temperature=0)
                raw = completion.content
                _write_json(query_dir / f"usage_attempt_{attempt}.json", {"input_tokens": completion.input_tokens, "output_tokens": completion.output_tokens, "total_tokens": completion.total_tokens, "usage_status": "provider_reported" if completion.total_tokens is not None else "usage_unavailable", "model": model, "latency_ms": round((time.perf_counter() - started) * 1000, 6), "temperature": 0, "thinking_mode": "disabled", "response_format": {"type": "json_object"}})
            except Exception as exc:
                return _failed(query["query_id"], "provider_failed", str(exc), raw_paths)
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(raw, encoding="utf-8")
            _write_json(checkpoint, {"identity_sha256": identity, "raw_sha256": _sha256_file(raw_path), "prompt_sha256": _sha256_text(prompt)})
        raw_paths.append(str(raw_path.relative_to(run_dir)))
        try:
            parsed, ledger = _parse_transport(raw, query)
            _write_json(query_dir / f"transport_attempt_{attempt}.json", ledger)
            return _verify(query["query_id"], parsed, passages, retrieval_ids, raw_paths)
        except TransportError as exc:
            if attempt == 1:
                prompt = prompt + "\n\nREPAIR: Return JSON matching the exact schema only."
                continue
            return _failed(query["query_id"], "transport_failed", str(exc), raw_paths)
        except ValidationError as exc:
            if attempt == 1:
                prompt = prompt + "\n\nREPAIR: Return JSON matching the exact schema only."
                continue
            status = "parse_failed" if "json_invalid" in str(exc) else "schema_failed"
            return _failed(query["query_id"], status, str(exc), raw_paths)
        except json.JSONDecodeError as exc:
            if attempt == 1:
                prompt = prompt + "\n\nREPAIR: Return JSON matching the exact schema only."
                continue
            return _failed(query["query_id"], "parse_failed", str(exc), raw_paths)
    return _failed(query["query_id"], "schema_failed", "unexpected retry state", raw_paths)


def _verify(query_id: str, raw: RawAnswer, passages: dict[str, dict[str, Any]], top_ids: list[str], raw_paths: list[str]) -> QAResult:
    if raw.status == "insufficient_evidence":
        return QAResult(query_id=query_id, answer_status="insufficient_evidence", execution_status="success", answer_zh=SAFE_INSUFFICIENT_ZH, limitations_zh=raw.limitations_zh, raw_response_artifacts=raw_paths, semantic_evidence_absent=True)
    claims = []
    for claim in raw.claims:
        verified = []
        for citation in claim.citations:
            if citation.passage_id not in top_ids or citation.passage_id not in passages:
                return _failed(query_id, "citation_validation_failed", "citation passage_id is not in this query top-10", raw_paths)
            mapped = map_verbatim_span(citation.evidence_quote, passages[citation.passage_id]["text"])
            if mapped.status != "ok":
                return _failed(query_id, "quote_grounding_failed", mapped.error_type, raw_paths)
            verified.append({"passage_id": citation.passage_id, "evidence_quote": mapped.evidence_text, "page_start": passages[citation.passage_id]["page_start"], "page_end": passages[citation.passage_id]["page_end"], "anchor_status": "exact_match" if mapped.method == "exact_match" else "normalized_exact_match", "mapper_method": mapped.method})
        claims.append({"claim_text_zh": claim.claim_text_zh, "citations": verified})
    return QAResult(query_id=query_id, answer_status="answered", execution_status="success", answer_zh=_render_answer(claims), claims=claims, limitations_zh=raw.limitations_zh, raw_response_artifacts=raw_paths)


def _verify_v11(query_id: str, raw: RawAnswerV11, passages: dict[str, dict[str, Any]], top_ids: list[str], raw_paths: list[str]) -> QAResult:
    if raw.status == "insufficient_evidence":
        return QAResult(query_id=query_id, answer_status="insufficient_evidence", execution_status="success", answer_zh=SAFE_INSUFFICIENT_ZH, limitations_zh=raw.limitations_zh, semantic_evidence_absent=True, raw_response_artifacts=raw_paths)
    top_paper_keys = {passages[passage_id]["paper_key"] for passage_id in top_ids}
    claims = []
    for claim in raw.claims:
        if claim.subject_paper_key not in top_paper_keys:
            return _failed(query_id, "citation_validation_failed", "subject_paper_key is not in this query top-10", raw_paths)
        verified = []
        seen_passage_ids: set[str] = set()
        for citation in claim.citations:
            if citation.passage_id not in top_ids or citation.passage_id not in passages:
                return _failed(query_id, "citation_validation_failed", "citation passage_id is not in this query top-10", raw_paths)
            passage = passages[citation.passage_id]
            if passage["paper_key"] != claim.subject_paper_key:
                return _failed(query_id, "citation_validation_failed", "citation paper_key does not match subject_paper_key", raw_paths)
            mapped = map_verbatim_span(citation.evidence_quote, passage["text"])
            if mapped.status != "ok":
                return _failed(query_id, "quote_grounding_failed", mapped.error_type, raw_paths)
            if citation.passage_id not in seen_passage_ids:
                verified.append({"passage_id": citation.passage_id, "evidence_quote": mapped.evidence_text, "page_start": passage["page_start"], "page_end": passage["page_end"], "anchor_status": "exact_match" if mapped.method == "exact_match" else "normalized_exact_match", "mapper_method": mapped.method})
                seen_passage_ids.add(citation.passage_id)
        claims.append({"subject_paper_key": claim.subject_paper_key, "claim_text_zh": claim.claim_text_zh, "citations": verified})
    return QAResult(query_id=query_id, answer_status="answered", execution_status="success", answer_zh=_render_answer_v11(claims, passages), claims=claims, limitations_zh=raw.limitations_zh, semantic_review_status="pending_author_review", raw_response_artifacts=raw_paths)


def _failed(query_id: str, status: str, error: str, raw_paths: list[str]) -> QAResult:
    return QAResult(query_id=query_id, answer_status="insufficient_evidence", execution_status=status, answer_zh=SAFE_EXECUTION_FAILURE_ZH, raw_response_artifacts=raw_paths, validation_error=error)


class TransportError(ValueError):
    pass


class CanonicalTransportError(ValueError):
    pass


def _parse_v11(raw: str) -> RawAnswerV11:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CanonicalTransportError("raw JSON parse failed") from exc
    fields = {"status", "claims", "limitations_zh"}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise CanonicalTransportError("canonical top-level fields must be exactly status, claims, limitations_zh")
    return RawAnswerV11.model_validate(payload)


def normalize_transport_payload(payload: Any, query: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise TransportError("transport payload must be a JSON object")
    direct_fields = {"status", "claims", "limitations_zh"}
    if set(payload) <= direct_fields and "status" in payload:
        return payload, {"original_transport_shape": "canonical_direct", "canonical_transport_shape": "canonical_direct", "envelope_unwrapped": False, "query_identity_verified": None, "normalization_warning": None}
    allowed = {"query_id", "query_zh", "schema"}
    if set(payload) != set(payload) & allowed or "schema" not in payload:
        raise TransportError("unknown transport envelope fields")
    if payload.get("query_id") != query["query_id"]:
        raise TransportError("transport query_id mismatch")
    if _normalize_query_text(str(payload.get("query_zh", ""))) != _normalize_query_text(query["query_zh"]):
        raise TransportError("transport query_zh mismatch")
    if not isinstance(payload["schema"], dict):
        raise TransportError("transport schema must be a JSON object")
    return payload["schema"], {"original_transport_shape": "legacy_query_schema_envelope", "canonical_transport_shape": "canonical_direct", "envelope_unwrapped": True, "query_identity_verified": True, "normalization_warning": "exact legacy envelope unwrapped", "raw_response_sha256": None}


def _parse_transport(raw: str, query: dict[str, Any]) -> tuple[RawAnswer, dict[str, Any]]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TransportError(f"invalid JSON: {exc}") from exc
    canonical, ledger = normalize_transport_payload(payload, query)
    ledger["raw_response_sha256"] = _sha256_text(raw)
    try:
        return RawAnswer.model_validate(canonical), ledger
    except ValidationError as exc:
        raise TransportError(f"strict schema validation failed after transport normalization: {exc}") from exc


def _normalize_query_text(value: str) -> str:
    import unicodedata

    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def replay_qa_transport(source_run_dir: Path, corpus_path: Path, queries_path: Path, out_dir: Path) -> dict[str, Any]:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ValueError("offline QA replay output directory already exists and is nonempty")
    passages = {item["passage_id"]: item for item in load_corpus(corpus_path)}
    queries = load_queries(queries_path)
    results = []
    ledger = []
    for query in queries:
        top_ids = _load_json(source_run_dir / "retrieval" / f"{query['query_id']}.json")
        query_dir = source_run_dir / "queries" / query["query_id"]
        attempts = []
        selected = None
        for attempt in (1, 2):
            raw_path = query_dir / f"raw_response_attempt_{attempt}.txt"
            raw = raw_path.read_text(encoding="utf-8")
            try:
                parsed, transport = _parse_transport(raw, query)
                result = _verify(query["query_id"], parsed, passages, top_ids, [str(raw_path.relative_to(source_run_dir))])
                attempts.append({"attempt": attempt, "valid": result.execution_status == "success", "transport": transport, "reason": None if result.execution_status == "success" else result.validation_error})
                if result.execution_status == "success":
                    selected = result
                    break
            except TransportError as exc:
                attempts.append({"attempt": attempt, "valid": False, "transport": None, "reason": str(exc)})
        if selected is None:
            selected = _failed(query["query_id"], "transport_failed", attempts[-1]["reason"], [f"queries/{query['query_id']}/raw_response_attempt_1.txt", f"queries/{query['query_id']}/raw_response_attempt_2.txt"])
        results.append(selected)
        ledger.append({"query_id": query["query_id"], "attempts": attempts, "selected_attempt": next((item["attempt"] for item in attempts if item["valid"]), None), "unselected_reason": attempts[0]["reason"] if len(attempts) > 1 and attempts[1]["valid"] else None})
        _write_json(out_dir / "retrieval" / f"{query['query_id']}.json", top_ids)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "replay_manifest.json", {"role": "offline_transport_replay", "external_llm_called": False, "source_online_run": source_run_dir.name, "source_online_status": "failed", "raw_responses_modified": False, "corpus_sha256": _sha256_file(corpus_path), "queries_sha256": _sha256_file(queries_path)})
    _write_json(out_dir / "normalization_ledger.json", ledger)
    _write_json(out_dir / "results.json", [result.model_dump() for result in results])
    return {"results": results, "ledger": ledger}


def _prompt(query: dict[str, Any], passages: list[dict[str, Any]]) -> str:
    allowed = [{key: passage[key] for key in ("passage_id", "paper_key", "citation_key", "title", "page_start", "page_end", "text")} for passage in passages]
    schema = {"status": "answered | insufficient_evidence", "claims": [{"claim_text_zh": "", "citations": [{"passage_id": "", "evidence_quote": ""}]}], "limitations_zh": ""}
    return "Answer only from the supplied passages. Return JSON only. Do not output answer_zh.\nIf status is answered, every claim needs at least one citation. If evidence is insufficient, claims must be empty. evidence_quote must be a short exact English quote from the cited passage.\n" + json.dumps({"query_id": query["query_id"], "query_zh": query["query_zh"], "schema": schema, "passages": allowed}, ensure_ascii=False)


def _prompt_v11(query: dict[str, Any], passages: list[dict[str, Any]]) -> str:
    allowed = [
        {
            key: passage[key]
            for key in (
                "passage_id",
                "paper_key",
                "citation_key",
                "title",
                "page_start",
                "page_end",
                "text",
            )
        }
        for passage in passages
    ]
    output_schema = {
        "status": "answered | insufficient_evidence",
        "claims": [
            {
                "subject_paper_key": "paper_key from supplied passages",
                "claim_text_zh": "Chinese atomic claim without a paper-title prefix",
                "citations": [
                    {
                        "passage_id": "supplied passage_id",
                        "evidence_quote": "short exact contiguous English quote",
                    }
                ],
            }
        ],
        "limitations_zh": "evidence scope or limitation",
    }
    instructions = (
        "Answer only from the supplied passages. Return JSON only, with exactly the top-level fields in OUTPUT_SCHEMA. "
        "Do not output query_id, query_zh, schema, data, result, answer, Markdown code fences, or any other fields. "
        "For answered, provide at least one claim and at least one citation per claim. Each subject_paper_key and citation passage_id must come from the supplied passages, and every citation in one claim must have the same paper_key as subject_paper_key. "
        "evidence_quote must copy one short, contiguous English source span exactly. Do not translate, paraphrase, join non-contiguous spans, use ellipses, or alter numbers, symbols, or proper nouns. "
        "If no such quote supports the answer, return insufficient_evidence with an empty claims list and explain the limitation in limitations_zh."
    )
    return instructions + "\nOUTPUT_SCHEMA:\n" + json.dumps(output_schema, ensure_ascii=False) + "\nQUESTION:\n" + json.dumps({"query_zh": query["query_zh"]}, ensure_ascii=False) + "\nSUPPLIED_PASSAGES:\n" + json.dumps(allowed, ensure_ascii=False)


def _render_answer(claims: list[dict[str, Any]]) -> str:
    return "\n".join(f"{index}. {claim['claim_text_zh']}（来源：" + "; ".join(f"{citation['passage_id']} pp.{citation['page_start']}-{citation['page_end']}" for citation in claim["citations"]) + "）" for index, claim in enumerate(claims, 1))


def _render_answer_v11(claims: list[dict[str, Any]], passages: dict[str, dict[str, Any]]) -> str:
    lines = ["根据当前检索到的证据，可以确认："]
    for index, claim in enumerate(claims, 1):
        first_passage = passages[claim["citations"][0]["passage_id"]]
        title = first_passage["title"]
        citation_key = first_passage["citation_key"]
        references = "; ".join(
            f"{citation['passage_id']} pp.{citation['page_start']}-{citation['page_end']}"
            for citation in claim["citations"]
        )
        lines.append(f"{index}. 【{title} ({citation_key})】{claim['claim_text_zh']}（来源：{references}）")
    return "\n".join(lines)


def write_qa_review_packet(run_dir: Path, corpus_path: Path, output_path: Path) -> None:
    passages = {item["passage_id"]: item for item in load_corpus(corpus_path)}
    results = [
        QAResult.model_validate(item)
        for item in _load_json(run_dir / "results.json")
    ]
    verified_results = [
        result
        for result in results
        if result.execution_status == "success" and result.answer_status == "answered"
    ]
    lines = [
        "# Evidence-Grounded QA Human Review Packet",
        "",
        "> Contains only answers that passed all automatic validation checks.",
        "",
    ]
    for result in verified_results:
        lines += [f"## {result.query_id}", f"- answer_status: `{result.answer_status}`", f"- execution_status: `{result.execution_status}`", "", "### Rendered Answer", result.answer_zh, "", "### Claims and Evidence"]
        for claim in result.claims:
            lines.append(f"- Claim: {claim['claim_text_zh']}")
            for citation in claim["citations"]:
                passage = passages[citation["passage_id"]]
                lines += [f"  - `{citation['passage_id']}` pp.{citation['page_start']}-{citation['page_end']} ({citation['anchor_status']})", "```text", citation["evidence_quote"], "```", "```text", passage["text"], "```"]
        lines += ["review_decision: ", "reviewer_notes: ", ""]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _rate(values: list[bool]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_sha() -> str | None:
    import subprocess
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None
