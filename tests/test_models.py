from litflow.models import CandidatePaper, CandidatePool


def test_candidate_pool_dedupes_by_doi():
    pool = CandidatePool.deduped(
        [
            CandidatePaper(title="A", doi="10.1/ABC"),
            CandidatePaper(title="A duplicate", doi="10.1/abc"),
        ]
    )

    assert len(pool.papers) == 1


def test_candidate_pool_dedupes_by_normalized_title_without_doi():
    pool = CandidatePool.deduped(
        [
            CandidatePaper(title="  A Useful Paper "),
            CandidatePaper(title="a useful   paper"),
        ]
    )

    assert len(pool.papers) == 1


def test_candidate_paper_requires_known_bucket():
    try:
        CandidatePaper(title="A", recommended_bucket="made_up")
    except ValueError as exc:
        assert "Invalid recommended_bucket" in str(exc)
    else:
        raise AssertionError("expected invalid bucket to fail")


def test_candidate_paper_serializes_phase_1a_fields():
    data = CandidatePaper(
        title="A",
        citation_count=12,
        relevance_score=0.8,
        tier="A",
        search_query="rgbd defect detection",
        recommended_bucket="uncertain",
    ).to_dict()

    assert data["citation_count"] == 12
    assert data["relevance_score"] == 0.8
    assert data["tier"] == "A"
    assert data["search_query"] == "rgbd defect detection"
    assert data["recommended_bucket"] == "uncertain"
