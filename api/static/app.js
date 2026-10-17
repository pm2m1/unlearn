/* Unlearn web UI. No build step: plain DOM + Cytoscape.js. Every number on screen comes from an API call,
   and every API call that ran Cypher lists its receipts. */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) n.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined) n.append(kid.nodeType ? kid : document.createTextNode(kid));
  return n;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const PLUMBING = new Set(["task_context", "set_pending", "session_state", "log_event", "complete_task", "set_tutor_plan", "name_vocabulary"]);

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `${res.status} ${res.statusText}`);
  return data;
}

const state = {
  classId: new URLSearchParams(location.search).get("class") || "demo",
  students: [],
  aliases: {},
  targets: [],
  targetNames: {},
  session: null,      // {id, studentId, target}
  pending: null,      // {kind: "diagnose"|"check", question, constructId}
  asked: 0,
  graphKey: null,
  cy: null,
  teacherReceipts: {},
  busy: false,
};

/* ------------------------------------------------------------------ health / tabs */

async function loadHealth() {
  const box = $("#health");
  try {
    const h = await api("/health");
    const nodes = Object.values(h.node_counts).reduce((a, b) => a + b, 0);
    box.className = "status ok";
    $(".label", box).textContent = `FalkorDB ${h.falkordb_version} · ${h.graphs.length} graphs · ${nodes.toLocaleString()} nodes`;
  } catch (e) {
    box.className = "status bad";
    $(".label", box).textContent = "FalkorDB unreachable";
  }
}

function showView(name) {
  document.querySelectorAll(".tab").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.view === name)));
  document.querySelectorAll(".view").forEach((v) => (v.hidden = v.dataset.view !== name));
  if (name === "teacher") loadTeacher();
  if (name === "eval") loadEval();
  if (name === "student" && state.cy) setTimeout(() => state.cy.resize(), 0);
  history.replaceState(null, "", `#${name}`);
}

/* ------------------------------------------------------------------ class data */

async function loadClasses() {
  const { classes } = await api("/classes");
  const sel = $("#class-select");
  sel.replaceChildren(...classes.map((c) => el("option", { value: c, text: c })));
  sel.value = state.classId;
  sel.addEventListener("change", () => {
    const q = new URLSearchParams(location.search);
    q.set("class", sel.value);
    q.delete("student");
    location.search = q.toString();
  });
}

function renderScoreboard() {
  const withCheck = state.students.filter((s) => s.check);
  $("#scoreboard").hidden = !withCheck.length;
  $("#scores").replaceChildren(...withCheck.map((s) => el("button", {
    class: `score${s.id === $("#student-select").value ? " active" : ""}`,
    onclick: () => { $("#student-select").value = s.id; syncTarget(); renderScoreboard(); },
  }, el("div", { class: "who", text: s.alias }),
     el("div", { class: "pct", text: `${Math.round((100 * s.check.correct) / s.check.total)}%` }),
     el("div", { class: "frac", text: `${s.check.correct} of ${s.check.total} right` }))));
}

async function loadClass() {
  const [s, t] = await Promise.all([api(`/classes/${state.classId}/students`), api(`/classes/${state.classId}/targets`)]);
  state.students = s.students;
  state.aliases = Object.fromEntries(s.students.map((x) => [x.id, x.alias]));
  state.targets = t.targets;
  state.targetNames = Object.fromEntries(t.targets.map((x) => [x.id, x.name]));
  const sel = $("#student-select");
  sel.replaceChildren(...s.students.map((x) => el("option", { value: x.id, text: `${x.alias} · ${x.id}${x.sessions ? ` · ${x.sessions} session${x.sessions > 1 ? "s" : ""}` : ""}` })));
  const wanted = new URLSearchParams(location.search).get("student") || (state.aliases.s18 ? "s18" : s.students[0]?.id);
  if (state.aliases[wanted]) sel.value = wanted;
  const groups = {};
  for (const x of t.targets) (groups[x.subtopic] ||= []).push(x);
  $("#target-select").replaceChildren(...Object.entries(groups).map(([sub, xs]) =>
    el("optgroup", { label: sub }, xs.map((x) => el("option", { value: x.id, text: `${x.name} (${x.depth} levels)` })))));
  syncTarget();
  renderScoreboard();
  $("#class-name").textContent = state.classId;
  $("#class-summary").textContent = `${s.students.length} simulated students · ${s.students.reduce((a, x) => a + x.sessions, 0)} sessions so far`;
}

function syncTarget() {
  const st = state.students.find((x) => x.id === $("#student-select").value);
  if (st && state.targetNames[st.default_target]) $("#target-select").value = String(st.default_target);
}

/* ------------------------------------------------------------------ student flow */

function resetStudentView() {
  ["#question-card", "#diagnosis-card", "#tutor-card", "#recall-banner", "#tutor-check"].forEach((s) => ($(s).hidden = true));
  $("#feedback").replaceChildren();
  $("#tutor-feedback").replaceChildren();
  $("#steps").replaceChildren();
  $("#explain-text").value = "";
  state.pending = null;
  state.asked = 0;
}

async function startSession() {
  if (state.busy) return;
  state.busy = true;
  resetStudentView();
  $("#q-score").textContent = "";
  const sid = $("#student-select").value;
  const target = Number($("#target-select").value);
  setBusy("#start-btn", true, "Starting…");
  try {
    const out = await api(`/classes/${state.classId}/students/${sid}/sessions`, { method: "POST", body: { construct_id: target } });
    state.session = { id: out.session_id, studentId: sid, target, n: out.session_n };
    addSteps(`Session ${out.session_n} start · ${state.aliases[sid]}`, out.receipts);
    showRecall(out.recall, out.greeting);
    state.pending = out.kind === "question" ? { kind: "diagnose", question: out.question, constructId: out.construct_id } : null;
    await refreshGraph();
    await handleStep(out);
  } catch (e) {
    toast(e.message);
  } finally {
    setBusy("#start-btn", false, "Start session");
    state.busy = false;
  }
}

