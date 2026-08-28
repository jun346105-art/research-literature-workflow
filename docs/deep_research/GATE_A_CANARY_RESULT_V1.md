# Gate A Canary Result v1

## Final status

`pass_text_only_single_call`

Attempt `glm-5.3-flash-text-canary-003` completed through the Zhipu BigModel ordinary-model API route using `glm-5.3-flash`. The immutable plan is bound to implementation commit `a932f8c96f25765e2bd8181bc4c69bc13911155e`, plan commit `07b9326a80d51d269b4126a8802967bfeb73563d`, and runtime source SHA-256 `c69952ee4d77cb7a3d58ee96405e9c4ee9f55ffb3b0fe876df6db4ce16524327`.

The terminal result was `complete` with exit code `0`. The artifact confirms HTTP `200`, received and confirmed provider response, valid application JSON, verified exact model identity, reported usage, verified cost, and complete cost audit. Usage was 88 input tokens, 185 output tokens, 273 total tokens, and `294.2000000` cost micros. Full replay matched with zero provider calls during replay.

## Artifact integrity and redaction

The preserved artifact directory is `outputs/deep_research/canary/v1.2/dr-run-3d18bc0c521412dd4bea920c`. Its 11 files are enumerated with byte lengths and SHA-256 digests in [the result manifest](canary/v1.2/canary_result_manifest.attempt-003.json). The manifest intentionally excludes credential material, Authorization data, raw provider response bodies, provider request identifiers, and private absolute paths.

The artifact's own secret scan reports no persisted credential, authorization, or private absolute path. It remains immutable. The first failed Canary artifact and the unexecuted attempt-002 plan remain preserved historical records and were not altered by this closure.

## Verified capability and limits

This result verifies controlled dispatch, layered transport/provider/application response contracts, exact model identity, token/cost audit, redacted artifacts, and zero-provider-call replay for one real GLM-5.3-Flash text-only invocation.

It does not verify a full DeepResearch Agent, tools, Web Research, multimodal input, remote exactly-once behavior, multi-process safety, provider-generic compatibility, or long-running task reliability.
