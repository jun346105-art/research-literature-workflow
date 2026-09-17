"""Offline, read-only local research executor for approved B04 plans.

This module deliberately owns no provider, writer, or final-answer path.  It
uses the B03R2 event store and replay reducer for its tool operations; the
only capabilities available through the registry are deterministic corpus
search and passage reads.
"""
from __future__ import annotations

import asyncio
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from litflow.llm.span_mapping import map_verbatim_span
from litflow.rag.bm25 import BM25Index

from .budgets import BudgetSpec, TokenUsage
from .contracts import (
    BriefApproval,
    ContractBundle,
    ContractModel,
    EvidenceLocator,
    EvidenceModality,
    EvidenceUnit,
    ResearchBrief,
    ResearchSubtask,
    ResearchTask,
    Source,
    SourceKind,
)
from .identity import canonical_json, make_stable_id, sha256_hex
from .operations import OperationKind
from .planner import PlannerError, ValidatedResearchPlan, require_approved_brief
from .runtime_v2 import (
    GENESIS_HASH,
    CoordinatedCheckpointV2,
    RuntimeEventEnvelope,
    RuntimeEventType,
    UnifiedEventStore,
    create_runtime_event,
    reduce_runtime_events,
    replay_runtime_events,
    write_coordinated_checkpoint,
)
from .state import RunState, RunStatus, transition
from .policies import CancellationToken


EXECUTOR_VERSION = "dr-local-research-executor-v1"
EVIDENCE_GRAPH_VERSION = "dr-evidence-graph-v1"


class ExecutorError(ValueError):
    """Code-bearing, fail-closed B05 error without a provider fallback."""

    def __init__(self, code: str, message: str, diagnostics: dict[str, object] | None = None):
        self.code, self.diagnostics = code, diagnostics or {}
        super().__init__(f"{code}: {message}")


class ToolName(str, Enum):
    search_local_corpus = "search_local_corpus"
    read_passage = "read_passage"


class LocalSearchRequest(ContractModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=1, ge=1, le=20)


class LocalSearchHit(ContractModel):
    passage_id: str
    source_id: str
    score: float = Field(ge=0)
    rank: int = Field(ge=1)


class ReadPassageRequest(ContractModel):
    passage_id: str = Field(min_length=1)


class LocalPassage(ContractModel):
    passage_id: str
    source: Source
    text: str = Field(min_length=1)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    chunk_id: str = Field(min_length=1)


class EvidenceCandidate(ContractModel):
    """Untrusted candidate anchor; only the program creates EvidenceUnit."""

    passage_id: str = Field(min_length=1)
    quote_hint: str = Field(min_length=1)


class EvidenceGraphEdge(ContractModel):
    run_id: str
    relation: str
    from_id: str
    to_id: str


