# LitFlow DR-S00 — Codex 执行单

## Session 身份

- 路线：LitFlow DeepResearch Track
- Session：`DR-S00`
- 名称：创建 DeepResearch 新里程碑并冻结授权边界
- 类型：仓库治理与文档初始化
- 本轮不实现任何 Agent、RAG、Web、Multimodal 或 UI 功能

## 1. 唯一目标

在不改动 LitFlow v1.0 MVP、历史 M8、历史 outputs 和任何产品代码的前提下：

1. 核实仓库身份与冻结基线；
2. 从当前 `main` 创建独立的 DeepResearch 里程碑分支；
3. 将附带的长期路线图纳入仓库；
4. 建立后续 Session 使用的边界、基线、ADR 和 Session Log；
5. 以一次独立文档提交结束。

本 Session 的成功标准是“新旧边界可审计”，不是“出现新的 Agent 功能”。

## 2. 附件与权威顺序

本轮应收到附件：

- `LitFlow_DeepResearch_Long_Term_Roadmap_v1.md`

请完整阅读附件，再读取仓库文件。发生冲突时使用以下优先级：

1. 用户在当前对话中的明确指令；
2. 仓库内 `AGENTS.md`；
3. 本执行单；
4. 附件路线图；
5. 仓库现有 README、release notes 和历史文档。

不得因为路线图提出长期目标，就在 S00 提前实现后续 Session。

## 3. 预期仓库基线

只把以下内容作为“待核验预期”，不要在未执行 Git 命令前直接宣布已确认：

- 仓库：`jun346105-art/research-literature-workflow`
- 当前分支：`main`
- 预期 `HEAD == origin/main`：`a5a01a41165822d668fac3e607d45c7be6b6b93b`
- 冻结标签：`v1.0.0-mvp`
- 标签历史指向：`36ae717`（需要用 Git 核验完整对象）
- 用户最近正式报告：`268 passed, 1 warning`
- 当前 M8 口径：`experimental_partial_pass`
- AG01 工具链执行通过，但 grounded answer 因 `evidence_anchor_not_found` 安全失败；不得写成端到端 Agent 已验证。

如果实际身份与上述内容不一致，停止在只读阶段，不创建/切换分支，不修改文件。

## 4. Phase A：只读预检

先只读执行并报告结果：

```powershell
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
git remote -v
git show-ref --tags "v1.0.0-mvp"
git log -1 --oneline
git diff --check
```

然后：

1. 搜索并完整读取适用的 `AGENTS.md`；
2. 读取 `README.md`、`RELEASE_NOTES_v1.0.0.md`；
3. 定位与 M8、MVP Docker、评测和 frozen outputs 有关的现有正式文档；
4. 只读确认以下历史目录是否存在，不读取或重写其中的大型内容：
   - `outputs/rag_bm25_v1`
   - `outputs/evidence_qa_v1_2`
   - `outputs/evidence_matrix_v1`
   - `outputs/m4_writing_v1`
   - `outputs/m5_fastapi_v1`
   - `outputs/m6_docker_runtime`
   - `outputs/m8_agent`
5. 检查目标分支 `milestone/litflow-deepresearch-v1` 是否已经存在于本地或远端。

### Phase A 停止条件

出现任一情况时立即停止，仅报告证据和建议：

- 工作树不 clean；
- `HEAD != origin/main`；
- HEAD 不是预期 commit；
- `v1.0.0-mvp` 缺失或身份异常；
- 发现未知同名目标分支；
- `AGENTS.md` 与本执行单冲突；
- 历史 outputs 出现访问拒绝或疑似缺失；
- 需要删除、覆盖、迁移或修改历史文件才能继续。

如果全部通过，可直接继续 Phase B，无需再次向用户询问普通文档创建权限。

## 5. Phase B：允许实施的精确范围

### 5.1 创建分支

从已核验的当前 `main` HEAD 创建：

```text
milestone/litflow-deepresearch-v1
```

如果该分支已存在，不得删除、重建、reset 或强行覆盖；停止并报告其 commit 和工作树状态。

### 5.2 允许创建的仓库文件

仅允许在 `docs/deep_research/` 下创建：

```text
docs/deep_research/
├── README.md
├── ROADMAP.md
├── BASELINE.md
├── FROZEN_BOUNDARIES.md
├── SESSION_LOG.md
├── baseline_manifest.json
└── adr/
    └── ADR-000-deepresearch-track.md
```

要求：

