from __future__ import annotations

import json


def build_structured_reading_prompt(llm_input: dict) -> str:
    schema_hint = {
        "zotero_key": "",
        "citation_key": "",
        "title": "",
        "reading_status": "llm_draft",
        "one_sentence_summary": "",
        "research_background": "",
        "research_gap": "",
        "core_contribution": "",
        "method_summary": "",
        "data_or_experiment": "",
        "model_or_algorithm": "",
        "objective_or_task": "",
        "key_results": "",
        "limitations": "",
        "relevance_to_my_research": "",
        "usable_quotes_or_evidence": [],
        "related_concepts": [],
        "tags_suggestion": [],
        "evidence_links": [
            {"claim": "", "chunk_id": "", "page_start": 1, "page_end": 1, "evidence_text": ""}
        ],
        "warnings": [],
    }
    return (
        "You are reading one academic paper from provided chunks only.\n"
        "Do not use external knowledge. Do not invent missing information.\n"
        "If information is not found, use \"not_found\" or an empty string/list.\n"
        "Return valid JSON only, matching this schema:\n"
        f"{json.dumps(schema_hint, ensure_ascii=False, indent=2)}\n\n"
        "Evidence rules:\n"
        "- Every important claim should include evidence_links when possible.\n"
        "- evidence_links must cite the exact chunk_id, page_start, page_end of the chunk that contains evidence_text.\n"
        "- Treat evidence_text as a quote_hint: a short phrase close to the original source span.\n"
        "- The program will extract final exact evidence_text from the cited chunk; do not rely on memory.\n"
        "- Keep quote_hint short, contiguous, and preferably under 200 characters.\n"
        "- quote_hint should be specific enough to locate one unique span in the cited chunk.\n"
        "- Do not use quote_hint that crosses pages, chunks, page headers, footers, tables, or figure captions.\n"
        "- If you cannot identify the supporting chunk and quote_hint, omit that evidence_link instead of guessing.\n"
        "- Do not invent page numbers.\n"
        "- section_guess is weak context and may be wrong.\n\n"
        "Provided clean context:\n"
        f"{json.dumps(llm_input, ensure_ascii=False)}"
    )