class EvidenceGraph(ContractModel):
    schema_version: Literal[EVIDENCE_GRAPH_VERSION] = EVIDENCE_GRAPH_VERSION
    run_id: str
    task_id: str
    plan_id: str
    subtasks: tuple[ResearchSubtask, ...]
    sources: tuple[Source, ...]
    evidence_units: tuple[EvidenceUnit, ...]
    edges: tuple[EvidenceGraphEdge, ...]

    @model_validator(mode="after")
    def validate_graph(self) -> "EvidenceGraph":
        ids = {
            "subtask": {item.subtask_id for item in self.subtasks},
            "source": {item.source_id for item in self.sources},
            "evidence": {item.evidence_id for item in self.evidence_units},
        }
        if len(ids["subtask"]) != len(self.subtasks) or len(ids["source"]) != len(self.sources) or len(ids["evidence"]) != len(self.evidence_units):
            raise ValueError("evidence graph node IDs must be unique")
        source_ids = ids["source"]
        if any(item.source_id not in source_ids for item in self.evidence_units):
            raise ValueError("evidence graph contains evidence with an unknown source")
        known = set().union(*ids.values())
        seen: set[tuple[str, str, str]] = set()
        allowed = {
            "subtask_retrieved_source": (ids["subtask"], ids["source"]),
            "source_contains_evidence": (ids["source"], ids["evidence"]),
            "evidence_supports_subtask": (ids["evidence"], ids["subtask"]),
        }
        for edge in self.edges:
            if edge.run_id != self.run_id or edge.relation not in allowed or edge.from_id not in known or edge.to_id not in known or edge.from_id == edge.to_id:
                raise ValueError("evidence graph contains an invalid edge")
            left, right = allowed[edge.relation]
            if edge.from_id not in left or edge.to_id not in right:
                raise ValueError("evidence graph edge endpoint type mismatch")
            identity = (edge.relation, edge.from_id, edge.to_id)
            if identity in seen:
                raise ValueError("evidence graph duplicate edge")
            seen.add(identity)
        if any(item.task_id != self.task_id for item in self.subtasks) or tuple(sorted(self.subtasks, key=lambda item: item.subtask_id)) != self.subtasks or tuple(sorted(self.sources, key=lambda item: item.source_id)) != self.sources or tuple(sorted(self.evidence_units, key=lambda item: item.evidence_id)) != self.evidence_units or tuple(sorted(self.edges, key=lambda item: (item.relation, item.from_id, item.to_id))) != self.edges:
            raise ValueError("evidence graph nodes and edges must be canonical")
        return self


class SubtaskExecutionStatus(str, Enum):
    completed = "completed"
    failed = "failed"


class SubtaskExecutionResult(ContractModel):
    subtask_id: str
    status: SubtaskExecutionStatus
    evidence_ids: tuple[str, ...] = ()
    error_code: str | None = None


class LocalExecutorResult(ContractModel):
    schema_version: Literal[EXECUTOR_VERSION] = EXECUTOR_VERSION
    run_id: str
    plan_id: str
    subtask_results: tuple[SubtaskExecutionResult, ...]
    evidence_graph: EvidenceGraph
    events: tuple[RuntimeEventEnvelope, ...]


class _LocalCorpus:
    """In-memory frozen corpus facade; no request may name a filesystem path."""

    def __init__(self, passages: list[dict[str, Any]]) -> None:
        ids = [str(item.get("passage_id", "")) for item in passages]
        if not passages or any(not item for item in ids) or len(ids) != len(set(ids)):
            raise ExecutorError("corpus_identity_mismatch", "corpus must contain unique stable passage IDs")
        self._passages = {str(item["passage_id"]): dict(item) for item in passages}
        self._sources = {passage_id: self._source(row) for passage_id, row in self._passages.items()}
        self._index = BM25Index([self._passages[key] for key in sorted(self._passages)])
        self.size = len(self._passages)

    @staticmethod
    def _source(row: dict[str, Any]) -> Source:
        context_hash = str(row.get("source_context_sha256", ""))
        if len(context_hash) != 64:
            raise ExecutorError("corpus_identity_mismatch", "passage source provenance hash is required")
        paper_key = str(row.get("paper_key", ""))
        if not paper_key:
            raise ExecutorError("corpus_identity_mismatch", "passage paper key is required")
        return Source.create(
            SourceKind.passage_corpus,
            f"corpus:{paper_key}:{context_hash}",
            str(row.get("title") or paper_key),
            context_hash,
            "en",
            bibliographic_metadata={"paper_key": paper_key, "citation_key": str(row.get("citation_key") or "")},
        )

    async def search(self, request: LocalSearchRequest) -> tuple[LocalSearchHit, ...]:
        return tuple(
            LocalSearchHit(passage_id=item["passage_id"], source_id=self._sources[item["passage_id"]].source_id, score=item["score"], rank=item["rank"])
            for item in self._index.search(request.query, top_k=request.top_k)
        )

    async def read(self, request: ReadPassageRequest) -> LocalPassage:
        row = self._passages.get(request.passage_id)
        if row is None:
            raise ExecutorError("passage_not_found", "passage ID is not part of the frozen corpus")
        return LocalPassage(
            passage_id=request.passage_id,
            source=self._sources[request.passage_id],
            text=str(row["text"]),
            page_start=int(row["page_start"]),
            page_end=int(row["page_end"]),
            chunk_id=str(row["chunk_id"]),
        )


