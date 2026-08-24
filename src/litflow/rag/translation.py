from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from litflow.llm.client import LLMError, OpenAICompatibleClient
from litflow.rag.qrels import load_queries


TRANSLATION_PROMPT_VERSION = "query-translation-en-v1"


class TranslationContractError(ValueError):
    pass


class TranslationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query_id: str
    source_language: Literal["zh"]
    target_language: Literal["en"]
    translated_query: str = Field(min_length=1)
    preserved_entities: list[str]
    preserved_numbers_and_units: list[str]

    def validate_against_query(self, query: dict[str, Any]) -> None:
        if self.query_id != query["query_id"]:
            raise TranslationContractError("query_id mismatch")
        translated = self.translated_query.casefold()
        entities = _protected_entities(query["query_zh"])
        missing_entities = [entity for entity in entities if entity.casefold() not in translated]
        if missing_entities:
            raise TranslationContractError("entity preservation failed: " + ", ".join(missing_entities))
        numbers = _numbers_and_units(query["query_zh"])
        missing_numbers = [item for item in numbers if item.casefold() not in translated]
        if missing_numbers:
            raise TranslationContractError("number or unit preservation failed: " + ", ".join(missing_numbers))
        _validate_scope(query["query_zh"], translated)


def build_translation_prompt(query: dict[str, Any]) -> str:
    schema = {
        "query_id": query["query_id"],
        "source_language": "zh",
        "target_language": "en",
        "translated_query": "",
        "preserved_entities": [],
        "preserved_numbers_and_units": [],
    }
    constraints = (
        "Translate the supplied Chinese research query into an English retrieval query. Return JSON only. "
        "Do not answer the question or add information. Preserve named entities, numbers, units, metrics, model versions, comparison relations, and scope words. "
        "Keep TPMN, Merge-YOLO, QZU-DET, WT-C3k2, and similar proper entities unchanged when present. "
        "If the source says dataset, retain dataset semantics and do not call it a model. "
        "Do not return Markdown or fields outside the schema."
    )
    return constraints + "\nOUTPUT_SCHEMA:\n" + json.dumps(schema, ensure_ascii=False) + "\nINPUT:\n" + json.dumps({"query_id": query["query_id"], "query_zh": query["query_zh"]}, ensure_ascii=False)


def plan_query_translation(queries_path: Path, *, model: str, query_ids: list[str]) -> dict[str, Any]:
    if not query_ids or len(query_ids) != len(set(query_ids)):
        raise ValueError("query_ids must be nonempty and unique")
    queries = {item["query_id"]: item for item in load_queries(queries_path)}
    items = []
    for query_id in query_ids:
        if query_id not in queries:
            raise ValueError("query_id is not in the frozen query set")
        query = queries[query_id]
        prompt = build_translation_prompt(query)
        query_sha = _sha_text(json.dumps({"query_id": query_id, "query_zh": query["query_zh"]}, ensure_ascii=False, sort_keys=True))
        prompt_sha = _sha_text(prompt)
        items.append({"query_id": query_id, "query_sha256": query_sha, "prompt_sha256": prompt_sha, "target_language": "en", "cache_identity_sha256": _sha_text(json.dumps({"query_sha256": query_sha, "model": model, "prompt_sha256": prompt_sha, "target_language": "en"}, sort_keys=True))})
    return {"role": "query_translation", "prompt_version": TRANSLATION_PROMPT_VERSION, "queries_sha256": _sha_file(queries_path), "model": model, "query_ids": query_ids, "query_count": len(query_ids), "minimum_calls": len(query_ids), "maximum_calls": len(query_ids), "retry_enabled": False, "items": items}


