from __future__ import annotations

import argparse
from pathlib import Path

from litflow.context import clean_reading_contexts
from litflow.context.quality_gate import audit_clean_contexts
from litflow.discovery.paper_search_pro_adapter import build_candidate_pool, write_candidate_pool
from litflow.discovery.paper_search_pro_inspector import (
    format_inspection_report,
    inspect_paper_search_pro_results,
)
from litflow.obsidian.writer import write_obsidian_notes
from litflow.obsidian.checker import check_obsidian_notes
from litflow.obsidian.reconcile import plan_citekey_note_migration
from litflow.obsidian.update_preview import preview_obsidian_update
from litflow.obsidian.apply_update import apply_obsidian_update
from litflow.llm.client import LLMError
from litflow.llm.evidence_bank_note import generate_note_from_evidence_bank
from litflow.llm.evidence_candidates import build_evidence_candidate_bank
from litflow.llm.structured_reader import read_paper_with_llm
from litflow.reading_context import build_reading_contexts
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
            )
            print(f"Wrote structured reading note: {args.out}")
            print(f"Evidence links: {len(note.evidence_links)}")
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
    except (ValueError, ZoteroReadError, LLMError) as exc:
        parser.exit(1, f"error: {exc}\n")

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
