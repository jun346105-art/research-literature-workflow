import json

from litflow.cli import main
from litflow.discovery.paper_search_pro_adapter import build_candidate_pool, write_candidate_pool


def test_build_candidate_pool_reads_papers_json_directory(tmp_path):
    (tmp_path / "papers.json").write_text(
        json.dumps(
            {
                "papers": [
                    {
                        "title": "Paper One",
                        "authors": ["Alice", "Bob"],
                        "publication_year": "2024",
                        "doi": "10.123/test",
                        "journal": "Journal",
                    },
                    {"title": "Paper One", "doi": "10.123/TEST"},
                    {"abstract": "missing title"},
                ]
            }
        ),
        encoding="utf-8",
    )

    pool = build_candidate_pool(tmp_path)

    assert len(pool.papers) == 1
    assert pool.papers[0].title == "Paper One"
    assert pool.papers[0].authors == ["Alice", "Bob"]
    assert pool.papers[0].year == 2024
    assert pool.papers[0].venue == "Journal"
    assert any("duplicate paper removed" in warning for warning in pool.warnings)
    assert any("missing title" in warning for warning in pool.warnings)


def test_write_candidate_pool_creates_json(tmp_path):
    (tmp_path / "papers.json").write_text('[{"title":"Paper"}]', encoding="utf-8")
    pool = build_candidate_pool(tmp_path / "papers.json")
    output = tmp_path / "out" / "candidate_pool.json"

    write_candidate_pool(pool, output)

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert data["paper_count"] == 1
    assert "warnings" in data


def test_build_candidate_pool_reads_papers_csv(tmp_path):
    (tmp_path / "papers.csv").write_text(
        "\n".join(
            [
                "Title,Authors,Year,Venue,DOI,URL,Abstract,citations,score,database,query,bucket",
                "CSV Paper,Alice and Bob,2025,Conf,10.1/csv,https://example.com,Abstract,42,0.91,OpenAlex,rgbd,frontier_recent",
            ]
        ),
        encoding="utf-8",
    )

    pool = build_candidate_pool(tmp_path)
    paper = pool.papers[0]

    assert paper.title == "CSV Paper"
    assert paper.authors == ["Alice", "Bob"]
    assert paper.year == 2025
    assert paper.venue == "Conf"
    assert paper.citation_count == 42
    assert paper.relevance_score == 0.91
    assert paper.source == "OpenAlex"
    assert paper.search_query == "rgbd"
    assert paper.recommended_bucket == "frontier_recent"


def test_build_candidate_pool_prefers_json_over_csv(tmp_path):
    (tmp_path / "papers.json").write_text('[{"title":"JSON Paper"}]', encoding="utf-8")
    (tmp_path / "papers.csv").write_text("Title\nCSV Paper\n", encoding="utf-8")

    pool = build_candidate_pool(tmp_path)

    assert pool.papers[0].title == "JSON Paper"


def test_build_candidate_pool_records_missing_field_warnings(tmp_path):
    (tmp_path / "papers.json").write_text('[{"title":"Sparse Paper"}]', encoding="utf-8")

    pool = build_candidate_pool(tmp_path)

    assert any("missing DOI" in warning for warning in pool.warnings)
    assert any("missing abstract" in warning for warning in pool.warnings)
    assert any("missing citation_count" in warning for warning in pool.warnings)


def test_build_candidate_pool_records_malformed_record_warning(tmp_path):
    (tmp_path / "papers.json").write_text(json.dumps([{"title": "Good"}, "bad"]), encoding="utf-8")

    pool = build_candidate_pool(tmp_path)

    assert len(pool.papers) == 1
    assert any("malformed record skipped" in warning for warning in pool.warnings)


def test_cli_prints_candidate_pool_stats(tmp_path, capsys):
    input_path = tmp_path / "papers.json"
    output_path = tmp_path / "candidate_pool.json"
    input_path.write_text('[{"title":"Paper"}]', encoding="utf-8")

    code = main(["build-candidate-pool", "--input", str(input_path), "--output", str(output_path)])

    captured = capsys.readouterr()
    assert code == 0
    assert "Wrote 1 papers" in captured.out
    assert "Warnings: 3" in captured.out
