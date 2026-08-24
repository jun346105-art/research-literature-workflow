from __future__ import annotations

from litflow.rag.mixed_smoke import MixedBM25Index, detect_language, mixed_tokenize, rrf_merge, route_query


def test_language_detection_and_tokenization_are_deterministic():
    assert detect_language("中文工程视觉论文")["source_language"] == "zh"
    assert detect_language("English engineering paper")["source_language"] == "en"
    assert detect_language("中文 YOLOv11-Pose")["source_language"] == "mixed"
    tokens = mixed_tokenize("混合2D/3D与YOLOv11-Pose的检测", "zh")
    assert "2d/3d" in tokens and "yolov11-pose" in tokens
    assert mixed_tokenize("Alpha-Beta 42", "en") == ["alpha", "beta", "42"]


def test_language_branch_routing_and_rrf_keep_original_passage_ids():
    passages = [
        {"passage_id": "ZH:1", "source_language": "zh", "text": "猪肉胴体肋排关键点识别 YOLOv11-Pose"},
        {"passage_id": "EN:1", "source_language": "en", "text": "Merge-YOLO detects book packaging defects"},
    ]
    index = MixedBM25Index(passages)
    route = route_query({"query_language": "zh", "query_text": "书籍包装缺陷检测", "translated_query": "book packaging defects"})
    assert route == [("zh", "书籍包装缺陷检测"), ("en", "book packaging defects")]
    zh = index.search_branch("肋排关键点", "zh")
    en = index.search_branch("book packaging", "en")
    merged = rrf_merge([zh, en], rrf_k=60, top_k=10)
    assert [item["passage_id"] for item in merged] == ["EN:1", "ZH:1"]
    assert all(item["passage_id"] in {"ZH:1", "EN:1"} for item in merged)


def test_chinese_branch_includes_mixed_source_passages():
    index = MixedBM25Index([{"passage_id": "MIXED:1", "source_language": "mixed", "text": "中文关键点识别 YOLOv11-Pose"}])
    assert index.search_branch("关键点识别", "zh")[0]["passage_id"] == "MIXED:1"
