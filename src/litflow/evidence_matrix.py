from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


class EvidenceMatrixError(ValueError):
    pass


def build_evidence_matrix(results_path: Path, review_path: Path, corpus_path: Path, queries_path: Path, output_dir: Path, *, input_identity: dict[str, Any]) -> dict[str, Any]:
    if output_dir.exists():
        raise EvidenceMatrixError("matrix output directory must not already exist")
    results = _load_json(results_path)
    review = _load_json(review_path).get("valid_answer_reviews", {})
    corpus = {item["passage_id"]: item for item in _load_jsonl(corpus_path)}
    queries = {item["query_id"]: item for item in _load_json(queries_path).get("queries", [])}
    records = []
    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_candidates = []
    for result in results:
        query_id = result.get("query_id")
        decision = review.get(query_id, {}).get("author_decision")
        if result.get("execution_status") != "success" or result.get("final_answer_status") not in {"answered", "partial_answer"} or decision not in {"pass", "pass_with_minor_revision"}:
            continue
        limitations = _limitations(result)
        for index, claim in enumerate(result.get("claims", []), 1):
            claim_text = review[query_id].get("human_reviewed_correction") if decision == "pass_with_minor_revision" else claim.get("claim_text_zh")
            if not claim_text:
                raise EvidenceMatrixError(f"missing reviewed claim text: {query_id}")
            citations = [_validated_citation(citation, claim.get("subject_paper_key"), corpus) for citation in claim.get("citations", [])]
            if not citations:
                raise EvidenceMatrixError(f"claim has no citations: {query_id}")
            paper = corpus[citations[0]["passage_id"]]
            record = {
                "evidence_record_id": _record_id(paper["paper_key"], claim_text),
                "paper_key": paper["paper_key"],
                "citation_key": paper.get("citation_key"),
                "title": paper.get("title"),
                "year": paper.get("year"),
                "source_language": paper.get("source_language", "en"),
                "evidence_category": _category(queries.get(query_id, {}).get("query_type")),
                "claim_text": claim_text,
                "claim_language": "zh",
                "original_model_claim": claim.get("claim_text_zh"),
                "human_reviewed_correction": review[query_id].get("human_reviewed_correction") if decision == "pass_with_minor_revision" else None,
                "review_decision": decision,
                "source_query_ids": [query_id],
                "citations": citations,
                "coverage_status": result.get("coverage_status") or "complete",
                "limitations": limitations,
                "created_from": "human_reviewed_qa_claim",
            }
            key = (record["paper_key"], _normalize(record["claim_text"]))
            if key in dedup:
                dedup[key]["source_query_ids"] = sorted(set(dedup[key]["source_query_ids"] + [query_id]))
                dedup[key]["citations"] = _unique_citations([*dedup[key]["citations"], *citations])
            else:
                if any(item["paper_key"] == record["paper_key"] and _normalize(item["claim_text"]) != key[1] and _normalize(item["claim_text"]) in _normalize(record["claim_text"]) for item in records):
                    duplicate_candidates.append(record["evidence_record_id"])
                dedup[key] = record
                records.append(record)
    records = sorted(dedup.values(), key=lambda item: item["evidence_record_id"])
    output_dir.mkdir(parents=True)
    _write_jsonl(output_dir / "evidence_records.jsonl", records)
    matrix = _comparison_matrix(records)
    _write_json(output_dir / "evidence_matrix.json", matrix)
    (output_dir / "evidence_matrix_claim_ledger.md").write_text(_claim_ledger(records), encoding="utf-8")
    (output_dir / "evidence_matrix_paper_comparison.md").write_text(_comparison_markdown(matrix), encoding="utf-8")
    (output_dir / "evidence_matrix_review_packet_zh.md").write_text(_review_packet(records, matrix), encoding="utf-8")
    manifest = {"role": "evidence_matrix_vertical_slice", "input_identity": input_identity, "record_count": len(records), "paper_count": len(matrix["papers"]), "category_counts": dict(Counter(item["evidence_category"] for item in records)), "review_counts": dict(Counter(item["review_decision"] for item in records)), "coverage_counts": dict(Counter(item["coverage_status"] for item in records)), "duplicate_candidates": duplicate_candidates, "citation_quote_revalidation": "passed", "output_files": {path.name: _sha(path) for path in output_dir.iterdir() if path.is_file()}}
    _write_json(output_dir / "evidence_matrix_manifest.json", manifest)
    return {"record_count": len(records), "paper_count": len(matrix["papers"]), "duplicate_candidates": duplicate_candidates}


def _validated_citation(citation: dict[str, Any], subject_paper_key: str | None, corpus: dict[str, dict[str, Any]]) -> dict[str, Any]:
    passage = corpus.get(citation.get("passage_id"))
    if passage is None:
        raise EvidenceMatrixError("citation passage missing from frozen corpus")
    quote = citation.get("evidence_quote") or ""
    if quote not in passage["text"]:
        raise EvidenceMatrixError("citation quote not grounded in frozen corpus")
    if subject_paper_key and passage["paper_key"] != subject_paper_key:
        raise EvidenceMatrixError("citation paper does not match subject paper")
    if citation.get("page_start") != passage["page_start"] or citation.get("page_end") != passage["page_end"]:
        raise EvidenceMatrixError("citation page provenance mismatch")
    return {"passage_id": passage["passage_id"], "page_start": passage["page_start"], "page_end": passage["page_end"], "evidence_quote": quote, "quote_language": passage.get("source_language", "en"), "anchor_status": citation.get("anchor_status"), "text_sha256": passage["text_sha256"]}


