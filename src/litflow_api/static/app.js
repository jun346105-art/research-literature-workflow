const byId = (id) => document.getElementById(id);
const state = { jobId: null, originalQuery: "", lastFocus: null, mode: "offline_demo" };
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[char]);
const quotePreview = (value) => value.length > 220 ? `${value.slice(0, 220)}...` : value;

async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "请求失败");
  return data;
}

function setPanel(id, visible) { byId(id).classList.toggle("is-hidden", !visible); }
function setStatus(text, kind = "neutral") { const target = byId("result-status"); target.innerHTML = `<span class="status status-${kind}">${escapeHtml(text)}</span>`; }
function showQueryView() { setPanel("query-view", true); setPanel("data-view", false); document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("is-active", item.dataset.view === "query")); }

function modeLabel(mode) { return mode === "online_qa" ? "Online QA / 在线问答" : "Offline demo / 离线演示"; }
function setMode(mode) { state.mode = mode; byId("mode-badge").textContent = modeLabel(mode); byId("mode-badge").className = `status ${mode === "online_qa" ? "status-neutral" : "status-insufficient"}`; }

function renderRoute(data) {
  setPanel("route-panel", true);
  byId("route").innerHTML = `<strong>${escapeHtml(data.route || "未执行检索")}</strong><br><span class="metadata">language: ${escapeHtml(data.query_language || "unknown")} · translation: ${escapeHtml(data.translation_status || "not_requested")}</span>`;
}

function renderProgress(text) { setPanel("progress-panel", true); byId("progress").textContent = text; }

function renderPassages(passages) {
  setPanel("passages-panel", true); byId("passage-count").textContent = `${passages.length} passages`;
  byId("passages").innerHTML = passages.map((item) => `<article class="passage-card"><h3>${escapeHtml(item.title)}</h3><div class="metadata">${escapeHtml(item.citation_key)} · ${escapeHtml(item.passage_id)} · pp.${item.page_start}-${item.page_end} · rank ${item.rank}</div><p>${escapeHtml(item.snippet)}</p><button class="button button-secondary passage-open" data-passage="${escapeHtml(item.passage_id)}" type="button">Inspect passage</button></article>`).join("");
  document.querySelectorAll(".passage-open").forEach((button) => button.addEventListener("click", () => openInspector({ passage_id: button.dataset.passage })));
}

function renderCoverage(ledger) {
  if (!ledger || ledger.coverage_status !== "partial") return "";
  const covered = (ledger.covered_entities || []).map((item) => item.entity_name).join("、") || "无";
  const uncovered = (ledger.uncovered_entities || []).map((item) => item.entity_name).join("、") || "无";
  return `<div class="coverage-list"><strong>Coverage / 覆盖范围</strong><ul><li>已覆盖：${escapeHtml(covered)}</li><li>未覆盖：${escapeHtml(uncovered)}</li></ul></div>`;
}

function renderResult(result) {
  setPanel("result-panel", true); const panel = byId("result-panel"); panel.className = "result-panel";
  const claims = result.claims || [];
  if (result.execution_status !== "success") {
    panel.classList.add("failure"); setStatus("Technical failure / 技术执行失败", "failure");
    byId("answer").innerHTML = `<p class="answer-copy">系统未展示未经验证的模型回答。请检查执行状态后重试，不将此状态计为证据不足拒答。</p>`;
    byId("claims").innerHTML = ""; byId("limitations").innerHTML = ""; return;
  }
  if (result.final_answer_status === "partial_answer") { panel.classList.add("partial"); setStatus("Partial answer / 部分回答", "partial"); }
  else if (result.final_answer_status === "insufficient_evidence") { panel.classList.add("insufficient"); setStatus("Insufficient evidence / 证据不足", "insufficient"); }
  else { panel.classList.add("verified"); setStatus("Verified answer / 已验证回答", "verified"); }
  byId("answer").innerHTML = `<div class="answer-copy">${escapeHtml(result.answer_zh || "基于当前检索到的文献片段，证据不足，无法给出可验证回答。")}</div>${renderCoverage(result.coverage_ledger)}`;
  byId("claims").innerHTML = claims.map((claim, index) => `<article class="claim-card"><h3>${index + 1}. ${escapeHtml(claim.claim_text_zh)}</h3>${claim.citations.map((citation) => `<blockquote class="quote-preview">${escapeHtml(quotePreview(citation.evidence_quote))}</blockquote>`).join("")}<div class="citation-list">${claim.citations.map((citation) => `<button class="citation-chip" data-passage="${escapeHtml(citation.passage_id)}" data-quote="${escapeHtml(citation.evidence_quote)}" type="button">${escapeHtml(citation.passage_id)} · pp.${citation.page_start}-${citation.page_end}</button>`).join("")}</div></article>`).join("");
  byId("limitations").innerHTML = result.limitations_zh ? `<div class="limitations"><strong>Limitations / 局限：</strong>${escapeHtml(result.limitations_zh)}</div>` : "";
  document.querySelectorAll(".citation-chip").forEach((button) => button.addEventListener("click", () => openInspector({ passage_id: button.dataset.passage, evidence_quote: button.dataset.quote }, button)));
}