def run_query_translation(queries_path: Path, run_dir: Path, *, model: str, query_ids: list[str], client: Any | None = None, resume: bool = False) -> dict[str, Any]:
    plan = plan_query_translation(queries_path, model=model, query_ids=query_ids)
    if run_dir.exists() and not resume:
        raise LLMError("translation output directory already exists; use --resume")
    if not run_dir.exists():
        run_dir.mkdir(parents=True)
        _write_json(run_dir / "run_manifest.json", {"plan": plan, "request_config": {"temperature": 0, "thinking_mode": "disabled", "response_format": {"type": "json_object"}}, "external_llm_called": True, "resume": resume})
    queries = {item["query_id"]: item for item in load_queries(queries_path)}
    by_plan = {item["query_id"]: item for item in plan["items"]}
    client = client or OpenAICompatibleClient.from_env(thinking_mode="disabled")
    if isinstance(client, OpenAICompatibleClient) and client.model != model:
        raise LLMError("--model must match LLM_MODEL when query translation executes")
    results = []
    for query_id in query_ids:
        query = queries[query_id]
        item = by_plan[query_id]
        query_dir = run_dir / "queries" / query_id
        raw_path = query_dir / "raw_response_attempt_1.txt"
        checkpoint_path = query_dir / "checkpoint_1.json"
        raw_paths = []
        try:
            if resume and raw_path.is_file() and checkpoint_path.is_file() and _load_json(checkpoint_path).get("cache_identity_sha256") == item["cache_identity_sha256"]:
                raw = raw_path.read_text(encoding="utf-8")
            else:
                started = time.perf_counter()
                completion = client.complete_json_with_usage(build_translation_prompt(query), temperature=0)
                raw = completion.content
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_text(raw, encoding="utf-8")
                _write_json(query_dir / "usage_attempt_1.json", {"input_tokens": completion.input_tokens, "output_tokens": completion.output_tokens, "total_tokens": completion.total_tokens, "usage_status": "provider_reported" if completion.total_tokens is not None else "usage_unavailable", "model": model, "latency_ms": round((time.perf_counter() - started) * 1000, 6), "temperature": 0, "thinking_mode": "disabled", "response_format": {"type": "json_object"}, "prompt_sha256": item["prompt_sha256"], "query_sha256": item["query_sha256"]})
                _write_json(checkpoint_path, {"cache_identity_sha256": item["cache_identity_sha256"], "raw_sha256": _sha_file(raw_path), "prompt_sha256": item["prompt_sha256"], "query_sha256": item["query_sha256"]})
            raw_paths.append(str(raw_path.relative_to(run_dir)))
            response = TranslationResponse.model_validate_json(raw)
            response.validate_against_query(query)
            result = {"query_id": query_id, "execution_status": "success", "translation": response.model_dump(), "preservation_ledger": _preservation_ledger(query, response), "raw_response_artifacts": raw_paths, "validation_error": None, **item}
        except TranslationContractError as exc:
            result = {"query_id": query_id, "execution_status": "contract_failed", "translation": None, "preservation_ledger": None, "raw_response_artifacts": raw_paths, "validation_error": str(exc), **item}
        except Exception as exc:
            result = {"query_id": query_id, "execution_status": "provider_or_parse_failed", "translation": None, "preservation_ledger": None, "raw_response_artifacts": raw_paths, "validation_error": str(exc), **item}
        results.append(result)
        _write_json(run_dir / "translations.json", results)
    return {"plan": plan, "results": results}


def replay_query_translation(source_run_dir: Path, queries_path: Path, out_dir: Path, *, query_id: str | None = None) -> dict[str, Any]:
    if out_dir.exists():
        raise ValueError("translation replay output directory must not already exist")
    source_queries = [path.name for path in (source_run_dir / "queries").iterdir() if path.is_dir()]
    if query_id is None:
        if len(source_queries) != 1:
            raise ValueError("query_id is required when source run contains multiple translations")
        query_id = source_queries[0]
    if query_id not in source_queries:
        raise ValueError("query_id is absent from source translation run")
    queries = {item["query_id"]: item for item in load_queries(queries_path)}
    if query_id not in queries:
        raise ValueError("query_id is absent from frozen queries")
    query = queries[query_id]
    raw_path = source_run_dir / "queries" / query_id / "raw_response_attempt_1.txt"
    checkpoint = _load_json(source_run_dir / "queries" / query_id / "checkpoint_1.json")
    if checkpoint.get("raw_sha256") != _sha_file(raw_path):
        raise ValueError("source translation raw SHA mismatch")
    source_manifest = _load_json(source_run_dir / "run_manifest.json")
    model = source_manifest.get("plan", {}).get("model", "unknown")
    prompt = build_translation_prompt(query)
    item = plan_query_translation(queries_path, model=model, query_ids=[query_id])["items"][0]
    raw = raw_path.read_text(encoding="utf-8")
    try:
        response = TranslationResponse.model_validate_json(raw)
        response.validate_against_query(query)
        result = {"query_id": query_id, "execution_status": "success", "translation": response.model_dump(), "preservation_ledger": _preservation_ledger(query, response), "raw_response_artifacts": [str(raw_path.relative_to(source_run_dir))], "validation_error": None, **item}
    except TranslationContractError as exc:
        result = {"query_id": query_id, "execution_status": "contract_failed", "translation": None, "preservation_ledger": None, "raw_response_artifacts": [str(raw_path.relative_to(source_run_dir))], "validation_error": str(exc), **item}
    except Exception as exc:
        result = {"query_id": query_id, "execution_status": "provider_or_parse_failed", "translation": None, "preservation_ledger": None, "raw_response_artifacts": [str(raw_path.relative_to(source_run_dir))], "validation_error": str(exc), **item}
    out_dir.mkdir(parents=True, exist_ok=False)
    _write_json(out_dir / "replay_manifest.json", {"role": "offline_translation_validator_replay", "source_run": source_run_dir.name, "source_raw_sha256": _sha_file(raw_path), "external_llm_called": False, "raw_response_modified": False, "query_id": query_id, "model": model, "prompt_sha256": _sha_text(prompt), "queries_sha256": _sha_file(queries_path)})
    _write_json(out_dir / "translations.json", [result])
    return {"results": [result]}


