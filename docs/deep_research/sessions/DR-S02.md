# LitFlow DR-S02 — Codex 执行单

## Session 身份

- 路线：LitFlow DeepResearch Track
- Session：`DR-S02`
- 名称：修复 NumPy / PyMuPDF 依赖可复现性
- 类型：小范围 packaging 维护 + clean-environment 验证
- 前置 Session：DR-S01 `pass`
- 本轮不实现任何 DeepResearch Runtime 或 Agent 功能

## 1. 唯一目标

修复当前仓库中已经被实际环境恢复暴露出的依赖声明缺口，使以下两条安装路径都有明确、可验证的结果：

1. 默认 Runtime / CLI 安装能够获得其真正需要的 NumPy；
2. Reading Context 测试或功能所需的 PyMuPDF 被放入正确的依赖层级，而不是继续依靠用户手动安装。

本轮必须根据真实 import、CLI、Docker 和测试路径判断 PyMuPDF 属于 core runtime、optional feature 还是 test/development dependency，不能因为“测试缺包”就机械塞进默认 Runtime。

Torch、Transformers 和 embedding model 不属于本轮恢复范围。

## 2. 当前已核验基线

- 当前分支：`milestone/litflow-deepresearch-v1`
- 当前 HEAD：`b02f41c69c019da4c54e7b2ce4e0a075540c48b1`
- S01 commit：`docs: map LitFlow assets for DeepResearch`
- 分支基点：`a5a01a41165822d668fac3e607d45c7be6b6b93b`
- `origin/main`：`a5a01a41165822d668fac3e607d45c7be6b6b93b`
- `v1.0.0-mvp` peeled commit：`36ae717adf02fe1c6c097f0a10eb9ad61faa22fc`
- 正式测试基线：`268 passed, 1 warning`
- 用户当前环境已验证：NumPy `2.5.2`、PyMuPDF `1.28.2`
- 已观察事实：
  - `src/litflow/rag/dense.py` 与 `windowed.py` 使用 NumPy；
  - CLI 顶层导入 Dense 路径，缺少 NumPy 时 `litflow --help` 曾失败；
  - Torch/Transformers 仅在 Dense `_Encoder` 内延迟导入；
  - 缺少 PyMuPDF/`fitz` 时 `test_reading_context.py` 曾有4项 skip；安装后该文件7项通过；
  - S01 将 PyMuPDF 记录为需要进一步确认边界的测试可选依赖。

以上均为待重新核验的起点，不得跳过源码检查直接改依赖。

## 3. 当前附件例外

用户会将以下文件作为本轮附件放入仓库根目录：

```text
LitFlow_DR-S02_Codex_Execution_Brief.md
```

若它是工作树唯一的未跟踪文件，视为已授权输入，不构成阻塞。核对内容后，在 Phase B 保留性移动为：

```text
docs/deep_research/sessions/DR-S02.md
```

如果出现其他 dirty/untracked 文件，停止，不得 clean、stash、reset、覆盖或顺手提交。

## 4. Phase A：只读预检

### 4.1 Git 与治理身份

执行并报告：

```powershell
git status --short --branch
git rev-parse HEAD
git rev-parse main
git rev-parse origin/main
git rev-parse "v1.0.0-mvp^{}"
git log -3 --oneline
git diff --check
```

读取所有适用 `AGENTS.md`，并完整读取：

```text
docs/deep_research/README.md
docs/deep_research/ROADMAP.md
docs/deep_research/FROZEN_BOUNDARIES.md
docs/deep_research/ASSET_MAP.md
docs/deep_research/TRACEABILITY_MATRIX.md
docs/deep_research/asset_inventory.json
docs/deep_research/SESSION_LOG.md
```

### 4.2 精确检查 packaging 现状

至少检查：

```text
pyproject.toml
requirements.runtime.lock
所有现有 requirements/constraints/lock 文件
Dockerfile
compose.yaml
tests/test_docker_packaging.py
tests/test_reading_context.py
src/litflow/cli.py
src/litflow/rag/dense.py
src/litflow/rag/windowed.py
Reading Context 对应生产模块与 CLI 命令
```

使用 `rg` 确认整个 `src/` 与 `tests/` 中：

- `numpy` / `np` 的所有直接 import；
- `fitz` / `pymupdf` 的所有直接或延迟 import；
- `torch` / `transformers` 的 import 边界；
- pytest 的 `importorskip`、skip marker 或 optional-dependency 判断；
- Docker 实际采用哪一个依赖文件安装。

### 4.3 只读环境记录

