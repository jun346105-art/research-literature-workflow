from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
from decimal import Decimal
from datetime import UTC, datetime
from pathlib import Path

import pytest

from litflow.deep_research.budgets import BudgetLedger, BudgetSpec, TokenUsage
from litflow.deep_research.contracts import BriefApproval, BriefApprovalStatus, ResearchBrief, ResearchTask
from litflow.deep_research.e2e import (
    DeepResearchRunner,
    E2EConfigurationError,
    E2ETerminalError,
    GLMAdapterError,
    GLME2EPilotPlan,
    GLME2ESinglePaperAttemptPlan,
    GLME2ESinglePaperAttemptTask,
    GLMInvocationPolicy,
    GLMSingleWriter,
    GLMStructuredAdapter,
    GLMStructuredPlanner,
    GLMStructuredReply,
    parse_e2e_pilot_plan,
    preflight_e2e_pilot,
    prompt_hashes,
    runtime_source_sha256,
    write_e2e_pilot_schema,
    write_e2e_pilot_attempt_schema,
    write_e2e_single_paper_schema,
)
from litflow.deep_research.executor import LocalResearchExecutor, ReadOnlyToolRegistry
from litflow.deep_research.gap_replan import AssessmentContext, assess_evidence_graph
from litflow.deep_research.planner import FakePlanner, PlannerDraft, PlannerError, PlannerSubtaskDraft, plan_approved_brief
from litflow.deep_research.operations import OperationKind
from litflow.deep_research.runtime_v2 import UnifiedEventStore, read_coordinated_checkpoint, reduce_runtime_events, replay_runtime_events
from litflow.deep_research.state import RunState
from litflow.deep_research.writer import ReportStatus, SingleWriterRunner
from litflow.deep_research.writer import WriterError
from litflow.deep_research.writer_calibration import WriterCalibrationPlan, build_writer_calibration_fixture, calibration_run_id, preflight_writer_calibration


NOW = datetime(2026, 9, 8, tzinfo=UTC)


class FakeStructuredClient:
    def __init__(self, responses: list[object]):
        self.responses, self.calls = responses, 0

    async def complete(self, *, prompt: str, operation_name: str) -> GLMStructuredReply:
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        assert isinstance(response, dict)
        return GLMStructuredReply(content=json.dumps(response), usage=TokenUsage(), model_identity_verified=True, usage_reported=True, request_id_present=True)


class RawStructuredClient:
    def __init__(self, content: str, *, finish_reason: str | None = None, usage: TokenUsage | None = None):
        self.content, self.finish_reason, self.usage = content, finish_reason, usage or TokenUsage()
        self.calls = 0

    async def complete(self, *, prompt: str, operation_name: str) -> GLMStructuredReply:
        self.calls += 1
        return GLMStructuredReply(content=self.content, usage=self.usage, model_identity_verified=True, usage_reported=True, request_id_present=False, finish_reason=self.finish_reason)


def _inputs():
    task = ResearchTask.create("Which local evidence supports alpha?", "en", ("local-only",), "grounded_report", NOW)
    brief = ResearchBrief.create(task.task_id, "Find local alpha evidence.", ("alpha",), (), "report", ("quote",), ("local-only",), BriefApprovalStatus.approved)
    approval = BriefApproval.create(brief.brief_id, task.task_id, BriefApprovalStatus.approved, "human", NOW)
    return task, brief, approval


