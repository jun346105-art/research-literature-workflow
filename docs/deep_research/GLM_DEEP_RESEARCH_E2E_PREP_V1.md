# GLM DeepResearch E2E Preparation v1

Status: `ready_for_real_e2e_read_only_audit`; `internal_result`; no real E2E run has occurred.

Implementation binding: `4ebbf7f26a2da40fccdf94c6b54fe7abf3aa1035`; runtime source SHA-256: `c135418ed4f07ff0be7b2d1538d176e3ccd552331d8ae71dd6ef05edcea08202`.

`B08E2E-PREP` is a non-logical Gate-A follow-on: S19/B08 and S20/B09 are historical and completed, while S21–S25 remain the unstarted Web track. This naming therefore does not claim completion of a future logical Web Session.

`DeepResearchRunner` is the single injected orchestration entry. It durably invokes the approved-brief Planner, shares that same B03R2 event stream with the B05 local Executor and B07 Writer, then applies deterministic B06 assessment and B07 validation. A persisted successful Planner/Writer result is resumed without calling either component; an incomplete durable stream fails closed rather than repeating a component.

`GLMStructuredPlanner` and `GLMSingleWriter` use the ordinary Zhipu model API transport already established by Gate A: `glm-5.3-flash`, text-only, non-streaming, `temperature=1`, `top_p=0.95`, `thinking.type=enabled`, `reasoning_effort=max`, `response_format=json_object`, 512 input / 256 output ceiling, 30-second operation timeout, zero retries, no tools, Web, vision, files, video, parallelism, or fallback. The frozen policy uses the Gate-A promotional snapshot (0.4 / 1.4 CNY per million input/output tokens), reserves at most 563.2 cost micros per model call, and caps the two-call pilot at 10,000 cost micros (0.01 CNY). The adapter classifies HTTP/JSON/provider/application failures separately and accepts no model-generated formal IDs.

Planner Prompt version/hash: `dr-glm-planner-prompt-v1` / `229c80135c804933239f4ca376aceb32366500cce723d1cdcda4c2d8d4851cce`.

Writer Prompt version/hash: `dr-glm-writer-prompt-v1` / `21c0eeb1b593408a50c88223091aa5040318f52d1bb19cd2be57b925caf2f64b`.

The prompts contain only their authorized view. Planner output is an untrusted `PlannerDraft`; Writer output is an untrusted `ReportDraft`. The program retains scope, IDs, DAG acceptance, Evidence/Claim/Citation identity, quote grounding, conflict disclosure, `author_review_required=true`, and `publication_ready=false` authority.

The prepared CLI is `python -m litflow.deep_research.e2e_cli --plan ... --task ... --artifact-dir ... --preflight|--dry-run|--execute`. It is intentionally independent of `litflow`'s frozen historical CLI source fingerprint used by the immutable B08R2 Canary plan. Preflight/dry-run verify the exact plan, frozen corpus hash, prompt hashes, deterministic run ID and absent artifact target without reading a credential or transporting. `--execute` is explicit and creates only a new target; it was not used by this batch.