function showRecall(rows, greeting) {
  const b = $("#recall-banner");
  if (rows && rows.length) {
    $("#recall-text").replaceChildren(...rows.slice(0, 3).map((r) =>
      el("div", {}, el("strong", { text: r.misconception }), el("span", { class: "muted", text: ` · ${r.times}×` }))));
    b.hidden = false;
  } else if (greeting && state.session && state.session.n > 1) {
    $("#recall-text").textContent = greeting;
    b.hidden = false;
  } else b.hidden = true;
}

async function handleStep(out) {
  if (out.kind === "question") return renderQuestion(out, "diagnose");
  if (out.kind === "diagnosis") return renderDiagnosis(out);
  if (out.kind === "check") return renderCheck(out);
  if (out.kind === "done") return renderDone(out);
}

function renderOptions(box, q, onPick) {
  box.classList.remove("locked");
  box.replaceChildren(...q.options.map((o) =>
    el("button", { class: "option", "data-key": o.key, onclick: () => onPick(o.key) },
      el("span", { class: "key", text: o.key }), el("span", { text: o.text }))));
}

function renderQuestion(out, kind) {
  state.pending = { kind, question: out.question, constructId: out.construct_id };
  state.asked = (out.asked || 0) + 1;
  $("#question-card").hidden = false;
  $("#q-agent").textContent = "Diagnoser";
  $("#q-progress").textContent = `question ${state.asked} of up to 6 · construct ${out.construct_id}`;
  $("#q-text").textContent = out.question.text;
  renderOptions($("#q-options"), out.question, (key) => submitAnswer(key));
  if ($("#autoplay").checked) autoplayNext();
}

async function submitAnswer(key, simulate = false) {
  if (state.busy || !state.pending) return;
  state.busy = true;
  const { question, kind } = state.pending;
  const box = kind === "check" ? $("#check-options") : $("#q-options");
  box.classList.add("locked");
  const explanation = kind === "diagnose" ? $("#explain-text").value : "";
  try {
    const out = await api(`/sessions/${state.session.id}/answer`, {
      method: "POST", body: { qid: question.id, key, explanation: explanation || null, simulate },
    });
    const a = out.answer;
    if (out.session_score) showSessionScore(out.session_score);
    markPicked(box, a.key, a.correct);
    showFeedback(kind === "check" ? "#tutor-feedback" : "#feedback", a, out.explanation_matches);
    addSteps(`${kind === "check" ? "Check" : "Answer"} ${question.id} → ${a.key}`, out.receipts);
    $("#explain-text").value = "";
    // The graph's "asked now" ring follows the next question, or disappears once there is none.
    state.pending = ["question", "check"].includes(out.kind) ? { ...state.pending, constructId: out.construct_id } : null;
    await refreshGraph();
    await sleep(650);
    state.busy = false;
    await handleStep(out);
  } catch (e) {
    toast(e.message);
    box.classList.remove("locked");
  } finally {
    state.busy = false;
  }
}

function showSessionScore(s) {
  $("#q-score").textContent = s.total ? `this session ${s.correct} of ${s.total} right` : "";
}

function markPicked(box, key, correct) {
  box.querySelectorAll(".option").forEach((b) => {
    if (b.dataset.key === key) b.classList.add("picked", correct ? "right" : "wrong");
  });
}

function showFeedback(sel, a, heard) {
  const f = $(sel);
  f.replaceChildren(
    el("div", {}, el("span", { class: `tag ${a.correct ? "right" : "wrong"}`, text: a.correct ? "correct" : "misconception" }),
      a.correct ? (a.mastered ? `Mastered construct ${a.mastered}.` : "Right answer.") : a.misconception),
    heard && heard.length ? el("div", { class: "heard", text: `Your explanation sounds closest to: “${heard[0].name}” (distance ${heard[0].score.toFixed(2)})` }) : null,
  );
}

function renderDiagnosis(out) {
  state.pending = null;
  $("#question-card").hidden = true;
  const card = $("#diagnosis-card");
  card.hidden = false;
  if (!out.root) {
    $("#dx-root").textContent = "No broken prerequisite found";
    $("#dx-chain").replaceChildren();
    $("#dx-message").textContent = out.message;
    $("#tutor-btn").hidden = true;
    return;
  }
  $("#dx-root").replaceChildren(document.createTextNode(out.root.name),
    el("span", { class: "ev", text: `evidence ${out.root.evidence.toFixed(2)} · ${out.root.depth} level${out.root.depth > 1 ? "s" : ""} down · ${out.asked} questions` }));
  $("#dx-chain").replaceChildren(...out.root.chain.map((n) => el("li", { text: n })));
  $("#dx-message").textContent = out.message;
  $("#tutor-btn").hidden = !out.next_task;
  if ($("#autoplay").checked && out.next_task) sleep(1400).then(startTutor);
}

async function startTutor() {
  if (state.busy) return;
  state.busy = true;
  setBusy("#tutor-btn", true, "Tutoring…");
  try {
    const out = await api(`/sessions/${state.session.id}/remediate`, { method: "POST" });
    addSteps("Tutor", out.receipts);
    $("#diagnosis-card").hidden = true;
    showRecall(out.recall, null);
    const t = $("#tutor-card");
    t.hidden = false;
    $("#tutor-skill").textContent = out.skill ? `skill: ${out.skill.skill} · worked ${Math.round(out.skill.rate * 100)}% so far` : "";
    $("#tutor-explain").replaceChildren(...formatExplanation(out.explanation));
    state.busy = false;
    await handleStep(out);
  } catch (e) {
    toast(e.message);
  } finally {
    setBusy("#tutor-btn", false, "Start tutoring");
    state.busy = false;
  }
}