async function openInspector(citation, trigger) {
  const suffix = citation.evidence_quote ? `?evidence_quote=${encodeURIComponent(citation.evidence_quote)}` : "";
  const passage = await api(`/api/v1/passages/${encodeURIComponent(citation.passage_id)}${suffix}`);
  state.lastFocus = trigger || document.activeElement; byId("inspector-empty").classList.add("is-hidden");
  byId("citation-drawer").innerHTML = `<dl class="inspector-metadata"><div><dt>Paper title</dt><dd>${escapeHtml(passage.title)}</dd></div><div><dt>Citation key</dt><dd>${escapeHtml(passage.citation_key)}</dd></div><div><dt>Page range</dt><dd>pp.${passage.page_start}-${passage.page_end}</dd></div><div><dt>Passage ID</dt><dd>${escapeHtml(passage.passage_id)}</dd></div><div><dt>Paper key</dt><dd>${escapeHtml(passage.paper_key)}</dd></div><div><dt>Anchor status</dt><dd>${escapeHtml(passage.anchor_status)}</dd></div></dl>${passage.evidence_quote ? `<h3>Evidence quote</h3><div class="quote-block">${escapeHtml(passage.evidence_quote)}</div>` : ""}<h3>Full source passage</h3><div class="passage-block">${escapeHtml(passage.passage_text)}</div><div class="inspector-actions"><button id="copy-citation" class="button button-secondary" type="button">Copy citation</button></div>`;
  byId("copy-citation")?.addEventListener("click", async () => { await navigator.clipboard?.writeText(`${passage.citation_key} · ${passage.passage_id} · pp.${passage.page_start}-${passage.page_end}`); });
  if (window.matchMedia("(max-width: 1279px)").matches) { byId("evidence-inspector").classList.add("is-open"); byId("evidence-inspector").setAttribute("aria-hidden", "false"); byId("drawer-backdrop").classList.remove("is-hidden"); byId("inspector-close").focus(); }
}

function closeInspector() { byId("evidence-inspector").classList.remove("is-open"); byId("drawer-backdrop").classList.add("is-hidden"); state.lastFocus?.focus?.(); }
function closeNav() { byId("primary-nav").classList.remove("is-open"); byId("nav-toggle").setAttribute("aria-expanded", "false"); byId("drawer-backdrop").classList.add("is-hidden"); }

async function retrieve() {
  const query = byId("query").value.trim(); if (!query) return;
  state.originalQuery = query; renderProgress("Retrieving passages / 正在检索文献片段");
  const data = await api("/api/v1/retrieve", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, query_language: "auto", top_k: 10 }) });
  renderRoute(data); renderPassages(data.passages); renderProgress(`Retrieval completed / 已检索 ${data.passages.length} 个 passages`);
}

function consumeEvent(event) { const labels = { job_created: "Job created / 已创建任务", translation_started: "Resolving language route / 正在解析语言路由", translation_completed: "Language route resolved / 语言路由已确定", translation_skipped: "Translation skipped / 未执行翻译", retrieval_completed: "Retrieval completed / 检索完成", generation_started: "Generating verified response / 正在生成", generation_completed: "Generation completed / 生成完成", validation_completed: "Validating citations and quotes / 正在验证引用", job_completed: "Job completed / 任务完成", job_failed: "Job failed / 任务失败" }; renderProgress(labels[event] || event); }

async function loadJob(jobId, recovered = false) {
  const status = await api(`/api/v1/jobs/${jobId}`); const result = await api(`/api/v1/jobs/${jobId}/result`);
  state.jobId = jobId; renderProgress(`Job ${jobId}: ${status.status}`); renderResult(result);
  if (recovered) { byId("recovery-badge").classList.remove("is-hidden"); byId("recovered-job-nav").classList.remove("is-hidden"); byId("recovered-job-nav").dataset.jobId = jobId; }
}

async function watchJob(jobId) {
  const source = new EventSource(`/api/v1/jobs/${jobId}/events`); source.onmessage = () => {};
  ["job_created", "translation_started", "translation_completed", "translation_skipped", "retrieval_completed", "generation_started", "generation_completed", "validation_completed", "job_completed", "job_failed"].forEach((name) => source.addEventListener(name, () => consumeEvent(name)));
  source.onerror = async () => { source.close(); await loadJob(jobId); };
}

