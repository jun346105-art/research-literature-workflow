# DeepResearch Session Log

状态仅反映已完成的治理工作，不伪造未来 commit、实验结果或指标。

| Session | 单一目标 | 状态 |
| --- | --- | --- |
| S00 | 创建 DeepResearch 新里程碑并冻结授权边界 | completed |
| S01 | 建立代码、schema、artifact 和指标资产地图 | completed |
| S02 | 单独修复 NumPy / PyMuPDF 依赖可复现性 | completed |
| S03 | 冻结目标架构与关键 ADR | completed (combined DR-S03/DR-S04 batch) |
| S04 | 冻结实验与数据治理协议 | completed (combined DR-S03/DR-S04 batch) |
| S05 | 定义 ResearchTask / Brief / Subtask schema | completed (B01 DR-S05/S06 batch) |
| S06 | 定义 Source / EvidenceUnit / Claim / Citation schema | completed (B01 DR-S05/S06 batch) |
| S07 | 定义 RunState 和显式状态机 | completed (B02 DR-S07/S08 batch) |
| S08 | 扩展 durable event / checkpoint / replay | completed (B02 DR-S07/S08 batch) |
| S09 | 建立预算、超时、取消与 retry policy | completed (B03 DR-S09/S10 batch) |
| S10 | 建立 Fake provider 与 Fake tools E2E harness | completed (B03 DR-S09/S10 batch) |
| B03R | 修复统一 runtime v2、canonical hash、crash-safe dispatch 与 fail-closed unknown outcome | completed; Gate A pending read-only re-audit; internal_result |
| B03R2 | 修复 replay boundary、checkpoint trust、retry/replan resume 与受控 runtime entry | completed; independently audited; internal_result |
| S11 | 实现 Research Brief 生成与人工确认 | completed (B04 S11/S12 batch) |
| S12 | 实现结构化 Planner | completed (B04 S11/S12 batch) |
| S13 | 实现本地论文 Research Executor | completed (B05 S13/S14 batch; offline/internal_result) |
| S14 | 实现 Claim–Evidence Graph | completed (B05 S13/S14 batch; deterministic verified relations only) |
| S15 | 实现 Evidence Gap / Conflict Checker | completed (B06; offline/internal_result) |
| S16 | 实现受控 replan | completed (B06; max_replans=1, unified event/ledger) |
| S17 | 实现 Single Writer | completed (B07 S17/S18 batch; offline FakeWriter/internal_result) |
| S18 | 实现 Report Validator 与 safe output | completed (B07 S17/S18 batch; deterministic grounding only; author review required) |
| S19 | 运行固定真实 canary 并保留全部 artifact | completed (B08; `pass_text_only_single_call`; GLM-5.3-Flash text-only single call with replay and cost audit) |
| S20 | 对 canary 失败做根因审计与一次硬化 | completed (B08R1; offline hardening; pending read-only re-audit) |
| B08R2 | 保持 v1.1 并冻结 v1.2 attempt identity、实现祖先与源码指纹绑定 | completed; pending read-only re-audit; no second call |
| B08R3 | 校准 GLM Canary application acknowledgement contract | completed; attempt 003 design frozen; pending read-only re-audit; no second call |
| B08E2E-PREP | Real GLM DeepResearch E2E 离线准备与三项 pilot 冻结 | completed; `ready_for_real_e2e_read_only_audit`; internal_result; exit semantics repaired in B08E2E-EXIT-SEMANTICS; no real E2E/API/Web call; does not occupy S21–S25 |
| B08E2E-R1 | Attempt-002 Planner contract failure audit and minimal exit/diagnostic repair | completed; Attempt-002 immutable; Attempt-003 frozen; no new real E2E/API/Web call |
| B08E2E-R2 | Attempt-003 budget, usage and elapsed calibration; Attempt-004 freeze | completed; Attempt-003 immutable; Attempt-004 dry-run only; no new real E2E/API/Web call |
| B08E2E-R3 | Attempt-004 stage-specific reasoning and token budget calibration; Attempt-005 freeze | completed; Attempt-004 immutable; Attempt-005 dry-run only; no new real E2E/API/Web call |
| B08E2E-R4 | Attempt-005 scope contract calibration and diagnostics; Attempt-006 freeze | completed; Attempt-005 immutable; Attempt-006 dry-run only; no new real E2E/API/Web call |
| B08E2E-R5 | Attempt-006 non-empty Planner output contract and Prompt calibration; Attempt-007 freeze | completed; Attempt-006 immutable; Attempt-007 dry-run only; no new real E2E/API/Web call |
| B08E2E-R6 | Attempt-007 Writer contract calibration, durable business artifacts and Writer-only dev channel | completed; implementation `adc04db10d41eb82bc1f1035f12f0d365f0dea51`; Attempt-007 immutable; calibration dry-run only; no new real E2E/API/Web call |
| B08E2E-R6C | Writer Calibration CLI explicit dry-run/execute wiring; calibration-001 retained as preflight-only; calibration-002 execution | completed; implementation `e8b12789cc747359808a351e70f5c4861edb4163`; calibration-002 known failure `writer_schema_invalid`; no retry |
| B08E2E-R7 | Writer identity ownership and content-draft finalization; calibration-003 freeze | completed; implementation `90262da09c4b23857ca7ad6aa3b87d0a0f3be199`; calibration-003 preflight passed; no real calibration call |
| B08E2E-R8 | Close successful writer-calibration-003 and freeze single-paper E2E Attempt-008 | completed; calibration-003 `pass_writer_contract_and_deterministic_grounding`; Attempt-008 `real_single_paper_e2e_pass`; cross-paper and insufficient-evidence follow-ups design-only |
| B08E2E-R9 | Cross-paper comparison corpus audit and immutable Pilot plan freeze | completed; two independent local Sources verified; dry-run/preflight passed; no real Pilot call |
| S21 | 定义 Search / Fetch provider 抽象 | not_started |
| S22 | 实现抓取、净化、缓存和内容哈希 | not_started |
| S23 | 建立来源质量与安全策略 | not_started |
| S24 | 实现 Local / Web 路由与跨来源去重 | not_started |
| S25 | 运行 Web canary | not_started |
| S26 | 定义 benchmark taxonomy 与首批任务 | not_started |
| S27 | 建立 dev / held-out 数据与冻结流程 | not_started |
| S28 | 实现 deterministic metrics | not_started |
| S29 | 实现成本、延迟与工具轨迹指标 | not_started |
| S30 | 生成人审 packet 与 rubric | not_started |
| S31 | 运行 Single-Agent dev baseline | not_started |
| S32 | 冻结并运行第一次 held-out | not_started |
| S33 | 区分 Evidence Store 与 Model Context View | not_started |
| S34 | 实现预算感知证据选择基线 | not_started |
| S35 | 实现可选分层压缩实验 | not_started |
| S36 | 做 context recall / token 消融 | not_started |
| S37 | 定义 DeepResearch FastAPI job contract | not_started |
| S38 | 实现 SSE trace、阶段进度与取消 | not_started |
| S39 | 实现 run persistence 与进程重启恢复 | not_started |
| S40 | 实现可观测页面 | not_started |
| S41 | Docker / CI / smoke / release candidate | not_started |
| S42 | 定义 PDF page-region 与 layout schema | not_started |
| S43 | 抽取 figure/table/formula/caption/nearby text | not_started |
| S44 | 建立多模态检索与候选选择基线 | not_started |
| S45 | 实现受控 VLM Region Reader | not_started |
| S46 | 实现跨模态 grounding validator | not_started |
| S47 | 构建专项 benchmark 并与 text-only 消融 | not_started |
| S48 | 预注册 Multi-Agent 假设和失败模式 | not_started |
| S49 | 实现 Supervisor + 隔离 Research Workers | not_started |
| S50 | 实现 asyncio + Semaphore 并发和配额 | not_started |
| S51 | 实现失败感知 replan / 降级 | not_started |
| S52 | 做 Single vs Multi 等模型等预算消融 | not_started |
| S53 | 做保留/拒绝决策 | not_started |
| S54 | 从真实错误构建 Critic taxonomy | not_started |
| S55 | 实现结构化 Critique 与白名单 Patch | not_started |
| S56 | 实现收敛、震荡和成本保护 | not_started |
| S57 | 做 no-critic vs critic 消融 | not_started |
| S58 | 适配公开 Deep Research benchmark 子集 | not_started |
| S59 | 完成 provider transport contract | not_started |
| S60 | 运行最终内外部评测 | not_started |
| S61 | 做安全、隐私与故障演练 | not_started |
| S62 | 完成 README、架构、Demo、面试材料 | not_started |
| S63 | Portfolio Release 与冻结 | not_started |

