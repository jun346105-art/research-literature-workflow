"""Deterministic JSON Schema export for DeepResearch domain contracts."""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import ContractBundle


SCHEMA_FILENAME = "research_contract_bundle.schema.json"


def render_contract_bundle_schema() -> str:
    """Render the primary schema with stable key ordering and formatting."""
    schema = ContractBundle.model_json_schema()
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_contract_schemas(output_dir: Path) -> dict[str, Path]:
    """Write deterministic schema files to a caller-controlled directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / SCHEMA_FILENAME
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_contract_bundle_schema())
    return {SCHEMA_FILENAME: target}
