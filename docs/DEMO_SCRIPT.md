# Local Demo Script

## 0:00-0:30 - Start Safely

Run the Offline Demo with `docker compose up --build`. State that the host port is loopback-only and that this mode neither needs nor constructs an LLM client.

## 0:30-1:15 - Research Workspace

Open the browser at the local URL. Point out the original research-question field, explicit Offline Demo status, frozen corpus navigation, and that the workspace distinguishes retrieval evidence from generated claims.

## 1:15-2:00 - Grounded Answer And Provenance

Open the persisted Q01 job. Show the verified-answer status, claim, citation chips, and limitations. Select a citation and show the Evidence Inspector: paper title, citation key, page range, real passage ID, anchor status, quote, and full source passage.

## 2:00-2:40 - Honest Failure States

Explain the partial-answer, insufficient-evidence, and technical-failure states. A technical failure never displays an unverified model answer. A partial answer lists covered and uncovered entities.

## 2:40-3:30 - Evidence Matrix And Writing Draft

Open Evidence Matrix and show sparse fields as `尚无已审核证据`. Open Bilingual Writing Draft and show that it is author-reviewed, author-editable, and not publication-ready.

## 3:30-4:15 - Evaluation Boundary

State the bounded pilot evidence: 9/17 answerable queries produced grounded answers, while all 9 displayed answers were author-reviewed as usable. Machine-translation BM25 Recall@10 was 0.7157 and the mixed-language smoke reached expected-paper Hit@10 of 5/6. These are small human-reviewed pilots, not broad benchmark claims.

## 4:15-5:00 - Optional Online Mode

Explain that Online QA is a separate explicit compose profile and may incur provider cost. It is not enabled during the default offline demonstration. Do not place credentials in files, screenshots, or source control.
