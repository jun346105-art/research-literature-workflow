# DeepResearch 五分钟 Demo

默认 Demo 完全离线：首页首个示例读取已有的 single-paper 冻结 artifact；另两个示例只运行本地检索，不套用报告。服务端仍可按精确冻结任务问题读取 cross-paper 与 insufficient-evidence artifact。DeepResearch job 走现有 FastAPI 与 SSE 入口，不构造在线 client，也不需要 API Key。若本机没有相应 artifact，接口明确返回失败而不伪装为成功。

```mermaid
flowchart LR
  A[Approved Brief] --> B[Planner]
  B --> C[Local read-only Tool]
  C --> D[EvidenceGraph]
  D --> E[Grounding Validator]
  E --> F[Writer / Report Validator]
  F --> G[Terminal + replay]
```

## 启动

### Local demo assets

公开 checkout 可启动 UI，但不分发论文全文、`outputs/` 语料或完整运行 artifact。仅克隆仓库不会得到可用的完整冻结报告。安装 Python 依赖需要网络；已有本地数据的 Demo 运行与 replay 不调用 Provider。

当前数据加载合同见 [DemoAssets](../src/litflow_api/mvp.py)。本机需保留既有、经授权的本地 `outputs/rag_bm25_v1/passages.jsonl`；冻结报告还依赖 `outputs/deep_research/e2e/v1.2/<run_id>/` 下的原始 artifact，相关身份与摘要见[单篇正式结果](deep_research/REAL_SINGLE_PAPER_E2E_RESULT_V1.md)。这些路径相对仓库根目录。不要将私人语料或运行输出提交到 Git。

若没有这些资产，可查看 README 截图与已提交的结果记录；冻结任务会返回 `demo_artifact_unavailable`，不会生成替代答案。旧 CLI 样例与数据前提见[历史文档](archive/README.md)。

Windows 最短路径（使用项目 `.venv`）：

```powershell
.\scripts\start-demo.ps1
```

脚本会检查项目解释器与端口；若 8015 已有 LitFlow 服务，则直接打开现有地址。手动排障方式如下：

```powershell
$env:PYTHONPATH = "src"
python -m uvicorn litflow_api.app:app --host 127.0.0.1 --port 8015
```

创建离线任务：

```powershell
$job = Invoke-RestMethod http://127.0.0.1:8015/api/deep-research/jobs -Method Post -ContentType 'application/json' -Body '{"query":"What components does the cited paper state that WT-C3k2 combines?"}'
$jobId = $job.job_id
Invoke-RestMethod "http://127.0.0.1:8015/api/deep-research/jobs/$jobId"
Invoke-RestMethod "http://127.0.0.1:8015/api/deep-research/jobs/$jobId/result"
curl.exe "http://127.0.0.1:8015/api/deep-research/jobs/$jobId/events"
```

返回内容包含 run/provider/model、阶段状态、Planner/Tool/Writer 计数、Evidence/Claim/Citation 数量、grounding、token/cost/elapsed、artifact 相对定位和 replay 外部调用数。`publication_ready` 始终保守为 false。引用抽屉只显示有界 quote，不返回整篇原文。Tabler 1.4.0 CSS/JS 随项目本地提供，许可证在 `src/litflow_api/static/vendor/tabler-1.4.0/LICENSE.txt`。若旧页面显示浏览器默认样式，刷新页面并检查版本化 CSS 链接是否成功加载。

## 入口与边界

- API：`POST /api/deep-research/jobs`、`GET /api/deep-research/jobs/{job_id}`、`GET .../result`、`GET .../events`。
- Windows 启动脚本：`scripts/start-demo.ps1`。
- `/api/v1/*` 保留原有 MVP QA job；DeepResearch Demo 不创建第二套 Runtime。
- `mode=online` 会被明确拒绝；真实 Provider 仍只能通过已有受控 CLI、run 授权和环境变量完成。
- 浏览器和 API 不接受 Key；不返回 Authorization、原始 Provider 响应、reasoning、私人路径或论文全文。

## Windows 排障

| 现象 | 处理 |
|---|---|
| 页面无法连接 | 确认脚本仍在运行，并访问 `http://127.0.0.1:8015/`；用 `Get-NetTCPConnection -LocalPort 8015` 检查监听。 |
| 端口被占用 | 关闭占用 8015 的旧服务，或运行 `.\scripts\start-demo.ps1 -Port 8016`。 |
| `.venv` 不存在 | 在仓库根目录创建项目环境并安装 `requirements.runtime.lock`。 |
| Uvicorn 未安装 | 使用项目 `.venv`，不要调用系统 Python。 |
| `/` 返回 404 | 确认命令使用 `litflow_api.app:app`，且当前目录是仓库根目录。 |
| 静态资源失败 | 检查 `/static/app.js` 与 `/static/style.css` 是否均返回 200。 |
| 浏览器代理影响 localhost | 将 `127.0.0.1` 加入代理 bypass，或使用 `curl.exe` 复核本地服务。 |

## 推荐阅读路径

README → 本 Demo → [Evidence/Citation grounding](EVIDENCE_GROUNDING.zh-CN.md) → [检索评测与失败分析](evaluation/README.md) → [Provider 工程细节](providers/README.md)。

## Privacy and reproducibility

默认离线 Demo 与 replay 不构造在线模型 client；可选真实 Provider 执行通过受控 CLI 使用服务端环境凭据和显式 run 授权。DeepResearch 浏览器/API 不接收凭据，公开结果使用相对 artifact 定位与有界引句。不可变运行身份、checkpoint 和零外部调用 replay 保留执行过程。

## Scope and known issues

- 精确匹配且已安装的冻结任务可读取报告；其他问题走本地检索。语言切换只改变 UI，不翻译论文原文。
- 确定性引用锚定证明引句位置与归属，不替代人工语义审核，也不代表报告可直接发表。
- R1 的 held-out no-answer FP@10 为 1.0；后续阈值仅在 development 校准。完整数值、H007 重叠与失败分析见[评测文档](evaluation/README.md)。
- 固定预算下的 DeepSeek Writer 截断属于已记录的可靠性结果，详见 [Provider 文档](providers/README.md)。
- 当前范围是本地科研语料；不包含生产托管、账号/多租户服务、开放域 Web 研究、多模态或多 Agent 执行。
