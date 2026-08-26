# LitFlow DR-S01 — Codex 执行单

## Session 身份

- 路线：LitFlow DeepResearch Track
- Session：`DR-S01`
- 名称：建立代码、Schema、Artifact 和指标资产地图
- 类型：只读仓库审计 + 版本化文档交付
- 前置 Session：DR-S00 `pass`
- 本轮不实现、不重构任何运行时代码

## 1. 唯一目标

对当前 LitFlow 仓库做一次可追溯的资产盘点，建立“现有能力究竟在哪里、由什么测试和 artifact 支撑、未来 DeepResearch 可以如何复用”的事实地图。

必须覆盖四类资产：

1. **代码资产**：CLI、PDF/context、retrieval、QA、evidence、writing、API/UI、evaluation、agent/durable event；
2. **Schema 资产**：Pydantic/dataclass/TypedDict/JSON contract、字段身份与序列化边界；
3. **Artifact 资产**：冻结 outputs、manifest、summary、review packet、trace、cache；
4. **指标资产**：指标定义、实现位置、分母、结果来源与适用边界。

本轮产物必须让未来 Codex 不需要依靠聊天记忆，就能回答：

- 某项能力是否真实存在；
- 它的代码、测试、CLI/API 入口和 artifact 在哪里；
- 哪些只是历史文档或实验结果；
- 哪些可原样复用、需要包装、需要新版本扩展，或只能作为历史参考；
- DeepResearch 后续 Session 目前还缺什么。

本轮不做架构选型，不设计新 Schema，不修依赖，不新增功能。

## 2. 当前已核验基线

- 当前分支：`milestone/litflow-deepresearch-v1`
- 当前 HEAD：`afccfb5ad200d284d831cee0cddf43d4271631eb`
- S00 commit：`docs: initialize LitFlow DeepResearch track`
- 分支基点：`a5a01a41165822d668fac3e607d45c7be6b6b93b`
- `origin/main`：`a5a01a41165822d668fac3e607d45c7be6b6b93b`
- `v1.0.0-mvp` peeled commit：`36ae717adf02fe1c6c097f0a10eb9ad61faa22fc`
- 正式测试数量：`268 passed, 1 warning`
- S00 状态：`pass`
- M8 状态：`experimental_partial_pass`
- 分支尚未 push。

以上仍需在 Phase A 重新核验，不得只复制文字。

## 3. 本轮附件例外

本轮用户会将以下文件作为附件放入仓库工作目录：

```text
LitFlow_DR-S01_Codex_Execution_Brief.md
```

如果工作树唯一的未跟踪文件正是这个同名附件，则将其视为已授权的 S01 输入，不构成阻塞。必须先核对标题和内容可读，然后在 Phase B 保留性移动为：

```text
docs/deep_research/sessions/DR-S01.md
```

如果还有其他修改或未跟踪文件，停止，不得自动清理、stash、提交或忽略。

## 4. Phase A：只读预检

### 4.1 Git 与治理身份

执行并报告：

```powershell
git status --short --branch
git rev-parse HEAD
git rev-parse main
git rev-parse origin/main
git rev-parse "v1.0.0-mvp^{}"
git log -2 --oneline
git diff --check
```

确认：

- 当前分支和 HEAD 与第2节一致；
- 除预期 S01 附件外工作树 clean；
- S00 文档均已被 Git 跟踪；
- 旧 tag、main 和 origin/main 未移动；
- 不存在已被提前创建的 S01 资产地图文件。

### 4.2 先读取治理文件

完整读取：

```text
AGENTS.md（所有适用层级）
docs/deep_research/README.md
docs/deep_research/ROADMAP.md
docs/deep_research/BASELINE.md
docs/deep_research/FROZEN_BOUNDARIES.md
docs/deep_research/SESSION_LOG.md
docs/deep_research/baseline_manifest.json
docs/deep_research/adr/ADR-000-deepresearch-track.md
```

验证 `baseline_manifest.json` 是合法 JSON，且不含 API key、环境变量值、私人绝对路径或未验证能力。

