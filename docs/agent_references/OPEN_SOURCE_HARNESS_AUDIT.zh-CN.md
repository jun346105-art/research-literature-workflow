# Open-Source Harness Audit for M8B.1

> Status: conceptual_reference_only. No upstream source code, dependency, runtime, or license-bearing implementation was copied into LitFlow.

## Audit snapshot

| Source | Audit commit | License | Read files / official docs |
| --- | --- | --- |
| [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) | `b150a551b8d465e31e418e1b2eaf5e79bbb7d28e` | MIT | `README.md`, `docs/architecture.md`, `docs/agent-lifecycle.md`, `docs/tool-execution-pipeline.md`, `packages/core/agent-loop/README.md`, `packages/core/agent-loop/src/tool-calls.ts`, `packages/core/tools/README.md`, `LICENSE` |
| [LangChain Deep Agents](https://github.com/langchain-ai/deepagents) | `dfde21e379201c833da4162444ef4a13b46980fd` | MIT | `README.md`, `libs/ARCHITECTURE.md`; requested HITL implementation path was not present at the documented raw path, so implementation-specific claims are not made |
| [PydanticAI](https://github.com/pydantic/pydantic-ai) | `bfa8e9187b86aad7ec583665ab2743fadea458b1` | MIT | `docs/agent.md`, Usage Limits section |
| [LangGraph](https://github.com/langchain-ai/langgraph) | `38031739e551638e373fb553453256c23feeb41f` | MIT | official Graph API, persistence, and interrupt documentation |

## Concepts adopted or adapted

- **DeepSeek Harness:** turn is a bounded interaction; step is one model request plus its tool batch. Durable event order, model-order tool results, immutable post-policy outcomes, and the invariant “model-visible means logged” are directly relevant concepts.
- **Deep Agents:** LangGraph remains the runtime while a thin control plane can compute request-time tool visibility from typed state. LitFlow adopts only this separation of concerns.
- **PydanticAI:** hard request/tool/token limits prevent runaway runs, while a lower soft budget should redirect a normal task toward grounded wrap-up rather than label a useful partial state as an execution failure.
- **LangGraph:** retain `StateGraph`, conditional routing, `interrupt`, `Command(resume=...)`, and checkpointing; do not introduce a replacement runtime.

## Explicit rejections

DeepSeek Harness: Cordis plugin runtime, TypeScript runtime, Web UI, generic filesystem/shell, sandbox, scheduling, subagents/agent teams, and community plugins are rejected. Deep Agents: subagents, filesystem backend, shell/code execution, long-context file management, and generic coding-agent prompts are rejected. PydanticAI is not added as a dependency and does not replace LitFlow Pydantic schemas or LangGraph.

## Why the scope is narrower

LitFlow is a domain-constrained evidence workflow. The required control plane is durable, replayable tool progress and bounded termination; it does not require a general-purpose coding-agent capability surface. No architecture decision here is based on repository popularity or GitHub stars.
