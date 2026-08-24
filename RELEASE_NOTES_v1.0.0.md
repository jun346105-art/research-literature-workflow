# LitFlow v1.0.0 MVP - Evidence-Grounded Bilingual Research Writing Copilot

## Release Scope

LitFlow v1.0.0 packages a local-first MVP for engineering literature. It combines page-provenanced clean context, language-aware retrieval, evidence-grounded QA, evidence/writing views, a native FastAPI workbench, and a localhost-only Docker demo.

## Highlights

- Human-reviewed bilingual retrieval pilot with machine translation -> BM25-EN Recall@10 `0.7157` versus BM25-ZH-raw `0.6275`.
- Evidence-grounded QA with strict citation membership, quote grounding, claim-citation coverage, partial-answer handling, and human review.
- Evidence Matrix and bilingual author-editable method-comparison draft with `publication_ready=false`.
- FastAPI/SSE, persisted job restoration, Evidence Inspector, and responsive native UI.
- Docker Offline Demo: non-root runtime user, read-only root filesystem, read-only inputs, localhost-only default binding, and explicit Online QA profile.

## Validation Summary

- QA grounded answer success: `9/17` answerable pilot queries.
- Displayed answers author-reviewed as usable: `9/9`.
- Displayed citation validity, strict quote grounding, and claim coverage: `100%`.
- No-answer abstention: `3/3`.
- Docker image: about `54.54 MB`; startup to health: `1.20s`; health latency: `142.04ms`.

## Boundaries

These are small human-reviewed pilot results, not a large-scale benchmark. LitFlow is not cloud hosted, not a multi-user SaaS, and not an automatic publication-ready paper generator. Retrieval and QA availability limits remain visible by design.

## Getting Started

```powershell
$env:LITFLOW_DEMO_INPUT_DIR = (Resolve-Path .\outputs)
docker compose up --build
```

See [Docker Demo](docs/DOCKER_DEMO.md), [Demo Checklist](docs/DEMO_CHECKLIST.md), and [Interview Guide](docs/INTERVIEW_GUIDE.zh-CN.md).