class ReadOnlyToolRegistry:
    """The only B05 tool entry point; capabilities are fixed at construction."""

    def __init__(self, passages: list[dict[str, Any]], *, allowed: tuple[ToolName, ...] = (ToolName.search_local_corpus, ToolName.read_passage), allowed_source_keys: tuple[str, ...] = (), allowed_passage_ids: tuple[str, ...] = (), _shared_calls: list[ToolName] | None = None, _pre_filter_count: int | None = None) -> None:
        if set(allowed) - {ToolName.search_local_corpus, ToolName.read_passage}:
            raise ExecutorError("tool_not_allowed", "B05 allows local corpus search and passage read only")
        source_scope = frozenset(allowed_source_keys)
        passage_scope = frozenset(allowed_passage_ids)
        pre_filter_count = len(passages) if _pre_filter_count is None else _pre_filter_count
        scoped = [row for row in passages if not source_scope or str(row.get("paper_key")) in source_scope]
        if source_scope and not scoped:
            raise ExecutorError("selected_source_evidence_missing", "source-scoped corpus contains no allowed passage", {"failure_stage": "executor_source_prefilter", "contract_error_code": "selected_source_evidence_missing", "allowed_source_count": len(source_scope), "pre_filter_candidate_count": len(passages), "source_scoped_result_count": 0, "bounded_top_k": 1, "target_qrel_rank": None, "validation_rule": "source_metadata_prefilter_before_bm25"})
        self._corpus = _LocalCorpus(scoped)
        self._allowed = frozenset(allowed)
        self.calls: list[ToolName] = _shared_calls if _shared_calls is not None else []
        self.allowed_source_keys, self.allowed_passage_ids = source_scope, passage_scope
        self._pre_filter_count = pre_filter_count
        self.last_search_stats: dict[str, object] = {}

    def scoped(self, source_keys: tuple[str, ...]) -> "ReadOnlyToolRegistry":
        return ReadOnlyToolRegistry(list(self._corpus._passages.values()), allowed=tuple(self._allowed), allowed_source_keys=source_keys, _shared_calls=self.calls, _pre_filter_count=self._pre_filter_count)

    async def invoke(self, name: ToolName, request: ContractModel) -> object:
        if name not in self._allowed:
            raise ExecutorError("tool_not_allowed", f"capability {name.value} is not enabled")
        self.calls.append(name)
        if name is ToolName.search_local_corpus:
            if not isinstance(request, LocalSearchRequest):
                raise ExecutorError("tool_contract_invalid", "search request contract is invalid")
            hits = await self._corpus.search(request)
            self.last_search_stats = {"pre_filter_candidate_count": self._pre_filter_count, "source_scoped_candidate_count": self._corpus.size, "source_scoped_result_count": len(hits), "bounded_top_k": request.top_k}
            return hits
        if name is ToolName.read_passage:
            if not isinstance(request, ReadPassageRequest):
                raise ExecutorError("tool_contract_invalid", "passage read request contract is invalid")
            return await self._corpus.read(request)
        raise ExecutorError("tool_not_allowed", "unknown capability")


def build_evidence(candidate: EvidenceCandidate, passage: LocalPassage) -> EvidenceUnit:
    if candidate.passage_id != passage.passage_id:
        raise ExecutorError("evidence_reference_invalid", "candidate passage must match the retrieved passage")
    mapped = map_verbatim_span(candidate.quote_hint, passage.text)
    if mapped.status != "ok" or mapped.start is None or mapped.end is None:
        raise ExecutorError("evidence_anchor_not_found", "candidate quote does not resolve to one exact passage span")
    return EvidenceUnit.create(
        passage.source.source_id,
        EvidenceModality.text,
        EvidenceLocator(passage_id=passage.passage_id, page_number=passage.page_start, span_start=mapped.start, span_end=mapped.end),
        mapped.evidence_text,
        "en",
        {"chunk_id": passage.chunk_id, "page_end": str(passage.page_end), "anchor_method": mapped.method},
    )


