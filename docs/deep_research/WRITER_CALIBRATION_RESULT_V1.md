# GLM Writer Calibration Result v1

Calibration-003 (`writer-calibration-003`) completed one controlled Writer-only development calibration on the deterministic local fixture.

Status: `pass_writer_contract_and_deterministic_grounding`.

- Provider calls: 1; Planner calls: 0; Tool calls: 0; retries: 0.
- Terminal: `complete`; CLI exit: 0.
- Usage: 1,231 input / 72 output / 1,303 total tokens; cost `593.2` micros.
- Client-observed elapsed: `2.3090693` seconds.
- Deterministic grounding: verified; validation issues: none.
- Replay matched the checkpoint and made zero external Provider, Planner or Tool calls.
- Credential, Authorization and private absolute path persistence: false.
- Semantic correctness remains unverified; author review is required and publication-ready is false.

The machine-readable artifact inventory is [writer_calibration_result.manifest.attempt-003.json](calibration/v1/writer_calibration_result_manifest.attempt-003.json). It records only relative paths, sizes, SHA-256 values and safe structured outcomes; it excludes API keys, Authorization, request IDs, full Provider responses and private paths.

This result validates the Writer contract and deterministic grounding on the fixture only. It is not a complete DeepResearch E2E result and does not validate Web, tools, multimodal, Multi-Agent, semantic correctness or long-task stability.
