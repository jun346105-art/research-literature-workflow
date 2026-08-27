# DeepResearch Contracts v1

`research_contract_bundle.schema.json` is the deterministic Pydantic v2 JSON Schema for `ContractBundle` under contract version `dr-contracts-v1`.

Regenerate to a temporary directory with `litflow.deep_research.schema_export.write_contract_schemas()` and compare bytes with the committed file. Tests perform that comparison without overwriting the repository artifact. The schema defines contracts only; it is not a runtime, provider request format, event format, or output artifact.