function formatExplanation(text) {
  const lines = (text || "").split("\n");
  const steps = lines.filter((l) => /^\s*\d+\.\s/.test(l)).map((l) => l.replace(/^\s*\d+\.\s/, ""));
  const prose = lines.filter((l) => !/^\s*\d+\.\s/.test(l) && l.trim());
  return [...prose.map((p) => el("p", { text: p })), steps.length ? el("ol", {}, steps.map((s) => el("li", { text: s }))) : null];
}

function renderCheck(out) {
  state.pending = { kind: "check", question: out.question, constructId: out.construct_id };
  $("#tutor-check").hidden = false;
  $("#check-text").textContent = out.question.text;
  renderOptions($("#check-options"), out.question, (key) => submitAnswer(key));
  if ($("#autoplay").checked) autoplayNext();
}

function renderDone(out) {
  state.pending = null;
  const f = $("#tutor-feedback");
  if (out.answer) {
    f.append(el("div", { class: "heard", text: out.escalated
      ? "Still held with confidence above 0.6, so the Tutor handed this to the Teacher agent. Check the Teacher view for the proposal."
      : "Session complete." }));
  } else {
    f.append(el("div", { class: "heard", text: out.explanation ? "No check question left this session." : "Nothing left to remediate." }));
  }
  loadClass().catch(() => {});
}

async function autoplayNext() {
  await sleep(1100);
  if (!$("#autoplay").checked || !state.pending) return;
  await submitAnswer(null, true);
}

/* ------------------------------------------------------------------ graph panel */

async function refreshGraph() {
  if (!state.session) return;
  const { studentId, target, id } = state.session;
  const g = await api(`/classes/${state.classId}/students/${studentId}/graph?construct_id=${target}&session=${encodeURIComponent(id)}`);
  $("#graph-title").textContent = `${state.aliases[studentId]} · ${state.targetNames[target] || g.constructs.find((c) => c.id === target)?.name || target}`;
  $("#graph-empty").hidden = true;
  drawGraph(g);
}

/* Node sizes are measured with a canvas so labels fit exactly (Cytoscape's width:"label" is deprecated). */
const FONT = "ui-sans-serif, -apple-system, Segoe UI, Roboto, sans-serif";
const CW = 236, C_FS = 14.5, C_LH = 18.5, M_FS = 12.5, M_H = 26, M_GAP = 6, MAX_MIS = 4;
const measureCtx = document.createElement("canvas").getContext("2d");
function textWidth(t, size, weight = 400) { measureCtx.font = `${weight} ${size}px ${FONT}`; return measureCtx.measureText(t).width; }
function wrapLines(t, size, maxW, weight) {
  const lines = []; let line = "";
  for (const w of t.split(/\s+/)) {
    const next = line ? `${line} ${w}` : w;
    if (line && textWidth(next, size, weight) > maxW) { lines.push(line); line = w; } else line = next;
  }
  if (line) lines.push(line);
  return lines.length;
}

function layout(g) {
  // Rows by longest-path depth from the target (prerequisites below what needs them). Each construct gets a
  // slot wide enough for its misconception column on the right, so the graph grows sideways, not downwards.
  const kids = {}, parents = {};
  for (const e of g.requires) { (kids[e.src] ||= []).push(e.dst); (parents[e.dst] ||= []).push(e.src); }
  const depth = { [g.target]: 0 };
  const queue = [g.target];
  for (let i = 0; i < queue.length; i++) {
    const n = queue[i];
    for (const k of kids[n] || []) if ((depth[k] ?? -1) < depth[n] + 1) { depth[k] = depth[n] + 1; queue.push(k); }
  }
  const misBy = attachMisconceptions(g);
  const rows = {};
  for (const c of g.constructs) (rows[depth[c.id] ?? 0] ||= []).push(c.id);
  const size = {};
  for (const c of g.constructs) {
    const bold = c.id === g.target || c.id === g.root_cause[0]?.id;
    size[c.id] = { w: CW, h: wrapLines(c.name, C_FS, CW - 26, bold ? 600 : 400) * C_LH + 24 };
  }
  const misW = (cid) => Math.max(0, ...(misBy[cid] || []).slice(0, MAX_MIS).map((m) => textWidth(misLabel(m), M_FS, 500) + 22), (misBy[cid] || []).length > MAX_MIS ? 90 : 0);
  const slotW = (cid) => CW + (misBy[cid] ? 22 + misW(cid) : 0);
  const stackH = (cid) => { const k = Math.min((misBy[cid] || []).length, MAX_MIS) + ((misBy[cid] || []).length > MAX_MIS ? 1 : 0); return k * (M_H + M_GAP); };
  const x = {}, pos = {};
  let y = 0;
  const maxRow = Math.max(...Object.keys(rows).map(Number));
  for (let d = 0; d <= maxRow; d++) {
    const ids = (rows[d] || []).slice();
    const bary = (id) => { const ps = (parents[id] || []).filter((q) => x[q] !== undefined); return ps.length ? ps.reduce((a, q) => a + x[q], 0) / ps.length : 0; };
    ids.sort((a, b) => bary(a) - bary(b) || a - b);
    const gap = 56;
    const total = ids.reduce((a, id) => a + slotW(id), 0) + gap * (ids.length - 1);
    const rowH = Math.max(...ids.map((id) => Math.max(size[id].h, stackH(id))));
    let left = -total / 2;
    for (const id of ids) {
      x[id] = left + CW / 2;
      pos[id] = { x: x[id], y: y + rowH / 2 };
      left += slotW(id) + gap;
    }
    y += rowH + 64;
  }
  return { pos, misBy, size, misW };
}

const misLabel = (m) => `${trunc(m.name, 42)}  ×${m.count}`;

