# Frozen Boundaries

## Protected historical baseline

- `v1.0.0-mvp` 必须保留为现有 annotated tag；DR-S00 记录的 peeled commit 是 `36ae717adf02fe1c6c097f0a10eb9ad61faa22fc`。不得移动、删除、重建或新建 release tag。
- 所有既有 `outputs/` 均为历史 artifact；尤其不得写入、覆盖、删除、迁移或重建：
  - `outputs/rag_bm25_v1`
  - `outputs/evidence_qa_v1_2`
  - `outputs/evidence_matrix_v1`
  - `outputs/m4_writing_v1`
  - `outputs/m5_fastapi_v1`
  - `outputs/m6_docker_runtime`
  - `outputs/m8_agent`
- MVP、M8、冻结 corpus/qrels、既有 schema、Prompt、Validator、Retriever、UI、Docker、依赖、`src/` 与 `tests/` 均不因 DR-S00 而改变。
- M8 的历史结论固定为 `experimental_partial_pass`。AG01 的 `evidence_anchor_not_found` 安全失败不得被重写为 Agent 成功。

## DR-S00 allowed namespace

本 Session 的可写范围严格限于 `docs/deep_research/`：路线图、S00 执行单、基线、冻结边界、ADR、manifest 和 Session Log。除在此目录内保留性移动的两份用户输入外，不得创建其他文件。

路线图提出的未来命名空间（例如 `outputs/deep_research_v1/` 与 `LITFLOW_DR_*`）只是后续 Session 的建议；DR-S00 不创建、不写入也不启用它们。

## External-call approval boundary

- DR-S00 禁止真实 LLM/provider、Web Search/Fetch、Zotero、Obsidian、PDF 重处理、M8 或后续 Agent 实验。
- 默认 Docker 演示保持 offline；不得因本 Session 启动或修改 Docker。
- 任何未来真实 provider 调用必须先满足路线图 Gate A，并在调用前获得用户对 provider、模型、任务数和最大预算的明确批准。
- Web Research 必须先满足 Gate B；Multi-Agent 之前必须满足 Gate C；Multi-Agent/Critic 仅在 Gate D 的等预算消融产生明确净收益时保留。

## Change-control rule

发现历史 output、tag、held-out 泄漏风险，或需要删除、覆盖、迁移历史文件才能继续时，应停止当前 Session、保留只读证据并请求新授权；不得通过放宽 validator 或扩大范围绕过该门槛。
