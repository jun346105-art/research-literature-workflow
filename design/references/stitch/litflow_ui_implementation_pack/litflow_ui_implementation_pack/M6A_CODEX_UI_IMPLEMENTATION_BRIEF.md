# M6A：LitFlow Minimal UI Refinement

请使用本包中的：

- `reference/screen.png`
- `reference/STITCH_DESIGN_ORIGINAL.md`
- `LITFLOW_UI_DESIGN_SPEC.md`
- `AUDIT.md`

完成现有 LitFlow UI 的最小视觉闭环。

## 目标

在不修改后端能力的前提下，将现有原生 HTML/CSS/JavaScript UI 改造成可公开展示的 Calm Research Workbench。

Stitch 文件仅作为视觉参考，不作为数据、业务逻辑或可直接合并代码。

## 技能顺序

如果当前环境已有对应技能：

1. 使用 Impeccable 进行主要 UI 审计与精修；
2. 使用 UI UX Pro Max 检查响应式、可访问性和状态层级；
3. DESIGN.md collection 仅参考 Notion、Linear、Airtable、Mintlify、IBM 的原则；
4. Taste Skill 只用于完成后的只读 critique。

不使用 Shadcn，不迁移 React/Vue/Tailwind，不新增前端构建系统。

如果相关技能不可用，使用 `LITFLOW_UI_DESIGN_SPEC.md` 作为唯一规范继续实施，不得阻塞任务。

## 冻结边界

不得修改：

- `/api/v1` contract；
- QA Prompt、Schema、Validator；
- Retriever、Translation；
- Corpus、qrels、Evidence Matrix 数据；
- SSE 事件顺序；
- Job 持久化和恢复；
- citation/quote grounding；
- online/offline 执行逻辑。

不得复制 Stitch 中的虚构数据、ID、论文、状态或 passage 文本。

## 实施范围

只允许修改：

- 现有 HTML；
- 现有 CSS；
- 为展示、drawer、focus management 和响应式行为所必需的最小原生 JavaScript；
- UI 专项测试与截图自动化；
- UI 设计说明文档。

不得增加新的产品功能或业务 API。

## 必须完成

1. 桌面三栏 Research Workbench；
2. 中间区按照 Query → Route → SSE → Result → Claim → Citation → Limitation 排列；
3. Citation 点击更新右侧 Evidence Inspector；
4. 中间展示短 quote，Inspector 展示完整 passage；
5. 修复 offline/online 状态矛盾；
6. 已有结果始终展示原始 query；
7. 真实 passage ID 与 job ID 严格区分；
8. 支持 Verified、Partial、Insufficient、Failure、Loading、Recovered；
9. 保留 Evidence Matrix 与 Bilingual Writing Draft 页面；
10. 1024px 以下 Inspector 转 drawer，768px 为单栏主视图；
11. 修复长标题、citation key、passage ID 与中英文文本溢出；
12. 保留 job 刷新恢复和现有 citation drawer 能力。

## 验收

使用真实 API 和历史 artifact 截图：

- Offline Demo；
- Q01 成功 job 恢复；
- Citation Inspector；
- Partial；
- Insufficient Evidence；
- Technical Failure；
- Evidence Matrix；
- Bilingual Writing Draft；
- 1280px；
- 768px。

检查：

- 浏览器 console 无错误；
- 键盘 focus 可见；
- 状态不只依赖颜色；
- 无横向页面滚动；
- FastAPI、SSE、job 恢复与验证逻辑不回归。

运行：

- UI 专项测试；
- FastAPI 专项测试；
- 全量测试；
- `git diff --check`。

输出：

1. 修改文件；
2. before/after 截图；
3. 各状态截图；
4. 响应式与可访问性结果；
5. 保留功能清单；
6. 测试与 commit；
7. `main == origin/main`；
8. worktree clean。

完成后停止 UI 设计迭代，进入 M6 Docker/Public Demo Packaging。