function attachMisconceptions(g) {
  // Each misconception sits beside the construct where it carries the most weight; extra SEEN_IN links are drawn.
  const best = {};
  for (const s of g.showed) if (!best[s.mid] || s.w > best[s.mid].w) best[s.mid] = s;
  const by = {};
  for (const s of Object.values(best)) (by[s.cid] ||= []).push(s);
  for (const k of Object.keys(by)) by[k].sort((a, b) => b.confidence - a.confidence || b.count - a.count);
  return by;
}

const trunc = (s, n) => (s.length > n ? s.slice(0, n - 1) + "…" : s);

function drawGraph(g) {
  if (!window.cytoscape) return;
  const { pos, misBy, size } = layout(g);
  const mastered = new Set(g.mastered.map((m) => m.id));
  const root = g.root_cause[0]?.id;
  const chain = g.chain_ids || [];
  const chainEdges = new Set(chain.slice(0, -1).map((c, i) => `${c}->${chain[i + 1]}`));
  const askedNow = state.pending?.constructId;
  const attempted = new Set((g.attempts || []).map((a) => a.construct_id));
  const els = [];
  for (const c of g.constructs) {
    const cls = ["construct"];
    if (c.id === g.target) cls.push("target");
    if (mastered.has(c.id)) cls.push("mastered");
    if (chain.includes(c.id)) cls.push("chain");
    if (c.id === root) cls.push("root");
    if (c.id === askedNow) cls.push("asked");
    else if (attempted.has(c.id)) cls.push("attempted");
    els.push({ group: "nodes", data: { id: `c${c.id}`, label: c.name, full: `${c.name} (construct ${c.id})`, w: size[c.id].w, h: size[c.id].h },
      position: pos[c.id], classes: cls.join(" ") });
  }
  for (const e of g.requires) {
    const key = `${e.src}->${e.dst}`;
    els.push({ group: "edges", data: { id: `r${key}`, source: `c${e.src}`, target: `c${e.dst}` }, classes: chainEdges.has(key) ? "requires chain" : "requires" });
  }
  const placed = new Set();
  for (const [cid, list] of Object.entries(misBy)) {
    const p = pos[cid];
    if (!p) continue;
    const shown = list.slice(0, MAX_MIS);
    const k = shown.length + (list.length > MAX_MIS ? 1 : 0);
    const top = p.y - ((k - 1) * (M_H + M_GAP)) / 2;
    shown.forEach((m, i) => {
      placed.add(m.mid);
      const label = misLabel(m), w = textWidth(label, M_FS, 500) + 22;
      els.push({ group: "nodes", data: { id: `m${m.mid}`, label, w, h: M_H, full: `${m.name}\nshown ${m.count}× · confidence ${m.confidence.toFixed(2)}` },
        position: { x: p.x + CW / 2 + 22 + w / 2, y: top + i * (M_H + M_GAP) }, classes: m.confidence > 0.6 ? "mis strong" : "mis" });
    });
    if (list.length > MAX_MIS) {
      const label = `+${list.length - MAX_MIS} more`, w = textWidth(label, 12, 500) + 20;
      els.push({ group: "nodes", data: { id: `more${cid}`, label, w, h: 22, full: list.slice(MAX_MIS).map((m) => m.name).join("\n") },
        position: { x: p.x + CW / 2 + 22 + w / 2, y: top + MAX_MIS * (M_H + M_GAP) }, classes: "more" });
    }
  }
  for (const s of g.showed) {
    if (!placed.has(s.mid) || misBy[s.cid]?.some((m) => m.mid === s.mid)) continue;  // beside its own construct already
    els.push({ group: "edges", data: { id: `s${s.mid}-${s.cid}`, source: `m${s.mid}`, target: `c${s.cid}` }, classes: "seen" });
  }

  const key = els.filter((e) => e.group === "nodes").map((e) => e.data.id).sort().join("|");
  if (!state.cy) state.cy = makeCy();
  const cy = state.cy;
  if (key === state.graphKey) {
    cy.batch(() => els.forEach((e) => { const n = cy.getElementById(e.data.id); if (n.nonempty()) { n.classes(e.classes); n.data(e.data); } }));
    return;
  }
  const fresh = new Set(els.filter((e) => e.group === "nodes" && cy.getElementById(e.data.id).empty()).map((e) => e.data.id));
  const first = !state.graphKey;
  state.graphKey = key;
  cy.batch(() => { cy.elements().remove(); cy.add(els); });
  cy.fit(undefined, 28);
  if (cy.zoom() > 1.15) { cy.zoom(1.15); cy.center(); }
  if (!first) cy.nodes().filter((n) => fresh.has(n.id())).style("opacity", 0).animate({ style: { opacity: 1 } }, { duration: 450 });
}

