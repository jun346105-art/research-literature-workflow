# LitFlow UI Design Specification

版本：MVP UI v1
状态：Implementation-ready
适用范围：现有 FastAPI + 原生 HTML/CSS/JavaScript UI

## 1. 产品界面定位

LitFlow 是面向工科研究场景的本地优先、证据驱动、双语文献研究写作 Copilot。界面应呈现为 **Calm Research Workbench**，而不是聊天机器人、营销落地页或通用知识问答工具。

界面的首要任务是让用户清楚地区分：

1. 用户提出了什么研究问题；
2. 系统使用了哪条语言与检索路径；
3. 当前运行处于什么阶段；
4. 哪些陈述得到了证据支持；
5. 每条证据来自哪篇论文、哪一页、哪个 passage；
6. 哪些内容仅得到部分覆盖或证据不足；
7. 哪些失败属于检索、生成、引用或系统执行问题。

## 2. 设计原则

### 2.1 证据优先

回答不是视觉终点。Claim、Citation、Evidence Quote、Source Passage 与验证状态必须构成可追踪的阅读路径。

### 2.2 状态诚实

必须显式区分：

- `answered / verified`
- `partial_answer`
- `insufficient_evidence`
- `technical_failure`
- `offline_demo`
- `online_qa`
- `persisted_job_recovered`

状态不能只依赖颜色表达。

### 2.3 本地优先

离线模式不得读取 API key、构造 LLM client 或暗示在线能力。在线模式必须显示实际路由与执行进度。

### 2.4 高密度但不拥挤

页面服务于长时间研究工作。优先使用清晰层级、细分隔线、可折叠区域和上下文 Inspector，避免卡片堆叠和大片装饰性留白。

### 2.5 渐进披露

中间区展示 Claim、短证据和 Citation；完整 metadata、anchor 状态和完整 passage 放入右侧 Evidence Inspector，避免重复。

## 3. 桌面信息架构

### 3.1 顶部栏

必须包含：

- LitFlow 品牌；
- 当前工作区名称；
- `Offline Demo` 或 `Online QA`，二者只能出现一个；
- 可选的持久化 job 恢复提示；
- 帮助或文档入口。

禁止将环境、连接和执行状态混为一个模糊徽标。

### 3.2 左侧导航

建议宽度：248–272px。

导航顺序：

1. New Research Query
2. Corpus / Papers
3. Language Route / Filters（仅在真实功能存在时）
4. Saved Jobs / Queries（仅在真实功能存在时）
5. Evidence Matrix
6. Bilingual Writing Draft
7. Settings / Documentation

不得为了匹配截图伪造未实现功能。不存在的入口应删除或明确标记为只读演示。

### 3.3 中央工作区

中央工作区是页面主视图，最小宽度建议为 560px。

信息顺序固定为：

1. 原始 Query
2. 执行按钮或历史 Job 身份
3. Language / Translation / Retrieval Route
4. SSE 进度
5. 最终状态摘要
6. Answer / Partial Answer / Insufficient / Failure
7. Verified Claims
8. Citation Chips 与短 Evidence Quote
9. Limitations

已有结果时必须同时显示原始 Query，不能出现“输入框为空但已有回答”的状态。

### 3.4 右侧 Evidence Inspector

桌面建议宽度：340–400px。

选中 Citation 后展示：

- Paper Title
- Citation Key
- Page Range
- 真实 `passage_id`
- `paper_key`
- Anchor Status
- Evidence Quote
- Full Source Passage
- Copy Citation / Open Passage 等已有动作

中间区只展示短 quote，右侧才展示完整 passage。Citation key、passage ID 与长论文标题必须使用安全换行。

## 4. 子页面

### 4.1 Evidence Matrix

使用数据库/表格型界面，不嵌入主问答屏幕。

建议列：

- Paper / Citation
- Category
- Claim
- Verified Evidence
- Coverage
- Review Status
- Page / Passage

必须显式展示稀疏字段为“尚无已审核证据”，不能将空值伪装成完整信息。

### 4.2 Bilingual Writing Draft

建议结构：

- Outline
- 中文草稿
- 英文草稿
- Sentence Evidence Ledger
- Coverage / Limitations

中英文句子必须保留相同的 `sentence_id` 与 EvidenceRecord bindings。明确显示 `author-editable draft`，不得标记为 publication-ready。

## 5. 视觉系统

### 5.1 Canonical Design Tokens