### B08E2E-R6 evidence

- Attempt-007 artifact `outputs/deep_research/e2e/v1/dr-run-f0357940cdcc28c42a2ed283` remains read-only. Current SHA-256: `runtime.jsonl` = `23D163B105ED8222A3D869BAB53353CD9EF94B2928A996745C06176104263DE1`; `checkpoint.json` = `F3FA39A377A1C290704DB1AB46CBFE8BFA54243652D0572ABB9A9C1AF3BC9944`.
- Writer-only plan: [`calibration/v1/writer_calibration_plan.json`](calibration/v1/writer_calibration_plan.json), `calibration_id=writer-calibration-001`, implementation commit `adc04db10d41eb82bc1f1035f12f0d365f0dea51`, runtime source SHA-256 `8bd375796790060d057a6cfb26064fb7ecadfe22a2db295977103c3aa8997aa4`, target `outputs/deep_research/writer_calibration/v1/dr-calibration-76017a7df7b64fc2dcad8730`.
- Only offline schema, mock/network-deny tests and dry-run/preflight were executed. No Key was read and no Provider/API/HTTP call or calibration artifact was created.

### B08E2E-R6C evidence

- `writer-calibration-001` and its plan remain unchanged and are recorded as `preflight_passed / real_execute_not_run`.
- [Calibration-002 plan](calibration/v1/writer_calibration_plan.calibration-002.json) binds implementation `e8b12789cc747359808a351e70f5c4861edb4163` and runtime source SHA-256 `84d1a54b7d775aca38cf831589694aa91313d6712fc707151677470cfff9ee8d` to run `dr-run-06f51068840bca6b745f6268`; its one artifact is retained as known failure `writer_schema_invalid`.
- Calibration-002 SHA-256: `runtime.jsonl` = `ACDE359A71E70309628662AC32718633A623C1163867313C7A6830A8BC08FE2F`; `checkpoint.json` = `705F8A0FD3DF880CACEAC4E5E15A5A49E842041D647553BCE65039D37B5575C9`; `calibration_result.json` = `964FF4275B3A3D25F57ABEA98016F95D9EA12AEF9B1FB90764470A55162E2787`.
- Offline CLI tests cover explicit mode selection, credential pre-dispatch failure, one Writer execution, known/unknown exit mapping, artifact persistence and network denial. Calibration-002 was not retried.

