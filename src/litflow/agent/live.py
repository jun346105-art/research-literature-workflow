"""Native tool-call planner used by the M8B single-agent pilot."""

from __future__ import annotations

import json
import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from litflow.agent.tools import TOOL_SCHEMAS
from litflow.llm.client import LLMToolCompletion
from litflow.rag.bm25 import BM25Index, load_corpus
from litflow.rag.qa import _load_entity_metadata, _parse_v12, _prompt_v12, _verify_v12
from litflow.rag.translation import TranslationResponse, build_translation_prompt


AGENT_PLANNER_PROMPT_VERSION = "evidence-bounded-agent-planner-v1"
PLANNER_SYSTEM_PROMPT = (
    "You are a bounded research workflow planner. Use only the provided native tools. "
    "Never request qrels, gold answers, files, shell, network, credentials, or side effects outside tools. "
    "Select exactly one tool when useful; otherwise return no tool call. "
    "Do not answer the user yourself. Use answer_grounded only after retrieve_evidence. "
    "Use stage_writing_draft only after query_evidence_matrix and only when the runtime grants approval."
)


def agent_tool_definitions() -> list[dict[str, Any]]:
    descriptions = {
        "list_papers": "List frozen corpus paper metadata only. Never request paths or files.",
        "retrieve_evidence": "Retrieve at most ten evidence snippets from the frozen corpus. No qrels or gold data are available.",
        "inspect_passages": "Inspect at most three known frozen passage IDs after retrieval.",
        "answer_grounded": "Generate a validated answer only after evidence retrieval. The deterministic core validates citations, quotes, entities, and coverage.",
        "query_evidence_matrix": "Read only author-reviewed Evidence Matrix records. It cannot create claims.",
        "stage_writing_draft": "Stage a new evidence-bound writing artifact only after human approval. It cannot overwrite a historical draft.",
    }
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": descriptions[name],
                "parameters": schema.model_json_schema(),
            },
        }
        for name, schema in TOOL_SCHEMAS.items()
    ]


@dataclass
class NativeToolPlanner:
    """One native-tool selection per bounded Agent planner turn."""

    client: Any
    task: dict[str, Any]
    usage: dict[str, int] = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "provider_reported_calls": 0})
    events: list[dict[str, Any]] = field(default_factory=list)
    pending_calls: list[dict[str, Any]] = field(default_factory=list)

    def decide(self, state: dict[str, Any]) -> dict[str, Any]:
        if self.pending_calls:
            action = self.pending_calls.pop(0)
            action["model_call_increment"] = 0
            self.events.append({"event": "planner_queued_tool_call", "tool_name": action["tool_name"], "arguments": action["args"]})
            return action
        completion = self.client.complete_tools_with_usage(self._messages(state), agent_tool_definitions(), temperature=0)
        if not isinstance(completion, LLMToolCompletion):
            return self._failure("planner_completion_invalid")
        self._record_usage(completion)
        calls = completion.tool_calls or []
        if not calls:
            self.events.append({"event": "planner_finish", "reason": "no_tool_call"})
            return {"tool_name": "finish", "args": {}, "decision_summary": "Planner returned no tool call."}
        actions = []
        for call in calls:
            function = call.get("function") if isinstance(call, dict) else None
            if not isinstance(function, dict) or function.get("name") not in TOOL_SCHEMAS:
                return self._failure("planner_unknown_tool")
            try:
                args = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                return self._failure("planner_tool_arguments_not_json")
            if not isinstance(args, dict):
                return self._failure("planner_tool_arguments_not_object")
            actions.append({"tool_name": function["name"], "args": args, "decision_summary": "Native tool selection recorded without hidden reasoning.", "model_call_increment": 0})
        self.pending_calls.extend(actions[1:])
        first = actions[0]
        first["model_call_increment"] = 1
        self.events.append({"event": "planner_tool_call", "tool_name": first["tool_name"], "arguments": first["args"], "parallel_call_count": len(actions)})
        return first

    def _messages(self, state: dict[str, Any]) -> list[dict[str, str]]:
        observations = _safe_observations(state)
        user = json.dumps(
            {
                "task_id": self.task["task_id"],
                "research_goal_zh": self.task["task_zh"],
                "required_tools": self.task.get("required_tools", []),
                "forbidden_tools": self.task.get("forbidden_tools", []),
                "observations": observations,
            },
            ensure_ascii=False,
        )
        return [{"role": "system", "content": PLANNER_SYSTEM_PROMPT}, {"role": "user", "content": user}]

    def _record_usage(self, completion: LLMToolCompletion) -> None:
        self.usage["provider_reported_calls"] += 1
        for key, value in (("input_tokens", completion.input_tokens), ("output_tokens", completion.output_tokens), ("total_tokens", completion.total_tokens)):
            if isinstance(value, int):
                self.usage[key] += value

    def _failure(self, reason: str) -> dict[str, Any]:
        self.events.append({"event": "planner_finish", "reason": reason})
        return {"tool_name": "finish", "args": {}, "decision_summary": reason}