def write_translation_review_packet(run_dir: Path, queries_path: Path, output_path: Path) -> None:
    queries = {item["query_id"]: item for item in load_queries(queries_path)}
    results = _load_json(run_dir / "translations.json")
    lines = ["# Chinese-to-English Translation Review Packet", "", "> Human-reviewed English queries are shown only after translation for offline comparison; they are not part of the translation prompt.", ""]
    for result in results:
        query = queries[result["query_id"]]
        lines += [f"## {result['query_id']}", f"- query_zh: {query['query_zh']}", f"- execution_status: `{result['execution_status']}`"]
        if result["translation"] is not None:
            translation = result["translation"]
            lines += [f"- machine_translated_query_en: {translation['translated_query']}", f"- human_reviewed_query_en_reference: {query['query_en']}", f"- preserved_entities: {', '.join(translation['preserved_entities'])}", f"- preserved_numbers_and_units: {', '.join(translation['preserved_numbers_and_units'])}"]
            ledger = result.get("preservation_ledger") or {}
            lines += [f"- verified_preserved_entities: {', '.join(ledger.get('verified_entities', []))}", f"- verified_preserved_numbers_and_units: {', '.join(ledger.get('verified_numbers_and_units', []))}"]
        else:
            lines += [f"- validation_error: {result['validation_error']}"]
        lines += ["", "### Author Review", "author_decision: ", "author_notes: ", ""]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _protected_entities(query_zh: str) -> list[str]:
    composite = re.compile(r"(?:\d+[A-Za-z]|[A-Za-z]\d+)(?:/(?:\d+[A-Za-z]|[A-Za-z]\d+))+|[A-Za-z][A-Za-z0-9]*@\d+(?:\.\d+)?|[A-Za-z]+(?:-[A-Za-z0-9]+)+|[A-Za-z]+\d+[A-Za-z0-9]*")
    matches = list(composite.finditer(query_zh))
    occupied = [match.span() for match in matches]
    for match in re.finditer(r"[A-Za-z]{2,}", query_zh):
        if not any(start <= match.start() < end or start < match.end() <= end for start, end in occupied):
            matches.append(match)
    return list(dict.fromkeys(match.group(0) for match in sorted(matches, key=lambda item: item.start())))


def _numbers_and_units(query_zh: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?(?:%|°|cm|FPS)?(?![A-Za-z])", query_zh, flags=re.IGNORECASE)))


def _preservation_ledger(query: dict[str, Any], response: TranslationResponse) -> dict[str, Any]:
    translated = response.translated_query.casefold()
    return {
        "verified_entities": [entity for entity in _protected_entities(query["query_zh"]) if entity.casefold() in translated],
        "verified_numbers_and_units": [item for item in _numbers_and_units(query["query_zh"]) if item.casefold() in translated],
        "model_reported_entities": response.preserved_entities,
        "model_reported_numbers_and_units": response.preserved_numbers_and_units,
    }


def _validate_scope(query_zh: str, translated: str) -> None:
    expected = {
        "哪些": ("which", "what"),
        "分别": ("respectively", "each"),
        "相比": ("compared", "versus", "relative"),
        "是否": ("whether", "does", "is", "are"),
    }
    for source, markers in expected.items():
        if source in query_zh and not any(marker in translated for marker in markers):
            raise TranslationContractError("query scope preservation failed: " + source)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
