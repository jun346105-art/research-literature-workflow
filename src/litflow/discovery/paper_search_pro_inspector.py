from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

EXPECTED_FILES = (
    "papers.json",
    "papers.csv",
    "papers.bib",
    "papers.ris",
    "report.md",
    "report.html",
)


@dataclass(frozen=True)
class PaperSearchProInspection:
    input_path: Path
    exists: bool
    is_dir: bool
    present_files: list[str]
    missing_files: list[str]

    @property
    def readable_by_litflow(self) -> list[str]:
        return [name for name in ("papers.json", "papers.csv") if name in self.present_files]

    @property
    def preferred_input(self) -> str | None:
        if "papers.json" in self.present_files:
            return "papers.json"
        if "papers.csv" in self.present_files:
            return "papers.csv"
        return None

    @property
    def can_build_candidate_pool(self) -> bool:
        return self.preferred_input is not None


def inspect_paper_search_pro_results(input_path: Path) -> PaperSearchProInspection:
    exists = input_path.exists()
    is_dir = input_path.is_dir()
    present: list[str] = []
    if is_dir:
        present = [name for name in EXPECTED_FILES if (input_path / name).exists()]
    return PaperSearchProInspection(
        input_path=input_path,
        exists=exists,
        is_dir=is_dir,
        present_files=present,
        missing_files=[name for name in EXPECTED_FILES if name not in present],
    )


def format_inspection_report(result: PaperSearchProInspection) -> str:
    lines = [
        f"Input: {result.input_path}",
        f"Directory exists: {result.exists and result.is_dir}",
        "Expected files:",
    ]
    for name in EXPECTED_FILES:
        marker = "OK" if name in result.present_files else "MISSING"
        lines.append(f"- {marker}: {name}")

    if result.preferred_input == "papers.json":
        lines.append("Litflow readable: papers.json, papers.csv")
        lines.append("Preferred input: papers.json")
    elif result.preferred_input == "papers.csv":
        lines.append("Litflow readable: papers.csv")
        lines.append("Preferred input: papers.csv")
    else:
        lines.append("WARNING: no papers.json or papers.csv found; build-candidate-pool cannot read this directory yet.")

    lines.append(
        f'Next step: python -m litflow.cli build-candidate-pool --input "{result.input_path}" --output "./outputs/candidate_pool.json"'
    )
    return "\n".join(lines)
