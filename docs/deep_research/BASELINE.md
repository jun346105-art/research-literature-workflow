# DeepResearch Track Baseline

本文档记录 DR-S00 创建时的基线。分级表示证据来源，而非对未来能力的承诺。

## repository-verified

- 远端：`https://github.com/jun346105-art/research-literature-workflow.git`。
- 起始 `main` 与 `origin/main` 都是 `a5a01a41165822d668fac3e607d45c7be6b6b93b`（`Document M8 experimental agent closure`）。
- `v1.0.0-mvp` 是存在的 annotated tag；tag object 为 `7806fffbb426835211fde0dd9d1c3536173c9868`，peeled commit 为 `36ae717adf02fe1c6c097f0a10eb9ad61faa22fc`（`Sanitize public path fixtures`）。
- 下列冻结历史 artifact 根目录在本次只读预检时存在且可访问：
  - `outputs/rag_bm25_v1`
  - `outputs/evidence_qa_v1_2`
  - `outputs/evidence_matrix_v1`
  - `outputs/m4_writing_v1`
  - `outputs/m5_fastapi_v1`
  - `outputs/m6_docker_runtime`
  - `outputs/m8_agent`
- 本地与 `origin` 均不存在 `milestone/litflow-deepresearch-v1`；DR-S00 因而从上述已核验 main commit 创建该本地分支。

## user-reported-and-reproduced

- DR-S00 在本地以 `./.venv/Scripts/python.exe -m pytest -q ./tests` 复现：`268 passed, 1 warning in 11.90s`。这验证的是当前仓库测试套件，不重跑历史 provider、Web、Zotero、Obsidian、PDF 或 M8 实验。

## historical-document-only

- 根目录 README 的 Development Check 仍记载 `238 passed`；这是现有文档陈述，不是本次正式测试证据。
- `RELEASE_NOTES_v1.0.0.md`、`docs/EVALUATION_RUN_002.md` 和 `docs/DOCKER_DEMO.md` 描述的 retrieval、QA、writing 与 Docker 结果均为历史范围受限的 pilot/demo 记录，不在 DR-S00 重跑。
- `M8_AGENT_EXPERIMENT_CLOSURE.zh-CN.md` 记录：M8 overall 为 `experimental_partial_pass`；AG01 的 planning/tool chain 通过，但 end-to-end grounded answer 在 `quote_grounding_failed / evidence_anchor_not_found` 处安全失败。因此不得表述为端到端 Agent 已验证。
- `docs/M8B_EVALUATION_PROTOCOL.zh-CN.md` 记录的 provider 预算、任务集和 Gate 是历史 M8 protocol；DR-S00 不运行其中任何外部调用。

## not-yet-validated

- DeepResearch runtime、Research Brief、Planner、Evidence Graph、动态 replan、Single Writer、Report Validator、Web Research、Multimodal evidence、Multi-Agent 与 Critic 均未在 DR-S00 实现或验证。
- Multi-Agent 和 Critic 只可作为后续等模型、等数据、等预算 held-out 消融通过后的条件实验；它们不是当前产品路径或已证实能力。
- 本 Session 不生成任何新的模型、成本、延迟、grounded completion 或 benchmark 指标。
