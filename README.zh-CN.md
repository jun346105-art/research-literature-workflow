# LitFlow Research Copilot

[English](README.md) | [简体中文](README.zh-CN.md)

[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](pyproject.toml) [![FastAPI](https://img.shields.io/badge/FastAPI-local%20API-009688.svg)](docs/API.md) [![Tests](https://github.com/jun346105-art/research-literature-workflow/actions/workflows/tests.yml/badge.svg)](https://github.com/jun346105-art/research-literature-workflow/actions/workflows/tests.yml)

> **把本地科研文献转化为可对照原文检查的研究回答。**

LitFlow 在本地研究工作台中连接文献检索、证据检查与带引用的研究报告。

![LitFlow Research Copilot Tabler 中文界面](docs/screenshots/litflow-v1.3-home-zh.png)

## 为什么使用 LitFlow

- **沿着结论找到原文。** 打开引用，即可检查论文、页码、原文片段与支持引句。
- **看清证据缺在哪里。** 部分结果与证据缺口帮助你决定下一步阅读或核验什么。
- **回看结果如何产生。** 保存的 artifact、checkpoint 与离线 replay 保留报告背后的执行过程。

## 一个可核验示例

**问题：** 论文指出 WT-C3k2 结合了哪些组件？

**已记录的结论：** WT-C3k2 结合 WTConv 的频率处理与 C3k2 路径，并在特征融合后保留通过 1 × 1 卷积实现的 bottleneck。

**来源：** *Merge-YOLO: An accurate detection model for book packaging defects in intelligent logistics scenarios*，第 6 页，passage `DZ6TYBIQ_chunk_0008`。

> “The bottleneck layer is implemented through 1 × 1 convolution, reducing the dimension of the feature map...”

打开引用，将结论与已锚定的引句及原文上下文对照。详见[已记录的单篇论文结果](docs/deep_research/REAL_SINGLE_PAPER_E2E_RESULT_V1.md)。

![LitFlow 可检查证据的结果页](docs/screenshots/litflow-v1.3-result-zh.png)

安装本地 Demo 数据后，冻结示例展示完整报告，自定义问题展示本地证据检索。安装与示例说明见 [Demo 指南](docs/DEEPRESEARCH_DEMO.md)。

## 五分钟 Quickstart

在仓库根目录操作，使用 Python 3.13：

**Windows PowerShell**

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\scripts\start-demo.ps1
```

**Linux / macOS**

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -e .
PYTHONPATH=src .venv/bin/python -m uvicorn litflow_api.app:app --host 127.0.0.1 --port 8015
```

打开 <http://127.0.0.1:8015/>。默认 Demo 无需 API Key，也不会调用 Provider。安装过程需要下载 Python 依赖，Demo 运行过程离线。带数据的交互需要本地语料与运行 artifact，这些文件未随公开仓库分发。详见[本地数据要求](docs/DEEPRESEARCH_DEMO.md#local-demo-assets)与[排障指南](docs/TROUBLESHOOTING.md)。

## 工作流程

```mermaid
flowchart LR
  A[本地论文] --> B[带页码的原文片段]
  B --> C[检索与本地工具]
  C --> D[EvidenceGraph]
  D --> E[带引用报告]
  E --> F[Grounding 验证]
  F --> G[研究工作台]
```

有界报告流程包含 Planner、本地只读 Executor 与 Writer。程序分配证据身份，并在展示报告前校验引用归属与原句锚定。详见[系统架构](docs/deep_research/ARCHITECTURE.md)。

## 评测亮点

R1 在本地科研语料上冻结了 **32 条 development + 16 条 held-out 查询**。BM25-EN 仅根据 development 选出，随后在 held-out 上执行一次评测。

| Held-out 检索指标 | 结果 |
|---|---:|
| Recall@10 | **84.0%** |
| nDCG@10 | **68.9%** |
| Answerable success@10 | **100%** |

这些指标衡量冻结语料上的检索表现；answerable success 指找到相关证据，不等于生成正确回答。[查看完整评测方法与失败分析 / View the full evaluation methodology and failure analysis](docs/evaluation/README.md)。

## 工程能力

- **证据流程：** 带页码溯源的 Zotero/PDF 摄取、BM25/Dense/Hybrid 评测与确定性引用验证。
- **本地应用：** FastAPI jobs、SSE 进度、结果持久化与响应式中英文 Tabler 界面。
- **Provider 集成：** 感知能力差异的 adapter、显式 Planner/Writer 预算、统一错误、有限重试与零外部调用 replay。[Provider 能力与已记录结果](docs/providers/README.md)。

## 隐私与可复现性融入设计

研究输入与运行 artifact 保存在本地工作区。默认 Demo 和 replay 离线运行；可选模型执行通过受控 CLI 使用服务端环境变量凭据。公开结果视图使用相对 artifact 定位与有界证据摘录，不可变运行身份和 checkpoint 让执行过程可检查。详见[隐私与执行说明](docs/DEEPRESEARCH_DEMO.md#privacy-and-reproducibility)。

## 文档入口

| 从这里开始 | 深入了解 |
|---|---|
| [启动 Demo](docs/DEEPRESEARCH_DEMO.md) | [系统架构](docs/deep_research/ARCHITECTURE.md) |
| [检查引用证据](docs/EVIDENCE_GROUNDING.zh-CN.md) | [API 参考](docs/API.md) |
| [常见排障](docs/TROUBLESHOOTING.md) | [评测](docs/evaluation/README.md) · [Providers](docs/providers/README.md) |
| [能力边界与已知问题](docs/DEEPRESEARCH_DEMO.md#scope-and-known-issues) | [全部文档](docs/README.md) |

当前版本聚焦本地科研语料、证据检索和可核验研究报告；完整能力边界与已知问题见项目文档。

## 许可状态

项目级 License 尚待维护者选择。详见[许可状态与第三方声明](docs/README.md#license-status)；随项目提供的 Tabler 资源保留其 MIT 许可证。
