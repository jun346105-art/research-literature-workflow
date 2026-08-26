# LitFlow DeepResearch Track

此目录承载 LitFlow DeepResearch 长期演进路线的治理记录。它不代表任何 DeepResearch runtime、Agent、Web、Multimodal 或 UI 功能已实现。

## 版本与使用

- 路线版本：`LitFlow DeepResearch 长期演进路线图 v1`
- 当前 Session：`DR-S01`（代码、Schema、Artifact 和指标资产审计）
- 当前简历状态：`not_ready`

按以下顺序使用这些文件：

1. [路线图](ROADMAP.md)：冻结长期方向、阶段 Gate、止损规则和条件实验原则。
2. [DR-S00 执行单](sessions/DR-S00.md)：已完成的治理初始化授权与验收记录。
3. [DR-S01 执行单](sessions/DR-S01.md)：已完成的只读资产审计授权与验收规则。
4. [资产图](ASSET_MAP.md)、[Traceability Matrix](TRACEABILITY_MATRIX.md) 和 [资产清单](asset_inventory.json)：现有代码、Schema、artifact 和指标的可追溯地图。
5. [基线](BASELINE.md)：当前仓库身份和历史证据的分级记录。
6. [冻结边界](FROZEN_BOUNDARIES.md)：不得触碰对象、允许命名空间和外部调用审批边界。
7. [Session Log](SESSION_LOG.md)：S00–S63 状态索引。
8. [Baseline manifest](baseline_manifest.json)：机器可读的基线身份与冻结 artifact 清单。
9. [ADR-000](adr/ADR-000-deepresearch-track.md)：演进策略的核心决策。

后续 Session 必须先以本目录的边界和 manifest 做只读预检；不得用路线图的长期目标提前扩张当前 Session 范围。
