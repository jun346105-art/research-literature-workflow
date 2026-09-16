const byId = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const frozen = {
  single: "What components does the cited paper state that WT-C3k2 combines?",
  cross: "How do the selected local papers describe their approaches to multi-scale feature handling?",
  insufficient: "What was the orbital inclination and propellant mass of the Mars Reconnaissance Orbiter mission?"
};
const examples = {
  single: frozen.single,
  frequency: "How does WT-C3k2 process high- and low-frequency features?",
  defects: "What packaging defects does Merge-YOLO address?"
};
const state = { lang: localStorage.getItem("litflow-language") === "en" ? "en" : "zh", phase: "empty", result: null, query: "", job: null, citations: [], origin: null };
const i18n = {
  zh: {navResearch:"研究",navSources:"文献",navRuns:"记录",navAbout:"关于",offlineBadge:"已验证离线演示",apiDocs:"API 文档",eyebrow:"本地文献研究",heroTitle:"基于你的文献，生成可核验的研究回答",heroCopy:"从本地论文中查找证据、整理结论，并将每条关键发现追溯到原文。",queryLabel:"你想研究什么？",queryPlaceholder:"例如：WT-C3k2 结合了哪些组件？",inputHint:"首个问题展示已验证报告；其余问题只进行本地检索，不套用固定报告。",startButton:"开始研究",examplesEyebrow:"从一个问题开始",examplesTitle:"示例问题",exampleOne:"WT-C3k2 结合了哪些组件？",exampleTwo:"WT-C3k2如何处理高频与低频特征？",exampleThree:"Merge-YOLO针对哪些包装缺陷？",progressTitle:"正在整理本地证据",stepOne:"分析问题",stepTwo:"查找文献",stepThree:"整理证据",stepFour:"生成回答",working:"处理中",newResearch:"研究新问题",sourcesTitle:"本地文献",sourcesCopy:"当前冻结语料中的论文。",runsTitle:"研究记录",runsCopy:"本次浏览会话中的离线结果。",aboutTitle:"让研究结论回到原文",aboutCopy:"本地优先、引用可核验，最终发表仍需人工审阅。",footer:"本地优先 · 证据可核验 · 发表需人工审阅",evidenceTitle:"原文证据",resultTitle:"研究结果",question:"研究问题",answer:"简明回答",findings:"关键发现",background:"相关背景",sources:"使用的论文",usedSources:"篇论文",evidenceCount:"条证据",direct:"直接支持",context:"背景支持",page:"第 {n} 页",citations:"条引用",grounding:"引用锚定已验证",noClaim:"没有可安全展示的 Claim。",insufficient:"当前文献中没有足够证据支持可靠回答。可以调整问题，或查看系统检查过的来源。",failed:"本次研究未能完成。你的文献和历史结果没有受到影响。",localOnly:"此问题不是固定示例。这里只展示本地检索，不套用其他报告。",localTitle:"本地检索",noPassage:"未找到可展示片段。",limits:"限制与人工复核",review:"引用经过确定性锚定检查；语义正确性和发表质量仍需人工审阅。",dev:"Developer details",details:"运行详情",provider:"Provider",phase:"阶段",tokens:"Token",cost:"费用 (micros)",elapsed:"耗时 (秒)",replay:"Replay 外部调用",run:"运行 ID",artifact:"Artifact",evidenceId:"证据 ID",sourceId:"来源 ID",passageId:"片段 ID",statusComplete:"已完成",statusInsufficient:"证据不足",statusPartial:"部分结果",statusFailed:"未完成",invalid:"请输入完整研究问题。",requestError:"离线演示暂不可用。",noRuns:"本次会话尚无研究记录。",quote:"支持原句",notPublished:"不具备自动发表条件"},
  en: {navResearch:"Research",navSources:"Sources",navRuns:"Runs",navAbout:"About",offlineBadge:"Verified offline demo",apiDocs:"API docs",eyebrow:"LOCAL LITERATURE RESEARCH",heroTitle:"Turn your papers into research you can verify",heroCopy:"Find evidence in local papers, shape a conclusion, and trace each key finding back to its source.",queryLabel:"What are you researching?",queryPlaceholder:"Example: What components does WT-C3k2 combine?",inputHint:"The first question shows a verified report. Others use local retrieval only, never a fixed report.",startButton:"Start research",examplesEyebrow:"START WITH A QUESTION",examplesTitle:"Example questions",exampleOne:"What components does WT-C3k2 combine?",exampleTwo:"How does WT-C3k2 handle high- and low-frequency features?",exampleThree:"What packaging defects does Merge-YOLO address?",progressTitle:"Organizing local evidence",stepOne:"Analyze question",stepTwo:"Find papers",stepThree:"Organize evidence",stepFour:"Write answer",working:"Working",newResearch:"Ask another question",sourcesTitle:"Local sources",sourcesCopy:"Papers in the frozen corpus.",runsTitle:"Research runs",runsCopy:"Offline results in this browser session.",aboutTitle:"Bring research claims back to the source",aboutCopy:"Local-first, verifiable citations, and human review before publication.",footer:"Local-first · Verifiable evidence · Human review required",evidenceTitle:"Source evidence",resultTitle:"Research result",question:"Research question",answer:"Short answer",findings:"Key findings",background:"Related background",sources:"Papers used",usedSources:"papers",evidenceCount:"evidence units",direct:"Direct support",context:"Contextual support",page:"Page {n}",citations:"citations",grounding:"Citation anchors verified",noClaim:"No claim is safe to display.",insufficient:"The current papers do not provide enough evidence for a reliable answer. Refine the question or inspect the checked sources.",failed:"This research did not finish. Your papers and prior results are unaffected.",localOnly:"This is not a frozen example. Only local retrieval is shown; no fixed report is reused.",localTitle:"Local retrieval",noPassage:"No displayable passage found.",limits:"Limits and human review",review:"Citations passed deterministic anchor checks; semantic correctness and publication quality still require human review.",dev:"Developer details",details:"Run details",provider:"Provider",phase:"Phase",tokens:"Tokens",cost:"Cost (micros)",elapsed:"Elapsed (seconds)",replay:"Replay external calls",run:"Run ID",artifact:"Artifact",evidenceId:"Evidence ID",sourceId:"Source ID",passageId:"Passage ID",statusComplete:"Complete",statusInsufficient:"Insufficient evidence",statusPartial:"Partial",statusFailed:"Failed",invalid:"Enter a complete research question.",requestError:"Offline demo unavailable.",noRuns:"No research run in this session.",quote:"Supporting quote",notPublished:"Not publication ready"}
};
const t = key => i18n[state.lang][key];
async function api(path, options) { const response = await fetch(path, options); if (!response.ok) throw Error("offline demo request failed"); return response.json(); }
function translate() {
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  byId("lang-zh").classList.toggle("active", state.lang === "zh"); byId("lang-en").classList.toggle("active", state.lang === "en");
  if (state.result) renderResult();
}
function renderResult() { if (state.result?.kind === "deep") renderDeep(state.result.data); else if (state.result?.kind === "local") renderLocal(state.result.data); else if (state.result?.kind === "error") byId("result-view").innerHTML = '<div class="alert alert-danger">' + t("failed") + '</div>'; }
async function startResearch(query) {
  query = (query ?? byId("query").value).trim();
  if (query.length < 8 || !/[A-Za-z\u4e00-\u9fff]/u.test(query)) { byId("query-error").textContent = t("invalid"); byId("query-error").hidden = false; setPhase("validating"); return; }
  byId("query-error").hidden = true; state.query = query; state.result = null; setPhase("running"); byId("start-research").disabled = true;
  try {
    if (Object.values(frozen).includes(query)) {
      const created = await api("/api/deep-research/jobs", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query,mode:"offline_demo"})});
      state.job = created.job_id;
      const result = await api('/api/deep-research/jobs/' + encodeURIComponent(created.job_id) + '/result');
      state.result = {kind:"deep",data:result}; setPhase(["complete","insufficient_evidence"].includes(result.terminal) ? result.terminal : "failed");
    } else {
      const data = await api("/api/v1/retrieve", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query,query_language:"auto",top_k:10})});
      state.result = {kind:"local",data}; setPhase("local_search");
    }
    renderResult(); showView("research");
  } catch (_) { state.result = {kind:"error"}; setPhase("failed"); renderResult(); }
  finally { byId("start-research").disabled = false; }
}
function openCitation(index, origin) {
  const c = state.citations[index]; if (!c) return;
  state.origin = origin;
  byId("drawer-body").innerHTML = '<span class="badge ' + (c.support_kind === "direct" ? 'bg-teal-lt text-teal' : 'bg-blue-lt text-blue') + '">' + t(c.support_kind === "direct" ? "direct" : "context") + '</span><h3 class="mt-3">' + esc(c.source_title) + '</h3><p class="text-secondary">' + (c.page_number ? t("page").replace("{n}",esc(c.page_number)) : '') + '</p><div class="section-label">' + t("quote") + '</div><blockquote class="evidence-quote">' + esc(c.quote) + '</blockquote><details class="run-details"><summary>' + t("dev") + '</summary><p>' + t("evidenceId") + ': ' + esc(c.evidence_id) + '<br>' + t("sourceId") + ': ' + esc(c.source_id) + '<br>' + t("passageId") + ': ' + esc(c.passage_id) + '</p></details>';
  // Tabler's data API opens the drawer after this delegated content update.
}
async function loadSources() {
  const target=byId("sources-list"); try { const data=await api("/api/v1/papers"); target.innerHTML=data.papers.map(p => '<div class="col-md-6"><div class="card"><div class="card-body"><h2 class="h3">' + esc(p.title) + '</h2><p class="text-secondary">' + esc(p.year || "") + '</p></div></div></div>').join(""); } catch (_) { target.textContent=t("requestError"); }
}
function renderRuns() { byId("runs-list").innerHTML=state.job ? '<div class="card"><div class="card-body"><p>' + esc(state.query) + '</p><span class="badge bg-teal-lt text-teal">' + t(state.phase === "complete" ? "statusComplete" : "statusPartial") + '</span></div></div>' : '<p class="text-secondary">' + t("noRuns") + '</p>'; }
document.addEventListener("DOMContentLoaded", () => {
  translate(); setPhase("empty");
  byId("lang-zh").onclick=()=>{state.lang="zh";localStorage.setItem("litflow-language","zh");translate();};
  byId("lang-en").onclick=()=>{state.lang="en";localStorage.setItem("litflow-language","en");translate();};
  byId("start-research").onclick=()=>startResearch();
  byId("new-research").onclick=()=>{state.result=null;state.query="";byId("query").value="";setPhase("empty");byId("query").focus();};
  document.querySelectorAll("[data-example]").forEach(el=>el.onclick=()=>startResearch(examples[el.dataset.example]));
  document.querySelectorAll("[data-view]").forEach(el=>el.onclick=()=>showView(el.dataset.view));
  byId("result-view").addEventListener("click",event=>{const button=event.target.closest("[data-citation]"); if(button) openCitation(Number(button.dataset.citation),button);});
  byId("evidence-drawer").addEventListener("hidden.bs.offcanvas",()=>state.origin?.focus());
  const params=new URLSearchParams(location.search); if(params.get("lang") === "en") { state.lang="en";translate(); }
  if (params.has("demo") && Object.hasOwn(frozen,params.get("demo"))) {
    startResearch(frozen[params.get("demo")]).then(()=>{if(params.get("evidence") === "1") byId("result-view").querySelector("[data-citation]")?.click();});
  }
});
function setPhase(phase) {
  state.phase = phase;
  byId("home-state").hidden = !["empty", "validating"].includes(phase);
  byId("progress-view").hidden = phase !== "running";
  byId("result-view").hidden = !["complete", "insufficient_evidence", "failed", "local_search"].includes(phase);
  byId("new-research").hidden = byId("result-view").hidden;
  if (phase === "running") { byId("progress-status").textContent = t("working"); document.querySelectorAll("#progress-steps li").forEach((el,i) => el.classList.toggle("active",i === 1)); }
}
function showView(view) {
  ["research","sources","runs","about"].forEach(v => byId(v + "-view").hidden = v !== view);
  document.querySelectorAll("[data-view]").forEach(el => el.classList.toggle("active",el.dataset.view === view));
  if (view === "sources") loadSources(); if (view === "runs") renderRuns();
  byId("site-nav").classList.remove("show");
}
function citationButtons(parts, claim) { return parts.filter(p => p.claim === claim).map(p => '<button type="button" class="citation-chip" data-citation="' + p.index + '" data-bs-toggle="offcanvas" data-bs-target="#evidence-drawer" aria-controls="evidence-drawer" aria-label="' + esc(t("evidenceTitle") + " " + (p.index+1)) + '">[' + (p.index+1) + ']</button>').join(" "); }
function renderDeep(result) {
  const direct = (result.findings || []).filter(f => f.support_kind === "direct");
  const background = (result.findings || []).filter(f => f.support_kind !== "direct");
  state.citations = []; const parts = [];
  for (const f of [...direct, ...background]) for (const c of f.citations || []) { parts.push({claim:f.claim_id,index:state.citations.length}); state.citations.push(c); }
  const complete = result.terminal === "complete";
  const status = complete ? "statusComplete" : result.terminal === "insufficient_evidence" ? "statusInsufficient" : result.terminal === "partial" ? "statusPartial" : "statusFailed";
  const note = complete ? (direct[0]?.text || t("noClaim")) : result.terminal === "insufficient_evidence" ? t("insufficient") : t("failed");
  const findingHtml = list => list.map(f => '<div class="finding"><p>' + esc(f.text) + ' ' + citationButtons(parts,f.claim_id) + '</p></div>').join("");
  const sources = (result.sources || []).map(s => { const selected = parts.find(p => state.citations[p.index].source_id === s.source_id); return '<div class="source-card"><div class="source-title">' + esc(s.title) + '</div><div class="text-secondary small">' + (s.year ? esc(s.year) + ' · ' : '') + esc(s.citation_count) + ' ' + t("citations") + '</div>' + (selected ? '<button type="button" class="btn btn-outline-teal btn-sm mt-2" data-citation="' + selected.index + '" data-bs-toggle="offcanvas" data-bs-target="#evidence-drawer" aria-controls="evidence-drawer">' + t("evidenceTitle") + '</button>' : '') + '</div>'; }).join("");
  byId("result-view").innerHTML = '<div class="result-heading"><span class="section-label">' + t("resultTitle") + '</span><span class="badge ' + (complete ? 'bg-teal-lt text-teal' : 'bg-yellow-lt text-yellow') + '">' + t(status) + '</span></div>' +
    '<div class="result-grid"><article class="card report-card"><div class="card-body"><div class="text-secondary small mb-2">' + t("question") + '</div><h1 class="report-question">' + esc(result.query) + '</h1>' +
    '<section class="answer-block"><div class="section-label">' + t("answer") + '</div><p>' + esc(note) + (complete && direct[0] ? ' ' + citationButtons(parts,direct[0].claim_id) : '') + '</p></section>' +
    (complete && direct.length > 1 ? '<section><h2>' + t("findings") + '</h2>' + findingHtml(direct.slice(1)) + '</section>' : '') +
    (background.length ? '<details class="background-section"><summary>' + t("background") + ' · ' + background.length + '</summary>' + findingHtml(background) + '</details>' : '') +
    '<section class="review-note"><h2>' + t("limits") + '</h2><p>' + t("review") + '</p><span class="badge bg-yellow-lt text-yellow">' + t("notPublished") + '</span></section>' +
    '<details class="run-details"><summary>' + t("details") + '</summary><dl><dt>' + t("provider") + '</dt><dd>' + esc(result.provider) + '</dd><dt>' + t("phase") + '</dt><dd>' + esc(result.phase) + '</dd><dt>' + t("tokens") + '</dt><dd>' + esc(result.usage?.total_tokens) + '</dd><dt>' + t("cost") + '</dt><dd>' + esc(result.cost_micros) + '</dd><dt>' + t("elapsed") + '</dt><dd>' + esc(result.elapsed_s) + '</dd><dt>' + t("replay") + '</dt><dd>' + esc(result.replay?.external_calls) + '</dd></dl><details><summary>' + t("dev") + '</summary><p>' + t("run") + ': ' + esc(result.run_id) + '<br>' + t("artifact") + ': ' + esc(result.artifact) + '</p></details></details>' +
    '</div></article><aside class="sources-column"><div class="card"><div class="card-body"><h2>' + t("sources") + '</h2><p class="text-secondary small">' + esc(result.sources?.length || 0) + ' ' + t("usedSources") + ' · ' + esc(result.evidence?.count || 0) + ' ' + t("evidenceCount") + '</p>' + (sources || '<p class="text-secondary">' + t("noPassage") + '</p>') + '</div></div>' + (result.grounding ? '<div class="grounding-note">✓ ' + t("grounding") + '</div>' : '') + '</aside></div>';
}
function renderLocal(data) {
  const rows = (data.passages || []).map(p => '<div class="source-card"><div class="source-title">' + esc(p.title) + '</div><p>' + esc(p.snippet) + '</p></div>').join("");
  byId("result-view").innerHTML = '<div class="result-grid"><article class="card report-card"><div class="card-body"><span class="badge bg-yellow-lt text-yellow">' + t("statusPartial") + '</span><h1 class="report-question mt-3">' + esc(state.query) + '</h1><div class="alert alert-info">' + t("localOnly") + '</div><h2>' + t("localTitle") + '</h2>' + (rows || '<p>' + t("noPassage") + '</p>') + '</div></article></div>';
}
