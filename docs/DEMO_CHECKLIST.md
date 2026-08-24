# Demo Checklist

Use the local Docker Offline Demo. Do not create a fresh online QA call for the recording.

## Before Recording

- [ ] Run `docker compose up --build` with local demo artifacts mounted.
- [ ] Confirm `GET /api/v1/health` returns `offline_demo`.
- [ ] Open `http://127.0.0.1:8015/`.
- [ ] Confirm the screen shows `Offline Demo`, not `Online QA`.
- [ ] Use the persisted verified Q01 job only when showing the answer flow.

## Recording Sequence

1. Show the Offline Demo home and local corpus navigation.
2. Restore Q01 with its original Chinese research query visible.
3. Show the verified-answer status, claim, citations, and stated limitation.
4. Select a citation and show paper title, citation key, page range, real passage ID, quote anchor, and source passage in Evidence Inspector.
5. Open Evidence Matrix and show an explicitly sparse field.
6. Open Bilingual Writing Draft and state `author-editable` and `not publication-ready`.
7. State that Online QA is explicit, budgeted, and may return partial, insufficient-evidence, or technical-failure states.

## Do Not Claim

- The restored Q01 job is a new real-time provider call.
- The 20-query pilot is a large benchmark.
- Strict quote grounding proves semantic correctness.
- LitFlow automatically writes a complete paper or supports cloud deployment.
