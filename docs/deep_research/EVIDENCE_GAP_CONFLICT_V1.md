# Evidence Gap, Potential Conflict and Bounded Replan v1

Status: `internal_result`. B06 deterministically detects structural evidence gaps from the B05 Evidence Graph, validates optional Fake-assessor conflict candidates, and admits at most one immutable replan through the existing unified event stream and BudgetLedger.

Deterministic gaps cover missing/insufficient evidence, missing required evidence types, insufficient source diversity, unsatisfied dependencies and uncovered structured scope. They do not claim semantic sufficiency. Potential conflicts require at least two existing Evidence IDs and remain `unresolved`; the assessor cannot create Evidence or decide truth.

Replan requires an approved Brief, matching run/assessment/original-plan identity, a nonterminal/noncancelled run, no unknown outcome, available `max_replans=1`, exact Brief scope, valid dependencies and a new non-equivalent Subtask. The original plan and completed Subtasks remain immutable. A single `replan_decided` event updates the existing ledger; repeated application is idempotent and replay calls no assessor, planner or tool.

This is offline Fake-assessment only. It does not implement Writer, Report Validator, final answer, real model assessment, Web, Multi-Agent or multimodal reasoning.
