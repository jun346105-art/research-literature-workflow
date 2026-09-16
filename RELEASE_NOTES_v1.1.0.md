# LitFlow v1.1.0 — DeepResearch local demo release

## Included

- Minimal DeepResearch FastAPI job facade with status, result and SSE event endpoints.
- Offline closure replay demo using the frozen single-paper artifact; no Provider key or network is needed.
- Reuse of existing MVP persistence, artifact boundaries, Evidence/Citation grounding and replay contracts.
- Provider hardening from Round 5: explicit budgets, capability profiles, error classes, offline doctor and one-command controlled execution script.
- R1 retrieval foundation and human-reviewed pilot documentation remain frozen and unchanged.

## Evidence and limits

- GLM-5.3-Flash single-paper, source-scoped cross-paper and obvious out-of-domain abstention results are recorded under their documented scopes.
- DeepSeek paired execution is retained as a known Writer truncation case under the fixed 4096/high-reasoning budget; no model-quality ranking is claimed.
- Semantic correctness, publication readiness, open-domain/Web research, multimodal, Multi-Agent, public deployment and multi-user security are not validated by this release.

## Quick start

See [DeepResearch Demo](docs/DEEPRESEARCH_DEMO.md) for the five-minute local API/UI walkthrough, or run the existing localhost-only Docker Offline Demo in [Docker Demo](docs/DOCKER_DEMO.md).
