const byId = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[char]);

async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "请求失败");
  return data;
}

function showPassages(passages) {
  byId("passages").innerHTML = passages.map((item) => `<article class="card"><strong>${escapeHtml(item.title)}</strong><br><small>${escapeHtml(item.citation_key)} · pp.${item.page_start}-${item.page_end} · score ${item.score}</small><p>${escapeHtml(item.snippet)}</p><button data-passage="${escapeHtml(item.passage_id)}">查看原文</button></article>`).join("");
  document.querySelectorAll("[data-passage]").forEach((button) => button.onclick = async () => {
    const passage = await api(`/api/v1/passages/${encodeURIComponent(button.dataset.passage)}`);
    byId("answer").innerHTML = `<div class="card"><strong>${escapeHtml(passage.title)}</strong><p>pp.${passage.page_start}-${passage.page_end}</p><div class="quote">${escapeHtml(passage.passage_text)}</div></div>`;
  });
}

async function retrieve() {
  const query = byId("query").value.trim(); if (!query) return;
  const data = await api("/api/v1/retrieve", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, query_language: "auto", top_k: 10 }) });
  byId("route").innerHTML = `<p class="status">路由：${escapeHtml(data.route)}；翻译：${escapeHtml(data.translation_status)}</p>`;
  showPassages(data.passages);
}

async function ask() {
  const query = byId("query").value.trim(); if (!query) return;
  try {
    const created = await api("/api/v1/qa/jobs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, query_language: "auto" }) });
    byId("progress").textContent = `Job ${created.job_id} 正在执行…`;
    const interval = setInterval(async () => {
      const status = await api(`/api/v1/jobs/${created.job_id}`);
      byId("progress").textContent = `Job ${created.job_id}: ${status.status}`;
      if (status.status === "completed" || status.status === "failed") {
        clearInterval(interval); renderResult(await api(`/api/v1/jobs/${created.job_id}/result`));
      }
    }, 500);
  } catch (error) { byId("answer").innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`; }
}

function renderResult(result) {
  if (!result.answer_zh) { byId("answer").innerHTML = `<div class="card error">${escapeHtml(result.user_message)}</div>`; return; }
  const claims = (result.claims || []).map((claim, index) => `<article class="card"><strong>${index + 1}. ${escapeHtml(claim.claim_text_zh)}</strong><div>${claim.citations.map((citation) => `<button class="citation" data-passage="${escapeHtml(citation.passage_id)}" data-quote="${escapeHtml(citation.evidence_quote)}">${escapeHtml(citation.passage_id)} · pp.${citation.page_start}-${citation.page_end}</button>`).join("")}</div></article>`).join("");
  byId("answer").innerHTML = `<div class="card">${escapeHtml(result.answer_zh)}</div>${claims}`;
  document.querySelectorAll(".citation").forEach((button) => button.onclick = async () => {
    const passage = await api(`/api/v1/passages/${encodeURIComponent(button.dataset.passage)}?evidence_quote=${encodeURIComponent(button.dataset.quote)}`);
    byId("citation-drawer").innerHTML = `<article class="card"><strong>${escapeHtml(passage.title)}</strong><p>${escapeHtml(passage.citation_key)} · pp.${passage.page_start}-${passage.page_end} · ${escapeHtml(passage.anchor_status)}</p><div class="quote">${escapeHtml(passage.evidence_quote)}</div><div class="quote">${escapeHtml(passage.passage_text)}</div></article>`;
  });
}

async function loadDemo(kind) {
  const data = await api(`/api/v1/${kind}/demo`);
  byId("demo").innerHTML = `<div class="card"><pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre></div>`;
}

async function bootstrap() {
  const [health, papers] = await Promise.all([api("/api/v1/health"), api("/api/v1/papers")]);
  byId("mode").textContent = health.mode;
  byId("papers").innerHTML = papers.papers.map((paper) => `<p><strong>${escapeHtml(paper.title)}</strong><br><small>${escapeHtml(paper.citation_key)} · ${paper.language}</small></p>`).join("");
  byId("retrieve").onclick = retrieve; byId("ask").onclick = ask;
  byId("matrix").onclick = () => loadDemo("evidence-matrix"); byId("writing").onclick = () => loadDemo("writing");
  document.querySelector(".example").onclick = (event) => { byId("query").value = event.target.textContent; };
  const jobId = new URLSearchParams(window.location.search).get("job_id");
  if (jobId) { const status = await api(`/api/v1/jobs/${jobId}`); byId("progress").textContent = `Job ${jobId}: ${status.status}`; renderResult(await api(`/api/v1/jobs/${jobId}/result`)); }
}
bootstrap().catch((error) => { byId("answer").textContent = error.message; });