function makeCy() {
  const cy = cytoscape({
    container: $("#cy"),
    layout: { name: "preset" },
    minZoom: 0.25, maxZoom: 2.5,
    autoungrabify: true,
    style: [
      { selector: "node", style: { "font-family": "ui-sans-serif, -apple-system, Segoe UI, Roboto, sans-serif" } },
      { selector: ".construct", style: {
        shape: "round-rectangle", width: "data(w)", height: "data(h)", "background-color": "#f1f1ee",
        "border-width": 1.5, "border-color": "#c9cbd1", label: "data(label)", "text-wrap": "wrap", "text-max-width": CW - 26,
        "font-size": C_FS, color: "#3c4049", "text-valign": "center", "text-halign": "center", "line-height": 1.25 } },
      { selector: ".construct.target", style: { "border-color": "#1b1d22", "border-width": 2.5, color: "#1b1d22", "font-weight": 600 } },
      { selector: ".construct.attempted", style: { "border-color": "#9aa0ab" } },
      { selector: ".construct.mastered", style: { "background-color": "#e3f3ea", "border-color": "#2e9b62", color: "#17603b" } },
      { selector: ".construct.chain", style: { "border-color": "#e3a33b", "border-width": 2.5 } },
      { selector: ".construct.root", style: { "background-color": "#fdf0d8", "border-color": "#e3a33b", "border-width": 6, color: "#6b4405", "font-weight": 600 } },
      { selector: ".construct.asked", style: { "underlay-color": "#2f3ab8", "underlay-padding": 7, "underlay-opacity": 0.16, "underlay-shape": "round-rectangle", "border-color": "#2f3ab8", "border-width": 2.5 } },
      { selector: ".mis", style: {
        shape: "round-rectangle", height: "data(h)", width: "data(w)", "background-color": "#fbeceb", "border-width": 1.5, "border-color": "#d2453f",
        label: "data(label)", "font-size": M_FS, "font-weight": 500, color: "#9a2d28", "text-valign": "center", "text-halign": "center" } },
      { selector: ".mis.strong", style: { "background-color": "#d2453f", color: "#ffffff" } },
      { selector: ".more", style: { shape: "round-rectangle", height: "data(h)", width: "data(w)", "background-color": "#ffffff", "border-width": 1, "border-color": "#d2453f", "border-style": "dashed", label: "data(label)", "font-size": 12, "font-weight": 500, color: "#9a2d28" } },
      { selector: "edge.requires", style: { width: 1.5, "line-color": "#c9cbd1", "target-arrow-color": "#c9cbd1", "target-arrow-shape": "triangle", "arrow-scale": 0.9, "curve-style": "bezier" } },
      { selector: "edge.requires.chain", style: { width: 4.5, "line-color": "#e3a33b", "target-arrow-color": "#e3a33b", "z-index": 5 } },
      { selector: "edge.seen", style: { width: 1, "line-color": "#e8a4a1", "line-style": "dashed", "curve-style": "bezier", opacity: 0.8 } },
    ],
  });
  const tip = el("div", { class: "cy-tip" });
  Object.assign(tip.style, { position: "absolute", pointerEvents: "none", background: "#1b1d22", color: "#fff", padding: "6px 10px", borderRadius: "8px", fontSize: "12.5px", maxWidth: "340px", zIndex: 5, display: "none", whiteSpace: "pre-line" });
  $(".graph-card").append(tip);
  cy.on("mouseover tap", "node", (ev) => {
    const p = ev.renderedPosition, box = $("#cy").getBoundingClientRect(), card = $(".graph-card").getBoundingClientRect();
    tip.textContent = ev.target.data("full");
    tip.style.left = `${Math.min(p.x + box.left - card.left + 14, card.width - 350)}px`;
    tip.style.top = `${p.y + box.top - card.top + 14}px`;
    tip.style.display = "block";
  });
  cy.on("mouseout", "node", () => (tip.style.display = "none"));
  window.addEventListener("resize", () => { cy.resize(); cy.fit(undefined, 28); if (cy.zoom() > 1.15) { cy.zoom(1.15); cy.center(); } });
  return cy;
}

/* ------------------------------------------------------------------ receipts */

function addSteps(title, receipts) {
  const list = $("#steps");
  const group = el("li", {}, el("div", { class: "step-group", text: title }));
  const shown = receipts.filter((r) => !PLUMBING.has(r.tool));
  for (const r of shown) {
    const isLlm = r.tool.startsWith("llm:");
    group.append(el("button", { onclick: () => openReceipt(r.id) },
      el("span", { class: `agent-chip ${r.agent.toLowerCase()}`, text: r.agent }),
      el("span", { class: "tool", text: isLlm ? `says (${r.source})` : r.tool }),
      isLlm ? el("span", { class: "said", text: r.text }) : el("span", { class: "q", text: r.queries.join(" · ") })));
  }
  const hidden = receipts.length - shown.length;
  if (hidden) group.append(el("div", { class: "step-group", style: "font-weight:400", text: `+ ${hidden} bookkeeping queries (task state, events)` }));
  list.prepend(group);
}

async function openReceipt(rid) {
  const r = await api(`/receipts/${rid}`);
  $("#drawer-agent").textContent = r.agent;
  $("#drawer-agent").className = `agent-chip ${r.agent.toLowerCase()}`;
  $("#drawer-id").textContent = r.id;
  $("#drawer-title").textContent = r.tool;
  const body = $("#drawer-body");
  body.replaceChildren();
  if (r.tool.startsWith("llm:")) {
    body.append(el("h3", { text: `Reply · written by ${r.source}` }), el("div", { class: "said", text: r.text }),
      el("h3", { text: "Receipt check" }), el("pre", { text: JSON.stringify(r.rows, null, 2) }));
  } else {
    r.cypher.forEach((q, i) => {
      body.append(el("h3", { text: `Query ${i + 1} of ${r.cypher.length}` }), el("span", { class: "qname", text: r.queries[i] }),
        el("pre", { text: q }), el("h3", { text: "Params" }), el("pre", { text: JSON.stringify(redactVectors(r.params[i]), null, 2) }));
    });
    const rows = Array.isArray(r.rows) ? r.rows : [r.rows];
    body.append(el("h3", { text: `Rows (${rows.length})` }), el("pre", { text: JSON.stringify(rows.slice(0, 50), null, 2) }));
    if (r.node_ids?.length) body.append(el("h3", { text: "Node path" }), el("pre", { text: r.node_ids.map((n) => `${n.label}:${n.id}`).join(" → ") }));
  }
  $("#drawer").classList.add("open");
  $("#drawer").setAttribute("aria-hidden", "false");
  $("#scrim").hidden = false;
  $("#drawer-close").focus();
}

function redactVectors(p) {
  if (!p) return p;
  const out = {};
  for (const [k, v] of Object.entries(p)) out[k] = Array.isArray(v) && v.length > 50 && typeof v[0] === "number" ? `[${v.length} floats]` : v;
  return out;
}

function closeDrawer() {
  $("#drawer").classList.remove("open");
  $("#drawer").setAttribute("aria-hidden", "true");
  $("#scrim").hidden = true;
}

