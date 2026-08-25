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