### 4.3 已知非阻塞文档漂移

S00 对话交接报告记录测试耗时 `9.88s`，而 `BASELINE.md` 当前记录 `11.90s`。通过数与 warning 数一致。

处理规则：

- wall-clock 测试耗时不是冻结性能指标；
- 不猜测哪一个耗时“更正确”；
- 在 S01 的审计说明中记录为 non-contractual run variance；
- 允许将 `BASELINE.md` 的测试表述规范为 `268 passed, 1 warning`，并明确运行时长会随机器/缓存变化；
- 不把这项调整扩大成根 README 的历史测试数字清理。

### Phase A 停止条件

出现以下任一情况立即停止，不修改文件：

- Git 身份、tag、分支基点不符；
- 除 S01 附件外存在其他 dirty/untracked 内容；
- S00 文档缺失、未跟踪或出现不明修改；
- `baseline_manifest.json` 无法解析或含 secret/私人绝对路径；
- 历史 outputs 无法只读访问；
- 需要修改源码、测试或历史 artifact 才能完成盘点；
- 发现适用 `AGENTS.md` 与本执行单冲突。

全部通过后可直接进入 Phase B，无需再次请求普通文档写入授权。

## 5. Phase B：只读资产发现方法

### 5.1 搜索原则

- 优先使用 `rg --files` 和 `rg`；
- 读取定义与测试，不只根据文件名猜测；
- 对 Python 资产记录精确相对路径和主要 symbol；
- 对 CLI/API 记录入口、参数/route 和调用的领域函数；
- 对 Schema 记录定义形式、字段身份、序列化位置和 validator；
- 对指标记录计算函数、公式/语义、分母和落盘位置；
- 对 output 只读查看目录结构、manifest、summary、metrics、review/audit 文件；
- 不递归读取大型 raw response、模型 cache、embedding `.npy`、PDF 或包含潜在私密内容的全文 artifact；
- 若只凭现有材料不能确认，标为 `unknown`，不得推断成已实现。

### 5.2 必查代码入口

至少检查：

```text
pyproject.toml
requirements*.lock / requirements*.txt
src/litflow/cli.py
src/litflow/models.py（若存在）
src/litflow/zotero/
src/litflow/pdf/
src/litflow/context/
src/litflow/obsidian/
src/litflow/rag/
src/litflow/llm/
src/litflow/evidence_matrix.py
src/litflow/evidence_writing.py
src/litflow/evaluation*.py 或 evaluation 相关目录
src/litflow/agent/
src/litflow_api/
tests/
Dockerfile
compose.yaml
```

路径不存在时记录 `not_present`，不要创建替代文件。

### 5.3 必查能力域

资产盘点至少包含：

1. Zotero / Better BibTeX 读取；
2. PDF 提取、clean context、页码/chunk provenance；
3. Obsidian preview/apply/backup；
4. passage corpus 与 qrels；
5. BM25、Dense、Windowed、Hybrid 与 query translation；
6. evidence-grounded QA 与 replay/review；
7. evidence candidate / span mapping / strict grounding；
8. Evidence Matrix 与 bilingual writing；
9. evaluation runner、manifest、checkpoint/resume；
10. FastAPI、SSE、persisted jobs、UI；
11. Docker offline/online 边界；
12. Agent scaffold、tools、state、durable events、replay 与 M8 gate。

### 5.4 历史 artifact 只读范围

至少对下列根目录记录：存在性、用途、主要 identity/summary 文件、冻结状态、是否适合未来复用；不得写入：

```text
outputs/rag_bm25_v1
outputs/evidence_qa_v1_2
outputs/evidence_matrix_v1
outputs/m4_writing_v1
outputs/m5_fastapi_v1
outputs/m6_docker_runtime
outputs/m8_agent
```

若仓库内还有正式文档引用的关键 frozen output，可加入目录，但必须注明发现来源。不要把 `pytest_tmp_*`、`.pytest_cache` 或 legacy scratch 当作产品资产。

## 6. 统一证据与状态分类

每项资产必须使用以下字段，不得只写自然语言印象：

