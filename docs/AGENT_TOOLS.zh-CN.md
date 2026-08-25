# M8A Agent Tool Contracts

| Tool | Permission | Schema | M8A 行为 |
| --- | --- | --- | --- |
| `list_papers` | read_only | language/title_keyword/year | 仅 paper metadata |
| `retrieve_evidence` | read_only | query/top_k<=10 | 仅 ID/title/page/score/snippet |
| `inspect_passages` | read_only | passage_ids，最多 3 | 完整 passage 与 SHA |
| `answer_grounded` | read_only_model_call | query_id | M8B 才接真实 QA v1.2 |
| `query_evidence_matrix` | read_only | topic/paper_keys/categories | 仅 reviewed records |
| `stage_writing_draft` | approval_required | record_ids | 必须 interrupt，M8A 仅 Fake artifact |

Policy Gate 在 `src/litflow/agent/runtime.py:_policy_gate` 中执行 allowlist、Pydantic args、tool/retrieval budget、重复调用和 approval 检查。Qrels、Gold、shell、任意路径、任意 URL、写 Obsidian、写 corpus 都没有 Tool Contract，因此必然 `tool_not_allowed`。
