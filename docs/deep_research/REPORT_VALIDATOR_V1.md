# Evidence-grounded Report Validator v1

Status: `internal_result`; deterministic grounding is not semantic proof.

The program validates every Writer proposal against the current B05 `EvidenceGraph` and B01 contracts. A displayable Citation must refer to current-graph Evidence, retain a valid Source/locator/passage/page provenance path, contain an exact quote mapped to the Evidence text, and be attached to a generated Claim. The shared `ContractBundle` then verifies Claim/Citation membership and quote/span correspondence. Unknown, cross-run, ungrounded, orphaned, duplicate, or provenance-incomplete references are excluded from display and recorded as structured validation issues.

Results are intentionally graded rather than all-or-nothing:

- `complete`: every displayable Claim/Citation passes deterministic checks; no gaps or unresolved conflicts remain.
- `partial`: only valid material is retained and all remaining gaps/conflicts/issues are explicit.
- `insufficient_evidence`: no safely displayable Claim remains.
- `manual_review_required`: an outcome is unknown or a potential conflict is undisclosed or unsafe for automatic resolution.

An unresolved conflict must disclose precisely its two (or more) referenced Evidence IDs to enter a `partial` report. It cannot be silently omitted or yield `complete`.

Every `ValidatedReport` has `author_review_required=true` and `publication_ready=false`. Exact quote grounding, canonical structure, and source provenance do **not** prove semantic entailment, factual completeness, scientific validity, or publication quality; those remain human-review responsibilities.