async function ask() {
  const query = byId("query").value.trim(); if (!query) return;
  try {
    state.originalQuery = query; renderProgress("Creating online QA job / 正在创建在线任务");
    const created = await api("/api/v1/qa/jobs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, query_language: "auto" }) });
    state.jobId = created.job_id; sessionStorage.setItem(`litflow-job-${created.job_id}`, query); const url = new URL(window.location.href); url.searchParams.set("job_id", created.job_id); url.searchParams.set("query", query); history.replaceState({}, "", url); await watchJob(created.job_id);
  } catch (error) { renderResult({ execution_status: "technical_failure", final_answer_status: null, limitations_zh: "" }); renderProgress(error.message); }
}

function activateNav(view) { document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("is-active", item.dataset.view === view)); closeNav(); }
async function loadDataView(view) {
  setPanel("query-view", false); setPanel("data-view", true); const target = byId("data-view"); target.innerHTML = `<div class="empty-message">Loading / 加载中...</div>`;
  if (view === "papers") { const data = await api("/api/v1/papers"); target.innerHTML = `<div class="view-heading"><div><span class="eyebrow">Frozen corpus</span><h1>Corpus / Papers</h1></div></div><div class="table-wrap"><table class="matrix-table"><thead><tr><th>Paper</th><th>Citation</th><th>Language</th><th>Passages</th></tr></thead><tbody>${data.papers.map((paper) => `<tr><td>${escapeHtml(paper.title)}</td><td>${escapeHtml(paper.citation_key)}</td><td>${escapeHtml(paper.language)}</td><td>${paper.passage_count}</td></tr>`).join("")}</tbody></table></div>`; }
  else if (view === "matrix") { const data = await api("/api/v1/evidence-matrix/demo"); const rows = data.matrix.papers.flatMap((paper) => Object.entries(paper.fields).flatMap(([field, records]) => records.length ? records.map((record) => `<tr><td>${escapeHtml(paper.title)}</td><td>${escapeHtml(paper.citation_key)}</td><td>${escapeHtml(field)}</td><td>${escapeHtml(record.claim_text)}</td><td>Reviewed evidence</td></tr>`) : [`<tr><td>${escapeHtml(paper.title)}</td><td>${escapeHtml(paper.citation_key)}</td><td>${escapeHtml(field)}</td><td>尚无已审核证据</td><td>Sparse field</td></tr>`])); target.innerHTML = `<div class="view-heading"><div><span class="eyebrow">Read-only demo artifact</span><h1>Evidence Matrix</h1></div></div><div class="table-wrap"><table class="matrix-table"><thead><tr><th>Paper</th><th>Citation</th><th>Category</th><th>Claim</th><th>Coverage</th></tr></thead><tbody>${rows.join("")}</tbody></table></div>`; }
  else if (view === "writing") { const data = await api("/api/v1/writing/demo"); target.innerHTML = `<div class="view-heading"><div><span class="eyebrow">Author-reviewed / read-only demo artifact</span><h1>Bilingual Writing Draft</h1></div><span class="status status-partial">Author-editable · not publication-ready</span></div><div class="writing-layout"><article class="data-card"><h3>Outline and limitations</h3><p>${escapeHtml(data.partial_coverage_limitations || data.outline.limitations_zh)}</p></article><article class="data-card draft-block"><h3>中文草稿</h3>${escapeHtml(data.draft_zh)}</article><article class="data-card draft-block"><h3>English draft</h3>${escapeHtml(data.draft_en)}</article><article class="data-card draft-block"><h3>Sentence Evidence Ledger</h3>${escapeHtml(data.sentence_evidence_ledger)}</article></div>`; }
  else if (view === "route") { showQueryView(); byId("route-panel").classList.remove("is-hidden"); byId("route").innerHTML = "使用当前输入查询后，显示真实 language/translation/retrieval route。"; }
  else { showQueryView(); }
}

async function bootstrap() {
  const health = await api("/api/v1/health"); setMode(health.mode); byId("ask").disabled = health.mode !== "online_qa"; byId("ask").title = health.mode === "online_qa" ? "" : "Offline demo mode does not construct an LLM client";
  byId("retrieve").addEventListener("click", retrieve); byId("ask").addEventListener("click", ask); byId("new-query").addEventListener("click", () => { showQueryView(); byId("query").focus(); });
  document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", async () => { activateNav(button.dataset.view); if (button.dataset.view === "recovered") await loadJob(button.dataset.jobId, true); else if (button.dataset.view === "query") showQueryView(); else await loadDataView(button.dataset.view); }));
  byId("inspector-close").addEventListener("click", closeInspector); byId("drawer-backdrop").addEventListener("click", () => { closeInspector(); closeNav(); }); byId("nav-toggle").addEventListener("click", () => { const open = byId("primary-nav").classList.toggle("is-open"); byId("nav-toggle").setAttribute("aria-expanded", String(open)); byId("drawer-backdrop").classList.toggle("is-hidden", !open); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") { closeInspector(); closeNav(); } });
  const params = new URLSearchParams(window.location.search); const jobId = params.get("job_id"); const query = params.get("query") || (jobId && sessionStorage.getItem(`litflow-job-${jobId}`)); if (query) { state.originalQuery = query; byId("query").value = query; }
  if (jobId) await loadJob(jobId, true);
}
bootstrap().catch((error) => { renderProgress(`Technical failure / ${error.message}`); });
