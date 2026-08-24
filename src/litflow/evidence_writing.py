from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from litflow.llm.client import LLMError, OpenAICompatibleClient


WRITING_PROMPT_VERSION = "evidence-grounded-method-comparison-v1"


class WritingValidationError(ValueError):
    pass


def build_writing_prompt(task: dict[str, Any], records: list[dict[str, Any]]) -> str:
    allowed = [{key: record.get(key) for key in ("evidence_record_id", "claim_text", "paper_key", "citation_key", "title", "evidence_category", "coverage_status", "limitations", "citations")} for record in records]
    schema = {"task_id": task["task_id"], "section_type": "method_comparison", "outline": [{"outline_id": "O1", "heading_zh": "", "heading_en": "", "purpose_zh": "", "supporting_record_ids": []}], "sentences": [{"sentence_id": "S1", "sentence_type": "evidence_claim | cross_paper_synthesis", "text_zh": "", "text_en": "", "supporting_record_ids": [], "citation_keys": []}], "limitations_zh": "", "limitations_en": ""}
    return "Write one editable bilingual method-comparison draft only from the supplied reviewed evidence records. Return JSON only. Do not add facts, citations, datasets, methods, or completeness claims absent from records. Cross-paper synthesis must compare only record-supported dimensions. Keep partial coverage explicit.\nTASK:\n" + json.dumps(task, ensure_ascii=False) + "\nOUTPUT_SCHEMA:\n" + json.dumps(schema, ensure_ascii=False) + "\nREVIEWED_EVIDENCE_RECORDS:\n" + json.dumps(allowed, ensure_ascii=False)


def validate_writing_output(output: dict[str, Any], task_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    if output.get("task_id") != task_id or output.get("section_type") != "method_comparison":
        raise WritingValidationError("task identity mismatch")
    by_id = {record["evidence_record_id"]: record for record in records}
    if not output.get("outline") or not output.get("sentences"):
        raise WritingValidationError("outline and sentences are required")
    for item in [*output["outline"], *output["sentences"]]:
        for record_id in item.get("supporting_record_ids", []):
            if record_id not in by_id:
                raise WritingValidationError("unknown evidence record")
            if by_id[record_id]["review_decision"] not in {"pass", "pass_with_minor_revision"}:
                raise WritingValidationError("unreviewed evidence record")
    for sentence in output["sentences"]:
        record_ids = sentence.get("supporting_record_ids", [])
        if not record_ids:
            raise WritingValidationError("sentence has no evidence record")
        supported_keys = sorted({by_id[record_id]["citation_key"] for record_id in record_ids})
        if sorted(sentence.get("citation_keys", [])) != supported_keys:
            raise WritingValidationError("citation key does not match evidence record")
        if sentence.get("sentence_type") == "cross_paper_synthesis" and len({by_id[record_id]["paper_key"] for record_id in record_ids}) < 2:
            raise WritingValidationError("cross-paper synthesis requires two distinct papers")
        if not sentence.get("text_zh") or not sentence.get("text_en") or not sentence.get("sentence_id"):
            raise WritingValidationError("bilingual sentence fields are required")
    partial = [record for record in records if record.get("coverage_status") == "partial"]
    if partial and not any("TPMN" in text for text in (output.get("limitations_zh", ""), output.get("limitations_en", ""))):
        raise WritingValidationError("partial coverage is not explicit")
    return output


def validate_author_closure(sentences: list[dict[str, Any]], records: list[dict[str, Any]]) -> None:
    by_id = {record["evidence_record_id"]: record for record in records}
    for sentence in sentences:
        ids = sentence.get("supporting_record_ids", [])
        if not ids:
            raise WritingValidationError("author-reviewed sentence has no evidence record")
        for record_id in ids:
            if record_id not in by_id:
                raise WritingValidationError("unknown evidence record")
            if by_id[record_id]["review_decision"] not in {"pass", "pass_with_minor_revision"}:
                raise WritingValidationError("failed evidence record")
        keys = sorted({by_id[record_id]["citation_key"] for record_id in ids})
        if sorted(sentence.get("citation_keys", [])) != keys:
            raise WritingValidationError("citation key does not match evidence record")


def render_writing(output: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, str]:
    by_id = {record["evidence_record_id"]: record for record in records}
    outline = ["# Method Comparison Outline", ""]
    for item in output["outline"]:
        outline += [f"## {item['outline_id']} {item['heading_zh']} / {item['heading_en']}", item["purpose_zh"], "Records: " + ", ".join(item["supporting_record_ids"]), ""]
    zh = ["# Method Comparison Draft (ZH)", ""]
    en = ["# Method Comparison Draft (EN)", ""]
    ledger = ["# Sentence Evidence Ledger", "", "| Sentence | Records | Citations |", "| --- | --- | --- |"]
    for sentence in output["sentences"]:
        refs = _citation_suffix(sentence["supporting_record_ids"], by_id)
        zh += [f"{sentence['text_zh']} {refs}", ""]
        en += [f"{sentence['text_en']} {refs}", ""]
        ledger.append(f"| {sentence['sentence_id']} | {', '.join(sentence['supporting_record_ids'])} | {', '.join(sentence['citation_keys'])} |")
    zh += ["## 局限", output.get("limitations_zh", "")]
    en += ["## Limitations", output.get("limitations_en", "")]
    return {"writing_outline_bilingual.md": "\n".join(outline) + "\n", "method_comparison_draft_zh.md": "\n".join(zh) + "\n", "method_comparison_draft_en.md": "\n".join(en) + "\n", "sentence_evidence_ledger.md": "\n".join(ledger) + "\n"}


def _citation_suffix(record_ids: list[str], by_id: dict[str, dict[str, Any]]) -> str:
    refs = []
    for record_id in record_ids:
        record = by_id[record_id]
        citation = record["citations"][0]
        refs.append(f"[@{record['citation_key']}, pp. {citation['page_start']}–{citation['page_end']}]")
    return " ".join(dict.fromkeys(refs))


def _sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def _write_json(path: Path, value: Any) -> None: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
