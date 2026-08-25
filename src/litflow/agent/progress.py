"""Deterministic progress policy projected from durable Agent events."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


STEERING_TEMPLATE_VERSION = "progress-aware-steering-v1"


def extract_requested_entities(goal: str, entity_metadata: dict[str, Any]) -> list[str]:
    names = []
    for entity in entity_metadata.get("entities", []):
        for alias in entity.get("aliases", []):
            if alias.casefold() in goal.casefold():
                names.append(entity["entity_name"])
                break
    # Keep unknown named technical entities visible as missing rather than inventing metadata.
    names.extend(re.findall(r"[A-Z][A-Za-z0-9]+(?:-[A-Za-z0-9]+)+", goal))
    return list(dict.fromkeys(names))


@dataclass(frozen=True)
class ProgressController:
    entity_metadata: dict[str, Any]

    def retrieval_limit(self, requested_entities: list[str]) -> int:
        return min(3, max(2, len(requested_entities)))

    def next_actions(self, projection: dict[str, Any], *, category: str, requested_entities: list[str]) -> list[str]:
        if category in {"evidence_matrix", "writing_approval"}:
            if projection.get("evidence_matrix_loaded"):
                return []
            return ["query_evidence_matrix"]
        if projection.get("retrieved_evidence_count", 0) == 0:
            return ["list_papers", "retrieve_evidence"]
        actions = ["answer_grounded"]
        if projection.get("retrieval_calls_used", 0) < self.retrieval_limit(requested_entities) and projection.get("missing_entities"):
            actions.insert(0, "retrieve_evidence")
        return actions

    def fingerprint(self, projection: dict[str, Any]) -> str:
        fields = {key: projection.get(key) for key in ("successful_tool_signatures", "retrieved_evidence_ids", "covered_entities", "missing_entities", "evidence_matrix_loaded", "approval_status", "final_answer_status")}
        fields["retrieved_evidence_ids"] = sorted(set(fields["retrieved_evidence_ids"] or []))
        return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def coverage_route(self, projection: dict[str, Any]) -> str:
        if not projection.get("retrieved_evidence_count", 0):
            return "none"
        if projection.get("missing_entities"):
            return "partial"
        return "complete"

    def soft_budget_reached(self, projection: dict[str, Any], requested_entities: list[str]) -> bool:
        return projection.get("retrieval_calls_used", 0) >= self.retrieval_limit(requested_entities)

    def steering_message(self, projection: dict[str, Any]) -> str | None:
        if projection.get("steering_used"):
            return None
        payload = {key: projection.get(key, [] if key in {"covered_entities", "missing_entities", "allowed_next_actions"} else 0) for key in ("retrieved_evidence_count", "covered_entities", "missing_entities", "retrieval_calls_remaining", "tool_calls_remaining", "allowed_next_actions")}
        return json.dumps({"instruction": "Use the current evidence to complete, partially answer, or abstain. Do not request disabled tools.", "progress": payload}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
