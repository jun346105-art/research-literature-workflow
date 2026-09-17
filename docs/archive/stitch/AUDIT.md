# LitFlow Stitch Export Audit

## 审计结论

上传的 `stitch_litflow_research_workbench.zip` 是设计参考包，不是可直接运行或合并的前端工程。

包内仅包含：

- `screen.png`：1127 × 944 的视觉参考图。
- `DESIGN.md`：Stitch 生成的设计系统说明。

未包含：

- HTML、CSS 或 JavaScript；
- React/Vue 等框架代码；
- `package.json` 或构建系统；
- FastAPI 集成；
- LitFlow 的真实 API、状态或数据绑定。

因此本包应作为只读视觉输入使用，不能覆盖现有 LitFlow UI。

## 可采用内容

- 三栏 Research Workbench 信息架构；
- 克制的青绿色视觉方向；
- 高信息密度、低阴影、细边框的研究工具风格；
- Evidence Inspector；
- Claim、Citation、Source Passage 的层次；
- 4px 基线间距系统；
- Verified、Partial、Insufficient、Failure 的语义状态。

## 不可采用内容

- 截图中的静态论文、回答、ID、状态或 passage 文本；
- 截图中互相矛盾的 `offline_demo` 与 `Online QA` 状态；
- 任何将 job ID 伪装成 passage ID 的内容；
- 未经真实 API 返回的数据；
- 外部字体或图标依赖，除非完成许可与离线可用性检查；
- 新前端框架或构建系统。

## 原始文件身份

- 原 ZIP SHA-256：`749eaba9e4f5a23e402a7e303f02b31dd2638f6c5b2b3758b3b9135350231a41`
- 原 `DESIGN.md` SHA-256：`cd16fc59cf7828f2a8b790086a5c14395caab63edea7f1fb80566b0bec1f9820`
- 原 `screen.png` SHA-256：`dc0b6306fb8bd787daf67ae191f5218f521c4ac0f152a0b249906691a99de1b2`
