# DeepResearch Experiment Governance

## Data and execution strata

| Stratum | Permitted purpose | Prohibited inference |
| --- | --- | --- |
| fake | deterministic state, safe-failure and replay tests | real-provider quality |
| canary | small real transport/grounding fault discovery | final performance claim |
| dev | diagnosis and bounded iteration | held-out result |
| heldout | frozen comparative evaluation | prompt, threshold or schema tuning after results |
| public_benchmark | externally comparable result with license/adapter note | equivalence to internal benchmark |

## Run identity and artifacts

Every future real run records `run_id`, schema version, Git commit, clean-worktree policy, input/task hashes, resolved provider/model mode, prompt/template hashes, tool/retriever versions, budgets/retry policy, timestamps and artifact contract version. It never records an API key, complete environment value or private absolute path.

The planned layout is defined in [ARCHITECTURE.md](ARCHITECTURE.md). Failed runs retain a failure artifact; retries count toward budget and never overwrite prior artifacts.

## Metrics and termination

- task: grounded completion, safe abstention, execution failure;
- claim: coverage, support/contradiction and unsupported leakage;
- citation: membership and quote/span/region grounding;
- trajectory: steps, replan, retry, cache, resume/replay;
- efficiency: provider calls, tokens, wall time and cost;
- human: pass/minor/major/reject.

LLM-as-Judge is supplementary only. Deterministic grounding and human review remain decisive. Every run ends structurally as complete, insufficient evidence, failed or cancelled; budgets and replan caps prevent unbounded work.

## Approval gates

- S05–S18 default to fake/offline.
- **Gate A:** real LLM canary only after Fake success/abstain/timeout/replan, budget/retry/cancel/checkpoint tests, immutable plan/manifest, and explicit user approval of provider/model/task count/max budget.
- **Gate B:** Web only after an explainable grounded local canary and unchanged citation/quote/coverage validators.
- Held-out runs require frozen manifest, data hashes, config and thresholds before results are viewed.
- Multimodal, Multi-Agent and Critic require pre-registered controls and retention thresholds. Multi-Agent/Critic remain outside the default path without demonstrated net benefit and no grounding regression.

## Stop-loss rules

Stop rather than relax validators when historical output/tag/held-out leakage appears, two sessions advance only by validator relaxation, or two real runs yield no new diagnosis. A failure classification is a valid result; it is not permission to overwrite artifacts or retry indefinitely.