/* ------------------------------------------------------------------ teacher view */

async function loadTeacher() {
  const c = state.classId;
  const who = (ids) => ids.map((id) => state.aliases[id] || id);
  const [co, ks, br, ps] = await Promise.all([
    api(`/classes/${c}/cohorts`), api(`/classes/${c}/keystones`), api(`/classes/${c}/bridges`), api(`/classes/${c}/proposals?state=pending`),
  ]).catch((e) => { toast(e.message); return []; });
  if (!co) return;
  state.teacherReceipts = { cohorts: co.receipt.id, keystones: ks.receipt.id, bridges: br.receipt.id };

  $("#cohorts").replaceChildren(...(co.rows.length ? co.rows.map((g) =>
    el("div", { class: "cohort" }, g.students.map((s) => el("span", { class: "chip", text: s })))) :
    [el("div", { class: "empty", text: "No cohorts yet: no two students share a confident misconception. Simulate the class to fill this in." })]));

  const maxK = Math.max(...ks.rows.map((k) => k.score), 1e-9);
  $("#keystones").replaceChildren(...ks.rows.map((k) => el("li", {}, el("div", {}, el("div", { text: k.name }), el("div", { class: "bar", style: `width:${(100 * k.score / maxK).toFixed(0)}%` })))));
  const maxB = Math.max(...br.rows.map((b) => b.score), 1e-9);
  $("#bridges").classList.add("bridges");
  $("#bridges").replaceChildren(...br.rows.map((b) => el("li", {}, el("div", {}, el("div", { text: b.name }), el("div", { class: "bar", style: `width:${(100 * b.score / maxB).toFixed(0)}%` })))));

  $("#proposals").replaceChildren(...(ps.rows.length ? ps.rows.map((p) => proposalCard(p, who)) :
    [el("div", { class: "empty", text: "No pending proposals. The Teacher agent writes one when a Tutor escalates a student." })]));
}

function proposalCard(p, who) {
  const card = el("div", { class: "proposal" },
    el("div", { class: "p-head" }, el("span", { class: "kind", text: p.kind }), el("strong", { text: who(p.students).join(", ") }),
      el("span", { class: "muted", text: p.id })),
    el("div", { class: "reason", text: p.payload.reason || JSON.stringify(p.payload) }));
  const actions = el("div", { class: "p-actions" },
    el("button", { class: "btn approve", onclick: () => decide(p, "approved", card) }, "Approve"),
    el("button", { class: "btn reject", onclick: () => decide(p, "rejected", card) }, "Reject"));
  card.append(actions);
  return card;
}

async function decide(p, decision, card) {
  card.querySelectorAll("button").forEach((b) => (b.disabled = true));
  try {
    const out = await api(`/proposals/${p.id}/decide`, { method: "POST", body: { decision, class_id: state.classId } });
    card.classList.add("done");
    const a = out.applied;
    toast(decision === "approved"
      ? `Approved ${out.kind}: ${a.group_id ? `group ${a.group_id}` : a.assignment_id ? `assignment ${a.assignment_id}` : `mastered ${a.construct_id}`} · event ${a.event_id}`
      : `Rejected ${out.kind}. Nothing changed.`);
    await loadTeacher();
  } catch (e) {
    toast(e.message);
    card.querySelectorAll("button").forEach((b) => (b.disabled = false));
  }
}

async function simulateAll() {
  const btn = $("#simulate-all-btn");
  setBusy(btn, true, "Simulating 60 sessions…");
  try {
    const out = await api(`/classes/${state.classId}/simulate-all?sessions=2`, { method: "POST" });
    toast(`Simulated ${out.sessions} sessions in ${out.seconds}s · planted root cause named in ${out.root_cause_hits}/${out.sessions}`);
    await Promise.all([loadClass(), loadTeacher()]);
  } catch (e) {
    toast(e.message);
  } finally {
    setBusy(btn, false, "Simulate the class (2 sessions each)");
  }
}

async function sendChat(ev) {
  ev.preventDefault();
  const input = $("#chat-input");
  const msg = input.value.trim();
  if (!msg) return;
  input.value = "";
  const log = $("#chat-log");
  log.append(el("div", { class: "msg me", text: msg }));
  const pending = el("div", { class: "msg bot muted", text: "…" });
  log.append(pending);
  log.scrollTop = log.scrollHeight;
  try {
    const out = await api(`/classes/${state.classId}/teacher/chat`, { method: "POST", body: { message: msg } });
    pending.className = "msg bot";
    pending.replaceChildren(el("div", { text: out.text }),
      el("div", { class: "meta" }, el("span", { class: "muted", style: "font-size:11px", text: `written by ${out.source}` }),
        out.receipts.filter((r) => !r.tool.startsWith("llm:")).map((r) => el("button", { onclick: () => openReceipt(r.id), text: r.tool }))));
  } catch (e) {
    pending.textContent = e.message;
  }
  log.scrollTop = log.scrollHeight;
}

/* ------------------------------------------------------------------ eval view */

