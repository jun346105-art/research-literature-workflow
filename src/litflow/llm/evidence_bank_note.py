from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from litflow.llm.client import LLMClient, LLMError, OpenAICompatibleClient
from litflow.llm.models import StructuredReadingNote
from litflow.llm.structured_reader import _parse_json_response, _validate_evidence_links, build_llm_input


FIELDS = [
    "one_sentence_summary",
    "research_background",
    "research_gap",
    "core_contribution",
    "method_summary",
    "data_or_experiment",
    "model_or_algorithm",
    "objective_or_task",
    "key_results",
    "limitations",
    "relevance_to_my_research",
]

USER_RESEARCH_CONTEXT = (
    "我正在做物流纸箱/包装箱表观缺陷检测，关注 hole / tear / breakage、wet、scratch 三类缺陷。"
    "当前研究路线包括 YOLO 检测、受控 scratch 合成、小缺陷检测分支、轻量注意力模块，以及工程应用型中文论文写作。"
    "目标是整理能支撑“包装箱表观缺陷检测、YOLO 改进、数据增强、小样本缺陷、实际物流包装检测”的文献素材。"
)


def generate_note_from_evidence_bank(
    candidate_bank_path: Path,
    clean_context_path: Path,
    output_path: Path,
    *,
    zotero_key: str,
    citation_key: str,
    title: str,
    client: LLMClient | None = None,
) -> StructuredReadingNote:
    bank = json.loads(candidate_bank_path.read_text(encoding="utf-8-sig"))
    clean_context = json.loads(clean_context_path.read_text(encoding="utf-8-sig"))
    candidates = _with_candidate_ids(zotero_key, bank.get("candidates", []))
    client = client or OpenAICompatibleClient.from_env()
    raw_response = client.complete_json(_bank_prompt(title, candidates))
    try:
        data = _parse_json_response(raw_response)
        note_data = _assemble_note(data, candidates, candidate_bank_path, zotero_key, citation_key, title)
        note = StructuredReadingNote.model_validate(note_data)
        allowed_chunks = {chunk["chunk_id"]: chunk for chunk in build_llm_input(clean_context)["chunks"]}
        _validate_evidence_links(note, allowed_chunks)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        _write_error(output_path, raw_response, exc)
        raise LLMError(f"LLM returned invalid evidence-bank note; raw response saved to {output_path.with_suffix('.error.json')}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(note.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return note


def _with_candidate_ids(zotero_key: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**candidate, "candidate_id": f"{zotero_key}_ev_{index:04d}"} for index, candidate in enumerate(candidates, 1)]


def _bank_prompt(title: str, candidates: list[dict[str, Any]]) -> str:
    schema = {field: "" for field in FIELDS}
    schema.update(
        {
            "related_concepts": [],
            "tags_suggestion": [],
            "warnings": [],
            "evidence_selections": [{"claim": "", "candidate_id": ""}],
        }
    )
    visible_candidates = [
        {
            "candidate_id": c["candidate_id"],
            "claim": c.get("claim", ""),
            "evidence_type": c.get("evidence_type", "other"),
            "evidence_text": c.get("evidence_text", ""),
        }
        for c in candidates
    ]
    return (
        "Use only this evidence candidate bank to draft a structured reading note.\n"
        "Return JSON only. Do not output evidence_text, chunk_id, page_start, or page_end.\n"
        "For evidence, select candidate_id values from the provided bank only.\n"
        "Use Chinese for explanatory fields except evidence text, which the program will copy from the bank.\n"
        "Write like an Obsidian close-reading note, not a short abstract.\n"
        "Use this user research context when writing relevance_to_my_research:\n"
        f"{USER_RESEARCH_CONTEXT}\n"
        "Field requirements:\n"
        "- one_sentence_summary: exactly 1 sentence.\n"
        "- research_background: 2-4 sentences about scenario, source of problem, and why detection is needed.\n"
        "- research_gap: 2-4 sentences about the limitations this paper addresses.\n"
        "- core_contribution: at least 3 bullet-like points, each 1-2 sentences.\n"
        "- method_summary: 3-6 sentences covering modules, workflow, and design motivation.\n"
        "- data_or_experiment: 2-4 sentences about data, setting, comparison, or metrics.\n"
        "- model_or_algorithm: 2-4 sentences about model structure or algorithm mechanism.\n"
        "- objective_or_task: 1-3 sentences defining the task.\n"
        "- key_results: 2-4 bullet-like points with interpretation, not only metrics.\n"
        "- limitations: at least 2 points; mark application-level inference explicitly when inferred.\n"
        "- relevance_to_my_research: 4-6 sentences; never use not_found. Explain direct or indirect relevance to logistics carton surface defects, YOLO, hole/wet/scratch, data augmentation, experiments, and what cannot be copied directly.\n"
        "- related_concepts and tags_suggestion: 5-10 items each.\n"
        "- warnings: include revised_longform_note.\n"
        "If information is not supported by the evidence bank, say it is an application-level inference rather than pretending it is directly evidenced.\n\n"
        f"Paper title: {title}\n"
        f"Schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        f"Evidence candidate bank:\n{json.dumps(visible_candidates, ensure_ascii=False)}"
    )


def _assemble_note(
    data: dict[str, Any],
    candidates: list[dict[str, Any]],
    candidate_bank_path: Path,
    zotero_key: str,
    citation_key: str,
    title: str,
) -> dict[str, Any]:
    by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    evidence_links = []
    for selection in data.get("evidence_selections", []):
        candidate_id = selection.get("candidate_id")
        if candidate_id not in by_id:
            raise ValueError(f"unknown candidate_id selected: {candidate_id}")
        candidate = by_id[candidate_id]
        evidence_links.append(
            {
                "claim": selection.get("claim") or candidate.get("claim", ""),
                "chunk_id": candidate["chunk_id"],
                "page_start": candidate["page_start"],
                "page_end": candidate["page_end"],
                "evidence_text": candidate["evidence_text"],
            }
        )
    if len(evidence_links) < 3:
        raise ValueError("fewer than 3 evidence selections")
    methods: dict[str, int] = {}
    for candidate in candidates:
        method = candidate.get("anchoring_method", "unknown")
        methods[method] = methods.get(method, 0) + 1
    return {
        "zotero_key": zotero_key,
        "citation_key": citation_key,
        "title": title,
        "reading_status": "llm_draft",
        **{field: _text_field(data.get(field, "")) for field in FIELDS},
        "usable_quotes_or_evidence": [],
        "related_concepts": data.get("related_concepts", []),
        "tags_suggestion": data.get("tags_suggestion", []),
        "evidence_links": evidence_links,
        "warnings": [
            "generated_from_evidence_candidate_bank",
            f"candidate_bank_path={candidate_bank_path}",
            f"evidence_candidate_count={len(candidates)}",
            f"selected_evidence_count={len(evidence_links)}",
            f"anchoring_methods_summary={json.dumps(methods, ensure_ascii=False)}",
            *data.get("warnings", []),
        ],
    }


def _text_field(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value)
    return str(value or "")


def _write_error(output_path: Path, raw_response: str, error: Exception) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.with_suffix(".error.json").write_text(
        json.dumps({"error_type": type(error).__name__, "error": str(error), "raw_response": raw_response}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
