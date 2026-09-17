# Documentation / 文档索引

[English homepage](../README.md) · [中文首页](../README.zh-CN.md)

## Use LitFlow

- [Demo setup, local assets, privacy and scope](DEEPRESEARCH_DEMO.md).
- Evidence grounding: [English](EVIDENCE_GROUNDING.md) / [中文](EVIDENCE_GROUNDING.zh-CN.md).
- Concepts: [English](CONCEPTS.md) / [中文](CONCEPTS.zh-CN.md).
- [Troubleshooting](TROUBLESHOOTING.md), [API reference](API.md), [Docker Demo](DOCKER_DEMO.md).
- Literature CLI workflow: [end-to-end guide](END_TO_END_WORKFLOW.md), [discovery-file workflow](PAPER_SEARCH_PRO_SKILL_WORKFLOW.md), [example file contracts](../examples/README.md).

## Results and implementation

- [Evaluation methodology and failure analysis](evaluation/README.md).
- [Provider capabilities and recorded outcomes](providers/README.md).
- [DeepResearch architecture](deep_research/ARCHITECTURE.md) and [engineering/research record index](deep_research/README.md).
- [Dependency reproducibility](deep_research/DEPENDENCY_REPRODUCIBILITY.md).
- Earlier Agent contracts: [architecture](AGENT_ARCHITECTURE.zh-CN.md), [tools](AGENT_TOOLS.zh-CN.md), [M8 closure](../M8_AGENT_EXPERIMENT_CLOSURE.zh-CN.md).
- Earlier runtime design: [durable-event schema](agent_references/DURABLE_AGENT_EVENT_SCHEMA_V2.md), [repair report](agent_references/M8B1A_RUNTIME_REPAIR_REPORT.md), [ADR](agent_references/M8B1_ADR.md), [design mapping](agent_references/M8B1_DESIGN_MAPPING.md), [harness audit](agent_references/OPEN_SOURCE_HARNESS_AUDIT.zh-CN.md).

## Presentation and history

- [Historical documents, releases, career narratives and UI designs](archive/README.md).
- Earlier MVP recording aids: [Demo checklist](DEMO_CHECKLIST.md), [Demo script](DEMO_SCRIPT.md).
- Architecture illustrations: [English](screenshots/litflow-architecture.svg) / [中文](screenshots/litflow-architecture-zh.svg).
- Current Tabler screenshots: [English home](screenshots/litflow-v1.3-home-en.png), [中文首页](screenshots/litflow-v1.3-home-zh.png), [English result](screenshots/litflow-v1.3-result-en.png), [中文结果](screenshots/litflow-v1.3-result-zh.png), [evidence inspector](screenshots/litflow-v1.3-evidence-open.png), [mobile](screenshots/litflow-v1.3-mobile-390.png).
- [v1.3.1 candidate cleanup decisions](engineering/PUBLIC_REPO_CLEANUP.md).

Frozen Session, Traceability, Round/Gate/Attempt, schemas and manifests remain at their original paths under `deep_research/`. Historic root-path mentions are resolved by the cleanup record's move table; frozen records keep their original meaning.

## License status

No repository-level license is currently declared; the maintainer has not yet chosen one. No project license is added by this cleanup. Public availability alone is not a project license grant.

Bundled Tabler assets keep their [MIT license](../src/litflow_api/static/vendor/tabler-1.4.0/LICENSE.txt) and [distribution manifest](../src/litflow_api/static/vendor/tabler-1.4.0/manifest.json). That notice applies to those assets, not automatically to LitFlow as a whole.
