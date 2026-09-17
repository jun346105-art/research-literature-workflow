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

README → 本 Demo → Evidence/Citation grounding → 检索评测 → Provider Adapter 工程细节。