在当前 `.venv` 中只读记录：

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip show numpy pymupdf
.\.venv\Scripts\python.exe -m pip check
```

不要运行 `pip freeze` 后整体覆盖 lock，不升级 pip，不升级任何无关依赖。

### Phase A 停止条件

出现任一情况立即停止：

- Git/分支/tag 身份不符；
- 除 S02 附件外存在其他 dirty/untracked 内容；
- packaging 文件与 S01 资产地图有重大冲突；
- NumPy/PyMuPDF 的实际使用路径无法确认；
- 需要修改产品逻辑才能决定依赖层级；
- 现有依赖体系不是 pip/pyproject/requirements，继续会引入第二套包管理机制；
- 发现当前环境依赖损坏或不相关冲突。

全部通过后可直接继续 Phase B。

## 5. 依赖边界决策规则

### 5.1 NumPy

若重新核验仍确认 CLI 默认导入链需要 NumPy，则：

- NumPy 是 default runtime dependency；
- 必须同时反映在 `pyproject.toml` 的默认依赖和 Docker/Runtime 实际使用的 lock 中；
- 使用当前已验证且支持 Python 3.13 的版本 `2.5.2` 作为 lock 精确版本；
- `pyproject.toml` 的版本表达遵循仓库现有风格，不无理由把所有依赖改为相同 pin 策略。

不得在 S02 通过重构 CLI lazy import 来规避依赖声明；那是独立架构问题。

### 5.2 PyMuPDF

按证据选择且记录唯一结论：

#### A. Core runtime

满足任一项即可：

- 默认公开 CLI 功能直接需要；
- 生产模块默认导入；
- 文档将对应 Reading Context 功能定义为默认 Runtime 能力；
- Docker Offline/正式主链需要它。

处理：加入默认 `project.dependencies` 和 Runtime lock，lock 使用已验证版本 `1.28.2`。

#### B. Optional feature

满足全部条件：

- 仅特定 Reading Context/PDF 子功能需要；
- 生产代码是延迟导入；
- 缺失时能给出明确可操作错误；
- 默认 API/Docker Offline/CLI help 不需要。

处理：加入或复用合理的 optional extra，并保证正式开发/测试安装路径会安装它。不得把 optional extra 写入默认 Runtime lock，除非 Docker 或正式测试合同确实使用该 extra。

#### C. Test/development only

只有在生产源码完全不 import/调用 PyMuPDF 时才允许。处理：放入现有 test/dev 依赖层；若仓库没有 dev lock，不为一个包盲目引入新包管理体系，使用现有 optional dependency 机制并记录精确验证版本。

无论选择哪一类，都必须说明：package 名为 `PyMuPDF`，当前兼容 import `fitz` 存在弃用提醒；S02 不顺手迁移生产代码 import，除非不迁移会使所选依赖合同无法验证。若必须改 import，应停止并请求扩展授权。

### 5.3 明确排除

- Torch、Transformers、sentence-transformers、embedding model 不加入默认依赖；
- 不重建 Dense cache；
- 不因最新版本存在而升级 FastAPI、Pydantic、LangGraph、pytest 或其他包；
- 不修改 frozen retrieval 结论。

## 6. 允许修改范围

根据实际仓库结构，只允许修改：

```text
pyproject.toml
requirements.runtime.lock
现有的 test/dev requirements 或 lock（仅在确实存在且属于正确层级时）
tests/test_docker_packaging.py（优先扩展现有 packaging 合同测试）
或新增 tests/test_dependency_contract.py（二选一，只有现有测试不适合时）
docs/deep_research/sessions/DR-S02.md
docs/deep_research/DEPENDENCY_REPRODUCIBILITY.md
docs/deep_research/README.md
docs/deep_research/SESSION_LOG.md
```

如资产地图中的依赖缺口表述因本轮修复变成事实性过时，允许对以下文件做最小状态更新，但不得重写 S01 盘点历史：

```text
docs/deep_research/ASSET_MAP.md
docs/deep_research/TRACEABILITY_MATRIX.md
```

不修改 `asset_inventory.json` 的 S01 快照身份，也不修改 `baseline_manifest.json`。

## 7. 实施要求

### 7.1 声明修改

- 只增加经过核验缺失的直接依赖；
- 保持名称规范和稳定排序；
- Runtime lock 使用精确版本；
- pyproject 与 lock 的直接依赖不得互相矛盾；
- 不使用当前环境中无关的 transitive packages 填充 lock；
- 不整体重生成 lock 导致大范围版本漂移，除非仓库已有明确的官方生成命令且 diff 证明只发生预期变化。

### 7.2 回归保护

新增或扩展 packaging 测试，至少能防止：

- NumPy 再次从默认声明中消失；
- PyMuPDF 再次从被选定的依赖层级中消失；
- Runtime lock 与 pyproject 的直接依赖边界明显不一致；
- Torch/Transformers 被意外加入默认 Runtime。

测试不得依赖网络，不得仅因当前 `.venv` 已手动安装包而通过。

### 7.3 文档

`DEPENDENCY_REPRODUCIBILITY.md` 必须记录：

- 实际 import graph 结论；
- NumPy 与 PyMuPDF 的最终层级和理由；
- 当前验证版本；
- 默认安装、完整开发测试安装和可选 Dense 重建安装边界；
- fresh-environment 验证命令；
- Torch/Transformers 为何不在本轮安装；
- `fitz` 弃用提醒及未来迁移建议，但不冒充已迁移。

## 8. Fresh-environment 验证

### 8.1 临时环境安全要求

- 临时 venv 必须位于系统临时目录，不得放入仓库；
- 使用唯一、明确记录的目录；
- 不覆盖当前 `.venv`；
- 不修改全局 Python；
- 只安装本项目声明的依赖及验证所需 pytest；
- 清理时只允许删除本 Session 创建并核验过的精确临时目录；若路径身份不确定则保留并报告，不递归误删。

### 8.2 必须验证两条路径

#### Runtime/CLI 路径

在 fresh venv 中按仓库正式 Runtime 安装合同安装，然后验证：

```text
pip check
import numpy
python -m litflow.cli --help
```

若 PyMuPDF 被判定为 core runtime，还必须验证 `import pymupdf` 和项目当前实际 import 名称。

#### Development test 路径

按仓库正式开发/测试安装合同安装，运行：

```text
tests/test_models.py
tests/test_reading_context.py
tests/test_docker_packaging.py 或 dependency contract test
```

必须确认 Reading Context 不再因缺包 skip。若所选合同仍允许 skip，则说明依赖层级设计失败，不得提交。

网络下载若发生 timeout/SSL 重试，只有最终安装失败才算 blocked；不得因瞬时网络错误擅自改版本。

## 9. 当前环境回归

在现有 `.venv` 运行：

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q ".\tests"
git diff --check
git diff --cached --check
git status --short --branch
```