async function loadEval() {
  const box = $("#eval-results");
  const { results } = await api("/eval/results");
  box.replaceChildren();
  if (!Object.keys(results).length) { box.append(el("p", { class: "empty", text: "No results yet." })); return; }
  const order = ["eval", "random_baseline", "concurrency", "latency", "crosscheck"];
  const names = Object.keys(results).sort((a, b) => (order.indexOf(a) + 99) % 99 - (order.indexOf(b) + 99) % 99);
  for (const name of names) {
    const r = results[name];
    if (r.summary && r.meta && name === "eval") box.append(...evalTable(r, "Graph vs vector RAG vs no memory"));
    else if (name.startsWith("eval_")) continue;  // partial runs (one seed at a time), already merged into eval.json
    else if (r.summary && r.meta && name.startsWith("crosscheck")) {
      const n = Object.entries(r.meta.n_per_condition || {}).map(([c, k]) => `${c}: ${k}`).join(", ");
      const foot = el("details", { class: "footnote" }, el("summary", { text: `Footnote: cross-check with ${r.meta.llm || "another LLM"} (n = ${n}). Indicative only, n too small to conclude.` }),
        ...evalTable(r, `Cross-check (${r.meta.llm}), indicative only`));
      box.append(foot);
    }
    else if (name === "random_baseline" && r.per_seed) box.append(...randomView(r));
    else if (name === "concurrency" && r.isolation) box.append(...concurrencyView(r));
    else if (r.tools) box.append(...latencyTable(r));
    else box.append(el("h2", { text: name }), el("pre", { text: JSON.stringify(r, null, 2).slice(0, 4000) }));
  }
}

function evalTable(r, title) {
  const conds = [["A", "A. No memory"], ["B", "B. Vector RAG"], ["B+", "B+. LLM + graph as text"], ["C", "C. Unlearn"]];
  const rows = [["Top-1 misconception", "top1_misconception", "%"], ["Top-3 misconception", "top3_misconception", "%"],
    ["Root-cause accuracy", "root_cause_accuracy", "%"], ["Questions to diagnosis", "questions_to_diagnosis", ""],
    ["Session-2 recall", "session2_recall", "%"], ["p50 latency (ms)", "latency_p50_ms", ""], ["p95 latency (ms)", "latency_p95_ms", ""]];
  const fmt = (x, u) => (u === "%" ? `${Math.round(100 * x)}%` : Number(x).toFixed(1));
  const cell = (c, m, u) => {
    const v = r.summary[c]?.[m];
    if (!r.summary[c]) return el("td", { class: "muted", text: "not run" });
    if (!v) return el("td", { text: "–" });
    if (v.min === v.max) return el("td", {}, el("strong", { text: fmt(v.mean, u) }));
    return el("td", {}, el("strong", { text: fmt(v.mean, u) }), el("span", { class: "muted", text: ` ${fmt(v.min, u)}–${fmt(v.max, u)}` }));
  };
  const m = r.meta;
  const notes = Object.entries(m.not_run || {}).map(([c, why]) => el("p", { class: "muted", text: `${c} not run: ${why}.` }));
  return [el("h2", { text: title }),
    el("p", { class: "muted", text: `${m.students} simulated students × seeds ${m.seeds.join(", ")} × ${m.sessions} sessions · mean, min–max across seeds · A/B model: ${m.llm || "none"} · C: template wording${m.stopped ? ` · stopped early: ${m.stopped}` : ""}` }),
    el("table", { class: "eval" }, el("thead", {}, el("tr", {}, el("th", { text: "Metric" }), conds.map(([c, l]) => {
      const n = r.meta.n_per_condition?.[c];
      const seeds = (r.meta.seeds_per_condition || {})[c] || r.meta.seeds;
      return el("th", {}, el("div", { text: l }), n ? el("div", { class: "muted", style: "font-weight:400;font-size:12px", text: `n=${n}, seed${seeds.length > 1 ? "s" : ""} ${seeds.join(", ")}` }) : null);
    }))),
      el("tbody", {}, rows.map(([label, key, u]) => el("tr", {}, el("td", { text: label }), conds.map(([c]) => cell(c, key, u)))))),
    ...seedTables(r, conds, rows, fmt),
    ...notes, ...(m.bplus_rescored ? [el("p", { class: "muted", text: `Correction: ${m.bplus_rescored}.` })] : []),
    el("p", { class: "muted", text: `Simulator bias: ${m.simulator_bias}.` })];
}

// A condition that ran on fewer seeds (B+) is compared on those seeds only, where every condition faced the same students.
function seedTables(r, conds, rows, fmt) {
  const m = r.meta, per = m.seeds_per_condition || {};
  const ran = conds.filter(([c]) => r.summary[c]);
  const short = ran.filter(([c]) => per[c] && per[c].length < m.seeds.length);
  if (!short.length || !r.per_seed) return [];
  const seeds = per[short[0][0]];
  const val = (c, key) => {
    const xs = seeds.map((s) => r.per_seed[s]?.[c]?.[key]).filter((x) => x !== null && x !== undefined);
    return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
  };
  const n = (c) => seeds.reduce((a, s) => a + (r.per_seed[s]?.[c]?.n || 0), 0);
  return [el("h3", { text: `Seed ${seeds.join(", ")} only: the same students for every condition` }),
    el("p", { class: "muted", text: `${short.map(([c]) => c).join(", ")} ran on seed ${seeds.join(", ")} only, so compare ${short.length > 1 ? "them" : "it"} here, not with the three-seed means above.` }),
    el("table", { class: "eval" }, el("thead", {}, el("tr", {}, el("th", { text: "Metric" }), ran.map(([c, l]) => el("th", {}, el("div", { text: l }),
      el("div", { class: "muted", style: "font-weight:400;font-size:12px", text: `n=${n(c)}` }))))),
      el("tbody", {}, rows.slice(0, 6).map(([label, key, u]) => el("tr", {}, el("td", { text: label }),
        ran.map(([c]) => { const v = val(c, key); return el("td", {}, el("strong", { text: v === null ? "–" : fmt(v, u) })); })))))];
}

