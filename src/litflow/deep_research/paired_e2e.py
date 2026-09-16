"""Immutable, offline-only contract for the paired single-paper comparison."""
from __future__ import annotations

import json
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .identity import canonical_json_bytes, make_stable_id, sha256_hex


_OUTPUT_ROOT = "out" + "puts"


class PairedSinglePaperPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["dr-paired-single-paper-e2e-v1"] = "dr-paired-single-paper-e2e-v1"
    provider: Literal["zhipu-bigmodel", "deepseek"]
    model_id: Literal["glm-5.3-flash", "deepseek-flash"]
    endpoint: str
    credential_environment_variable: Literal["ZHIPUAI_API_KEY", "DEEPSEEK_API_KEY"]
    channel: Literal["ordinary_model_api"] = "ordinary_model_api"
    text_only: Literal[True] = True
    thinking: Literal["enabled"] = "enabled"
    planner_reasoning_effort: Literal["low"] = "low"
    writer_reasoning_effort: Literal["high"] = "high"
    planner_max_input_tokens: Literal[2048] = 2048
    writer_max_input_tokens: Literal[4096] = 4096
    planner_max_output_tokens: Literal[4096] = 4096
    writer_max_output_tokens: Literal[4096] = 4096
    max_provider_calls: Literal[2] = 2
    max_provider_attempts: Literal[2] = 2
    max_retries: Literal[0] = 0
    max_replans: Literal[1] = 1
    operation_timeout_seconds: Literal[60] = 60
    run_timeout_seconds: Literal[180] = 180
    fallback_enabled: Literal[False] = False
    tools_enabled: Literal[False] = False
    web_enabled: Literal[False] = False
    vision_enabled: Literal[False] = False
    files_enabled: Literal[False] = False
    parallel_enabled: Literal[False] = False
    monetary_budget_currency: Literal["CNY", "USD"]
    input_price_per_million: Decimal
    cache_hit_input_price_per_million: Decimal
    output_price_per_million: Decimal
    monetary_budget_limit_micros: Decimal
    task_id: str = Field(pattern=r"^dr-task-[0-9a-f]{24}$")
    brief_id: str = Field(pattern=r"^dr-brief-[0-9a-f]{24}$")
    attempt_id: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]*$")
    run_id: str = Field(pattern=r"^dr-run-[0-9a-f]{24}$")
    artifact_dir: str = Field(pattern=rf"^{_OUTPUT_ROOT}/deep_research/e2e/v1\.2/dr-run-[0-9a-f]{{24}}$")
    implementation_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    runtime_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    corpus_path: str = Field(pattern=rf"^{_OUTPUT_ROOT}/rag_bm25_v1/[a-z0-9_.-]+$")
    corpus_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    planner_prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    writer_prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acceptance_metrics: list[Literal["terminal_status", "grounding", "claims_citations", "replay_zero_calls", "tokens", "provider_native_cost", "client_elapsed", "author_review_required"]]

    @model_validator(mode="after")
    def validate_identity(self) -> "PairedSinglePaperPlan":
        expected_provider = {"zhipu-bigmodel": ("glm-5.3-flash", "https://open.bigmodel.cn/api/paas/v4/chat/completions", "ZHIPUAI_API_KEY"), "deepseek": ("deepseek-flash", "https://api.deepseek.com/chat/completions", "DEEPSEEK_API_KEY")}[self.provider]
        if (self.model_id, self.endpoint, self.credential_environment_variable) != expected_provider:
            raise ValueError("paired provider identity mismatch")
        expected = make_stable_id("run", {"runtime": "dr-single-agent-e2e-v1", "task_id": self.task_id, "brief_id": self.brief_id, "attempt_id": self.attempt_id})
        if self.run_id != expected:
            raise ValueError("paired run identity mismatch")
        expected_prices = {"zhipu-bigmodel": ("CNY", Decimal("0.4"), Decimal("0"), Decimal("1.4")), "deepseek": ("USD", Decimal("0.30"), Decimal("0.006"), Decimal("1.20"))}[self.provider]
        if (self.monetary_budget_currency, self.input_price_per_million, self.cache_hit_input_price_per_million, self.output_price_per_million) != expected_prices or self.monetary_budget_limit_micros != Decimal("20000"):
            raise ValueError("paired native pricing contract mismatch")
        if len(set(self.acceptance_metrics)) != 8:
            raise ValueError("paired plan must freeze all acceptance metrics once")
        return self


def render_paired_plan_schema() -> str:
    schema = PairedSinglePaperPlan.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_paired_plan_schema(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "paired_single_paper_plan.schema.json"
    path.write_text(render_paired_plan_schema(), encoding="utf-8", newline="\n")
    return path


def paired_runtime_source_sha256() -> str:
    root = Path(__file__).resolve().parents[3]
    names = ("src/litflow/deep_research/e2e.py", "src/litflow/deep_research/e2e_cli.py", "src/litflow/deep_research/paired_cli.py", "src/litflow/deep_research/deepseek_e2e.py", "src/litflow/deep_research/paired_e2e.py", "src/litflow/deep_research/gap_replan.py", "src/litflow/deep_research/executor.py", "src/litflow/deep_research/writer.py", "src/litflow/deep_research/runtime_v2.py")
    return sha256_hex(canonical_json_bytes({name: sha256_hex((root / name).read_bytes()) for name in names}))


def parse_paired_plan(data: dict[str, object]) -> PairedSinglePaperPlan:
    return PairedSinglePaperPlan.model_validate(data)


def preflight_paired_plan(plan: PairedSinglePaperPlan, *, repo_root: Path) -> None:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, capture_output=True, text=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo_root, check=True, capture_output=True, text=True).stdout.strip()
    if status:
        raise ValueError("paired E2E worktree must be clean")
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", plan.implementation_commit_sha, head], cwd=repo_root, check=False)
    if ancestor.returncode != 0 or plan.runtime_source_sha256 != paired_runtime_source_sha256():
        raise ValueError("paired implementation binding mismatch")
    corpus = repo_root / plan.corpus_path
    if not corpus.is_file() or sha256_hex(corpus.read_bytes()) != plan.corpus_sha256:
        raise ValueError("paired corpus identity mismatch")
    if plan.artifact_dir and (repo_root / plan.artifact_dir).exists():
        raise ValueError("paired artifact directory must not already exist")


__all__ = ["PairedSinglePaperPlan", "paired_runtime_source_sha256", "parse_paired_plan", "preflight_paired_plan", "render_paired_plan_schema", "write_paired_plan_schema"]