预期：

```text
268 passed, 1 warning
```

测试耗时不是冻结性能指标。

### Docker 边界

本 Session 不启动 Docker、不 build、不 pull。只通过 Dockerfile 和 packaging test 验证依赖文件引用。Linux 容器实际 build 留到后续 Docker/CI Session，避免把 S02 扩大成运行时部署验证。

## 10. 本轮禁止

- 不修改 `src/`、Prompt、Schema、Validator、Retriever、API、UI 或 Agent；
- 不写入或重建任何历史 `outputs/`；
- 不运行真实 LLM、Web、Zotero、Obsidian、PDF 处理、Dense 或 M8；
- 不修改 root README 的 `238 passed` 文案；
- 不安装 Torch/Transformers；
- 不升级无关依赖、pip 或 Python；
- 不创建新 tag；
- 不 reset、clean、stash、force push、prune；
- 不 push。

## 11. 验收标准

必须同时满足：

1. NumPy 的默认依赖声明与实际默认 import 链一致；
2. PyMuPDF 的依赖层级由生产代码、CLI、Docker、测试证据决定；
3. 当前环境不再是唯一能完整运行测试的隐式环境；
4. fresh Runtime 安装后 CLI help 可启动；
5. fresh Development 安装后 Reading Context 测试不 skip；
6. packaging 合同测试可阻止两个依赖再次漏声明；
7. Torch/Transformers 未进入默认 Runtime；
8. 无无关依赖版本漂移；
9. 现有正式测试仍为 `268 passed, 1 warning`；
10. 历史 outputs、M8、tag、Docker 和产品源码未修改；
11. 提交后工作树 clean；
12. 无外部模型调用和 push。

## 12. 提交要求

提交前展示：

```powershell
git diff --stat
git diff --check
git status --short --branch
```

确认范围正确后创建一个本地 commit：

```text
build: make Python dependency boundaries reproducible
```

提交后：

```powershell
git status --short --branch
git log -3 --oneline
```

不要 push。

## 13. 最终交接报告

### A. Session 结论

- `pass` / `blocked` / `failed`
- 是否解锁 DR-S03/DR-S04 合并设计批次
- 简历状态：`not_ready`

### B. Git 身份

- 起始、新 commit、分支、worktree、tag、push 状态

### C. 依赖边界决策

- NumPy 最终层级、版本、证据
- PyMuPDF 最终层级、版本、证据
- Torch/Transformers 排除证据

### D. 修改文件与依赖 diff

- 逐个文件用途
- 新增/变化的直接依赖；确认无无关漂移

### E. Fresh-environment 证据

- 临时环境路径
- 安装命令与 `pip check`
- CLI smoke
- 专项测试与 skip 数
- 临时目录是否安全清理

### F. 正式回归

- 全量 pytest
- diff checks
- 外部调用与 Docker 状态

### G. 风险与后续事项

- `fitz` 迁移、optional Dense、跨平台 wheel 等真实风险

### H. 冻结边界确认

- 源码、outputs、M8、tag、Docker 是否保持不变

### I. 下一步

- 仅判断能否进入压缩后的 `DR-S03/DR-S04：目标架构与实验治理冻结` 合并设计批次
- 不提前实施 Schema 或 Runtime

## 14. 简历状态

固定为：

```text
not_ready
```

S02 是可复现性修复，不应单独包装为 Agent 功能成果。
