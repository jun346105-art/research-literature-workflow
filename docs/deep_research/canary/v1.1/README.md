# GLM Canary execution-plan v1.1

`canary_execution_plan.schema.json` is the stable contract for the only approved text-only ordinary-model API route. The example is a non-secret input contract, not a record of a completed call. The runner creates the immutable per-run plan and artifacts only after its pre-dispatch checks, then uses the B03R2 ordered stream: reservation, durable dispatch, one invocation, durable terminal event, checkpoint and replay.

The plan fixes one `glm-5.3-flash` call, zero retries, 512/256 token ceilings, a 30-second operation timeout, a 45-second deadline, and a 0.01 CNY limit. It forbids tools, vision, video, files, Web, parallelism and fallback. `ZHIPUAI_API_KEY` is a variable name only; its value is never stored or accepted as a CLI argument.