def _safe_observations(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for call in state.get("tool_calls", []):
        refs = call.get("result_refs", [])
        rows.append({"tool_name": call.get("tool_name"), "result_refs": refs[:10] if isinstance(refs, list) else []})
    return rows


@dataclass
class LiveAgentTools:
    """M8B adapter around frozen corpus, QA validator, and reviewed Matrix inputs."""

    corpus_path: Path
    entity_metadata_path: Path
    matrix_records_path: Path
    artifact_dir: Path
    client: Any
    model: str
    task: dict[str, Any]
    calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "provider_reported_calls": 0})
    _last_top: list[dict[str, Any]] = field(default_factory=list)
    _matrix_records: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.passages = load_corpus(self.corpus_path)
        self.by_id = {item["passage_id"]: item for item in self.passages}
        self.index = BM25Index(self.passages)
        self.entities = _load_entity_metadata(self.entity_metadata_path)
        self._matrix_records = _load_jsonl(self.matrix_records_path)

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        method = getattr(self, f"_{name}", None)
        if method is None:
            raise ValueError("tool_not_allowed")
        result = method(args)
        self.calls.append({"tool_name": name, "args": args, "result_refs": result.get("evidence_refs", result.get("record_ids", [item.get("passage_id") for item in result.get("passages", []) if isinstance(item, dict)]))})
        return result

    def _list_papers(self, args: dict[str, Any]) -> dict[str, Any]:
        papers: dict[str, dict[str, Any]] = {}
        for passage in self.passages:
            paper = papers.setdefault(passage["paper_key"], {key: passage.get(key) for key in ("paper_key", "title", "citation_key", "year", "source_language")})
            paper["language"] = paper.pop("source_language", "en")
        rows = list(papers.values())
        if args.get("language"):
            rows = [row for row in rows if row.get("language") == args["language"]]
        if args.get("title_keyword"):
            term = args["title_keyword"].casefold()
            rows = [row for row in rows if term in (row.get("title") or "").casefold()]
        if args.get("year"):
            rows = [row for row in rows if row.get("year") == args["year"]]
        return {"papers": sorted(rows, key=lambda item: item["paper_key"])}

    def _retrieve_evidence(self, args: dict[str, Any]) -> dict[str, Any]:
        translated = self._translate(args["query"])
        hits = self.index.search(translated, top_k=args.get("top_k", 10))
        self._last_top = [self.by_id[item["passage_id"]] for item in hits]
        passages = []
        for hit, passage in zip(hits, self._last_top):
            passages.append({"passage_id": passage["passage_id"], "paper_key": passage["paper_key"], "title": passage.get("title"), "citation_key": passage.get("citation_key"), "page_start": passage["page_start"], "page_end": passage["page_end"], "score": hit["score"], "snippet": passage["text"][:480]})
        self._write_json("retrieval.json", {"query_zh": args["query"], "retrieval_query_en": translated, "passage_ids": [item["passage_id"] for item in passages]})
        return {"passages": passages, "evidence_refs": [item["passage_id"] for item in passages]}

    def _inspect_passages(self, args: dict[str, Any]) -> dict[str, Any]:
        unknown = [item for item in args["passage_ids"] if item not in self.by_id]
        if unknown:
            raise ValueError("unknown_passage_id")
        return {"passages": [{key: self.by_id[item].get(key) for key in ("passage_id", "paper_key", "citation_key", "title", "page_start", "page_end", "text", "text_sha256")} for item in args["passage_ids"]]}

    def _answer_grounded(self, args: dict[str, Any]) -> dict[str, Any]:
        if not self._last_top:
            raise ValueError("answer_grounded_requires_retrieval")
        query = {"query_id": self.task["task_id"], "query_zh": self.task["task_zh"]}
        prompt = _prompt_v12(query, self._last_top, self.entities)
        started = time.perf_counter()
        completion = self.client.complete_json_with_usage(prompt, temperature=0)
        self._record_usage(completion)
        raw_path = self._task_dir() / "answer_raw_response.txt"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(completion.content, encoding="utf-8")
        result = _verify_v12(query["query_id"], _parse_v12(completion.content), self.by_id, [item["passage_id"] for item in self._last_top], [str(raw_path.name)], self.entities, query)
        data = result.model_dump()
        self._write_json("answer_validation.json", {"result": data, "latency_ms": round((time.perf_counter() - started) * 1000, 6)})
        if data["execution_status"] != "success":
            return {"coverage_status": "execution_failed", "execution_status": data["execution_status"], "validation_error": data.get("validation_error")}
        citations = [citation["passage_id"] for claim in data.get("claims", []) for citation in claim.get("citations", [])]
        return {"coverage_status": data.get("coverage_status") or "none", "verified_claim_ids": [f"{self.task['task_id']}:C{index}" for index, _ in enumerate(data.get("claims", []), 1)], "evidence_refs": citations, "qa_result": data, "displayed_citation_validity": True, "displayed_quote_grounding": True, "displayed_claim_coverage": True}

    def _query_evidence_matrix(self, args: dict[str, Any]) -> dict[str, Any]:
        records = [row for row in self._matrix_records if row.get("review_decision") in {"pass", "pass_with_minor_revision"}]
        if args.get("paper_keys"):
            records = [row for row in records if row.get("paper_key") in set(args["paper_keys"])]
        if args.get("categories"):
            records = [row for row in records if row.get("evidence_category") in set(args["categories"])]
        if args.get("topic"):
            terms = args["topic"].casefold().split()
            records = [row for row in records if all(term in json.dumps(row, ensure_ascii=False).casefold() for term in terms)]
        return {"record_ids": [row["evidence_record_id"] for row in records], "records": records}

    def _stage_writing_draft(self, args: dict[str, Any]) -> dict[str, Any]:
        records = [row for row in self._matrix_records if row.get("evidence_record_id") in set(args["record_ids"])]
        if len(records) != len(set(args["record_ids"])) or any(row.get("review_decision") not in {"pass", "pass_with_minor_revision"} for row in records):
            raise ValueError("unreviewed_or_unknown_evidence_record")
        # The M8B pilot stages an isolated request; it never applies an Obsidian draft.
        stage = {"task_id": self.task["task_id"], "record_ids": args["record_ids"], "record_count": len(records), "approval_required": True}
        self._write_json("staged_writing_request.json", stage)
        return {"artifact": "staged_writing_request.json", "record_ids": args["record_ids"], "evidence_refs": args["record_ids"]}

    def _translate(self, query_zh: str) -> str:
        query = {"query_id": self.task["task_id"], "query_zh": query_zh}
        completion = self.client.complete_json_with_usage(build_translation_prompt(query), temperature=0)
        self._record_usage(completion)
        raw_path = self._task_dir() / "translation_raw_response.txt"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(completion.content, encoding="utf-8")
        response = TranslationResponse.model_validate_json(completion.content)
        response.validate_against_query(query)
        self._write_json("translation.json", {"translation": response.model_dump(), "raw_sha256": _sha256_file(raw_path)})
        return response.translated_query

    def _record_usage(self, completion: Any) -> None:
        self.usage["provider_reported_calls"] += 1
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = getattr(completion, key, None)
            if isinstance(value, int):
                self.usage[key] += value

    def _task_dir(self) -> Path:
        return self.artifact_dir / self.task["task_id"]

    def _write_json(self, name: str, payload: dict[str, Any]) -> None:
        path = self._task_dir() / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