function randomView(r) {
  const seeds = Object.keys(r.per_seed);
  const avg = (f) => seeds.reduce((a, s) => a + f(r.per_seed[s]), 0) / seeds.length;
  const pct = (x) => (x < 0.1 ? `${(100 * x).toFixed(1)}%` : `${Math.round(100 * x)}%`);
  const conds = ["A", "B", "B+"];
  const row = (label, key) => el("tr", {}, el("td", { text: label }), ...conds.map((c) => el("td", { text: pct(avg((p) => p[c][key])) })));
  const sz = (k) => avg((p) => p.candidate_list_sizes[k]).toFixed(1);
  return [el("h2", { text: "Random guess from the same candidate lists" }),
    el("p", { class: "muted", text: `Expected score of picking uniformly from what each condition is scored on, over the same students (seeds ${seeds.join(", ")}). A and B: ${sz("prerequisites")} root-cause candidates, ${sz("A_misconceptions")} misconceptions for A, ${sz("B_misconceptions")} for B. B+ is scored on every id it was shown: ${sz("Bplus_misconceptions")} misconceptions and ${sz("Bplus_constructs")} constructs. C has no list; it searches the whole graph.` }),
    el("table", { class: "eval" }, el("thead", {}, el("tr", {}, ["Metric", "A", "B", "B+"].map((h) => el("th", { text: h })))),
      el("tbody", {}, row("Top-1 misconception", "top1_misconception"), row("Top-3 misconception", "top3_misconception"),
        row("Root-cause accuracy", "root_cause_accuracy"),
        el("tr", {}, el("td", { text: "Planted misconception on the list" }),
          ...conds.map((c) => el("td", { text: pct(avg((p) => p.planted_misconception_on_list[c])) })))))];
}

function concurrencyView(r) {
  const t = (title, x) => el("tr", {}, el("td", { text: title }), el("td", { text: x.p50_ms.toFixed(2) }), el("td", { text: x.p95_ms.toFixed(2) }), el("td", { text: String(x.n) }));
  const iso = r.isolation;
  return [el("h2", { text: "Concurrency: one graph per class" }),
    el("p", { class: "muted", text: `${r.students_per_graph} simulated students in each of ${r.graphs.join(" and ")}, at once, through the async client.` }),
    el("table", {}, el("thead", {}, el("tr", {}, ["", "p50 ms", "p95 ms", "queries"].map((h) => el("th", { text: h })))),
      el("tbody", {}, Object.entries(r.per_graph).map(([g, x]) => t(`${g} (both classes running)`, x)))),
    el("p", { class: "muted", text: "Probe writes into class A, one at a time, while other load runs:" }),
    el("table", {}, el("thead", {}, el("tr", {}, ["", "p50 ms", "p95 ms", "writes"].map((h) => el("th", { text: h })))),
      el("tbody", {}, t("A alone (baseline)", iso.baseline), t("heavy writes on class B (other graph)", iso.load_on_other_graph),
        t("heavy writes on class A (same graph)", iso.load_on_same_graph),
        ...(iso.sessions_on_other_graph ? [t("a class of sessions on B", iso.sessions_on_other_graph), t("a class of sessions on A", iso.sessions_on_same_graph)] : []))),
    el("p", { class: "muted", text: "Probes run in a separate process with their own connection. Writes in A wait behind A's writes, not B's; a load that fills the server's query thread pool slows every class equally." })];
}

function latencyTable(r) {
  return [el("h2", { text: "Tool latency" }),
    el("p", { class: "muted", text: `${r.calls_per_tool} calls per tool on ${r.class_graph} · ${r.measured}` }),
    el("table", {}, el("thead", {}, el("tr", {}, ["tool", "p50 ms", "p95 ms"].map((h) => el("th", { text: h })))),
      el("tbody", {}, Object.entries(r.tools).map(([t, v]) => el("tr", {}, el("td", { text: t }), el("td", { text: v.p50_ms.toFixed(2) }), el("td", { text: v.p95_ms.toFixed(2) })))))];
}

/* ------------------------------------------------------------------ small helpers */

function setBusy(btn, busy, label) {
  const b = typeof btn === "string" ? $(btn) : btn;
  b.disabled = busy;
  b.textContent = label;
}

let toastTimer;
function toast(msg) {
  let t = $("#toast");
  if (!t) {
    t = el("div", { id: "toast", role: "status" });
    Object.assign(t.style, { position: "fixed", left: "50%", bottom: "24px", transform: "translateX(-50%)", background: "#1b1d22", color: "#fff",
      padding: "10px 16px", borderRadius: "10px", fontSize: "14px", zIndex: 50, maxWidth: "min(720px, calc(100vw - 32px))", boxShadow: "0 8px 30px rgba(0,0,0,.2)" });
    document.body.append(t);
  }
  t.textContent = msg;
  t.style.display = "block";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.style.display = "none"), 5200);
}

/* ------------------------------------------------------------------ wire up */

document.addEventListener("DOMContentLoaded", async () => {
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => showView(t.dataset.view)));
  $("#start-btn").addEventListener("click", startSession);
  $("#student-select").addEventListener("change", () => { syncTarget(); renderScoreboard(); });
  $("#simulate-btn").addEventListener("click", () => submitAnswer(null, true));
  $("#tutor-btn").addEventListener("click", startTutor);
  $("#autoplay").addEventListener("change", () => { if ($("#autoplay").checked && state.pending) autoplayNext(); });
  $("#drawer-close").addEventListener("click", closeDrawer);
  $("#scrim").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
  $("#refresh-btn").addEventListener("click", loadTeacher);
  $("#simulate-all-btn").addEventListener("click", simulateAll);
  $("#chat-form").addEventListener("submit", sendChat);
  document.querySelectorAll("[data-receipt-for]").forEach((b) => b.addEventListener("click", () => {
    const rid = state.teacherReceipts[b.dataset.receiptFor];
    if (rid) openReceipt(rid);
  }));
  window.addEventListener("hashchange", () => {
    const v = location.hash.slice(1);
    if (["student", "teacher", "eval"].includes(v)) showView(v);
  });
  loadHealth();
  loadClasses().catch(() => {});
  try { await loadClass(); } catch (e) { toast(`Could not load the class: ${e.message}`); }
  const view = location.hash.slice(1);
  showView(["student", "teacher", "eval"].includes(view) ? view : "student");
});