class LocalResearchExecutor:
    """Sequential B05 executor: approved plan -> registry -> verified EvidenceGraph."""

    def __init__(self, registry: ReadOnlyToolRegistry, *, budget: BudgetSpec | None = None, token: CancellationToken | None = None) -> None:
        self._registry = registry
        self._budget = budget or BudgetSpec(max_tool_attempts=64, max_tool_calls=64, max_retries=0, max_replans=0, run_timeout_s=30.0, operation_timeout_s=10.0)
        self._token = token or CancellationToken()

    async def execute(
        self,
        task: ResearchTask,
        brief: ResearchBrief,
        approval: BriefApproval,
        plan: ValidatedResearchPlan,
        *,
        event_path: Path,
        checkpoint_path: Path,
        candidates: dict[str, tuple[EvidenceCandidate, ...]] | None = None,
        run_id: str | None = None,
        allowed_source_keys: tuple[str, ...] | None = None,
        allowed_passage_ids: tuple[str, ...] | None = None,
        allowed_source_keys_by_subtask: dict[str, tuple[str, ...]] | None = None,
        retrieval_top_k: int = 1,
    ) -> LocalExecutorResult:
        self._validate_plan(task, brief, approval, plan)
        run_id = run_id or make_stable_id("run", {"runtime": EXECUTOR_VERSION, "plan_id": plan.plan_id})
        initial_state = RunState(run_id=run_id, task_id=task.task_id, brief_id=brief.brief_id, brief_approved=True)
        store = UnifiedEventStore(event_path, run_id=run_id)
        events = store.read_all()
        if not events:
            state = initial_state
            self._append(store, events, RuntimeEventType.run_started, {"executor_version": EXECUTOR_VERSION, "plan_id": plan.plan_id, "spec": self._budget.model_dump(mode="json")})
            state = self._lifecycle(store, events, state, RunStatus.brief_approved)
            state = self._lifecycle(store, events, state, RunStatus.researching)
        else:
            state = reduce_runtime_events(initial_state, events, self._budget).run_state
            if state.status is not RunStatus.researching:
                raise ExecutorError("plan_not_executable", "shared runtime stream must be researching before local tool dispatch")
        sources: dict[str, Source] = {}
        evidence: dict[str, EvidenceUnit] = {}
        edges: set[tuple[str, str, str]] = set()
        results: list[SubtaskExecutionResult] = []
        complete: set[str] = set()
        allowed_sources = frozenset(allowed_source_keys or ())
        allowed_passages = frozenset(allowed_passage_ids or ())
        for subtask in plan.subtasks:
            if self._token.cancelled:
                raise ExecutorError("cancelled", "execution was cancelled before the next subtask")
            if any(item not in complete for item in subtask.dependency_ids):
                raise ExecutorError("subtask_dependency_unsatisfied", "subtask dependencies must complete before execution")
            scoped_registry = self._registry.scoped(allowed_source_keys_by_subtask[subtask.subtask_id]) if allowed_source_keys_by_subtask and subtask.subtask_id in allowed_source_keys_by_subtask else self._registry
            hits = await self._tool(store, events, initial_state, subtask, ToolName.search_local_corpus, LocalSearchRequest(query=subtask.question, top_k=retrieval_top_k), registry=scoped_registry)
            if not hits:
                raise ExecutorError("source_not_found", "local corpus search returned no passage")
            if allowed_passages:
                selected_hits = tuple(hit for hit in hits if hit.passage_id in allowed_passages)
                if not selected_hits:
                    stats = getattr(scoped_registry, "last_search_stats", {})
                    raise ExecutorError("selected_source_evidence_missing", "retrieval returned no passage from the immutable cross-paper allowlist", {"failure_stage": "executor_source_retrieval", "contract_error_code": "selected_source_evidence_missing", "allowed_source_count": len(allowed_sources), "pre_filter_candidate_count": stats.get("pre_filter_candidate_count"), "source_scoped_candidate_count": stats.get("source_scoped_candidate_count"), "source_scoped_result_count": 0, "bounded_top_k": stats.get("bounded_top_k", 1), "target_qrel_rank": None, "validation_rule": "source_metadata_prefilter_before_bm25"})
                hits = selected_hits
            selected = candidates.get(subtask.subtask_id) if candidates else None
            evidence_ids: list[str] = []
            candidate_items: list[tuple[EvidenceCandidate, LocalPassage]] = []
            if selected is None:
                passage = await self._tool(store, events, initial_state, subtask, ToolName.read_passage, ReadPassageRequest(passage_id=hits[0].passage_id), registry=scoped_registry)
                assert isinstance(passage, LocalPassage)
                candidate_items.append((EvidenceCandidate(passage_id=passage.passage_id, quote_hint=passage.text), passage))
            else:
                for candidate in selected:
                    if allowed_passages and candidate.passage_id not in allowed_passages:
                        raise ExecutorError("cross_paper_source_selection_mismatch", "candidate passage is outside the immutable cross-paper allowlist")
                    passage = await self._tool(store, events, initial_state, subtask, ToolName.read_passage, ReadPassageRequest(passage_id=candidate.passage_id), registry=scoped_registry)
                    assert isinstance(passage, LocalPassage)
                candidate_items.append((candidate, passage))
            for candidate, passage in candidate_items:
                source_key = passage.source.bibliographic_metadata.get("paper_key")
                if allowed_sources and source_key not in allowed_sources:
                    raise ExecutorError("cross_paper_source_selection_mismatch", "passage source is outside the immutable cross-paper allowlist")
                unit = build_evidence(candidate, passage)
                sources[passage.source.source_id] = passage.source
                evidence[unit.evidence_id] = unit
                evidence_ids.append(unit.evidence_id)
                edges.update({
                    ("subtask_retrieved_source", subtask.subtask_id, passage.source.source_id),
                    ("source_contains_evidence", passage.source.source_id, unit.evidence_id),
                    ("evidence_supports_subtask", unit.evidence_id, subtask.subtask_id),
                })
            results.append(SubtaskExecutionResult(subtask_id=subtask.subtask_id, status=SubtaskExecutionStatus.completed, evidence_ids=tuple(sorted(set(evidence_ids)))))
            complete.add(subtask.subtask_id)
        replayed = replay_runtime_events(initial_state, events, self._budget)
        write_coordinated_checkpoint(checkpoint_path, CoordinatedCheckpointV2.from_result(replayed))
        graph = EvidenceGraph(
            run_id=run_id, task_id=task.task_id, plan_id=plan.plan_id,
            subtasks=tuple(sorted(plan.subtasks, key=lambda item: item.subtask_id)),
            sources=tuple(sorted(sources.values(), key=lambda item: item.source_id)),
            evidence_units=tuple(sorted(evidence.values(), key=lambda item: item.evidence_id)),
            edges=tuple(EvidenceGraphEdge(run_id=run_id, relation=relation, from_id=source, to_id=target) for relation, source, target in sorted(edges)),
        )
        return LocalExecutorResult(run_id=run_id, plan_id=plan.plan_id, subtask_results=tuple(results), evidence_graph=graph, events=tuple(events))

    def _validate_plan(self, task: ResearchTask, brief: ResearchBrief, approval: BriefApproval, plan: ValidatedResearchPlan) -> None:
        try:
            require_approved_brief(task, brief, approval)
            if plan.task_id != task.task_id or plan.brief_id != brief.brief_id or plan.approval_id != approval.approval_id:
                raise PlannerError("plan_not_executable", "plan must bind to the approved task, brief, and approval")
            bundle = ContractBundle(task=task, brief=brief, brief_approvals=(approval,), subtasks=plan.subtasks)
            if bundle.topological_subtask_ids() != plan.topological_subtask_ids:
                raise PlannerError("plan_not_executable", "plan topological order must be canonical")
        except (PlannerError, ValueError) as error:
            raise ExecutorError("plan_not_executable", "validated approved plan is required before any tool call") from error

    @staticmethod
    def _append(store: UnifiedEventStore, events: list[RuntimeEventEnvelope], event_type: RuntimeEventType, payload: dict[str, Any], *, operation_id: str | None = None, attempt_id: str | None = None, causal_parent_id: str | None = None) -> RuntimeEventEnvelope:
        event = create_runtime_event(store.run_id, len(events) + 1, event_type, payload=payload, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=causal_parent_id, previous_event_hash=events[-1].event_hash if events else GENESIS_HASH)
        store.append(event)
        events.append(event)
        return event

    def _lifecycle(self, store: UnifiedEventStore, events: list[RuntimeEventEnvelope], state: RunState, target: RunStatus) -> RunState:
        next_state, lifecycle = transition(state, target)
        self._append(store, events, RuntimeEventType.lifecycle_transition, lifecycle.model_dump(mode="json"), causal_parent_id=events[-1].event_id)
        return next_state

    async def _tool(self, store: UnifiedEventStore, events: list[RuntimeEventEnvelope], initial_state: RunState, subtask: ResearchSubtask, name: ToolName, request: ContractModel, *, registry: ReadOnlyToolRegistry | None = None) -> object:
        if self._token.cancelled:
            raise ExecutorError("cancelled", "execution was cancelled before tool dispatch")
        operation_id = make_stable_id("operation", {"run_id": initial_state.run_id, "subtask_id": subtask.subtask_id, "tool": name.value, "request": request.model_dump(mode="json")})
        attempt_id = make_stable_id("attempt", {"operation_id": operation_id, "attempt_number": 1})
        usage = TokenUsage()
        reserved = self._append(store, events, RuntimeEventType.operation_reserved, {"operation_kind": OperationKind.tool.value, "operation_name": name.value, "attempt_number": 1, "idempotent": True, "side_effecting": False, "usage": usage.model_dump(mode="json")}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=events[-1].event_id)
        try:
            reduce_runtime_events(initial_state, events, self._budget)
        except ValueError as error:
            raise ExecutorError("budget_exhausted", "budget reservation failed before tool dispatch") from error
        dispatched = self._append(store, events, RuntimeEventType.operation_dispatched, {"operation_kind": OperationKind.tool.value, "operation_name": name.value, "attempt_number": 1, "effective_timeout_s": self._budget.operation_timeout_s}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=reserved.event_id)
        try:
            result = await asyncio.wait_for((registry or self._registry).invoke(name, request), timeout=self._budget.operation_timeout_s)
        except TimeoutError as error:
            self._append(store, events, RuntimeEventType.operation_unknown, {"error_code": "unknown_outcome", "attempt_number": 1, "usage": usage.model_dump(mode="json")}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=dispatched.event_id)
            raise ExecutorError("unknown_outcome", "tool timeout after durable dispatch requires manual review") from error
        except ExecutorError as error:
            self._append(store, events, RuntimeEventType.operation_failed, {"error_code": error.code, "attempt_number": 1, "usage": usage.model_dump(mode="json")}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=dispatched.event_id)
            raise
        except Exception as error:
            self._append(store, events, RuntimeEventType.operation_failed, {"error_code": "tool_failure", "attempt_number": 1, "usage": usage.model_dump(mode="json")}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=dispatched.event_id)
            raise ExecutorError("tool_failure", "read-only tool raised an unexpected error") from error
        encoded = canonical_json(_result_json(result))
        self._append(store, events, RuntimeEventType.operation_succeeded, {"attempt_number": 1, "status": "success", "usage": usage.model_dump(mode="json"), "result_sha256": sha256_hex(encoded.encode("utf-8"))}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=dispatched.event_id)
        return result


def _result_json(value: object) -> object:
    if isinstance(value, ContractModel):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return [_result_json(item) for item in value]
    return value