def _corpus():
    text = "Alpha evidence is preserved in this local passage."
    return [{"passage_id": "P1:P1_chunk_0001", "paper_key": "P1", "citation_key": "cite", "title": "Paper", "chunk_id": "P1_chunk_0001", "page_start": 1, "page_end": 1, "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "source_context_sha256": "a" * 64}]


def _planner_response(task, brief):
    return PlannerDraft(task_id=task.task_id, brief_id=brief.brief_id, locale=task.locale, constraints=brief.constraints, scope_inclusions=brief.scope_inclusions, scope_exclusions=brief.scope_exclusions, subtasks=(PlannerSubtaskDraft(local_key="find", question="alpha evidence", rationale="find", expected_evidence=("quote",), completion_criteria=("one",)),)).model_dump(mode="json")


def _runner(planner, writer):
    spec = BudgetSpec(max_provider_calls=2, max_provider_attempts=2, max_tool_calls=8, max_tool_attempts=8, max_retries=0, max_replans=1, run_timeout_s=90, operation_timeout_s=30)
    registry = ReadOnlyToolRegistry(_corpus())
    return DeepResearchRunner(planner, LocalResearchExecutor(registry, budget=spec), writer, budget=spec), registry, spec


def test_formal_runner_composes_injected_adapters_through_one_stream_and_resume(tmp_path: Path):
    task, brief, approval = _inputs()
    planner_client = FakeStructuredClient([_planner_response(task, brief)])
    planner = GLMStructuredPlanner(planner_client)
    writer_client = FakeStructuredClient([])
    writer = GLMSingleWriter(writer_client)
    spec = BudgetSpec(max_provider_calls=2, max_provider_attempts=2, max_tool_calls=8, max_tool_attempts=8, max_retries=0, max_replans=1, run_timeout_s=90, operation_timeout_s=30)
    registry = ReadOnlyToolRegistry(_corpus())
    executor = LocalResearchExecutor(registry, budget=spec)
    runner = DeepResearchRunner(planner, executor, writer, budget=spec)

    writer_calls = []

    async def writer_response(**kwargs):
        writer_calls.append(True)
        graph = kwargs["graph"]
        unit = graph.evidence_units[0]
        return {"schema_version": "dr-report-draft-v1", "task_id": task.task_id, "brief_id": brief.brief_id, "plan_id": graph.plan_id, "run_id": graph.run_id, "sections": [{"heading": "Findings", "claims": [{"text": "Alpha is supported.", "language": "en", "citations": [{"evidence_id": unit.evidence_id, "quote": unit.verbatim_content, "relation": "support"}]}]}]}

    writer.create_draft = writer_response  # type: ignore[method-assign]
    result = asyncio.run(runner.run(task, brief, approval, event_path=tmp_path / "runtime.jsonl", checkpoint_path=tmp_path / "checkpoint.json"))
    assert result.terminal == "complete" and result.validation and result.validation.status is ReportStatus.complete
    assert planner_client.calls == 1 and writer_client.calls == 0 and len(writer_calls) == 1
    assert all((tmp_path / name).is_file() for name in ("validated_plan.json", "evidence_graph.json", "assessment.json"))
    assert all((tmp_path / name).is_file() for name in ("validated_plan.json", "evidence_graph.json", "assessment.json"))
    events = UnifiedEventStore(tmp_path / "runtime.jsonl", run_id=result.run_id).read_all()
    initial = RunState(run_id=result.run_id, task_id=task.task_id, brief_id=brief.brief_id, brief_approved=True)
    full = replay_runtime_events(initial, events, spec)
    assert full == replay_runtime_events(initial, events, spec, checkpoint=read_coordinated_checkpoint(tmp_path / "checkpoint.json"))
    assert reduce_runtime_events(initial, events, spec).ledger.provider_calls == 2
    replay = asyncio.run(runner.run(task, brief, approval, event_path=tmp_path / "runtime.jsonl", checkpoint_path=tmp_path / "checkpoint.json"))
    assert replay.resumed and planner_client.calls == 1 and writer_client.calls == 0 and len(writer_calls) == 1 and len(registry.calls) == 2


def test_glm_adapters_apply_json_application_contracts_without_formal_ids():
    task, brief, _ = _inputs()
    planner = GLMStructuredPlanner(FakeStructuredClient([_planner_response(task, brief)]))
    draft = asyncio.run(planner.create_draft(task=task, brief=brief))
    assert draft["subtasks"][0].get("subtask_id") is None
    writer = GLMSingleWriter(FakeStructuredClient([{ "schema_version": "dr-report-draft-v1", "task_id": task.task_id, "brief_id": brief.brief_id, "plan_id": "dr-plan-" + "a" * 24, "run_id": "dr-run-" + "b" * 24, "sections": [{"heading": "Findings", "claims": []}], "harmless_metadata": "ignored" }]))
    raw = asyncio.run(writer.create_draft(graph=type("Graph", (), {"model_dump": lambda _self, **_kwargs: {}})(), assessment=type("Assessment", (), {"model_dump": lambda _self, **_kwargs: {}})()))
    assert "harmless_metadata" not in raw
    assert not (set(raw) & {"schema_version", "task_id", "brief_id", "plan_id", "run_id"})


def test_glm_planner_ignores_harmless_metadata_but_rejects_formal_identity():
    task, brief, _ = _inputs()
    response = _planner_response(task, brief)
    response["harmless_metadata"] = "ignored"
    draft = asyncio.run(GLMStructuredPlanner(FakeStructuredClient([response])).create_draft(task=task, brief=brief))
    assert "harmless_metadata" not in draft
    forbidden = _planner_response(task, brief)
    forbidden["plan_id"] = "dr-plan-" + "f" * 24
    with pytest.raises(PlannerError, match="program-controlled"):
        asyncio.run(GLMStructuredPlanner(FakeStructuredClient([forbidden])).create_draft(task=task, brief=brief))


def test_adapter_error_is_classified_and_never_silently_falls_back():
    task, brief, _ = _inputs()
    client = FakeStructuredClient([GLMAdapterError("outcome_unknown", outcome_unknown=True)])
    with pytest.raises(Exception, match="outcome_unknown"):
        asyncio.run(GLMStructuredPlanner(client).create_draft(task=task, brief=brief))
    assert client.calls == 1


def test_planner_unknown_is_durable_exit_class_three_and_never_calls_writer_or_retries(tmp_path: Path):
    task, brief, approval = _inputs()
    planner_client = FakeStructuredClient([GLMAdapterError("outcome_unknown", outcome_unknown=True, diagnostics={"failure_stage": "transport", "contract_error_code": "outcome_unknown", "http_status": None, "response_received": False, "response_json_parsed": False, "model_identity_verified": False, "usage_reported": False, "finish_reason": None, "content_length": 0, "content_sha256": None, "observed_type": "unknown", "observed_keys": []})])
    writer_client = FakeStructuredClient([])
    runner, registry, spec = _runner(GLMStructuredPlanner(planner_client), GLMSingleWriter(writer_client))
    with pytest.raises(E2ETerminalError) as error:
        asyncio.run(runner.run(task, brief, approval, event_path=tmp_path / "runtime.jsonl", checkpoint_path=tmp_path / "checkpoint.json"))
    assert error.value.error_code == "outcome_unknown" and error.value.outcome_unknown
    assert planner_client.calls == 1 and writer_client.calls == 0 and registry.calls == []
    run_id = DeepResearchRunner.run_id(task, brief)
    events = UnifiedEventStore(tmp_path / "runtime.jsonl", run_id=run_id).read_all()
    assert any(event.event_type.value == "operation_unknown" for event in events) and (tmp_path / "checkpoint.json").is_file()
    diagnostics = next(event.payload["diagnostics"] for event in events if event.event_type.value == "operation_unknown")
    assert {"failure_stage", "contract_error_code", "http_status", "response_received", "response_json_parsed", "model_identity_verified", "usage_reported", "finish_reason", "content_length", "content_sha256", "observed_type", "observed_keys"}.issubset(diagnostics)
    assert "raw_response" not in diagnostics and "authorization" not in diagnostics and "api_key" not in diagnostics
    replayed = replay_runtime_events(RunState(run_id=run_id, task_id=task.task_id, brief_id=brief.brief_id, brief_approved=True), events, spec)
    assert replayed.manual_intervention is not None and planner_client.calls == 1 and writer_client.calls == 0


def test_planner_known_failure_is_durable_and_exit_class_two_without_writer(tmp_path: Path):
    task, brief, approval = _inputs()
    planner_client = FakeStructuredClient([GLMAdapterError("content_missing")])
    writer_client = FakeStructuredClient([])
    runner, registry, _ = _runner(GLMStructuredPlanner(planner_client), GLMSingleWriter(writer_client))
    with pytest.raises(E2ETerminalError) as error:
        asyncio.run(runner.run(task, brief, approval, event_path=tmp_path / "runtime.jsonl", checkpoint_path=tmp_path / "checkpoint.json"))
    assert error.value.error_code == "provider_response_invalid" and not error.value.outcome_unknown
    assert planner_client.calls == 1 and writer_client.calls == 0 and registry.calls == []
    checkpoint = json.loads((tmp_path / "checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["run_state"]["status"] == "failed" and checkpoint["run_state"]["terminal_reason"] == "provider_response_invalid"


def test_planner_application_contract_classification_and_fence_are_deterministic():
    task, brief, _ = _inputs()
    raw = json.dumps(_planner_response(task, brief), ensure_ascii=False, separators=(",", ":"))
    fenced = RawStructuredClient("```json\n" + raw + "\n```")
    draft = asyncio.run(GLMStructuredPlanner(fenced).create_draft(task=task, brief=brief))
    assert draft["task_id"] == task.task_id
    for content, code in (
        ("{not-json", "planner_json_invalid"),
        (json.dumps({"schema_version": "dr-planner-draft-v1", "subtasks": [{"local_key": "x"}]}), "planner_schema_invalid"),
    ):
        with pytest.raises(PlannerError) as error:
            asyncio.run(GLMStructuredPlanner(RawStructuredClient(content)).create_draft(task=task, brief=brief))
        assert error.value.code == code
    with pytest.raises(PlannerError) as truncated:
        asyncio.run(GLMStructuredPlanner(RawStructuredClient(raw, finish_reason="length")).create_draft(task=task, brief=brief))
    assert truncated.value.code == "planner_content_truncated"


@pytest.mark.parametrize("payload", ({"schema_version": "dr-planner-draft-v1"}, {"schema_version": "dr-planner-draft-v1", "subtasks": None}, {"schema_version": "dr-planner-draft-v1", "subtasks": []}, {"schema_version": "dr-planner-draft-v1", "subtask": [{"local_key": "x"}]}))
def test_empty_planner_shapes_have_safe_nonempty_diagnostics(payload):
    task, brief, _ = _inputs()
    with pytest.raises(PlannerError) as error:
        asyncio.run(GLMStructuredPlanner(FakeStructuredClient([payload])).create_draft(task=task, brief=brief))
    assert error.value.code == "planner_empty"
    diagnostics = getattr(error.value, "diagnostics", {})
    assert diagnostics["contract_error_code"] == "planner_empty"
    assert diagnostics["normalization_accepted_count"] == 0
    assert "raw_response" not in diagnostics and "reasoning" not in diagnostics


def test_planner_prompt_freezes_nonempty_shape_and_schema_limits():
    from litflow.deep_research.e2e import PLANNER_PROMPT

    assert "subtasks" in PLANNER_PROMPT and "non-empty" in PLANNER_PROMPT and "local_key" in PLANNER_PROMPT


def test_writer_provider_contract_errors_have_safe_diagnostics():
    for content, code in (("not-json", "writer_json_invalid"), ("{}", "writer_content_truncated")):
        writer = GLMSingleWriter(RawStructuredClient(content, finish_reason="length" if code == "writer_content_truncated" else None))
        with pytest.raises(WriterError) as error:
            asyncio.run(writer.create_draft(graph=type("Graph", (), {"model_dump": lambda _self, **_kwargs: {}})(), assessment=type("Assessment", (), {"model_dump": lambda _self, **_kwargs: {}})()))
        assert error.value.code == code
        assert error.value.diagnostics and "content_sha256" in error.value.diagnostics
        assert "raw_response" not in error.value.diagnostics and "authorization" not in error.value.diagnostics


def test_writer_calibration_preflight_is_offline_and_artifact_unique():
    import subprocess
    from litflow.deep_research.e2e import runtime_source_sha256

    plan = WriterCalibrationPlan(implementation_commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), runtime_source_sha256=runtime_source_sha256(), calibration_id="writer-calibration-001", artifact_dir="outputs/deep_research/writer_calibration/v1/dr-calibration-" + "a" * 24)
    preflight_writer_calibration(plan, repo_root=Path.cwd())


def test_committed_writer_calibration_cli_preflight_is_network_denied(tmp_path: Path, monkeypatch):
    from litflow.deep_research.writer_calibration_cli import main

    plan = WriterCalibrationPlan(calibration_id="writer-calibration-test", implementation_commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), runtime_source_sha256=runtime_source_sha256(), artifact_dir="outputs/deep_research/writer_calibration/v1/dr-calibration-" + "e" * 24)
    path = tmp_path / "plan.json"; path.write_text(plan.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr("litflow.deep_research.canary.urllib.request.urlopen", lambda *_args, **_kwargs: pytest.fail("network attempted"))
    assert main(["--plan", str(path), "--artifact-dir", plan.artifact_dir, "--dry-run"], repo_root=Path.cwd(), artifact_root=tmp_path) == 0


def test_writer_calibration_cli_requires_explicit_mutually_exclusive_mode():
    import subprocess
    command = [".venv\\Scripts\\python.exe", "-m", "litflow.deep_research.writer_calibration_cli", "--plan", "docs/deep_research/calibration/v1/writer_calibration_plan.json", "--artifact-dir", "outputs/deep_research/writer_calibration/v1/dr-calibration-76017a7df7b64fc2dcad8730"]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 2
    help_result = subprocess.run(command[:3] + ["--help"], capture_output=True, text=True)
    assert help_result.returncode == 0 and "--dry-run" in help_result.stdout and "--execute" in help_result.stdout


def test_writer_calibration_subprocess_enters_execute_branch_without_credential(tmp_path: Path):
    import sys
    import shutil
    plan = WriterCalibrationPlan(calibration_id="writer-calibration-subprocess", implementation_commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), runtime_source_sha256=runtime_source_sha256(), artifact_dir="outputs/deep_research/writer_calibration/v1/dr-calibration-" + "a" * 24)
    plan_path = tmp_path / "plan.json"; plan_path.write_text(plan.model_dump_json(), encoding="utf-8")
    env = {"PYTHONPATH": str(Path.cwd() / "src"), "PATH": str(Path(shutil.which("git")).parent) + ";" + str(Path.cwd() / ".venv" / "Scripts"), "SystemRoot": "C:\\Windows", "WINDIR": "C:\\Windows", "TEMP": str(tmp_path), "TMP": str(tmp_path)}
    result = subprocess.run([sys.executable, "-m", "litflow.deep_research.writer_calibration_cli", "--plan", str(plan_path), "--artifact-dir", plan.artifact_dir, "--execute"], cwd=Path.cwd(), env=env, capture_output=True, text=True)
    assert result.returncode == 2 and "configuration_invalid" in result.stdout


def test_writer_calibration_execute_missing_credential_fails_before_dispatch(tmp_path: Path, monkeypatch):
    from litflow.deep_research import writer_calibration_cli
    plan = WriterCalibrationPlan(calibration_id="writer-calibration-test", implementation_commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), runtime_source_sha256=runtime_source_sha256(), artifact_dir="outputs/deep_research/writer_calibration/v1/dr-calibration-" + "c" * 24, run_id=None)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(writer_calibration_cli.GLMStructuredAdapter, "require_credential_for_execute", lambda _self: (_ for _ in ()).throw(E2EConfigurationError("credential missing")))
    assert writer_calibration_cli.main(["--plan", str(plan_path), "--artifact-dir", plan.artifact_dir, "--execute"], repo_root=Path.cwd(), artifact_root=tmp_path) == 2
    assert not (tmp_path / plan.artifact_dir).exists()


def test_writer_calibration_execute_offline_mock_enters_real_cli_branch_once(tmp_path: Path, monkeypatch):
    from litflow.deep_research import writer_calibration_cli
    plan = WriterCalibrationPlan(calibration_id="writer-calibration-test", implementation_commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), runtime_source_sha256=runtime_source_sha256(), artifact_dir="outputs/deep_research/writer_calibration/v1/dr-calibration-" + "d" * 24)
    task, brief, approval, validated_plan, graph, assessment = build_writer_calibration_fixture(plan)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan.model_dump_json(), encoding="utf-8")
    class OfflineAdapter:
        def __init__(self, *_args, **_kwargs): self.calls = 0
        def require_credential_for_execute(self): return "offline-fixture"
        async def complete(self, *, prompt: str, operation_name: str):
            self.calls += 1
            unit = graph.evidence_units[0]
            return GLMStructuredReply(content=json.dumps({"schema_version": "dr-report-draft-v1", "task_id": task.task_id, "brief_id": brief.brief_id, "plan_id": validated_plan.plan_id, "run_id": graph.run_id, "sections": [{"heading": "Findings", "claims": [{"text": "The fixture is grounded.", "language": "en", "citations": [{"evidence_id": unit.evidence_id, "quote": unit.verbatim_content, "relation": "support"}]}]}]}), usage=TokenUsage(input_tokens=10, output_tokens=20), model_identity_verified=True, usage_reported=True, request_id_present=False)
    monkeypatch.setattr(writer_calibration_cli, "GLMStructuredAdapter", OfflineAdapter)
    assert writer_calibration_cli.main(["--plan", str(plan_path), "--artifact-dir", plan.artifact_dir, "--execute"], repo_root=Path.cwd(), artifact_root=tmp_path) == 0
    target = tmp_path / plan.artifact_dir
    assert (target / "runtime.jsonl").is_file() and (target / "checkpoint.json").is_file() and (target / "calibration_result.json").is_file()


