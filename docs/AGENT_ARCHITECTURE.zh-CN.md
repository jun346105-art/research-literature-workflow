# Evidence-Bounded Research Agent

## M8A Contract

M8A 使用 `langgraph.graph.StateGraph` 建模单 Agent。节点为 `intake_guardrail`、`planner`、`policy_gate`、`tool_executor`、`evidence_verifier`、`coverage_router`、`human_approval`、`finalizer`。

Agent 负责工具选择和有限重规划；LitFlow 既有内核继续负责检索、Entity Binding、Citation Membership、Quote Grounding、Coverage 与最终展示安全。

## State

`ResearchAgentState` 位于 `src/litflow/agent/runtime.py`。它只保存 run-scoped short-term state：goal、tool calls、evidence refs、coverage、budget、pending approval、final status 和 trace。它不保存跨用户长期 memory，也不保存隐藏 Chain-of-Thought。

## Runtime Guarantees

- 默认最多 4 model turns、6 tool calls、2 retrieval calls。
- 同 tool 同 args 第二次出现时终止。
- `stage_writing_draft` 在执行前通过 LangGraph `interrupt()` 暂停，使用 `Command(resume=...)` 恢复。
- trace 保存 node、action、guardrail、result refs 和终止原因。
- `replay_agent_trace` 只读取 trace，不构造 planner 或 tools，也不调用外部 LLM。

## M8 Experimental Closure

M8A scaffold、M8B.1A durable event/replay kernel 与 M8B.1B progress-aware Fake E2E 已通过。M8B.1B 进一步将 provider tool call、approval 和 internal control-plane action 的身份分开记录，支持 hash-chained event log、state projection 与 canonical request replay。

唯一真实 Flash canary AG01 完成 `list_papers -> retrieve_evidence -> answer_grounded`，但最终 QA 严格 quote grounding 失败（`evidence_anchor_not_found`），因此未达到端到端 grounded answer gate。AG07/AG11 real canary、12-task pilot 与 stability 未运行。该 Agent 不得描述为生产可用或已通过任务完成基准。
