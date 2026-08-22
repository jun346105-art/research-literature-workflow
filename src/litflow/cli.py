from __future__ import annotations

import argparse
import json
from pathlib import Path

from litflow.context import clean_reading_contexts
from litflow.context.quality_gate import audit_clean_contexts
from litflow.discovery.paper_search_pro_adapter import build_candidate_pool, write_candidate_pool
from litflow.discovery.paper_search_pro_inspector import (
    format_inspection_report,
    inspect_paper_search_pro_results,
)
from litflow.evaluation import compare_evidence_notes, write_eval_run_manifest
from litflow.evaluation_aggregate import aggregate_evaluation_pilot
from litflow.anchoring_audit import audit_anchoring_failures
from litflow.anchoring_replay import replay_anchoring_recovery
from litflow.evaluation_runner import ContextWindowConfig, EvaluationRunner, PricingConfig
from litflow.obsidian.writer import write_obsidian_notes
from litflow.obsidian.checker import check_obsidian_notes
from litflow.obsidian.reconcile import plan_citekey_note_migration
from litflow.obsidian.update_preview import preview_obsidian_update
from litflow.obsidian.apply_update import apply_obsidian_update
from litflow.llm.client import LLMError, OpenAICompatibleClient
from litflow.llm.evidence_bank_note import generate_note_from_evidence_bank
from litflow.llm.evidence_candidates import build_evidence_candidate_bank
from litflow.llm.deep_reading import extract_deep_reading_objects, plan_deep_reading, replay_deep_reading_response
from litflow.llm.structured_reader import read_paper_with_llm
from litflow.obsidian.deep_reading_preview import preview_deep_reading_objects
from litflow.reading_context import build_reading_contexts
from litflow.rag.bm25 import BM25Index, build_corpus, evaluate_bm25, load_corpus
from litflow.rag.dense import MODEL_NAME, MODEL_REVISION, build_dense_cache, evaluate_retriever
from litflow.rag.qrels import freeze_human_reviewed_qrels, import_ai_assisted_qrels
from litflow.rag.windowed import build_windowed_dense_cache, evaluate_windowed
from litflow.selection.export import export_zotero_import
from litflow.selection.selector import write_selection_template
from litflow.zotero.client import ZoteroReadError
from litflow.zotero.collection_reader import write_collection_snapshot
from litflow.zotero.diagnostics import write_citekey_diagnostics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="litflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build-candidate-pool")
    build.add_argument("--input", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)

    inspect = subparsers.add_parser("inspect-psp-results")
    inspect.add_argument("--input", required=True, type=Path)

    select = subparsers.add_parser("select-candidates")
    select.add_argument("--candidates", required=True, type=Path)
    select.add_argument("--out", required=True, type=Path)

    export = subparsers.add_parser("export-zotero-import")
    export.add_argument("--selected", required=True, type=Path)
    export.add_argument("--format", required=True, choices=["bib", "ris"])
    export.add_argument("--out", required=True, type=Path)

    read_zotero = subparsers.add_parser("read-zotero-collection")
    read_zotero.add_argument("--collection", required=True)
    read_zotero.add_argument("--output", required=True, type=Path)

    make_notes = subparsers.add_parser("make-obsidian-notes")
    make_notes.add_argument("--items", required=True, type=Path)
    make_notes.add_argument("--vault", required=True, type=Path)
    make_notes.add_argument("--inbox", required=True)
    make_notes.add_argument("--overwrite", action="store_true")

    diagnose_keys = subparsers.add_parser("diagnose-zotero-citekeys")
    diagnose_keys.add_argument("--collection", required=True)
    diagnose_keys.add_argument("--output", required=True, type=Path)

    check_notes = subparsers.add_parser("check-obsidian-notes")
    check_notes.add_argument("--vault", required=True, type=Path)
    check_notes.add_argument("--inbox", required=True)
    check_notes.add_argument("--out", required=True, type=Path)

    plan_migration = subparsers.add_parser("plan-citekey-note-migration")
    plan_migration.add_argument("--items", required=True, type=Path)
    plan_migration.add_argument("--vault", required=True, type=Path)
    plan_migration.add_argument("--inbox", required=True)
    plan_migration.add_argument("--out", required=True, type=Path)

    reading_context = subparsers.add_parser("build-reading-context")
    reading_context.add_argument("--items", required=True, type=Path)
    reading_context.add_argument("--out-dir", required=True, type=Path)
    reading_context.add_argument("--manifest", required=True, type=Path)
    reading_context.add_argument("--max-pages", type=int)

    clean_context = subparsers.add_parser("clean-reading-context")
    clean_context.add_argument("--context-dir", required=True, type=Path)
    clean_context.add_argument("--manifest", required=True, type=Path)
    clean_context.add_argument("--out-dir", required=True, type=Path)
    clean_context.add_argument("--out-manifest", required=True, type=Path)
    clean_context.add_argument("--chunk-size", type=int, default=3500)
    clean_context.add_argument("--overlap", type=int, default=400)

    audit_context = subparsers.add_parser("audit-clean-context")
    audit_context.add_argument("--clean-dir", required=True, type=Path)
    audit_context.add_argument("--manifest", required=True, type=Path)
    audit_context.add_argument("--out", required=True, type=Path)

    llm_read = subparsers.add_parser("read-paper-with-llm")
    llm_read.add_argument("--clean-context", required=True, type=Path)
    llm_read.add_argument("--out", required=True, type=Path)
    llm_read.add_argument("--max-chunks", type=int)

    evidence_bank = subparsers.add_parser("build-evidence-candidate-bank")
    evidence_bank.add_argument("--clean-context", required=True, type=Path)
    evidence_bank.add_argument("--out", required=True, type=Path)
    evidence_bank.add_argument("--report", required=True, type=Path)

    bank_note = subparsers.add_parser("generate-note-from-evidence-bank")
    bank_note.add_argument("--candidate-bank", required=True, type=Path)
    bank_note.add_argument("--clean-context", required=True, type=Path)
    bank_note.add_argument("--out", required=True, type=Path)
    bank_note.add_argument("--zotero-key", required=True)
    bank_note.add_argument("--citation-key", required=True)
    bank_note.add_argument("--title", required=True)
    bank_note.add_argument("--research-context")
    bank_note.add_argument("--research-context-file", type=Path)

    deep_reading = subparsers.add_parser("extract-deep-reading-objects")
    deep_reading.add_argument("--candidate-bank", required=True, type=Path)
    deep_reading.add_argument("--clean-context", required=True, type=Path)
    deep_reading.add_argument("--out", required=True, type=Path)
    deep_reading.add_argument("--model", default="unconfigured")
    deep_reading.add_argument("--thinking-mode", choices=["enabled", "disabled"], default="disabled")
    deep_reading.add_argument("--context-limit-tokens", type=int, default=1_000_000)
    deep_reading.add_argument("--max-output-tokens", type=int, default=8192)
    deep_reading.add_argument("--context-safety-margin-tokens", type=int, default=16_384)
    deep_reading.add_argument("--resume", action="store_true")
    deep_mode = deep_reading.add_mutually_exclusive_group(required=True)
    deep_mode.add_argument("--plan-only", action="store_true")
    deep_mode.add_argument("--execute", action="store_true")

    deep_preview = subparsers.add_parser("preview-deep-reading-objects")
    deep_preview.add_argument("--sidecar", required=True, type=Path)
    deep_preview.add_argument("--out", required=True, type=Path)

    deep_replay = subparsers.add_parser("replay-deep-reading-response")
    deep_replay.add_argument("--raw-response", required=True, type=Path)
    deep_replay.add_argument("--expected-raw-sha256", required=True)
    deep_replay.add_argument("--candidate-bank", required=True, type=Path)
    deep_replay.add_argument("--clean-context", required=True, type=Path)
    deep_replay.add_argument("--out-dir", required=True, type=Path)

    rag_build = subparsers.add_parser("build-rag-corpus")
    rag_build.add_argument("--frozen-manifest", required=True, type=Path)
    rag_build.add_argument("--corpus", required=True, type=Path)
    rag_build.add_argument("--manifest", required=True, type=Path)

    rag_search = subparsers.add_parser("search-bm25")
    rag_search.add_argument("--corpus", required=True, type=Path)
    rag_search.add_argument("--query", required=True)
    rag_search.add_argument("--top-k", type=int, default=10)

    rag_evaluate = subparsers.add_parser("evaluate-bm25")
    rag_evaluate.add_argument("--corpus", required=True, type=Path)
    rag_evaluate.add_argument("--queries", required=True, type=Path)
    rag_evaluate.add_argument("--out-dir", required=True, type=Path)
    rag_evaluate.add_argument("--mode", required=True, choices=["en", "zh_raw"])

    dense_build = subparsers.add_parser("build-dense-cache")
    dense_build.add_argument("--corpus", required=True, type=Path)
    dense_build.add_argument("--cache-dir", required=True, type=Path)
    dense_build.add_argument("--model", default=MODEL_NAME)
    dense_build.add_argument("--revision", default=MODEL_REVISION)

    dense_evaluate = subparsers.add_parser("evaluate-dense-retriever")
    dense_evaluate.add_argument("--corpus", required=True, type=Path)
    dense_evaluate.add_argument("--queries", required=True, type=Path)
    dense_evaluate.add_argument("--cache-dir", required=True, type=Path)
    dense_evaluate.add_argument("--out-dir", required=True, type=Path)
    dense_evaluate.add_argument("--mode", required=True, choices=["dense_en", "dense_zh", "hybrid_zh", "hybrid_bilingual"])

    qrels_import = subparsers.add_parser("import-ai-assisted-qrels")
    qrels_import.add_argument("--source-csv", required=True, type=Path)
    qrels_import.add_argument("--original-queries", required=True, type=Path)
    qrels_import.add_argument("--out", required=True, type=Path)

    qrels_freeze = subparsers.add_parser("freeze-human-reviewed-qrels")
    qrels_freeze.add_argument("--pending-queries", required=True, type=Path)
    qrels_freeze.add_argument("--source-csv", required=True, type=Path)
    qrels_freeze.add_argument("--corpus", required=True, type=Path)
    qrels_freeze.add_argument("--out", required=True, type=Path)

    window_build = subparsers.add_parser("build-windowed-dense-cache")
    window_build.add_argument("--corpus", required=True, type=Path)
    window_build.add_argument("--cache-dir", required=True, type=Path)

    window_evaluate = subparsers.add_parser("evaluate-windowed-retriever")
    window_evaluate.add_argument("--corpus", required=True, type=Path)
    window_evaluate.add_argument("--queries", required=True, type=Path)
    window_evaluate.add_argument("--cache-dir", required=True, type=Path)
    window_evaluate.add_argument("--out-dir", required=True, type=Path)
    window_evaluate.add_argument("--mode", required=True, choices=["dense_zh_windowed", "hybrid_zh_windowed"])

    preview_update = subparsers.add_parser("preview-obsidian-update")
    preview_update.add_argument("--structured-note", required=True, type=Path)
    preview_update.add_argument("--vault", required=True, type=Path)
    preview_update.add_argument("--inbox", required=True)
    preview_update.add_argument("--out", required=True, type=Path)
    preview_update.add_argument("--manifest", required=True, type=Path)

    apply_update = subparsers.add_parser("apply-obsidian-update")
    apply_update.add_argument("--preview", required=True, type=Path)
    apply_update.add_argument("--target", required=True, type=Path)
    apply_update.add_argument("--manifest", required=True, type=Path)
    apply_update.add_argument("--approved", action="store_true")
    apply_update.add_argument("--dry-run", action="store_true")

    eval_manifest = subparsers.add_parser("write-eval-run-manifest")
    eval_manifest.add_argument("--out", required=True, type=Path)
    eval_manifest.add_argument("--run-id", required=True)
    eval_manifest.add_argument("--model", default="")
    eval_manifest.add_argument("--prompt-version", default="")
    eval_manifest.add_argument("--chunk-config", default="")
    eval_manifest.add_argument("--input-count", type=int, default=0)
    eval_manifest.add_argument("--success-count", type=int, default=0)
    eval_manifest.add_argument("--strict-evidence-failures", type=int, default=0)

    compare_notes = subparsers.add_parser("compare-evidence-notes")
    compare_notes.add_argument("--baseline", required=True, type=Path)
    compare_notes.add_argument("--proposed", required=True, type=Path)
    compare_notes.add_argument("--clean-context", required=True, type=Path)
    compare_notes.add_argument("--out", required=True, type=Path)

    evaluation_pilot = subparsers.add_parser("run-evaluation-pilot")
    evaluation_pilot.add_argument("--frozen-manifest", required=True, type=Path)
    evaluation_pilot.add_argument("--out-dir", required=True, type=Path)
    evaluation_pilot.add_argument("--research-context-file", required=True, type=Path)
    evaluation_pilot.add_argument("--model")
    evaluation_pilot.add_argument("--paper-key")
    evaluation_pilot.add_argument("--thinking-mode", choices=["enabled", "disabled"])
    evaluation_pilot.add_argument("--temperature", type=float, default=0)
    evaluation_pilot.add_argument("--allow-dirty", action="store_true")
    evaluation_pilot.add_argument("--resume", action="store_true")
    evaluation_pilot.add_argument("--max-calls", type=int)
    evaluation_pilot.add_argument("--context-limit-tokens", type=int)
    evaluation_pilot.add_argument("--max-output-tokens", type=int)
    evaluation_pilot.add_argument("--context-safety-margin-tokens", type=int, default=0)
    evaluation_pilot.add_argument("--input-price-per-million-tokens", type=float)
    evaluation_pilot.add_argument("--output-price-per-million-tokens", type=float)
    evaluation_mode = evaluation_pilot.add_mutually_exclusive_group()
    evaluation_mode.add_argument("--plan-only", action="store_true")
    evaluation_mode.add_argument("--execute", action="store_true")

    aggregate_pilot = subparsers.add_parser("aggregate-evaluation-pilot")
    aggregate_pilot.add_argument("--run-dir", required=True, type=Path, action="append")
    aggregate_pilot.add_argument("--out-dir", required=True, type=Path)
    aggregate_pilot.add_argument("--reviewed-csv-sha", required=True, action="append", metavar="PAPER_KEY=SHA256")
    aggregate_pilot.add_argument("--input-price-cny-per-million-tokens", type=float, default=1)
    aggregate_pilot.add_argument("--output-price-cny-per-million-tokens", type=float, default=2)

    anchoring_audit = subparsers.add_parser("audit-anchoring-failures")
    anchoring_audit.add_argument("--failure-inventory", required=True, type=Path)
    anchoring_audit.add_argument("--frozen-manifest", required=True, type=Path)
    anchoring_audit.add_argument("--run-dir", required=True, type=Path, action="append")
    anchoring_audit.add_argument("--out-dir", required=True, type=Path)

    anchoring_replay = subparsers.add_parser("replay-anchoring-recovery")
    anchoring_replay.add_argument("--audit-dir", required=True, type=Path)
    anchoring_replay.add_argument("--frozen-manifest", required=True, type=Path)
    anchoring_replay.add_argument("--run-dir", required=True, type=Path, action="append")
    anchoring_replay.add_argument("--out-dir", required=True, type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "build-candidate-pool":
            pool = build_candidate_pool(args.input)
            write_candidate_pool(pool, args.output)
            print(f"Wrote {len(pool.papers)} papers to {args.output}")
            print(f"Warnings: {len(pool.warnings)}")
            for warning in pool.warnings:
                print(f"- {warning}")
            return 0

        if args.command == "inspect-psp-results":
            result = inspect_paper_search_pro_results(args.input)
            print(format_inspection_report(result))
            return 0

        if args.command == "select-candidates":
            template = write_selection_template(args.candidates, args.out)
            print(f"Wrote {len(template['papers'])} candidates to {args.out}")
            print("Default selected count: 0")
            return 0

        if args.command == "export-zotero-import":
            count = export_zotero_import(args.selected, args.out, args.format)
            print(f"Wrote {count} selected papers to {args.out}")
            return 0

        if args.command == "read-zotero-collection":
            papers = write_collection_snapshot(args.collection, args.output)
            print(f"Wrote {len(papers)} Zotero items to {args.output}")
            return 0

        if args.command == "make-obsidian-notes":
            manifest = write_obsidian_notes(args.items, args.vault, args.inbox, overwrite=args.overwrite)
            print(f"Created notes: {manifest['metadata']['created_count']}")
            print(f"Skipped existing: {manifest['metadata']['skipped_existing_count']}")
            print(f"Failed: {manifest['metadata']['failed_count']}")
            print("Manifest: outputs\\obsidian_note_manifest.json")
            return 0

        if args.command == "diagnose-zotero-citekeys":
            report = write_citekey_diagnostics(args.collection, args.output)
            print(f"Diagnosed {report['metadata']['total_items']} Zotero items")
            print(f"Citation keys: {report['metadata']['citation_key_count']}")
            print(f"Missing citation keys: {report['metadata']['citation_key_missing_count']}")
            print(f"Output: {args.output}")
            return 0

        if args.command == "check-obsidian-notes":
            report = check_obsidian_notes(args.vault, args.inbox, args.out)
            print(f"Checked notes: {report['metadata']['note_count']}")
            print(f"Warnings: {report['metadata']['warning_count']}")
            print(f"Output: {args.out}")
            return 0

        if args.command == "plan-citekey-note-migration":
            report = plan_citekey_note_migration(args.items, args.vault, args.inbox, args.out)
            print(f"Items: {report['metadata']['items']}")
            print(f"Rename recommended: {report['metadata']['needs_rename_count']}")
            print(f"Conflicts: {report['metadata']['conflict_count']}")
            print(f"Output: {args.out}")
            return 0

        if args.command == "build-reading-context":
            manifest = build_reading_contexts(args.items, args.out_dir, args.manifest, max_pages=args.max_pages)
            print(f"Processed items: {manifest['metadata']['total_items']}")
            print(f"Success: {manifest['metadata']['success_count']}")
            print(f"Missing PDFs: {manifest['metadata']['missing_pdf_count']}")
            print(f"PDF extract failed: {manifest['metadata']['pdf_extract_failed_count']}")
            print(f"Annotation read failed: {manifest['metadata']['annotation_read_failed_count']}")
            print(f"Manifest: {args.manifest}")
            return 0

        if args.command == "clean-reading-context":
            manifest = clean_reading_contexts(
                args.context_dir,
                args.manifest,
                args.out_dir,
                args.out_manifest,
                chunk_size=args.chunk_size,
                overlap=args.overlap,
            )
            print(f"Processed items: {manifest['metadata']['total_items']}")
            print(f"Success: {manifest['metadata']['success_count']}")
            print(f"Failed: {manifest['metadata']['failed_count']}")
            print(f"Total chunks: {manifest['metadata']['total_chunks']}")
            print(f"Aligned annotations: {manifest['metadata']['total_aligned_annotations']}")
            print(f"Manifest: {args.out_manifest}")
            return 0

        if args.command == "audit-clean-context":
            report = audit_clean_contexts(args.clean_dir, args.manifest, args.out)
            print(f"Total items: {report['metadata']['total_items']}")
            print(f"Ready for LLM: {report['metadata']['ready_for_llm_count']}")
            print(f"Needs manual check: {report['metadata']['needs_manual_check_count']}")
            print(f"Failed: {report['metadata']['failed_count']}")
            print(f"Output: {args.out}")
            return 0

        if args.command == "read-paper-with-llm":
            note = read_paper_with_llm(args.clean_context, args.out, max_chunks=args.max_chunks)
            print(f"Wrote structured reading note: {args.out}")
            print(f"zotero_key: {note.zotero_key}")
            return 0

        if args.command == "build-evidence-candidate-bank":
            report = build_evidence_candidate_bank(args.clean_context, args.out, args.report)
            print(f"Chunks: {report['metadata']['chunk_count']}")
            print(f"Anchored candidates: {report['metadata']['anchored_count']}")
            print(f"Failed candidates: {report['metadata']['failed_count']}")
            print(f"Output: {args.out}")
            print(f"Report: {args.report}")
            return 0

        if args.command == "generate-note-from-evidence-bank":
            note = generate_note_from_evidence_bank(
                args.candidate_bank,
                args.clean_context,
                args.out,
                zotero_key=args.zotero_key,
                citation_key=args.citation_key,
                title=args.title,
                research_context=_research_context_arg(args),
            )
            print(f"Wrote structured reading note: {args.out}")
            print(f"Evidence links: {len(note.evidence_links)}")
            return 0

        if args.command == "extract-deep-reading-objects":
            if args.plan_only:
                print(json.dumps(plan_deep_reading(args.candidate_bank, args.clean_context, model=args.model, context_limit_tokens=args.context_limit_tokens, max_output_tokens=args.max_output_tokens, safety_margin_tokens=args.context_safety_margin_tokens), ensure_ascii=False, indent=2))
                return 0
            note = extract_deep_reading_objects(args.candidate_bank, args.clean_context, args.out, model=args.model, context_limit_tokens=args.context_limit_tokens, max_output_tokens=args.max_output_tokens, safety_margin_tokens=args.context_safety_margin_tokens, resume=args.resume, thinking_mode=args.thinking_mode)
            print(f"Wrote deep-reading objects: {args.out}")
            print(f"Method components: {len(note.method_components)}")
            return 0

        if args.command == "preview-deep-reading-objects":
            preview_deep_reading_objects(args.sidecar, args.out)
            print(f"Preview: {args.out}")
            return 0

        if args.command == "replay-deep-reading-response":
            sidecar = replay_deep_reading_response(args.raw_response, args.candidate_bank, args.clean_context, args.out_dir, expected_raw_sha256=args.expected_raw_sha256)
            print(f"Offline replay sidecar: {args.out_dir / 'deep_reading_objects.json'}")
            print(f"Method components: {len(sidecar.method_components)}")
            return 0

        if args.command == "build-rag-corpus":
            report = build_corpus(args.frozen_manifest, args.corpus, args.manifest)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        if args.command == "search-bm25":
            results = BM25Index(load_corpus(args.corpus)).search(args.query, top_k=args.top_k)
            print(json.dumps(results, ensure_ascii=False, indent=2))
            return 0

        if args.command == "evaluate-bm25":
            report = evaluate_bm25(args.corpus, args.queries, args.out_dir, mode=args.mode)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        if args.command == "build-dense-cache":
            print(json.dumps(build_dense_cache(args.corpus, args.cache_dir, model_name=args.model, revision=args.revision), ensure_ascii=False, indent=2))
            return 0

        if args.command == "evaluate-dense-retriever":
            print(json.dumps(evaluate_retriever(args.corpus, args.queries, args.out_dir, mode=args.mode, cache_dir=args.cache_dir), ensure_ascii=False, indent=2))
            return 0

        if args.command == "import-ai-assisted-qrels":
            queries = import_ai_assisted_qrels(args.source_csv, args.original_queries, args.out)
            print(f"Imported {len(queries)} AI-assisted qrels queries to {args.out}")
            return 0

        if args.command == "freeze-human-reviewed-qrels":
            manifest = freeze_human_reviewed_qrels(args.pending_queries, args.source_csv, args.corpus, args.out)
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0

        if args.command == "build-windowed-dense-cache":
            print(json.dumps(build_windowed_dense_cache(args.corpus, args.cache_dir), ensure_ascii=False, indent=2))
            return 0

        if args.command == "evaluate-windowed-retriever":
            print(json.dumps(evaluate_windowed(args.corpus, args.queries, args.cache_dir, args.out_dir, mode=args.mode), ensure_ascii=False, indent=2))
            return 0

        if args.command == "preview-obsidian-update":
            manifest = preview_obsidian_update(args.structured_note, args.vault, args.inbox, args.out, args.manifest)
            item = manifest["items"][0]
            print(f"Status: {item['status']}")
            print(f"Target note: {item['target_note_path']}")
            print(f"Preview: {item['preview_path']}")
            print(f"Manifest: {args.manifest}")
            return 0

        if args.command == "apply-obsidian-update":
            manifest = apply_obsidian_update(
                args.preview,
                args.target,
                args.manifest,
                approved=args.approved,
                dry_run=args.dry_run,
            )
            item = manifest["items"][0]
            print(f"Status: {item['status']}")
            print(f"Target note: {item['target_note_path']}")
            print(f"Backup: {item['backup_path']}")
            print(f"Manifest: {args.manifest}")
            return 0

        if args.command == "write-eval-run-manifest":
            manifest = write_eval_run_manifest(
                args.out,
                run_id=args.run_id,
                model=args.model,
                prompt_version=args.prompt_version,
                chunk_config=args.chunk_config,
                input_count=args.input_count,
                success_count=args.success_count,
                strict_evidence_failures=args.strict_evidence_failures,
            )
            print(f"Eval run: {manifest['run_id']}")
            print(f"Output: {args.out}")
            return 0

        if args.command == "compare-evidence-notes":
            report = compare_evidence_notes(args.baseline, args.proposed, args.clean_context, args.out)
            print(f"Baseline exact grounding rate: {report['baseline']['exact_grounding_rate']:.3f}")
            print(f"Proposed exact grounding rate: {report['proposed']['exact_grounding_rate']:.3f}")
            print(f"Output: {args.out}")
            return 0

        if args.command == "run-evaluation-pilot":
            if not args.plan_only and not args.execute:
                raise ValueError("provide exactly one of --plan-only or --execute")
            context_window = None
            if args.context_limit_tokens is not None or args.max_output_tokens is not None:
                if args.context_limit_tokens is None or args.max_output_tokens is None:
                    raise ValueError("context-limit-tokens and max-output-tokens must be provided together")
                context_window = ContextWindowConfig(
                    context_limit_tokens=args.context_limit_tokens,
                    max_output_tokens=args.max_output_tokens,
                    safety_margin_tokens=args.context_safety_margin_tokens,
                )
            pricing = None
            if args.input_price_per_million_tokens is not None or args.output_price_per_million_tokens is not None:
                if args.input_price_per_million_tokens is None or args.output_price_per_million_tokens is None:
                    raise ValueError("input-price-per-million-tokens and output-price-per-million-tokens must be provided together")
                pricing = PricingConfig(args.input_price_per_million_tokens, args.output_price_per_million_tokens)
            if args.execute:
                if context_window is None or args.max_calls is None:
                    raise ValueError("--execute requires --context-limit-tokens, --max-output-tokens, and --max-calls")
                client = OpenAICompatibleClient.from_env(thinking_mode=args.thinking_mode)
                if args.model and args.model != client.model:
                    raise ValueError("--model must match LLM_MODEL when --execute is used")
                resolved_model = client.model
            else:
                client = None
                resolved_model = args.model or "unconfigured"
            runner = EvaluationRunner(
                args.frozen_manifest,
                args.out_dir,
                args.research_context_file,
                model=resolved_model,
                temperature=args.temperature,
                client=client,
                allow_dirty=args.allow_dirty,
                resume=args.resume,
                context_window=context_window,
                max_calls=args.max_calls,
                pricing=pricing,
                paper_key=args.paper_key,
                thinking_mode=args.thinking_mode,
            )
            if args.execute:
                result = runner.execute()
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
            print(json.dumps(runner.plan(), ensure_ascii=False, indent=2))
            return 0

        if args.command == "aggregate-evaluation-pilot":
            expected_hashes = _parse_reviewed_csv_hashes(args.reviewed_csv_sha)
            command_args = ["python", "-m", "litflow.cli", "aggregate-evaluation-pilot"]
            for run_dir in args.run_dir:
                command_args.extend(["--run-dir", str(run_dir)])
            command_args.extend(["--out-dir", str(args.out_dir)])
            for value in args.reviewed_csv_sha:
                command_args.extend(["--reviewed-csv-sha", value])
            command_args.extend([
                "--input-price-cny-per-million-tokens", str(args.input_price_cny_per_million_tokens),
                "--output-price-cny-per-million-tokens", str(args.output_price_cny_per_million_tokens),
            ])
            report = aggregate_evaluation_pilot(
                args.run_dir,
                args.out_dir,
                expected_reviewed_sha256=expected_hashes,
                command_args=command_args,
                input_price_cny_per_million_tokens=args.input_price_cny_per_million_tokens,
                output_price_cny_per_million_tokens=args.output_price_cny_per_million_tokens,
            )
            print(json.dumps({"output": str(args.out_dir), "papers": report["micro_aggregate"]["paper_count"]}, ensure_ascii=False))
            return 0

        if args.command == "audit-anchoring-failures":
            report = audit_anchoring_failures(
                args.failure_inventory,
                args.frozen_manifest,
                args.run_dir,
                args.out_dir,
            )
            print(json.dumps({"output": str(args.out_dir), "failures": report["total_failures"]}, ensure_ascii=False))
            return 0

        if args.command == "replay-anchoring-recovery":
            report = replay_anchoring_recovery(args.audit_dir, args.frozen_manifest, args.run_dir, args.out_dir)
            print(json.dumps({"output": str(args.out_dir), "recovered": report["newly_recovered"]}, ensure_ascii=False))
            return 0
    except (ValueError, ZoteroReadError, LLMError) as exc:
        parser.exit(1, f"error: {exc}\n")

    parser.error(f"Unknown command: {args.command}")
    return 2


def _research_context_arg(args: argparse.Namespace) -> str | None:
    if args.research_context and args.research_context_file:
        raise ValueError("use either --research-context or --research-context-file, not both")
    if args.research_context_file:
        return args.research_context_file.read_text(encoding="utf-8-sig").strip()
    return args.research_context


def _parse_reviewed_csv_hashes(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        paper_key, separator, digest = value.partition("=")
        if not separator or not paper_key or len(digest) != 64 or any(character not in "0123456789abcdefABCDEF" for character in digest):
            raise ValueError("--reviewed-csv-sha must use PAPER_KEY=64-character-SHA256")
        if paper_key in result:
            raise ValueError(f"duplicate --reviewed-csv-sha key: {paper_key}")
        result[paper_key] = digest.lower()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