@pytest.mark.parametrize(("provider_error", "expected_exit"), (("provider_response_invalid", 2), ("outcome_unknown", 3)))
def test_writer_calibration_execute_maps_known_and_unknown_and_persists_artifact(tmp_path: Path, monkeypatch, provider_error: str, expected_exit: int):
    from litflow.deep_research import writer_calibration_cli
    plan = WriterCalibrationPlan(calibration_id="writer-calibration-test", implementation_commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), runtime_source_sha256=runtime_source_sha256(), artifact_dir="outputs/deep_research/writer_calibration/v1/dr-calibration-" + ("1" if provider_error == "provider_response_invalid" else "2") * 24)
    path = tmp_path / "plan.json"; path.write_text(plan.model_dump_json(), encoding="utf-8")
    class ErrorAdapter:
        def __init__(self, *_args, **_kwargs): self.calls = 0
        def require_credential_for_execute(self): return "offline-fixture"
        async def complete(self, **_kwargs):
            self.calls += 1
            raise GLMAdapterError(provider_error, outcome_unknown=provider_error == "outcome_unknown", diagnostics={"failure_stage": "transport", "contract_error_code": provider_error, "response_received": False, "response_json_parsed": False})
    monkeypatch.setattr(writer_calibration_cli, "GLMStructuredAdapter", ErrorAdapter)
    assert writer_calibration_cli.main(["--plan", str(path), "--artifact-dir", plan.artifact_dir, "--execute"], repo_root=Path.cwd(), artifact_root=tmp_path) == expected_exit
    target = tmp_path / plan.artifact_dir
    assert (target / "runtime.jsonl").is_file() and (target / "checkpoint.json").is_file() and (target / "calibration_result.json").is_file()
    result = json.loads((target / "calibration_result.json").read_text(encoding="utf-8"))
    assert result["error_code"] == provider_error and result["provider_calls"] == 1 and result["planner_calls"] == result["tool_calls"] == 0
    assert "offline-fixture" not in (target / "calibration_result.json").read_text(encoding="utf-8")