### B08E2E-R7 evidence

- Calibration-003 plan: [`calibration/v1/writer_calibration_plan.calibration-003.json`](calibration/v1/writer_calibration_plan.calibration-003.json), implementation `90262da09c4b23857ca7ad6aa3b87d0a0f3be199`, runtime source SHA-256 `ced52128187176fd7e8f59b41e20df215df183525054aa2749f25d0cf12865e1`, run `dr-run-ea36f934bb751fb5a0d4885a`, target `outputs/deep_research/writer_calibration/v1/dr-calibration-ea36f934bb751fb5a0d4885a` (absent).
- R7 changes keep formal `ReportDraft`/`ValidatedReport` ownership in program code and add the untrusted `WriterContentDraft` schema. Model-supplied identity field names are bounded diagnostics only; their values are discarded.
- Only offline tests and calibration-003 dry-run/preflight were executed. No Key, HTTP, Provider call or real calibration-003 artifact exists.

### B08E2E-R8 evidence

- Calibration-003 closure manifest: [`calibration/v1/writer_calibration_result_manifest.attempt-003.json`](calibration/v1/writer_calibration_result_manifest.attempt-003.json); result: [`WRITER_CALIBRATION_RESULT_V1.md`](WRITER_CALIBRATION_RESULT_V1.md).
- Attempt-008 plan: [`e2e/v1.2/glm_e2e_pilot_plan.attempt-008.json`](e2e/v1.2/glm_e2e_pilot_plan.attempt-008.json), one `single_paper` task, run `dr-run-8b30915e93a6e6b5ee8137c5`, target `outputs/deep_research/e2e/v1.2/dr-run-8b30915e93a6e6b5ee8137c5` (executed once and retained read-only).
- Plan is bound to implementation commit `f53a2a1554744ae7e8fc9b48796e417c3d95d5b1`, runtime source SHA-256 `4316910cc027744314eb657f7d579a82ac7d068a2b46590901757fbcf6efc472`, Planner prompt SHA-256 `cfd418a50d2c9a91230994a24bf0605f4db336fd557f0f2a13135112dee1bd3b`, Writer prompt SHA-256 `a0a3ead0fccac18ffb0d92e6e150b56e5943ad29971259b34b45431f176257e1`, and corpus SHA-256 `d099dc9ef22678af17ffbb12fc5198c9a6fce71d56576dde6f2b62984b8a7de6`.
- Attempt-008 closure manifest: [`e2e/v1.2/e2e_result_manifest.attempt-008.json`](e2e/v1.2/e2e_result_manifest.attempt-008.json); terminal `complete`, deterministic grounding passed, semantic correctness/publication quality unverified.
- Follow-up designs: [`e2e/v1.2/FOLLOWUP_PILOTS.md`](e2e/v1.2/FOLLOWUP_PILOTS.md) and [`e2e/v1.2/followup_pilot_designs.json`](e2e/v1.2/followup_pilot_designs.json). Both targets are absent and no follow-up request was executed.

### B08E2E-R9 evidence

- Executable plan: [`e2e/v1.2/glm_e2e_cross_paper_plan.attempt-001.json`](e2e/v1.2/glm_e2e_cross_paper_plan.attempt-001.json), run `dr-run-8e3c2028b68e14c88fc7b17e`, artifact target absent.
- Corpus audit selected two independent Sources: `dr-source-76a2766b4e0d53670687ff4e` (L4DLHQUZ / TPMN) and `dr-source-c82227e5b40e464045457dd3` (3NLKTSIP / Modified YOLO), each with a real method passage and stable locator.
- The plan binds implementation `d286ca0c3a187d7237e399d766a2370f5683812b`, runtime source SHA-256 `76b894d0b596c16d804ba1fedd893a64e4e717a28de11a866e2ae673e65db2d3`, task input SHA-256 `4315f8de67e0cfd65c1e9ce4a296bb6fb6a08cf0652483627417df2a537bfe0e`, and frozen Planner/Writer/corpus hashes. Only offline plan validation and Mock cross-source gate tests ran.
