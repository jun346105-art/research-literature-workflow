from litflow.cli import main
from litflow.discovery.paper_search_pro_inspector import (
    format_inspection_report,
    inspect_paper_search_pro_results,
)


def test_inspect_psp_results_prefers_papers_json(tmp_path):
    (tmp_path / "papers.json").write_text("[]", encoding="utf-8")
    (tmp_path / "papers.csv").write_text("title\nA\n", encoding="utf-8")

    result = inspect_paper_search_pro_results(tmp_path)

    assert result.exists is True
    assert result.is_dir is True
    assert result.readable_by_litflow == ["papers.json", "papers.csv"]
    assert result.preferred_input == "papers.json"
    assert result.can_build_candidate_pool is True


def test_inspect_psp_results_accepts_only_papers_csv(tmp_path):
    (tmp_path / "papers.csv").write_text("title\nA\n", encoding="utf-8")

    result = inspect_paper_search_pro_results(tmp_path)
    report = format_inspection_report(result)

    assert result.readable_by_litflow == ["papers.csv"]
    assert result.preferred_input == "papers.csv"
    assert "Preferred input: papers.csv" in report


def test_inspect_psp_results_warns_without_readable_files(tmp_path):
    (tmp_path / "report.md").write_text("# Report\n", encoding="utf-8")

    result = inspect_paper_search_pro_results(tmp_path)
    report = format_inspection_report(result)

    assert result.readable_by_litflow == []
    assert result.preferred_input is None
    assert result.can_build_candidate_pool is False
    assert "WARNING: no papers.json or papers.csv found" in report


def test_inspect_psp_results_cli_prints_next_step(tmp_path, capsys):
    (tmp_path / "papers.json").write_text("[]", encoding="utf-8")

    code = main(["inspect-psp-results", "--input", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 0
    assert "Preferred input: papers.json" in captured.out
    assert "build-candidate-pool" in captured.out