```text
asset_id
category
capability
path
symbols_or_entrypoints
evidence
verification_status
historical_status
frozen
deepresearch_disposition_candidate
notes
```

### 6.1 verification_status

仅使用：

```text
verified_in_code
verified_by_test
verified_by_artifact
historical_doc_only
not_verified
not_present
```

同一项可有多条 evidence，但 JSON 中主状态必须选择最强且可解释的一项。

### 6.2 historical_status

仅使用：

```text
active_mvp
frozen_pilot
experimental_pass
experimental_partial_pass
experimental_fail
legacy_support
not_applicable
```

### 6.3 deepresearch_disposition_candidate

这只是 S03 架构决策前的候选分类，不是最终 ADR：

```text
reuse_as_is
wrap_with_new_contract
extend_as_new_version
reference_only
avoid_in_default_path
new_capability_required
unknown
```

禁止在 S01 因此修改旧实现。

## 7. 必须产出

### 7.1 `docs/deep_research/ASSET_MAP.md`

至少包括：

- 仓库入口与模块树；
- 12 个能力域的现状；
- 关键 CLI/API 到领域函数的调用关系；
- 关键数据流和 artifact 流；
- 可复用候选、扩展候选、历史参考和明确缺口；
- 当前已观察到的重复 contract、耦合点和依赖缺口；
- 不做架构决策，只给带证据的候选分类。

可以使用小型 Mermaid 图，但图中的每个节点必须能在资产清单中找到代码或 artifact 依据。

### 7.2 `docs/deep_research/TRACEABILITY_MATRIX.md`

每个主要能力一行，至少包含：

```text
Capability
Code / symbols
CLI / API entry
Tests
Artifacts / docs
Metrics
Current status
DR candidate disposition
Known gap
```

“存在测试文件”不等于能力已端到端验证；必须区分 unit、fixture/fake、offline replay、real provider 和 human review。

### 7.3 `docs/deep_research/asset_inventory.json`

机器可读，要求：

- 顶层包含 `schema_version`、`generated_at`、`git_commit_sha`、`inventory_scope`、`assets`、`known_gaps`；
- `git_commit_sha` 记录盘点所基于的 S00 HEAD，而不是尚未产生的 S01 commit；
- path 全部为仓库相对路径；
- 不包含 Windows 绝对路径、secret、环境变量值、完整 raw model response；
- JSON 中的 asset 必须能在 Markdown 资产图或 traceability matrix 中定位；
- 用标准库解析验证，并保持稳定排序，避免无意义 diff。

### 7.4 Session 与导航更新

- 保留性移动附件为 `docs/deep_research/sessions/DR-S01.md`；
- 更新 `docs/deep_research/README.md`，加入 S01 和三项资产地图入口；
- 更新 `docs/deep_research/SESSION_LOG.md`：S01 → `completed`；
- 如果规范测试耗时表述，仅允许最小更新 `docs/deep_research/BASELINE.md`；
- 不修改 `ROADMAP.md`、`FROZEN_BOUNDARIES.md`、ADR-000 或 `baseline_manifest.json`，除非发现事实性安全错误；若发现此类错误，应先停止并报告，不自行重写治理基线。

## 8. 已知缺口必须如实记录

至少核查并记录：

- NumPy 顶层导入与 runtime lock 声明关系；
- PyMuPDF/`fitz` 与 reading-context 测试/runtime 声明关系；
- Torch/Transformers 是 Dense `_Encoder` 的延迟依赖，不得误写成 MVP 必需；
- 根 README `238 passed` 与当前正式 `268 passed` 的文档漂移；
- M6 若只有截图/正式文档而缺独立结构化 runtime summary，按实际情况标注；
- M8 durable event/replay 的已验证范围与 grounded completion 未验证的边界；
- Dense/Hybrid 冻结负结果不能写成当前默认检索能力；
- DeepResearch Brief、Evidence Graph、动态 replan、Web、多模态、Multi-Agent/Critic 尚未实现。

如果仓库证据与上述预期不符，以仓库证据为准并在报告中解释，不要为满足执行单而伪造。