- `ROADMAP.md` 以附件路线图为内容来源；不得擅自删掉 Gate、止损规则或条件式 Multi-Agent 决策。
- `README.md` 只做目录导航、版本说明和使用方法。
- `BASELINE.md` 记录已经由仓库或用户正式输出支持的事实，并区分：
  - repository-verified；
  - user-reported-and-reproduced；
  - historical-document-only；
  - not-yet-validated。
- `FROZEN_BOUNDARIES.md` 精确记录不可触碰对象、允许的新命名空间和外部调用审批边界。
- `SESSION_LOG.md` 建立 S00–S63 索引，S00 标记为本轮状态，其余为 `not_started`；不要伪造未来 commit 或指标。
- `baseline_manifest.json` 只记录可机器读取的基线身份，例如 commit、tag、branch、测试命令与结果来源、冻结 artifact 路径、路线版本。不要存绝对私人路径、secret 或模型 API 配置值。
- `ADR-000-deepresearch-track.md` 记录核心决策：演进 LitFlow 而非重写；Single-Agent first；Evidence-first；Multimodal 是主要差异点；Multi-Agent/Critic 仅在等预算消融通过后保留。

### 5.3 本轮明确禁止

- 不修改 `src/`、`tests/`、`pyproject.toml`、任何 lock 文件、Dockerfile、Compose、Prompt、Schema、Validator、Retriever 或 UI；
- 不修复 NumPy/PyMuPDF 声明缺口，该任务属于 S02；
- 不创建 DeepResearch 运行时代码、数据库、API、状态机或 LangGraph graph；
- 不改动或写入任何历史 `outputs/`；
- 不运行真实 LLM、Web Search、Zotero、Obsidian、PDF 重处理或 M8；
- 不移动或创建 release tag；
- 不执行 `git reset --hard`、`git clean`、`git checkout --`、`git push --force`、Docker prune 或删除命令；
- 不提交 `.venv`、`.pytest_cache`、`pytest_tmp_*`、PDF、模型缓存、API Key 或本机绝对路径；
- 不 push。本轮只允许建立本地分支和本地 commit。

## 6. 基线验证

文档创建完成后，在普通权限 PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q ".\tests"
git diff --check
git status --short --branch
```

预期测试结果为：

```text
268 passed, 1 warning
```

若数量变化、出现 skip/failure 或产生非预期文件：

- 不修改产品代码“顺手修复”；
- 保留完整输出；
- 检查是否由环境、收集路径或本轮文档操作引起；
- 无法在本轮边界内解释时停止，不提交。

## 7. 内容验收标准

必须同时满足：

1. 新分支准确从核验后的 main HEAD 创建；
2. 只新增上述 `docs/deep_research/` 文件；
3. 路线图已纳入仓库且没有被弱化；
4. `BASELINE.md` 不把历史文档数字冒充本轮新验证；
5. `FROZEN_BOUNDARIES.md` 明确旧 tag、outputs、MVP 与 M8 的保护规则；
6. Agent 状态诚实写为 `experimental_partial_pass`；
7. Multi-Agent 和 Critic 明确为条件实验；
8. 不出现任何 secret、私人绝对路径或未验证指标；
9. 正式测试通过；
10. `git diff --check` 通过。

## 8. 提交要求

提交前展示：

```powershell
git diff --stat
git diff --check
git status --short --branch
```

确认只有 S00 文档后，创建一个本地 commit：

```text
docs: initialize LitFlow DeepResearch track
```

提交后核验：

```powershell
git status --short --branch
git log -1 --oneline
```

不要 push，等待用户检查最终报告后再决定远端操作。

## 9. 最终交接报告格式

请严格按以下顺序报告：

### A. Session 结论

- `pass` / `blocked` / `failed`
- 是否解锁 S01

### B. Git 身份

- 起始 main commit
- 当前分支
- 新 commit
- worktree 状态
- tag 状态

### C. 新增文件

- 逐个列出相对路径和用途

### D. 基线验证

- 测试命令与完整汇总
- `git diff --check`
- 是否发生外部调用

### E. 冻结边界确认

- 是否修改历史 outputs、MVP、M8、tag、源码、依赖和 Docker

### F. 风险与不确定项

- 只列真实存在的风险

### G. 下一步

- 仅说明是否可以进入 `DR-S01：建立代码、schema、artifact 和指标资产地图`
- 不提前实施 S01

## 10. 本 Session 的简历状态

固定标记为：

```text
not_ready
```

S00 只建立工程治理和可复现边界，不应独立包装成简历成果。
