import csv
import hashlib
import json
import re
from pathlib import Path

import pytest

from litflow.cli import main
from litflow.evaluation_runner import FrozenInputError, EvaluationRunner


class StageAwareFakeLLM:
    def __init__(self):
        self.calls = []

    def complete_json(self, prompt):
        self.calls.append(prompt)
        zotero_key = re.search(r'"zotero_key":\s*"([^"]+)"', prompt)
        key = zotero_key.group(1) if zotero_key else "P1"
        if "raw-baseline-multichunk-v1" in prompt:
            return json.dumps(
                {
                    "zotero_key": key,
                    "title": f"Title {key}",
                    "evidence_links": [
                        {
                            "claim": "raw claim",
                            "chunk_id": "missing_chunk",
                            "page_start": 1,
                            "page_end": 1,
                            "evidence_text": "rewritten evidence",
                        }
                    ],
                }
            )
        if "You extract evidence candidates from one paper chunk only." in prompt:
            match = re.search(r'"text":\s*"([^"]+)"', prompt)
            evidence = match.group(1) if match else "exact source evidence"
            return json.dumps(
                {
                    "candidates": [
                        {"claim": "candidate one", "quote_hint": evidence, "evidence_type": "method"},
                        {"claim": "candidate two", "quote_hint": evidence, "evidence_type": "result"},
                    ]
                }
            )
        if "Use only this evidence candidate bank" in prompt:
            candidate_ids = re.findall(r'"candidate_id":\s*"([^"]+)"', prompt)
            return json.dumps(
                {
                    "one_sentence_summary": "summary",
                    "evidence_selections": [
                        {"claim": f"selected {index}", "candidate_id": candidate_id}
                        for index, candidate_id in enumerate(candidate_ids[:3], 1)
                    ],
                }
            )
        raise AssertionError("unexpected prompt")


def test_plan_only_uses_manifest_counts_and_never_calls_llm(tmp_path):
    manifest, research_context = _frozen_inputs(tmp_path)
    client = StageAwareFakeLLM()

    report = EvaluationRunner(manifest, tmp_path / "run", research_context, model="fake", temperature=0, client=client).plan()

    assert report["paper_count"] == 3
    assert [item["chunk_count"] for item in report["papers"]] == [2, 2, 2]
    assert report["estimated_calls"] == {
        "baseline_initial": 3,
        "proposed_candidate": 6,
        "proposed_final_note": 3,
        "minimum_total": 12,
        "maximum_with_one_baseline_retry": 15,
    }
    assert client.calls == []
    assert all(item["baseline_prompt_char_count"] > 0 for item in report["papers"])
    assert all(item["proposed_candidate_prompt_char_count"] > 0 for item in report["papers"])