def test_writer_calibration_artifact_exists_fails_closed(tmp_path: Path):
    from litflow.deep_research.writer_calibration_cli import main
    plan = WriterCalibrationPlan(calibration_id="writer-calibration-test", implementation_commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), runtime_source_sha256=runtime_source_sha256(), artifact_dir="outputs/deep_research/writer_calibration/v1/dr-calibration-" + "9" * 24)
    path = tmp_path / "plan.json"; path.write_text(plan.model_dump_json(), encoding="utf-8")
    (tmp_path / plan.artifact_dir).mkdir(parents=True)
    assert main(["--plan", str(path), "--artifact-dir", plan.artifact_dir, "--dry-run"], repo_root=Path.cwd(), artifact_root=tmp_path) == 2


def test_writer_calibration_schema_export_is_byte_stable(tmp_path: Path):
    from litflow.deep_research.schema_export import write_writer_calibration_schema
    committed = Path("docs/deep_research/calibration/v1/writer_calibration.schema.json").read_bytes()
    first = write_writer_calibration_schema(tmp_path / "one").read_bytes()
    second = write_writer_calibration_schema(tmp_path / "two").read_bytes()
    assert first == second == committed


def test_single_paper_attempt_008_plan_preflight_and_schema_are_deterministic(tmp_path: Path):
    raw = json.loads(Path("docs/deep_research/e2e/v1.1/glm_e2e_pilot_plan.attempt-007.json").read_text(encoding="utf-8"))
    item = dict(raw["tasks"][0])
    item.update({"attempt_id": "glm-5.3-flash-deepresearch-e2e-008", "implementation_commit_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), "runtime_source_sha256": runtime_source_sha256(), "planner_prompt_sha256": prompt_hashes()["planner"], "writer_prompt_sha256": prompt_hashes()["writer"], "run_id": "dr-run-8b30915e93a6e6b5ee8137c5", "artifact_dir": "outputs/deep_research/e2e/v1.2/dr-run-8b30915e93a6e6b5ee8137c5"})
    plan = GLME2ESinglePaperAttemptPlan.model_validate({"schema_version": "dr-glm-e2e-pilot-v1.2", "provider": raw["provider"], "channel": raw["channel"], "policy": raw["policy"], "tasks": [item]})
    with pytest.raises(E2EConfigurationError, match="binding|artifact"):
        preflight_e2e_pilot(plan, repo_root=Path.cwd())
    committed = Path("docs/deep_research/e2e/v1.2/glm_e2e_pilot.schema.json").read_bytes()
    assert write_e2e_single_paper_schema(tmp_path).read_bytes() == committed


def test_planner_scope_and_dependency_failures_remain_separate_codes(tmp_path: Path):
    task, brief, approval = _inputs()
    bad_scope = _planner_response(task, brief)
    bad_scope["scope_inclusions"] = ["outside-scope"]
    runner, _, _ = _runner(GLMStructuredPlanner(FakeStructuredClient([bad_scope])), GLMSingleWriter(FakeStructuredClient([])))
    with pytest.raises(E2ETerminalError) as error:
        asyncio.run(runner.run(task, brief, approval, event_path=tmp_path / "scope-runtime.jsonl", checkpoint_path=tmp_path / "scope-checkpoint.json"))
    assert error.value.error_code == "planner_scope_invalid"
    scope_event = next(event for event in UnifiedEventStore(tmp_path / "scope-runtime.jsonl", run_id=DeepResearchRunner.run_id(task, brief)).read_all() if event.event_type.value == "operation_failed")
    assert scope_event.payload["diagnostics"]["validation_rule"] == "approved_scope_is_program_owned"
    assert scope_event.payload["diagnostics"]["field_location"] == "scope_inclusions"
    bad_dependency = _planner_response(task, brief)
    bad_dependency["subtasks"][0]["dependencies"] = ["missing"]
    dependency_runner, _, _ = _runner(GLMStructuredPlanner(FakeStructuredClient([bad_dependency])), GLMSingleWriter(FakeStructuredClient([])))
    with pytest.raises(E2ETerminalError) as dependency_error:
        asyncio.run(dependency_runner.run(task, brief, approval, event_path=tmp_path / "dependency-runtime.jsonl", checkpoint_path=tmp_path / "dependency-checkpoint.json"))
    assert dependency_error.value.error_code == "planner_dependency_invalid"


def test_planner_inherits_approved_scope_and_rejects_explicit_unauthorized_tools():
    task, brief, _ = _inputs()
    response = _planner_response(task, brief)
    for field in ("task_id", "brief_id", "locale", "constraints", "scope_inclusions", "scope_exclusions"):
        response.pop(field, None)
    response["subtasks"][0]["tool_intent"] = "local_read_only_retrieval"
    draft = asyncio.run(GLMStructuredPlanner(FakeStructuredClient([response])).create_draft(task=task, brief=brief))
    assert draft["task_id"] == task.task_id and draft["brief_id"] == brief.brief_id and draft["scope_inclusions"] == list(brief.scope_inclusions)
    bad = _planner_response(task, brief)
    bad["subtasks"][0]["tool_intent"] = "web_search"
    with pytest.raises(PlannerError) as error:
        asyncio.run(GLMStructuredPlanner(FakeStructuredClient([bad])).create_draft(task=task, brief=brief))
    assert error.value.code == "planner_scope_invalid" and getattr(error.value, "diagnostics", {}).get("field_location") == "subtasks[find].tool_intent"


def test_planner_rejects_writer_action_as_a_scope_contract_violation():
    task, brief, _ = _inputs()
    response = _planner_response(task, brief)
    response["subtasks"][0]["research_action"] = "compose_report"
    with pytest.raises(PlannerError) as error:
        asyncio.run(GLMStructuredPlanner(FakeStructuredClient([response])).create_draft(task=task, brief=brief))
    assert error.value.code == "planner_scope_invalid"
    assert error.value.diagnostics["field_location"] == "subtasks[find].research_action"


def test_writer_allows_fenced_json_and_explicit_abstention():
    payload = {"schema_version": "dr-report-draft-v1", "task_id": "task", "brief_id": "brief", "plan_id": "plan", "run_id": "run", "abstention_reason": "No grounded evidence", "sections": [{"heading": "Insufficient evidence", "claims": []}]}
    writer = GLMSingleWriter(RawStructuredClient("```json\n" + json.dumps(payload) + "\n```"))
    draft = asyncio.run(writer.create_draft(graph=type("Graph", (), {"model_dump": lambda _self, **_kwargs: {}})(), assessment=type("Assessment", (), {"model_dump": lambda _self, **_kwargs: {}})()))
    assert draft["abstention_reason"] == "No grounded evidence"


def test_writer_schema_failure_has_bounded_diagnostics():
    writer = GLMSingleWriter(RawStructuredClient(json.dumps({"schema_version": "dr-report-draft-v1", "sections": []})))
    with pytest.raises(WriterError) as error:
        asyncio.run(writer.create_draft(graph=type("Graph", (), {"model_dump": lambda _self, **_kwargs: {}})(), assessment=type("Assessment", (), {"model_dump": lambda _self, **_kwargs: {}})()))
    assert error.value.code == "writer_schema_invalid"
    assert error.value.diagnostics["failure_stage"] == "writer_schema"
    assert error.value.diagnostics["validation_errors"] and "location" in error.value.diagnostics["validation_errors"][0]
    assert "raw_response" not in error.value.diagnostics and "authorization" not in error.value.diagnostics


def test_writer_prompt_does_not_request_system_identity_fields():
    from litflow.deep_research.e2e import WRITER_PROMPT
    for field in ("schema_version", "task_id", "brief_id", "plan_id", "run_id", "report_id", "claim_id", "citation_id"):
        assert f'"{field}":' not in WRITER_PROMPT
    assert "Never output schema_version" in WRITER_PROMPT


def test_writer_response_owned_identity_is_discarded_before_finalization(tmp_path: Path):
    from litflow.deep_research.writer import FakeWriter
    task, brief, approval = _inputs()
    plan = asyncio.run(plan_approved_brief(task, brief, approval, FakePlanner(_planner_response(task, brief))))
    execution = asyncio.run(LocalResearchExecutor(ReadOnlyToolRegistry(_corpus())).execute(task, brief, approval, plan, event_path=tmp_path / "executor.jsonl", checkpoint_path=tmp_path / "executor.checkpoint.json"))
    graph = execution.evidence_graph
    assessment = asyncio.run(assess_evidence_graph(graph, (), AssessmentContext(completed_subtask_ids=tuple(item.subtask_id for item in plan.subtasks))))
    unit = graph.evidence_units[0]
    content = {"sections": [{"heading": "Findings", "claims": [{"text": "The fixture is grounded.", "language": "en", "citations": [{"evidence_id": unit.evidence_id, "quote": unit.verbatim_content, "relation": "support"}]}]}]}
    content.update({"schema_version": "wrong", "task_id": "dr-task-short", "brief_id": "brief-short", "plan_id": "plan-short", "run_id": "run-short"})
    writer = FakeWriter(content)
    result = asyncio.run(SingleWriterRunner(writer).run(task, brief, approval, plan, graph, assessment, event_path=tmp_path / "identity.jsonl", checkpoint_path=tmp_path / "identity.checkpoint.json"))
    report = result.validation.report
    assert report is not None and report.task_id == task.task_id and report.brief_id == brief.brief_id and report.plan_id == plan.plan_id and report.run_id == graph.run_id
    event = next(event for event in result.events if event.event_type.value == "operation_succeeded")
    assert set(event.payload["model_supplied_owned_fields"]) == {"schema_version", "task_id", "brief_id", "plan_id", "run_id"}


def test_writer_content_schema_reports_bounded_multiple_errors_without_values():
    writer = GLMSingleWriter(RawStructuredClient(json.dumps({"sections": [{"claims": [{"citations": [{}]}]}]})))
    with pytest.raises(WriterError) as error:
        asyncio.run(writer.create_draft(graph=type("Graph", (), {"model_dump": lambda _self, **_kwargs: {}})(), assessment=type("Assessment", (), {"model_dump": lambda _self, **_kwargs: {}})()))
    diagnostics = error.value.diagnostics
    assert 1 <= diagnostics["validation_errors_count"] <= 16
    assert all(set(item) == {"type", "location"} for item in diagnostics["validation_errors"])
    assert "input" not in json.dumps(diagnostics).lower()


def test_planner_known_failure_reconciles_actual_usage_and_elapsed(tmp_path: Path):
    task, brief, approval = _inputs()
    observed = TokenUsage(input_tokens=64, output_tokens=128, cost_micros=Decimal("204.8"))
    planner = GLMStructuredPlanner(RawStructuredClient("{}", finish_reason="length", usage=observed))
    runner, _, spec = _runner(planner, GLMSingleWriter(FakeStructuredClient([])))
    with pytest.raises(E2ETerminalError) as error:
        asyncio.run(runner.run(task, brief, approval, event_path=tmp_path / "runtime.jsonl", checkpoint_path=tmp_path / "checkpoint.json"))
    assert error.value.error_code == "planner_content_truncated"
    run_id = DeepResearchRunner.run_id(task, brief)
    events = UnifiedEventStore(tmp_path / "runtime.jsonl", run_id=run_id).read_all()
    failed = next(event for event in events if event.event_type.value == "operation_failed")
    assert failed.payload["usage"]["input_tokens"] == 64 and failed.payload["usage"]["output_tokens"] == 128
    elapsed = next(event.payload["elapsed_s"] for event in events if event.event_type.value == "elapsed_recorded")
    assert elapsed > 0
    checkpoint = json.loads((tmp_path / "checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["ledger"]["input_tokens"] == 64 and checkpoint["ledger"]["output_tokens"] == 128
    assert checkpoint["ledger"]["cost_micros"] == "204.8"
    replayed = replay_runtime_events(RunState(run_id=run_id, task_id=task.task_id, brief_id=brief.brief_id, brief_approved=True), events, spec)
    assert replayed.ledger.input_tokens == 64 and replayed.ledger.cost_micros == Decimal("204.8")


def test_writer_known_and_unknown_are_durable_distinct_terminals_without_retry(tmp_path: Path):
    task, brief, approval = _inputs()
    for code, unknown, expected in (("content_missing", False, "operation_failed"), ("outcome_unknown", True, "operation_unknown")):
        planner_client = FakeStructuredClient([_planner_response(task, brief)])
        writer_client = FakeStructuredClient([GLMAdapterError(code, outcome_unknown=unknown)])
        runner, _, spec = _runner(GLMStructuredPlanner(planner_client), GLMSingleWriter(writer_client))
        event_path = tmp_path / f"{code}.jsonl"
        checkpoint = tmp_path / f"{code}.checkpoint.json"
        if unknown:
            result = asyncio.run(runner.run(task, brief, approval, event_path=event_path, checkpoint_path=checkpoint))
            assert result.terminal == "manual_review_required" and result.validation is not None
        else:
            with pytest.raises(WriterError, match="provider_response_invalid"):
                asyncio.run(runner.run(task, brief, approval, event_path=event_path, checkpoint_path=checkpoint))
        events = UnifiedEventStore(event_path, run_id=DeepResearchRunner.run_id(task, brief)).read_all()
        assert any(event.event_type.value == expected and event.payload.get("operation_name") == "single_writer" for event in events)
        assert planner_client.calls == writer_client.calls == 1
        replay_runtime_events(RunState(run_id=DeepResearchRunner.run_id(task, brief), task_id=task.task_id, brief_id=brief.brief_id, brief_approved=True), events, spec)
        assert planner_client.calls == writer_client.calls == 1


@pytest.mark.parametrize(
    ("status", "payload", "error"),
    (
        (200, {"model": "glm-5.3-flash", "choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}, "id": "opaque"}, None),
        (401, {"error": {"message": "denied"}}, "transport_failure"),
        (200, {"error": {"message": "denied"}}, "provider_response_invalid"),
        (200, {"model": "other", "choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}}, "provider_response_invalid"),
        (200, {"model": "glm-5.3-flash", "choices": [{"message": {"content": "{}"}}]}, "provider_response_invalid"),
    ),
)
def test_shared_glm_adapter_classifies_mock_transport_without_environment_access(status, payload, error):
    async def transport(**_kwargs):
        return status, {}, json.dumps(payload).encode("utf-8")

    adapter = GLMStructuredAdapter(GLMInvocationPolicy(), transport=transport, credential="offline-fixture")
    if error is None:
        reply = asyncio.run(adapter.complete(prompt="offline", operation_name="test"))
        assert reply.content == "{}" and reply.model_identity_verified and reply.usage_reported and str(reply.usage.cost_micros) == "3.2"
    else:
        with pytest.raises(GLMAdapterError, match=error):
            asyncio.run(adapter.complete(prompt="offline", operation_name="test"))


def test_shared_glm_adapter_keeps_malformed_json_and_timeout_fail_closed():
    async def malformed(**_kwargs):
        return 200, {}, b"not-json"

    with pytest.raises(GLMAdapterError, match="provider_response_invalid"):
        asyncio.run(GLMStructuredAdapter(GLMInvocationPolicy(), transport=malformed, credential="offline-fixture").complete(prompt="offline", operation_name="test"))

    async def lost(**_kwargs):
        raise TimeoutError()

    with pytest.raises(GLMAdapterError, match="outcome_unknown") as error:
        asyncio.run(GLMStructuredAdapter(GLMInvocationPolicy(), transport=lost, credential="offline-fixture").complete(prompt="offline", operation_name="test"))
    assert error.value.outcome_unknown


def test_glm_adapter_freezes_text_only_request_and_never_serializes_credential():
    captured = {}

    async def transport(**kwargs):
        captured.update(kwargs)
        return 200, {}, json.dumps({"model": "glm-5.3-flash", "choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}).encode("utf-8")

    asyncio.run(GLMStructuredAdapter(GLMInvocationPolicy(), transport=transport, credential="offline-fixture-token").complete(prompt="offline", operation_name="glm_structured_planner"))
    request = json.loads(captured["body"])
    assert request["model"] == "glm-5.3-flash" and request["stream"] is False and request["thinking"] == {"type": "enabled"}
    assert request["reasoning_effort"] == "low" and request["max_tokens"] == 4096
    assert "tools" not in request and "offline-fixture-token" not in captured["body"].decode("utf-8")


def test_writer_stage_uses_high_reasoning_and_same_shared_transport():
    captured = {}

    async def transport(**kwargs):
        captured.update(kwargs)
        return 200, {}, json.dumps({"model": "glm-5.3-flash", "choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}).encode("utf-8")

    asyncio.run(GLMStructuredAdapter(GLMInvocationPolicy(), transport=transport, credential="offline-fixture-token").complete(prompt="offline", operation_name="glm_single_writer"))
    request = json.loads(captured["body"])
    assert request["reasoning_effort"] == "high" and request["max_tokens"] == 4096


def test_stage_specific_budget_reserves_two_calls_and_rejects_third_before_dispatch():
    policy = GLMInvocationPolicy()
    spec = BudgetSpec(max_provider_calls=2, max_provider_attempts=2, max_input_tokens=6144, max_output_tokens=8192, max_total_tokens=14336, max_cost_micros=20000, max_retries=0, max_replans=1, run_timeout_s=180, operation_timeout_s=60)
    ledger = BudgetLedger.empty(spec)
    first = policy.reservation("planner")
    second = policy.reservation("writer")
    ledger, _ = ledger.reserve(spec, operation_id="dr-operation-" + "a" * 24, attempt_id="dr-attempt-" + "a" * 24, kind=OperationKind.provider, usage=first)
    ledger, _ = ledger.reserve(spec, operation_id="dr-operation-" + "b" * 24, attempt_id="dr-attempt-" + "b" * 24, kind=OperationKind.provider, usage=second)
    with pytest.raises(ValueError, match="budget exhausted"):
        ledger.reserve(spec, operation_id="dr-operation-" + "c" * 24, attempt_id="dr-attempt-" + "c" * 24, kind=OperationKind.provider, usage=second)
    assert first.total_tokens == 6144 and second.total_tokens == 8192 and ledger.cost_micros <= 20000


@pytest.mark.parametrize("fail_at", (4, 5))
def test_planner_reserve_or_dispatch_fsync_failure_prevents_provider_call(tmp_path: Path, monkeypatch, fail_at: int):
    task, brief, approval = _inputs()
    client = FakeStructuredClient([_planner_response(task, brief)])
    spec = BudgetSpec(max_provider_calls=2, max_provider_attempts=2, max_tool_calls=8, max_tool_attempts=8, max_retries=0, max_replans=1, run_timeout_s=90, operation_timeout_s=30)
    runner = DeepResearchRunner(GLMStructuredPlanner(client), LocalResearchExecutor(ReadOnlyToolRegistry(_corpus()), budget=spec), GLMSingleWriter(FakeStructuredClient([])), budget=spec)
    original = __import__("os").fsync
    calls = {"count": 0}

    def fsync(fd):
        calls["count"] += 1
        if calls["count"] == fail_at:
            raise OSError("fsync")
        return original(fd)

    monkeypatch.setattr("litflow.deep_research.runtime_v2.os.fsync", fsync)
    with pytest.raises(OSError, match="fsync"):
        asyncio.run(runner.run(task, brief, approval, event_path=tmp_path / f"{fail_at}.jsonl", checkpoint_path=tmp_path / f"{fail_at}.checkpoint.json"))
    assert client.calls == 0


def test_pilot_preflight_is_offline_fails_closed_and_schema_is_stable(tmp_path: Path):
    corpus = tmp_path / "outputs" / "rag_bm25_v1" / "passages.jsonl"
    corpus.parent.mkdir(parents=True)
    corpus.write_text("fixture", encoding="utf-8")
    digest = hashlib.sha256(b"fixture").hexdigest()
    hashes = prompt_hashes()
    rows = []
    for key, terminal in (("single_paper", "complete"), ("cross_paper_comparison", "partial"), ("insufficient_evidence", "insufficient_evidence")):
        task = ResearchTask.create(f"Question for {key}", "en", ("local-only", key), "grounded_report", NOW)
        brief = ResearchBrief.create(task.task_id, f"Objective for {key}", (key,), (), "grounded report", ("exact citation",), task.constraints, BriefApprovalStatus.approved)
        run_id = DeepResearchRunner.run_id(task, brief)
        rows.append({"task_key": key, "task_id": task.task_id, "brief_id": brief.brief_id, "original_question": task.original_question, "locale": task.locale, "constraints": list(task.constraints), "deliverable_type": task.deliverable_type, "created_at": task.created_at.isoformat(), "brief_objective": brief.objective, "scope_inclusions": list(brief.scope_inclusions), "scope_exclusions": list(brief.scope_exclusions), "brief_deliverable": brief.deliverable, "success_criteria": list(brief.success_criteria), "approval_actor": "human", "approval_decided_at": NOW.isoformat(), "implementation_commit_sha": subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip(), "runtime_source_sha256": runtime_source_sha256(), "expected_terminal": terminal, "acceptance_metrics": ["terminal_status", "evidence_citation_quote_grounding", "unsupported_claim_count", "abstention_correctness", "provider_attempts_responses", "tokens_cost", "latency", "replay_zero_calls", "secret_scan"], "corpus_path": "outputs/rag_bm25_v1/passages.jsonl", "corpus_sha256": digest, "planner_prompt_sha256": hashes["planner"], "writer_prompt_sha256": hashes["writer"], "artifact_dir": f"outputs/deep_research/e2e/v1/{run_id}", "run_id": run_id})
    plan = GLME2EPilotPlan.model_validate({"schema_version": "dr-glm-e2e-pilot-v1", "provider": "zhipu-bigmodel", "channel": "ordinary_model_api", "policy": GLMInvocationPolicy().model_dump(mode="json"), "tasks": rows})
    assert len(preflight_e2e_pilot(plan, repo_root=tmp_path)) == 3
    artifact = tmp_path / rows[0]["artifact_dir"]; artifact.mkdir(parents=True)
    with pytest.raises(E2EConfigurationError, match="artifact"):
        preflight_e2e_pilot(plan, repo_root=tmp_path)
    assert write_e2e_pilot_schema(tmp_path / "schemas").read_bytes() == write_e2e_pilot_schema(tmp_path / "schemas-again").read_bytes()


def test_committed_pilot_cli_preflight_is_network_denied(tmp_path: Path, monkeypatch):
    from litflow.deep_research.writer_calibration_cli import main

    plan = WriterCalibrationPlan(calibration_id="writer-calibration-test", implementation_commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), runtime_source_sha256=runtime_source_sha256(), artifact_dir="outputs/deep_research/writer_calibration/v1/dr-calibration-" + "f" * 24)
    path = tmp_path / "plan.json"; path.write_text(plan.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr("litflow.deep_research.canary.urllib.request.urlopen", lambda *_args, **_kwargs: pytest.fail("network attempted"))
    assert main(["--plan", str(path), "--artifact-dir", plan.artifact_dir, "--dry-run"], repo_root=Path.cwd(), artifact_root=tmp_path) == 0


@pytest.mark.parametrize(("terminal", "expected_exit"), (("complete", 0), ("partial", 2), ("manual_review_required", 3)))
def test_execute_cli_maps_only_complete_to_zero_without_real_transport(monkeypatch, terminal, expected_exit):
    from litflow.deep_research import e2e_cli

    class OfflineAdapter:
        def __init__(self, *_args, **_kwargs):
            pass

        def require_credential_for_execute(self):
            return "offline-fixture"

    class OfflineRunner:
        def __init__(self, *_args, **_kwargs):
            pass

        async def run(self, *_args, **_kwargs):
            return type("Result", (), {"terminal": terminal, "run_id": "dr-run-offline"})()

    monkeypatch.setattr(e2e_cli, "GLMStructuredAdapter", OfflineAdapter)
    monkeypatch.setattr(e2e_cli, "DeepResearchRunner", OfflineRunner)
    monkeypatch.setattr(e2e_cli, "preflight_e2e_pilot", lambda plan, repo_root: tuple(plan.tasks))
    assert e2e_cli.main(["--plan", "docs/deep_research/e2e/v1/glm_e2e_pilot_plan.json", "--task", "single_paper", "--artifact-dir", "outputs/deep_research/e2e/v1/dr-run-30a882141ca5a7b2093d8fd2", "--execute"]) == expected_exit


@pytest.mark.parametrize(("error", "expected_exit"), ((E2ETerminalError("planner_contract_invalid"), 2), (E2ETerminalError("outcome_unknown", outcome_unknown=True), 3)))
def test_execute_cli_maps_structured_planner_errors_without_text_matching(monkeypatch, error, expected_exit):
    from litflow.deep_research import e2e_cli

    class OfflineAdapter:
        def __init__(self, *_args, **_kwargs):
            pass

        def require_credential_for_execute(self):
            return "offline-fixture"

    class OfflineRunner:
        def __init__(self, *_args, **_kwargs):
            pass

        async def run(self, *_args, **_kwargs):
            raise error

    monkeypatch.setattr(e2e_cli, "GLMStructuredAdapter", OfflineAdapter)
    monkeypatch.setattr(e2e_cli, "DeepResearchRunner", OfflineRunner)
    monkeypatch.setattr(e2e_cli, "preflight_e2e_pilot", lambda plan, repo_root: tuple(plan.tasks))
    assert e2e_cli.main(["--plan", "docs/deep_research/e2e/v1/glm_e2e_pilot_plan.json", "--task", "single_paper", "--artifact-dir", "outputs/deep_research/e2e/v1/dr-run-30a882141ca5a7b2093d8fd2", "--execute"]) == expected_exit


def test_execute_cli_invalid_configuration_remains_known_failure(monkeypatch):
    from litflow.deep_research import e2e_cli

    monkeypatch.setattr(e2e_cli, "preflight_e2e_pilot", lambda plan, repo_root: tuple(plan.tasks))
    assert e2e_cli.main(["--plan", "docs/deep_research/e2e/v1/glm_e2e_pilot_plan.json", "--task", "single_paper", "--artifact-dir", "outputs/deep_research/e2e/v1/not-the-frozen-target", "--dry-run"]) == 2


def test_committed_pilot_freezes_three_distinct_tasks_and_schema(tmp_path: Path):
    plan = parse_e2e_pilot_plan(json.loads(Path("docs/deep_research/e2e/v1.1/glm_e2e_pilot_plan.attempt-007.json").read_text(encoding="utf-8")))
    assert {item.task_key for item in plan.tasks} == {"single_paper", "cross_paper_comparison", "insufficient_evidence"}
    assert len({item.run_id for item in plan.tasks}) == len({item.artifact_dir for item in plan.tasks}) == 3
    assert plan.budget_spec().max_provider_calls == 2 and plan.budget_spec().max_cost_micros == 20000
    assert write_e2e_pilot_schema(tmp_path).read_bytes() == Path("docs/deep_research/e2e/v1/glm_e2e_pilot.schema.json").read_bytes()
    assert write_e2e_pilot_attempt_schema(tmp_path / "v1.1").read_bytes() == Path("docs/deep_research/e2e/v1.1/glm_e2e_pilot.schema.json").read_bytes()
