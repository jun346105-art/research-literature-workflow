from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
HEADINGS = [
    ("Why LitFlow", "为什么使用 LitFlow"),
    ("A verifiable example", "一个可核验示例"),
    ("Five-minute Quickstart", "五分钟 Quickstart"),
    ("How it works", "工作流程"),
    ("Evaluation highlights", "评测亮点"),
    ("Engineering capabilities", "工程能力"),
    ("Privacy and reproducibility by design", "隐私与可复现性融入设计"),
    ("Documentation", "文档入口"),
    ("License status", "许可状态"),
]


def test_bilingual_readmes_keep_product_sections_and_language_switch():
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    assert english.startswith("# LitFlow Research Copilot\n\n[English](README.md) | [简体中文](README.zh-CN.md)")
    assert chinese.startswith("# LitFlow Research Copilot\n\n[English](README.md) | [简体中文](README.zh-CN.md)")
    assert re.findall(r"^## (.+)$", english, re.MULTILINE) == [en for en, _ in HEADINGS]
    assert re.findall(r"^## (.+)$", chinese, re.MULTILINE) == [zh for _, zh in HEADINGS]


def test_readme_images_and_relative_links_exist():
    for name in ("README.md", "README.zh-CN.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        for target in re.findall(r"!\[[^]]*\]\(([^)]+)\)|\[[^]]+\]\(([^)]+)\)", text):
            link = next(item for item in target if item)
            if link.startswith(("http://", "https://", "#")):
                continue
            path, _, anchor = link.partition("#")
            target_path = ROOT / path
            assert target_path.exists(), f"broken link in {name}: {link}"
            if anchor:
                headings = re.findall(r"^#{1,6} (.+)$", target_path.read_text(encoding="utf-8"), re.MULTILINE)
                anchors = [re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-") for heading in headings]
                assert anchor in anchors, f"broken anchor in {name}: {link}"


def test_readme_uses_conservative_claims_and_frozen_metrics():
    for name in ("README.md", "README.zh-CN.md"):
        text = (ROOT / name).read_text(encoding="utf-8").casefold()
        assert "state-of-the-art" not in text
        assert "production-ready" not in text
        assert "solves hallucination" not in text
        assert "better than deepseek" not in text
        assert "fully autonomous scientist" not in text
        assert "zhipuai_api_key" not in text
        assert "c:\\users\\" not in text and "d:\\论文" not in text
    result = json.loads((ROOT / "docs/deep_research/retrieval_quality_r1/results/r1_result.json").read_text(encoding="utf-8"))
    held_out = result["held_out"]
    for name in ("README.md", "README.zh-CN.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert f'{held_out["metrics"]["recall_at_10"]:.1%}' in text
        assert f'{held_out["metrics"]["ndcg_at_10"]:.1%}' in text
        assert f'{held_out["answerable_success_at_10"]:.0%}' in text
        assert str(result["split_policy"]["development_query_count"]) in text
        assert str(result["split_policy"]["held_out_query_count"]) in text
        assert "docs/evaluation/README.md" in text and "docs/providers/README.md" in text
        assert "View the full evaluation methodology and failure analysis" in text
        assert "POST /api/" not in text and "GLM-5.3-Flash" not in text
        assert "docs/DEEPRESEARCH_DEMO.md#local-demo-assets" in text
    evaluation = (ROOT / "docs/evaluation/README.md").read_text(encoding="utf-8")
    assert "No-answer false-positive rate@10 | 1.000000 | 1.000000" in evaluation
    assert "3 of 15" in evaluation and "not an independently validated" in evaluation
