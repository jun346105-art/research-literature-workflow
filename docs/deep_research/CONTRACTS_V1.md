# DeepResearch Domain Contracts v1

## Scope

B01 implements immutable, strict Pydantic v2 contracts under `src/litflow/deep_research/`: ResearchTask, ResearchBrief, BriefApproval, ResearchSubtask, Source, EvidenceLocator, EvidenceUnit, Claim, Citation and ContractBundle. They are an `internal_result`, not a completed DeepResearch runtime.

## Ownership and identity

The program creates IDs through deterministic canonical JSON plus SHA-256, with a type prefix and a 24-hex digest fragment. The fragment provides a stable compact identifier, not an authentication or collision-proof security guarantee. Persisted/replayed objects may parse existing IDs, but production creation uses the program factories.

All durable models reject extra fields, normalize ordinary strings, reject blank values, require UTC-aware datetimes, and use explicit `dr-contracts-v1`. Durable facts are frozen; a changed Brief or evidence record is represented by a new contract object rather than silent mutation.

## Contract boundaries

- Task/Brief/Subtask describe intent and a dependency DAG, not runtime status, budget or worker identity.
- Source has a portable canonical reference and content hash, never a private absolute path.
- EvidenceUnit contains verbatim groundable content and a locator; Claim is separate derived assertion; Citation links Claim to Evidence.
- Text locators require a passage ID and may use a text span. Region locators are a planned schema capability only: they require page+bbox+coordinate space and perform no OCR, crop or VLM work.
- ContractBundle checks task ownership, approval records, unique IDs, DAG cycles, source/evidence/claim/citation references, content hashes and quote/span correspondence.

Semantic support, claim coverage, final display validation, run state, events, budgets, provider calls and artifact execution remain outside B01.
