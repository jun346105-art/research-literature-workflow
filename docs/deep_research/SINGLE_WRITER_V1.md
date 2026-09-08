# Single Writer v1

Status: `internal_result`; offline only.

B07 / S17 adds exactly one async `Writer` boundary.  It receives an approved Brief, the current validated Plan, the current run's `EvidenceGraph`, and the restricted B06 gap/conflict assessment. `FakeWriter` is a scripted test fixture only; it does not establish real-model quality or provider behavior.

The Writer returns an untrusted `ReportDraft`. It may propose section headings, natural-language claims, existing `evidence_id` references, exact quote candidates, and conflict disclosures. Unknown presentation metadata is ignored, but any attempt to own a formal `claim_id`, `citation_id`, Source, Evidence, full EvidenceGraph, or final-answer field is rejected. The program alone creates final Claim/Citation/section/report IDs, canonicalizes and de-duplicates them, and decides what is displayable.

`SingleWriterRunner` reuses the B03R2 `UnifiedEventStore`, `BudgetLedger`, checkpoint writer, and replay reducer. It uses the EvidenceGraph run ID rather than a second event stream. The one Writer operation is durably reserved and dispatched before invocation, then receives a durable succeeded, known-failed, or unknown terminal event. A persisted successful validation is returned on resume without another Writer call; a dispatched prefix without a terminal event remains `manual_review_required` and is never retried automatically.

This batch has no real Provider/API/HTTP, key access, Web, tool execution, multi-writer fan-out, Writer repair loop, formal output artifact, or publication-ready report.
