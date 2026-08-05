import json

from litflow.cli import main
from litflow.evaluation import compare_evidence_notes, write_eval_run_manifest


def test_write_eval_run_manifest_records_run_metadata(tmp_path):
    out = tmp_path / "manifest.json"

    manifest = write_eval_run_manifest(
        out,
        run_id="run-001",
        model="test-model",
        prompt_version="p1",
        chunk_config="3500/400",
        input_count=2,
        success_count=1,
        strict_evidence_failures=3,
    )

    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved == manifest
    assert saved["run_id"] == "run-001"
    assert saved["model"] == "test-model"
    assert saved["metrics"]["strict_evidence_failures"] == 3


def test_compare_evidence_notes_reports_baseline_and_proposed_grounding(tmp_path):
    clean = tmp_path / "clean.json"
    baseline = tmp_path / "baseline.json"
    proposed = tmp_path / "proposed.json"
    out = tmp_path / "comparison.json"
    clean.write_text(
        json.dumps(
            {
                "chunks": [
                    {
                        "chunk_id": "P1_chunk_0001",
                        "page_start": 1,
                        "page_end": 1,
                        "text": "exact source evidence",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    baseline.write_text(json.dumps(_note("rewritten evidence")), encoding="utf-8")
    proposed.write_text(json.dumps(_note("exact source evidence")), encoding="utf-8")

    report = compare_evidence_notes(baseline, proposed, clean, out)

    assert report["baseline"]["exact_grounding_rate"] == 0
    assert report["baseline"]["failure_count"] == 1
    assert report["proposed"]["exact_grounding_rate"] == 1
    assert report["proposed"]["failure_count"] == 0
    assert json.loads(out.read_text(encoding="utf-8")) == report


def test_eval_manifest_cli_writes_manifest(tmp_path):
    out = tmp_path / "manifest.json"

    code = main(
        [
            "write-eval-run-manifest",
            "--out",
            str(out),
            "--run-id",
            "run-001",
            "--input-count",
            "2",
            "--success-count",
            "1",
            "--strict-evidence-failures",
            "3",
        ]
    )

    assert code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["metrics"]["input_count"] == 2


def test_compare_evidence_notes_cli_writes_report(tmp_path):
    clean = tmp_path / "clean.json"
    baseline = tmp_path / "baseline.json"
    proposed = tmp_path / "proposed.json"
    out = tmp_path / "comparison.json"
    clean.write_text(json.dumps({"chunks": [{"chunk_id": "P1_chunk_0001", "page_start": 1, "page_end": 1, "text": "exact"}]}), encoding="utf-8")
    baseline.write_text(json.dumps(_note("wrong")), encoding="utf-8")
    proposed.write_text(json.dumps(_note("exact")), encoding="utf-8")

    code = main(
        [
            "compare-evidence-notes",
            "--baseline",
            str(baseline),
            "--proposed",
            str(proposed),
            "--clean-context",
            str(clean),
            "--out",
            str(out),
        ]
    )

    assert code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["proposed"]["failure_count"] == 0


def _note(evidence_text):
    return {
        "evidence_links": [
            {
                "claim": "claim",
                "chunk_id": "P1_chunk_0001",
                "page_start": 1,
                "page_end": 1,
                "evidence_text": evidence_text,
            }
        ]
    }