## 9. 本轮明确禁止

- 不修改 `src/`、`tests/`、依赖、lock、Docker、Compose、根 README、Prompt、Schema、Validator、Retriever、API 或 UI；
- 不写入、移动、删除或重新生成任何历史 `outputs/`；
- 不运行 LLM、Web、Zotero、Obsidian、PDF 重处理、Dense 重建或 M8；
- 不创建新 runtime、Pydantic model、状态机、数据库或 benchmark；
- 不修复盘点发现的问题；所有修复进入后续对应 Session；
- 不改变历史指标、qrels、corpus、review 结论或实验状态；
- 不创建、移动或删除 tag；
- 不执行 reset、clean、stash、force push、prune 或删除命令；
- 不 push；本轮仍只创建本地 commit。

## 10. 验证要求

### 10.1 文档与清单一致性

- 用 Python 标准库解析 `asset_inventory.json`；
- 检查所有 inventory path 均为相对路径；
- 对声称存在的 code/test/artifact 路径执行存在性检查；
- 检查 JSON asset_id 唯一；
- 检查三份资产文档中的主要能力域无遗漏；
- 搜索私人绝对路径、API key 模式和明显 placeholder；
- 检查 Markdown 相对链接。

允许为验证编写一次性内存/命令行检查，但不将临时脚本提交到仓库。

### 10.2 正式回归

运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q ".\tests"
git diff --check
git diff --cached --check
git status --short --branch
```

预期仍为 `268 passed, 1 warning`。运行耗时只作日志，不作为冻结性能指标。

失败时不得修改源码绕过；保留证据并停止。

## 11. 验收标准

必须同时满足：

1. 只修改 `docs/deep_research/` 内本执行单允许的文件；
2. 12 个能力域全部进入资产图和 traceability matrix；
3. 代码、schema、artifact、metrics 均有精确路径或明确 `not_present`；
4. 每项事实能追溯到 code/test/artifact/正式文档之一；
5. 不将 fake/unit test 冒充真实 provider E2E；
6. 不将历史 pilot 指标冒充新结果；
7. 不将 M8 写成完整 Agent 成功；
8. 新旧可复用候选与缺口清晰，但没有提前作 S03 架构决策；
9. JSON 合法、稳定、无 secret/绝对路径；
10. 正式测试和 diff check 通过；
11. 工作树在提交后 clean；
12. 没有 push 和外部调用。

## 12. 提交要求

提交前展示：

```powershell
git diff --stat
git diff --check
git status --short --branch
```

确认范围正确后创建一个本地 commit：

```text
docs: map LitFlow assets for DeepResearch
```

提交后核验：

```powershell
git status --short --branch
git log -2 --oneline
```

不要 push。

## 13. 最终交接报告格式

### A. Session 结论

- `pass` / `blocked` / `failed`
- 是否解锁 DR-S02
- 简历状态固定为 `not_ready`

### B. Git 身份

- 起始 commit、当前分支、新 commit、worktree、tag、是否 push

### C. 资产盘点规模

- asset 总数及按 category/status/disposition 的统计
- 12 个能力域覆盖情况

### D. 关键资产与复用候选

- 最重要的代码、Schema、artifact、metric
- `reuse_as_is` / `wrap` / `extend` / `reference_only` 的证据

### E. 已确认缺口与风险

- 依赖、contract、artifact、指标和文档漂移
- 区分“应在 S02 处理”和“仅供 S03/S04 决策”

### F. 修改文件

- 逐个相对路径和用途

### G. 验证

- JSON/路径/链接/secret 检查
- pytest 汇总
- diff check
- 外部调用情况

### H. 冻结边界确认

- 源码、测试、依赖、outputs、M8、tag、Docker 是否保持不变

### I. 下一步

- 仅判断是否可以进入 `DR-S02：单独修复 NumPy / PyMuPDF 依赖可复现性`
- 不提前修复依赖或实施 S03

## 14. 本 Session 简历状态

固定为：

```text
not_ready
```

S01 是后续可靠演进所需的资产审计，不应单独包装成 Agent 项目成果。