def test_hash_mismatch_fails_before_any_llm_call(tmp_path):
    manifest, research_context = _frozen_inputs(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["papers"][0]["clean_context_sha256"] = "0" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    client = StageAwareFakeLLM()

    with pytest.raises(FrozenInputError, match="clean context SHA-256 mismatch"):
        EvaluationRunner(manifest, tmp_path / "run", research_context, model="fake", temperature=0, client=client).plan()

    assert client.calls == []


def test_pdf_hash_mismatch_fails_before_any_llm_call(tmp_path):
    manifest, research_context = _frozen_inputs(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["papers"][0]["pdf_sha256"] = "0" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    client = StageAwareFakeLLM()

    with pytest.raises(FrozenInputError, match="PDF SHA-256 mismatch"):
        EvaluationRunner(manifest, tmp_path / "run", research_context, model="fake", temperature=0, client=client).plan()

    assert client.calls == []


def test_execute_keeps_raw_baseline_evidence_and_writes_metrics_and_manual_csv(tmp_path):
    manifest, research_context = _frozen_inputs(tmp_path)
    run_dir = tmp_path / "run"
    result = EvaluationRunner(
        manifest,
        run_dir,
        research_context,
        model="fake-model",
        temperature=0,
        client=StageAwareFakeLLM(),
    ).execute()

    raw_note = json.loads((run_dir / "papers" / "P1" / "baseline" / "raw_note.json").read_text(encoding="utf-8"))
    assert raw_note["evidence_links"][0]["chunk_id"] == "missing_chunk"
    assert raw_note["evidence_links"][0]["evidence_text"] == "rewritten evidence"
    assert result["aggregate"]["baseline"]["exact_grounding_failure_count"] == 3
    assert result["aggregate"]["proposed"]["exact_grounding_pass_count"] == 9

    records = json.loads((run_dir / "call_metrics.json").read_text(encoding="utf-8"))
    assert {record["stage"] for record in records} == {
        "baseline_raw",
        "proposed_candidate_chunk",
        "proposed_final_note",
    }
    assert all(record["input_tokens"] is None for record in records)
    assert all(record["estimated_cost"] is None for record in records)
    assert len(records) == 12
    assert all(record["chunk_id"] for record in records if record["stage"] == "proposed_candidate_chunk")
    assert all(record["attempt"] == 1 for record in records if record["stage"] == "proposed_candidate_chunk")
    assert all(record["raw_response_artifact"] for record in records)
    assert all((run_dir / record["raw_response_artifact"]).is_file() for record in records)

    run_manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert "git_commit_sha" in run_manifest
    assert "git_worktree_status" in run_manifest

    with (run_dir / "manual_claim_evidence_review.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert all(row[field] == "" for row in rows for field in ("support_label", "needs_revision", "acceptance", "reviewer_notes"))


def test_baseline_format_retry_preserves_both_responses_without_evidence_repair(tmp_path):
    manifest, research_context = _frozen_inputs(tmp_path)
    run_dir = tmp_path / "run"

    EvaluationRunner(manifest, run_dir, research_context, model="fake", temperature=0, client=RetryFirstBaselineFake()).execute()

    baseline_dir = run_dir / "papers" / "P1" / "baseline"
    assert (baseline_dir / "raw_response_attempt_1.txt").read_text(encoding="utf-8") == "not json"
    assert json.loads((baseline_dir / "raw_note.json").read_text(encoding="utf-8"))["evidence_links"][0]["chunk_id"] == "missing_chunk"
    metrics = json.loads((baseline_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["initial_success"] is False
    assert metrics["retry_count"] == 1
    assert metrics["final_success"] is True


def test_candidate_anchor_rate_uses_only_returned_candidates_and_failures(tmp_path):
    manifest, research_context = _frozen_inputs(tmp_path, chunk_count=4)
    run_dir = tmp_path / "run"

    EvaluationRunner(manifest, run_dir, research_context, model="fake", temperature=0, client=PartialCandidateFake()).execute()

    metrics = json.loads((run_dir / "papers" / "P1" / "proposed" / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["anchored_candidate_count"] == 4
    assert metrics["failed_anchor_count"] == 4
    assert metrics["candidate_anchor_rate"] == 0.5
    assert metrics["chunk_evidence_coverage_rate"] == 1


def test_cli_rejects_execute_and_plan_only_without_constructing_real_client(tmp_path, capsys):
    manifest, research_context = _frozen_inputs(tmp_path)

    code = main(["run-evaluation-pilot", "--frozen-manifest", str(manifest), "--out-dir", str(tmp_path / "run"), "--research-context-file", str(research_context), "--execute"])

    assert code == 1
    assert "real LLM execution not configured in this phase" in capsys.readouterr().out


def test_cli_plan_only_validates_without_llm_client_or_environment(tmp_path, capsys, monkeypatch):
    manifest, research_context = _frozen_inputs(tmp_path)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    code = main(
        [
            "run-evaluation-pilot",
            "--frozen-manifest",
            str(manifest),
            "--out-dir",
            str(tmp_path / "run"),
            "--research-context-file",
            str(research_context),
            "--plan-only",
        ]
    )

    assert code == 0
    assert '"minimum_total": 12' in capsys.readouterr().out


def test_manifest_with_non_frozen_extra_paper_is_rejected(tmp_path):
    manifest, research_context = _frozen_inputs(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["papers"].append(payload["papers"][0])
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(FrozenInputError, match="exactly three papers"):
        EvaluationRunner(manifest, tmp_path / "run", research_context, model="fake", temperature=0).plan()


def test_fully_invalid_baseline_saves_error_artifact_without_a_success_note(tmp_path):
    manifest, research_context = _frozen_inputs(tmp_path)
    run_dir = tmp_path / "run"

    EvaluationRunner(manifest, run_dir, research_context, model="fake", temperature=0, client=AlwaysInvalidBaselineFake()).execute()

    baseline_dir = run_dir / "papers" / "P1" / "baseline"
    assert (baseline_dir / "raw_response_attempt_1.txt").exists()
    assert (baseline_dir / "raw_response_attempt_2.txt").exists()
    assert not (baseline_dir / "raw_note.json").exists()
    assert json.loads((baseline_dir / "metrics.json").read_text(encoding="utf-8"))["final_success"] is False


class RetryFirstBaselineFake(StageAwareFakeLLM):
    def __init__(self):
        super().__init__()
        self._failed_once = False

    def complete_json(self, prompt):
        if "raw-baseline-multichunk-v1" in prompt and not self._failed_once:
            self._failed_once = True
            self.calls.append(prompt)
            return "not json"
        return super().complete_json(prompt)


class PartialCandidateFake(StageAwareFakeLLM):
    def complete_json(self, prompt):
        if "You extract evidence candidates from one paper chunk only." in prompt:
            self.calls.append(prompt)
            match = re.search(r'"text":\s*"([^"]+)"', prompt)
            evidence = match.group(1) if match else "exact source evidence"
            return json.dumps(
                {
                    "candidates": [
                        {"claim": "anchored", "quote_hint": evidence, "evidence_type": "method"},
                        {"claim": "missing", "quote_hint": "not in chunk", "evidence_type": "result"},
                    ]
                }
            )
        return super().complete_json(prompt)


class AlwaysInvalidBaselineFake(StageAwareFakeLLM):
    def complete_json(self, prompt):
        if "raw-baseline-multichunk-v1" in prompt:
            self.calls.append(prompt)
            return "not json"
        return super().complete_json(prompt)


def _frozen_inputs(tmp_path: Path, chunk_count: int = 2) -> tuple[Path, Path]:
    papers = []
    for index, key in enumerate(("P1", "P2", "P3"), 1):
        pdf = tmp_path / f"{key}.pdf"
        pdf.write_bytes(f"pdf-{key}".encode())
        clean = tmp_path / f"{key}.json"
        clean.write_text(
            json.dumps(
                {
                    "metadata": {"zotero_key": key, "citation_key": f"cite{index}", "title": f"Title {key}", "pdf_attachment_path": str(pdf)},
                    "chunks": [
                        {"chunk_id": f"{key}_chunk_{chunk_index}", "page_start": chunk_index, "page_end": chunk_index, "section_guess": "method", "text": f"exact source evidence {key} {chunk_index}"}
                        for chunk_index in range(1, chunk_count + 1)
                    ],
                }
            ),
            encoding="utf-8",
        )
        papers.append(
            {
                "zotero_key": key,
                "citation_key": f"cite{index}",
                "title": f"Title {key}",
                "source_clean_context_path": str(clean),
                "clean_context_sha256": _sha256(clean),
                "pdf_path": str(pdf),
                "pdf_sha256": _sha256(pdf),
                "quality_status": "ready_for_llm",
            }
        )
    manifest = tmp_path / "frozen.json"
    manifest.write_text(json.dumps({"metadata": {"role": "development_pilot"}, "papers": papers}), encoding="utf-8")
    research_context = tmp_path / "research_context.txt"
    research_context.write_text("same research context", encoding="utf-8")
    return manifest, research_context


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
