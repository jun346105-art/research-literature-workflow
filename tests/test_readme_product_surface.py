from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
HEADINGS = [
    "Overview", "Demo", "Why LitFlow", "Key Features", "Architecture",
    "How It Works", "Evaluation", "Provider Compatibility",
    "Five-Minute Offline Quickstart", "API", "Project Structure",
    "Reproducibility and Safety", "Known Limitations", "Documentation",
    "Roadmap", "License",
]


def test_bilingual_readmes_keep_product_sections_and_language_switch():
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    assert english.startswith("# LitFlow Research Copilot\n\n[English](README.md) | [简体中文](README.zh-CN.md)")
    assert chinese.startswith("# LitFlow Research Copilot\n\n[English](README.md) | [简体中文](README.zh-CN.md)")
    for heading in HEADINGS:
        assert f"## " in english and heading.casefold() in english.casefold()
    assert "## 16. License" in chinese


def test_readme_images_and_relative_links_exist():
    for name in ("README.md", "README.zh-CN.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        for target in re.findall(r"!\[[^]]*\]\(([^)]+)\)|\[[^]]+\]\(([^)]+)\)", text):
            link = next(item for item in target if item)
            if link.startswith(("http://", "https://", "#")):
                continue
            assert (ROOT / link).exists(), f"broken link in {name}: {link}"


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
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "0.840278" in english and "1.000000 → 0.800000" in english
