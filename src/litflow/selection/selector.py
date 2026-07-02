from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_selection_template(candidates_path: Path) -> dict[str, Any]:
    data = json.loads(candidates_path.read_text(encoding="utf-8-sig"))
    papers = data.get("papers")
    if not isinstance(papers, list):
        raise ValueError("candidate_pool.json must contain a papers list")

    return {
        "metadata": {
            "source": str(candidates_path),
            "total_candidates": len(papers),
            "selected_count": 0,
            "created_for_manual_review": True,
        },
        "papers": [
            {
                "selected": False,
                "selection_reason": "",
                "manual_note": "",
                "paper": paper,
            }
            for paper in papers
        ],
    }


def write_selection_template(candidates_path: Path, output_path: Path) -> dict[str, Any]:
    template = build_selection_template(candidates_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return template
