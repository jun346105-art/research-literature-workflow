# LitFlow DeepResearch Track

此目录承载 LitFlow DeepResearch 长期演进路线的治理记录。v2 runtime 仅表示离线、脚本化的可靠性测试边界，不代表真实 Agent、Web、Multimodal 或 UI 功能已实现。

## 版本与使用

- 路线版本：`LitFlow DeepResearch 长期演进路线图 v1`
- 当前 Session：`B03R2 / replay boundary correctness`（Gate A pending second read-only re-audit）
- 当前简历状态：`not_ready`

按以下顺序使用这些文件：

1. [路线图](ROADMAP.md)：冻结长期方向、阶段 Gate、止损规则和条件实验原则。
2. [DR-S00 执行单](sessions/DR-S00.md)：已完成的治理初始化授权与验收记录。
3. [DR-S01 执行单](sessions/DR-S01.md)：已完成的只读资产审计授权与验收规则。
4. [DR-S02 执行单](sessions/DR-S02.md)：依赖边界与 fresh-environment 验收规则。
5. [DR-S03/S04 执行单](sessions/DR-S03-S04.md)：架构与实验治理冻结规则。
6. [目标架构](ARCHITECTURE.md)、[参考模式取舍](REFERENCE_PATTERN_DECISIONS.md)、[实验治理](EXPERIMENT_GOVERNANCE.md) 和 [实施节奏](IMPLEMENTATION_CADENCE.md)：S05 前的可实施合同。
7. [B01 执行单](sessions/B01-DR-S05-S06.md)、[Contracts v1](CONTRACTS_V1.md) 与 [Schema](contracts/v1/README.md)：离线领域合同与稳定导出。
8. [B02 执行单](sessions/B02-DR-S07-S08.md)、[Runtime Kernel v1](RUNTIME_KERNEL_V1.md) 与 [runtime schema](runtime/v1/README.md)：离线状态、事件、checkpoint 和 replay 合同。
9. [B03 执行单](sessions/B03-DR-S09-S10.md)、[Execution Policies v1](EXECUTION_POLICIES_V1.md)、[Fake E2E v1](FAKE_E2E_V1.md) 与 [policy schema](policies/v1/README.md)：预算、deadline、取消、retry、replan、journal 和离线确定性测试台。
10. [B03R Unified Runtime v2](B03R_UNIFIED_RUNTIME_V2.md) 与 [runtime schema v2](runtime/v2/README.md)：单一 ordered event stream、crash-safe dispatch、canonical hash、coordinated checkpoint 和 fail-closed unknown outcome。
11. [B03R2 Replay Boundaries](B03R2_REPLAY_BOUNDARIES.md)：事实 reducer、流尾 unknown finalization、retry/replan 恢复、checkpoint trust 和受控入口。
12. [资产图](ASSET_MAP.md)、[Traceability Matrix](TRACEABILITY_MATRIX.md) 和 [资产清单](asset_inventory.json)：现有代码、Schema、artifact 和指标的可追溯地图。
13. [依赖可复现性](DEPENDENCY_REPRODUCIBILITY.md)：Runtime、test extra 与 Dense-only 依赖边界。
14. [基线](BASELINE.md)：当前仓库身份和历史证据的分级记录。
15. [冻结边界](FROZEN_BOUNDARIES.md)：不得触碰对象、允许命名空间和外部调用审批边界。
16. [Session Log](SESSION_LOG.md)：S00–S63 状态索引。
17. [Baseline manifest](baseline_manifest.json)：机器可读的基线身份和冻结 artifact 清单。
18. [ADR-000](adr/ADR-000-deepresearch-track.md)、[ADR-001](adr/ADR-001-runtime-and-evidence-boundaries.md) 与 [ADR-002](adr/ADR-002-experiment-and-data-governance.md)：演进、架构和实验治理决策。

后续 Session 必须先以本目录的边界和 manifest 做只读预检；不得用路线图的长期目标提前扩张当前 Session 范围。