```css
:root {
  --lf-bg: #f7faf9;
  --lf-surface: #ffffff;
  --lf-surface-subtle: #f0f5f3;
  --lf-surface-muted: #e7eeeb;
  --lf-text: #17201e;
  --lf-text-muted: #52605d;
  --lf-border: #cbd7d3;
  --lf-border-subtle: #e0e8e5;

  --lf-primary: #0f766e;
  --lf-primary-hover: #115e59;
  --lf-primary-soft: #ccfbf1;

  --lf-verified: #15803d;
  --lf-verified-soft: #dcfce7;
  --lf-partial: #b45309;
  --lf-partial-soft: #fef3c7;
  --lf-insufficient: #475569;
  --lf-insufficient-soft: #e2e8f0;
  --lf-failure: #b91c1c;
  --lf-failure-soft: #fee2e2;

  --lf-radius-sm: 3px;
  --lf-radius-md: 6px;
  --lf-radius-lg: 8px;
  --lf-space-1: 4px;
  --lf-space-2: 8px;
  --lf-space-3: 12px;
  --lf-space-4: 16px;
  --lf-space-6: 24px;
  --lf-space-10: 40px;
}
```

### 5.2 Typography

默认不依赖公网字体。推荐系统栈：

```css
--lf-font-sans: Inter, "IBM Plex Sans", "Noto Sans SC", "Microsoft YaHei", system-ui, sans-serif;
--lf-font-mono: "JetBrains Mono", "Cascadia Code", "SFMono-Regular", Consolas, monospace;
```

字体规则：

- 页面标题：20–24px / 600；
- 区块标题：16–18px / 600；
- 主体研究文本：14–16px，行高不低于 1.55；
- metadata：12–13px；
- 技术 ID：12px monospace；
- monospace 只用于 ID、SHA、Citation Key 和原文 quote，不用于整段回答。

### 5.3 形状与层级

- 以 1px 细边框和浅表面层级区分区域；
- 避免大面积阴影；
- 输入与按钮 4–6px 圆角；
- Evidence Card 使用左侧语义色边框；
- Badge 必须包含文本或图标，不使用纯色圆点单独传达意义。

## 6. 状态呈现

| 状态 | 颜色 | 必须显示的文本 |
|---|---|---|
| Verified | Green | 已验证 / Verified |
| Partial | Amber | 部分回答 / Partial evidence |
| Insufficient | Slate | 证据不足 / Insufficient evidence |
| Technical failure | Red | 技术执行失败 / Technical failure |
| Offline | Neutral | 离线演示 / Offline demo |
| Online | Teal | 在线问答 / Online QA |
| Recovered | Blue-gray | 已恢复历史任务 / Recovered job |

失败状态不得显示未经验证的模型回答。Partial 必须列出已覆盖与未覆盖实体。

## 7. 响应式行为

### ≥ 1280px

- 三栏：左导航 + 中央工作区 + Evidence Inspector。

### 1024–1279px

- 左导航缩窄或折叠；
- 中央工作区为主；
- Evidence Inspector 变为可打开的右侧 drawer。

### ≤ 767px

- 单栏中央工作区；
- 左导航使用 menu drawer；
- Evidence Inspector 使用全高 drawer 或 bottom sheet；
- Citation chips 可换行；
- 页面不得出现横向滚动。

## 8. 可访问性

- 普通正文和背景满足 WCAG AA；
- 所有交互元素有可见键盘焦点；
- Drawer 打开后管理焦点并支持 Escape 关闭；
- 状态使用文本、图标与颜色共同表达；
- SSE 进度使用适当的 live region，但避免重复播报；
- 按钮、链接与只读标签语义明确；
- 长中文、英文、citation key 和 passage ID 均可选择和复制。

## 9. 数据与安全边界

- 页面只绑定当前 FastAPI 真实响应；
- 不复制 Stitch 截图中的静态论文、回答、ID 或状态；
- `passage_id` 不得使用 job ID 替代；
- Offline 模式不读取密钥，不构造 LLM client；
- qrels、gold summary 和未检索内容不得进入在线回答；
- validation failure 只能显示安全降级或技术错误；
- 不增加 CORS wildcard；
- 不在响应或页面中暴露绝对路径、密钥或内部错误堆栈。

## 10. MVP UI 验收场景

必须用真实数据验证：

1. Offline Demo 首页；
2. Q01 成功 Job 恢复；
3. 选中 Citation 后的 Evidence Inspector；
4. Partial Answer（含已覆盖和未覆盖实体）；
5. Insufficient Evidence；
6. Technical Failure 安全状态；
7. Evidence Matrix；
8. Bilingual Writing Draft；
9. 1280px；
10. 768px。

验收同时要求：浏览器 console 无错误、无横向溢出、现有 API/SSE/Job 恢复行为不变。