def _limitations(result: dict[str, Any]) -> list[str]:
    if result.get("coverage_status") != "partial":
        return []
    return [f"当前证据未覆盖：{item['entity_name']}" for item in result.get("coverage_ledger", {}).get("uncovered_entities", [])]


def _category(query_type: str | None) -> str:
    return {"method": "method", "experiment": "result", "background_limitation": "limitation", "cross_paper": "other"}.get(query_type or "", "other")


def _comparison_matrix(records: list[dict[str, Any]]) -> dict[str, Any]:
    fields = ["research_problem", "method", "component_or_step", "dataset_or_sample", "experimental_setup", "metric_result", "baseline_or_comparison", "ablation", "limitation"]
    papers = {}
    for record in records:
        paper = papers.setdefault(record["paper_key"], {"paper_key": record["paper_key"], "citation_key": record["citation_key"], "title": record["title"], "year": record["year"], "fields": {field: [] for field in fields}, "evidence_count": 0, "review_status": []})
        field = {"research_problem": "research_problem", "method": "method", "component_or_step": "component_or_step", "dataset_or_sample": "dataset_or_sample", "experimental_setup": "experimental_setup", "metric": "metric_result", "result": "metric_result", "baseline_or_comparison": "baseline_or_comparison", "ablation": "ablation", "limitation": "limitation"}.get(record["evidence_category"], "method")
        paper["fields"][field].append({"record_id": record["evidence_record_id"], "claim_text": record["claim_text"]})
        paper["evidence_count"] += 1
        paper["review_status"].append(record["review_decision"])
    for paper in papers.values(): paper["review_status"] = sorted(set(paper["review_status"]))
    return {"fields": fields, "papers": sorted(papers.values(), key=lambda item: item["paper_key"])}


def _claim_ledger(records: list[dict[str, Any]]) -> str:
    lines = ["# Evidence Matrix Claim Ledger", "", "| Record | Paper | Category | Claim | Query | Passage/Page | Review | Coverage |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for record in records:
        citation = record["citations"][0]
        lines.append(f"| {record['evidence_record_id']} | {record['citation_key']} | {record['evidence_category']} | {record['claim_text']} | {', '.join(record['source_query_ids'])} | {citation['passage_id']} pp.{citation['page_start']}-{citation['page_end']} | {record['review_decision']} | {record['coverage_status']} |")
    return "\n".join(lines) + "\n"


def _comparison_markdown(matrix: dict[str, Any]) -> str:
    lines = ["# Evidence Matrix Paper Comparison", "", "| Paper | Research Problem | Method | Component/Step | Dataset/Sample | Experimental Setup | Metric/Result | Baseline/Comparison | Ablation | Limitation | Evidence Count | Review Status |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- |"]
    for paper in matrix["papers"]:
        cells = []
        for field in matrix["fields"]:
            items = paper["fields"][field]
            cells.append("<br>".join(f"{item['record_id']}: {item['claim_text']}" for item in items) if items else "— / 尚无已审核证据")
        lines.append("| " + " | ".join([paper["citation_key"], *cells, str(paper["evidence_count"]), ", ".join(paper["review_status"])]) + " |")
    return "\n".join(lines) + "\n"


def _review_packet(records: list[dict[str, Any]], matrix: dict[str, Any]) -> str:
    lines = ["# Evidence Matrix Review Packet", ""]
    for record in records:
        lines += [f"## {record['evidence_record_id']}", f"- Matrix row: `{record['paper_key']}`", f"- Claim: {record['claim_text']}", f"- Original model claim: {record['original_model_claim']}", f"- Human correction: {record['human_reviewed_correction'] or '—'}", f"- Review decision: `{record['review_decision']}`", f"- Coverage: `{record['coverage_status']}`", f"- Limitations: {', '.join(record['limitations']) or '—'}"]
        for citation in record["citations"]:
            lines += [f"- Citation: `{citation['passage_id']}` pp.{citation['page_start']}-{citation['page_end']}", "```text", citation["evidence_quote"], "```"]
        lines += ["- Future review: accept / pass_with_minor_revision / reject", "- author_notes: ", ""]
    return "\n".join(lines) + "\n"


def _record_id(paper_key: str, claim_text: str) -> str:
    return f"ev_{paper_key}_{hashlib.sha256(_normalize(claim_text).encode('utf-8')).hexdigest()[:12]}"


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _unique_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set(); output = []
    for citation in citations:
        key = (citation["passage_id"], citation["evidence_quote"])
        if key not in seen: seen.add(key); output.append(citation)
    return output


def _load_json(path: Path) -> Any: return json.loads(path.read_text(encoding="utf-8-sig"))
def _load_jsonl(path: Path) -> list[dict[str, Any]]: return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line]
def _write_json(path: Path, value: Any) -> None: path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def _write_jsonl(path: Path, values: list[dict[str, Any]]) -> None: path.write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values), encoding="utf-8")
def _sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
