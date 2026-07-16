/* Scranton UI - vanilla JS, no framework (stack decision, SCRANTON_CONTEXT §4).
 *
 * ONE OS, role-based views (recadrage 2026-07-12, slide 08 of the deck):
 * - Manager: Dashboard / Michael's Desk / Meet Toby
 * - Team member: My board / Pretzel Day
 * - Dwight and Pam are omnipresent ACTIONS (bottom bar overlays), never tabs.
 *
 * Character names and avatars are FETCHED from /api/v1/config/ui, never
 * hardcoded: the character map stays the single rebrand seam. The only
 * literal feature name below is "Pretzel Day", which has no character.
 */

const API = "/api/v1";

/* Celebrations are PAUSED (owner, QA 2026-07-14: TWSS felt like "une
 * nuisance", the Maire popin "sinistre et intrusif"). The code stays:
 * the dedicated celebrations session will rework frequency, triggers
 * and form (gamification), then flip this back on. */
const CELEBRATIONS = false;

const state = {
  characters: {},
  role: "manager",
  selfId: null, // who I am, in the team-member role (identity, not proxy)
  members: [],
  labels: { team_member: {}, project: {}, client: {} },
  entryId: null, // the entry currently discussed in the Dwight overlay
  mayorOverview: null,
  celebrated: false, // Maire celebration: once per page load
  // Edited documents (2026-07-16): generated results kept at hand for
  // the save gesture, and the editor's working state.
  deskSummaries: {},
  pamSummaries: [],
  editorDoc: null,
  editorProposal: null,
  editorOpenId: null, // set before switching to the Desk to auto-open
};

/* --- helpers --- */

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `${response.status} ${response.statusText}`);
  }
  return response.json();
}

/* Escape everything user- or model-authored before it touches innerHTML. */
function esc(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function show(container, html) {
  const element = document.getElementById(container);
  element.classList.remove("placeholder");
  element.innerHTML = html;
}

function character(key) {
  return state.characters[key] || { display_name: key, avatar_asset: "" };
}

/* --- the OS chrome: roles, views, actions --- */

/* The closed view list per role (recadrage 2026-07-12). Labels for
 * Michael's Desk and Meet Toby come from the character map (seam). */
function roleViews() {
  if (state.role === "manager") {
    return [
      { id: "dashboard", label: "Dashboard", icon: null, load: loadDashboard },
      { id: "desk", label: character("michael").display_name, icon: character("michael").avatar_asset, load: loadDesk },
      { id: "toby", label: character("toby").display_name, icon: character("toby").avatar_asset, load: loadToby },
    ];
  }
  return [
    { id: "myboard", label: "My board", icon: null, load: loadMyBoard },
    { id: "pretzel", label: "Pretzel Day", icon: "pretzelday.jpg", pretzel: true, load: loadPretzel },
  ];
}

function renderChrome() {
  // Role switch
  document.getElementById("role-switch").onclick = (event) => {
    const button = event.target.closest("button[data-role]");
    if (button) switchRole(button.dataset.role);
  };

  // Identity: who am I when acting as a team member. Never a proxy -
  // in the member role every write is about YOURSELF.
  const identity = document.getElementById("identity");
  identity.innerHTML = state.members
    .map((m) => `<option value="${m.id}">${esc(m.full_name)}</option>`)
    .join("");
  state.selfId = state.members.length ? state.members[0].id : null;
  identity.onchange = () => {
    state.selfId = Number(identity.value);
    switchRole("member");
  };

  // The agents, everywhere: Dwight and Pam act, Jim waits for V2.
  const dwight = character("dwight");
  const pam = character("pam");
  const jim = character("jim");
  document.getElementById("action-bar").innerHTML = `
    <button class="abtn dw" data-overlay="dwight-overlay">
      <img src="assets/${esc(dwight.avatar_asset)}" alt="" />+ ${esc(dwight.display_name)}
    </button>
    <button class="abtn pm" data-overlay="pam-overlay">
      <img src="assets/${esc(pam.avatar_asset)}" alt="" />? ${esc(pam.display_name)}
    </button>
    <button class="abtn wj" disabled title="Ephemeral chat - V2">
      <img src="assets/${esc(jim.avatar_asset)}" alt="" />~ ${esc(jim.display_name)} <span class="v2">V2</span>
    </button>`;
  document.getElementById("action-bar").onclick = (event) => {
    const button = event.target.closest("[data-overlay]");
    if (button) openOverlay(button.dataset.overlay);
  };

  for (const [id, key] of [["dwight-avatar", "dwight"], ["pam-avatar", "pam"],
                           ["desk-avatar", "michael"], ["toby-avatar", "toby"]]) {
    const img = document.getElementById(id);
    if (img) img.src = `assets/${character(key).avatar_asset}`;
  }
  document.getElementById("dwight-title").textContent = dwight.display_name;
  document.getElementById("pam-title").textContent = pam.display_name;
}

function switchRole(role) {
  state.role = role;
  document.querySelectorAll("#role-switch button").forEach((b) =>
    b.classList.toggle("active", b.dataset.role === role));
  document.getElementById("identity").hidden = role !== "member";
  const self = state.members.find((m) => m.id === state.selfId);
  document.getElementById("window-title").textContent =
    role === "manager" ? "SCRANTON - MANAGER VIEW"
      : `SCRANTON - TEAM MEMBER VIEW${self ? ` (${self.full_name})` : ""}`;

  const views = roleViews();
  document.getElementById("viewnav").innerHTML = views
    .map((view) => {
      const icon = view.icon
        ? `<img class="${view.pretzel ? "pretzel-ico" : ""}" src="assets/${esc(view.icon)}" alt="" />`
        : "";
      return `<button data-view="${view.id}">${icon}${esc(view.label)}</button>`;
    })
    .join("");
  document.getElementById("viewnav").onclick = (event) => {
    const button = event.target.closest("button[data-view]");
    if (button) switchView(button.dataset.view);
  };
  switchView(views[0].id);
}

function switchView(viewId) {
  document.querySelectorAll(".view").forEach((section) => {
    section.hidden = section.id !== `view-${viewId}`;
  });
  document.querySelectorAll("#viewnav button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewId);
  });
  const view = roleViews().find((v) => v.id === viewId);
  if (view?.load) view.load();
}

/* --- overlays (Tell Dwight / Ask Pam) --- */

function openOverlay(id) {
  const overlay = document.getElementById(id);
  overlay.hidden = false;
  // The history strip loads with the overlay and reopens folded back
  // to the last 5 of each memory (owner, 2026-07-15).
  if (id === "pam-overlay") loadPamArchive(true);
  overlay.querySelector("textarea, input")?.focus();
}

function bindOverlays() {
  document.querySelectorAll(".overlay").forEach((overlay) => {
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay || event.target.matches("[data-close]")) {
        overlay.hidden = true;
      }
      // Display only (owner, QA 2026-07-16): notes, decisions and
      // answers are already safe in the base - this declutters.
      if (event.target.matches("[data-erase]")) {
        document.getElementById(event.target.dataset.erase).innerHTML = "";
      }
    });
  });
}

/* --- human-readable tags (recadrage: clarity everywhere) --- */

const VIEW_LABELS = {
  team_member_file: "Member",
  project_file: "Project",
  client_file: "Client",
  meeting_agenda: "Meeting agenda",
  meeting_cr: "Meeting notes",
  annual_review: "Annual review",
  idea_box: "Idea box",
  team_radar: "Team radar",
  commitment: "Commitment",
  retrospective: "Retrospective",
};

function confidenceBadge(confidence) {
  // Spelled out, not a bare float: 'to check' is what asks for the eye.
  if (confidence >= 0.85) return `<span class="conf sure">&#10003; sure</span>`;
  return `<span class="conf check">? to check</span>`;
}

function tagChip(tag) {
  if (tag.view_type) {
    const label = VIEW_LABELS[tag.view_type] || tag.view_type;
    return `<span class="htag kind-view">${esc(label)} ${confidenceBadge(tag.confidence)}</span>`;
  }
  const name = state.labels[tag.entity_type]?.[tag.entity_id];
  const label = name || `${tag.entity_type} #${tag.entity_id}`;
  return `<span class="htag kind-${tag.entity_type}">${esc(label)} ${confidenceBadge(tag.confidence)}</span>`;
}

/* --- Tell Dwight: capture, clarification thread, rework loop --- */

function sensitivityDots(level) {
  const dots = [1, 2, 3, 4, 5]
    .map((step) => `<span class="${step <= level ? "on" : ""}">&#9679;</span>`)
    .join("");
  return `<span class="sensitivity" title="sensitivity ${level}/5">${dots}</span>`;
}

function segmentCard(segment) {
  const decided = segment.validation_status !== "proposed";
  const statusChip = decided
    ? `<span class="chip status-${segment.validation_status}">${segment.validation_status}</span>`
    : "";
  const actions = decided
    ? ""
    : `<div class="card-actions">
         <button class="btn btn-validate" data-decision="validated" data-segment="${segment.id}">Validate</button>
         <button class="btn btn-reject" data-reject-open data-segment="${segment.id}">Reject</button>
       </div>
       <div class="rework-box" hidden>
         <input type="text" placeholder="What is wrong or missing?" data-rework-input />
         <button class="btn btn-primary" data-rework-send data-segment="${segment.id}">Send to Dwight</button>
         <button class="btn btn-ghost" data-decision="rejected" data-segment="${segment.id}">Forget it</button>
       </div>`;
  return `
    <article class="card ${segment.data_type} ${decided ? "decided" : ""}" id="segment-${segment.id}">
      <p class="card-content">${esc(segment.content)}</p>
      <div class="card-meta">
        <span class="chip ${segment.data_type}">${segment.data_type}</span>
        ${sensitivityDots(segment.sensitivity_level)}
        ${segment.tags.map(tagChip).join("")}
        ${statusChip}
      </div>
      ${actions}
    </article>`;
}

function dwightBubble(text) {
  return `
    <div class="bubble-row">
      <img class="bubble-avatar" src="assets/${esc(character("dwight").avatar_asset)}" alt="" />
      <div class="bubble dwight">${esc(text)}</div>
    </div>`;
}

function managerBubble(text) {
  return `<div class="bubble-row manager"><div class="bubble manager">${esc(text)}</div></div>`;
}

function replyForm() {
  return `
    <form class="reply-form" data-reply-form>
      <input type="text" placeholder="Your answer to Dwight..." required />
      <button type="submit" class="btn btn-primary">Answer</button>
    </form>`;
}

function renderSegments(segments) {
  return (
    `<p class="sources-title">Proposed segments - you decide</p>` +
    segments.map(segmentCard).join("")
  );
}

/* Profile data is member-owned and member-DECLARED (owner, QA
 * 2026-07-14): the manager-side suggestion flow is gone. Members
 * declare through their own Pretzel Day space, and only there. */

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/* A birthday is a day + month, never an age: the stored year (always
 * 2000, see backend) is dropped at display time. */
function formatBirthday(iso) {
  if (!iso) return "";
  const [, month, day] = iso.split("-");
  return `${MONTHS[Number(month) - 1]} ${Number(day)}`;
}

/* The capture overlay is a running feed: each note appends a report
 * block ABOVE the input, and the input follows the conversation
 * (recadrage: "Anything else to tell Dwight?"). */
async function submitDwight(event) {
  event.preventDefault();
  const input = document.getElementById("dwight-input");
  const button = document.getElementById("dwight-submit");
  button.disabled = true;
  const result = document.getElementById("dwight-result");
  result.insertAdjacentHTML("beforeend",
    `<div class="report-block" data-open><p class="thinking">Dwight is structuring</p></div>`);
  const block = result.lastElementChild;
  try {
    // source_type stays server-side vocabulary; the picker was UI
    // friction (owner, QA 2026-07-14) - Dwight copes with what he gets.
    const answer = await api("/dwight/entries", {
      method: "POST",
      body: JSON.stringify({ raw_content: input.value, source_type: "note" }),
    });
    state.entryId = answer.entry_id;
    if (answer.clarification) {
      block.innerHTML = `
        <div class="thread">
          ${managerBubble(input.value)}
          ${dwightBubble(answer.clarification)}
        </div>
        ${replyForm()}`;
    } else {
      // The privacy acknowledgment (personal info left out, said out
      // loud) reads like Dwight talking, whether segments came or not.
      const privacy = answer.privacy_note ? dwightBubble(answer.privacy_note) : "";
      // The note itself stays on screen above the proposals (owner, QA
      // 2026-07-16): input and output side by side, comparable.
      block.innerHTML =
        `<div class="thread">${managerBubble(input.value)}</div>` +
        (answer.segments.length ? renderSegments(answer.segments) : "") + privacy;
    }
    input.value = "";
    input.placeholder = "Anything else to tell Dwight?";
    block.scrollIntoView({ block: "nearest" });
  } catch (error) {
    block.innerHTML = `<div class="error-banner">${esc(error.message)}</div>`;
  } finally {
    button.disabled = false;
  }
}

async function sendReply(form) {
  const input = form.querySelector("input");
  const answer = input.value;
  const block = form.closest(".report-block");
  const thread = block.querySelector(".thread");
  thread.insertAdjacentHTML("beforeend", managerBubble(answer));
  input.value = "";
  input.disabled = true;
  try {
    const result = await api(`/dwight/entries/${state.entryId}/reply`, {
      method: "POST",
      body: JSON.stringify({ message: answer }),
    });
    if (result.clarification) {
      // Dwight is still unsure: the thread simply continues.
      thread.insertAdjacentHTML("beforeend", dwightBubble(result.clarification));
    } else {
      form.remove();
      const privacy = result.privacy_note ? dwightBubble(result.privacy_note) : "";
      thread.insertAdjacentHTML(
        "afterend",
        (result.segments.length ? renderSegments(result.segments) : "") + privacy
      );
    }
  } catch (error) {
    thread.insertAdjacentHTML("beforeend", `<div class="error-banner">${esc(error.message)}</div>`);
  } finally {
    input.disabled = false;
  }
}

async function decideSegment(segmentId, decision) {
  const card = document.getElementById(`segment-${segmentId}`);
  const block = card.closest(".report-block");
  const segment = await api(`/dwight/segments/${segmentId}/validate`, {
    method: "POST",
    body: JSON.stringify({ status: decision }),
  });
  card.outerHTML = segmentCard(segment);
  checkReportComplete(block);
}

async function reworkSegment(segmentId, comment, button) {
  const card = document.getElementById(`segment-${segmentId}`);
  button.disabled = true;
  button.textContent = "Dwight is rewriting...";
  try {
    const replacement = await api(`/dwight/segments/${segmentId}/rework`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    });
    // The rejected proposal gives way to the corrected one, same spot.
    card.outerHTML = segmentCard(replacement);
  } catch (error) {
    card.insertAdjacentHTML("afterend", `<div class="error-banner">${esc(error.message)}</div>`);
  }
}

/* End of a report = every segment of THAT report decided, whatever the
 * mix of validates and rejects. The reward fires once per report.
 * (The old inline mood panel is gone: proxy entry is abolished - each
 * member declares their own mood in their own Pretzel Day space.) */
function checkReportComplete(block) {
  if (!block || !block.hasAttribute("data-open")) return;
  const undecided = block.querySelectorAll(".card:not(.decided):not(.profile-suggestion)").length;
  if (undecided > 0) return;
  block.removeAttribute("data-open");
  twss();
}

function bindDwightOverlay() {
  document.getElementById("dwight-form").addEventListener("submit", submitDwight);
  // One delegated handler for everything inside the result feed.
  document.getElementById("dwight-result").addEventListener("click", async (event) => {
    const target = event.target;
    if (target.matches("[data-reject-open]")) {
      const card = target.closest(".card");
      card.querySelector(".card-actions").hidden = true;
      card.querySelector(".rework-box").hidden = false;
      card.querySelector("[data-rework-input]").focus();
      return;
    }
    if (target.matches("[data-rework-send]")) {
      const card = target.closest(".card");
      const comment = card.querySelector("[data-rework-input]").value.trim();
      if (!comment) return;
      await reworkSegment(target.dataset.segment, comment, target);
      return;
    }
    if (target.matches("[data-decision]")) {
      target.disabled = true;
      try {
        await decideSegment(target.dataset.segment, target.dataset.decision);
      } catch (error) {
        target.disabled = false;
        alert(error.message);
      }
      return;
    }
  });
  document.getElementById("dwight-result").addEventListener("submit", async (event) => {
    if (!event.target.matches("[data-reply-form]")) return;
    event.preventDefault();
    await sendReply(event.target);
  });
}

/* --- Ask Pam (overlay thread) --- */

function sourceRow(source, index) {
  const date = source.created_at ? source.created_at.slice(0, 10) : "";
  // ref is the excerpt number the answer's [n] citations use; sources
  // are filtered to the cited ones server-side, so numbering must NOT
  // be recomputed from position (QA 2026-07-14: source noise).
  const number = source.ref ?? index + 1;
  // Two memories, two badges (session 2026-07-15): a validated team
  // note, or a shared document with the link back to the original.
  const isDoc = source.kind === "document";
  // A document source opens the in-app preview (owner, QA 2026-07-16:
  // direct access to the cited document); Drive stays one click away
  // inside it.
  const docName = isDoc
    ? (source.document_id
        ? `<button class="doc-preview-link" data-doc-preview="${source.document_id}">${esc(source.title)}</button>`
        : `<strong>${esc(source.title)}</strong>`) + " - "
    : "";
  const badge = isDoc
    ? `<span class="chip doc">document</span>`
    : `<span class="chip ${source.data_type}">team memory</span>`;
  return `
    <div class="source-row">
      <span class="source-num">[${number}]</span>
      <span class="source-text">${docName}${esc(source.content)}</span>
      ${badge}
      <span class="source-date">${date}</span>
    </div>`;
}

/* --- The history strip (inside the Pam overlay) --- */

/* Two memories, one strip (owner, 2026-07-15): the last Dwight notes
 * ABOVE the last Darryl documents, plus the unclassified bin and the
 * manager's one-click corrections. Opens on 5 of each; "Show more"
 * unfolds 10 more of each. Optional by design: any error hides the
 * strip and never blocks Pam. */

const HISTORY_FIRST = 5;
const HISTORY_STEP = 10;
let historyDepth = { notes: HISTORY_FIRST, docs: HISTORY_FIRST };

function snippet(text, max = 140) {
  return text.length > max ? text.slice(0, max - 3).trimEnd() + "..." : text;
}

function noteRow(entry) {
  const date = entry.created_at ? entry.created_at.slice(0, 10) : "";
  // The counter says what became of the note without opening it: how
  // many segments Dwight kept, how many the manager validated.
  const kept = entry.segments_total === 0
    ? `<span class="chip">no segments</span>`
    : `<span class="chip">${entry.segments_validated}/${entry.segments_total} validated</span>`;
  return `
    <div class="doc-row">
      <span class="source-text">${esc(snippet(entry.raw_content))}</span>
      ${kept}
      <span class="source-date">${date}</span>
    </div>`;
}

function docTagChips(doc) {
  return doc.tags
    .map((tag) => {
      const name = state.labels[tag.entity_type]?.[tag.entity_id]
        || `${tag.entity_type} #${tag.entity_id}`;
      return `<span class="htag kind-${tag.entity_type}">${esc(name)}</span>`;
    })
    .join("");
}

function docBadges(doc) {
  if (doc.status === "unclassified") {
    return `<button class="htag not-filed" data-classify="${doc.id}">not filed - file it</button>`;
  }
  return docTagChips(doc);
}

function docRow(doc) {
  const date = doc.modified_at ? doc.modified_at.slice(0, 10) : "";
  // The title opens the in-app preview (owner, QA 2026-07-16: read
  // before filing); the Drive link now lives inside the preview.
  const title = `<button class="doc-preview-link" data-doc-preview="${doc.id}">${esc(doc.title)}</button>`;
  const version = doc.is_latest ? "" : `<span class="chip">older version</span>`;
  return `
    <div class="doc-row">
      <span class="source-text">${title}</span>
      ${docBadges(doc)}${version}
      <span class="source-date">${date}</span>
    </div>`;
}

/* Filing a binned document: the picker offers the known clients and
 * projects (closed world, same seam-resolved labels as the tags). */
function classifyPicker(docId) {
  const groups = [["client", "Clients"], ["project", "Projects"]]
    .map(([kind, label]) => {
      const options = Object.entries(state.labels[kind] || {})
        .map(([id, name]) => `<option value="${kind}:${id}">${esc(name)}</option>`)
        .join("");
      return options ? `<optgroup label="${label}">${options}</optgroup>` : "";
    })
    .join("");
  return `
    <span class="classify-picker">
      <select data-classify-target>${groups}</select>
      <button class="btn btn-primary" data-classify-send="${docId}">File</button>
    </span>`;
}

async function loadPamArchive(reset = false) {
  const container = document.getElementById("pam-archive");
  const darryl = character("darryl");
  const dwight = character("dwight");
  if (reset) historyDepth = { notes: HISTORY_FIRST, docs: HISTORY_FIRST };
  try {
    const [notes, recent, bin] = await Promise.all([
      api(`/dwight/entries/recent?limit=${historyDepth.notes}`),
      api(`/darryl/documents/recent?limit=${historyDepth.docs}`),
      api("/darryl/documents/unclassified"),
    ]);
    const noteRows = notes.length
      ? notes.map(noteRow).join("")
      : `<p class="silent-line">No notes yet - tell ${esc(dwight.display_name)} what happened.</p>`;
    // The header and the sync button stay even on an empty corpus:
    // the FIRST sync has to start somewhere.
    const rows = recent.length
      ? recent.map(docRow).join("")
      : `<p class="silent-line">No documents in the archive yet - share a folder and sync.</p>`;
    // One 'Show more' PER memory (owner, QA 2026-07-16), each on its
    // own line; a full page means there may be more below.
    const noteMore = notes.length === historyDepth.notes
      ? `<div class="strip-foot"><button class="linklike" data-history-more="notes">Show more notes</button></div>`
      : "";
    const docMore = recent.length === historyDepth.docs
      ? `<div class="strip-foot"><button class="linklike" data-history-more="docs">Show more documents</button></div>`
      : "";
    const binLine = bin.length
      ? `<div class="strip-foot"><button class="linklike" data-bin-toggle>${bin.length} document${bin.length > 1 ? "s" : ""} not filed - open the bin</button></div>`
      : "";
    container.innerHTML = `
      <div class="archive-head">
        <p class="sources-title">Last notes to ${esc(dwight.display_name)}</p>
      </div>
      ${noteRows}
      ${noteMore}
      <div class="archive-head">
        <p class="sources-title">${esc(darryl.display_name)} filed these recently</p>
        <button class="btn btn-ghost" data-darryl-sync>Sync the shared folder</button>
      </div>
      <p class="thinking-none" id="archive-feedback"></p>
      ${rows}
      ${binLine}
      <div class="bin-rows" id="bin-rows" hidden>${bin.map(docRow).join("")}</div>
      ${docMore}`;
    container.hidden = false;
  } catch {
    container.hidden = true;
  }
}

function bindPamArchive() {
  const container = document.getElementById("pam-archive");
  // onclick, not addEventListener: the container survives overlay
  // openings and the handler must not accumulate (frontend gotcha).
  container.onclick = async (event) => {
    const target = event.target;
    if (target.matches("[data-bin-toggle]")) {
      const bin = document.getElementById("bin-rows");
      bin.hidden = !bin.hidden;
      return;
    }
    if (target.matches("[data-history-more]")) {
      // Only the clicked memory unfolds: the strips grow independently.
      historyDepth[target.dataset.historyMore] += HISTORY_STEP;
      await loadPamArchive();
      return;
    }
    if (target.matches("[data-darryl-sync]")) {
      target.disabled = true;
      target.textContent = "Darryl is filing...";
      try {
        const report = await api("/darryl/sync", { method: "POST" });
        await loadPamArchive();
        document.getElementById("archive-feedback").textContent =
          `Sync done: ${report.added} added, ${report.updated} updated, ` +
          `${report.removed} removed.`;
      } catch (error) {
        target.disabled = false;
        target.textContent = "Sync the shared folder";
        document.getElementById("archive-feedback").textContent = error.message;
      }
      return;
    }
    if (target.matches("[data-classify]")) {
      // The badge becomes the picker, in place: one click to correct.
      target.outerHTML = classifyPicker(target.dataset.classify);
      return;
    }
    if (target.matches("[data-classify-send]")) {
      const picker = target.closest(".classify-picker");
      const choice = picker.querySelector("[data-classify-target]").value;
      if (!choice) return;
      const [kind, id] = choice.split(":");
      target.disabled = true;
      try {
        await api(`/darryl/documents/${target.dataset.classifySend}/classify`, {
          method: "POST",
          body: JSON.stringify({ entity_type: kind, entity_id: Number(id) }),
        });
        await loadPamArchive();
      } catch (error) {
        target.disabled = false;
        alert(error.message);
      }
    }
  };
}

/* --- Document preview (owner, QA 2026-07-16: read before filing) --- */

/* The preview shows the extracted text re-read from SQLite - exactly
 * what Pam reasons over - never a rendering of the original format:
 * Drive displays originals natively, Scranton does not rebuild that. */
async function openDocPreview(docId) {
  const title = document.getElementById("doc-preview-title");
  const meta = document.getElementById("doc-preview-meta");
  const body = document.getElementById("doc-preview-body");
  title.textContent = "";
  meta.textContent = "";
  body.innerHTML = `<p class="thinking">Opening</p>`;
  openOverlay("doc-overlay");
  try {
    const doc = await api(`/darryl/documents/${docId}`);
    title.textContent = doc.title;
    meta.textContent = [
      doc.folder_path,
      doc.modified_at ? doc.modified_at.slice(0, 10) : "",
    ].filter(Boolean).join(" - ");
    // Chips are informative here, not actionable: filing happens in
    // the strip, where the picker's handler lives.
    const chips = doc.status === "unclassified"
      ? `<span class="htag not-filed">not filed yet</span>`
      : docTagChips(doc);
    const version = doc.is_latest ? "" : `<span class="chip">older version</span>`;
    const drive = doc.web_view_link
      ? `<a class="btn btn-ghost" href="${esc(doc.web_view_link)}" target="_blank" rel="noopener">Open in Drive</a>`
      : "";
    const content = doc.content
      ? `<div class="doc-content">${esc(doc.content)}</div>`
      : `<p class="silent-line">${doc.status === "cataloged"
          ? "Cataloged by name, date and link - spreadsheet content is never extracted."
          : "No text could be extracted from this file - the original in Drive is the reference."}</p>`;
    body.innerHTML = `<div class="doc-preview-bar">${chips}${version}${drive}</div>${content}`;
  } catch (error) {
    body.innerHTML = `<div class="error-banner">${esc(error.message)}</div>`;
  }
}

/* A summary served AS the answer (recadrage): Pam understood that the
 * question called for the full picture of one entity. */
function pamSummaryCard(summary) {
  const label = [summary.title, summary.target_label].filter(Boolean).join(" - ");
  const sections = summary.sections
    .map(
      (section) =>
        `<p class="summary-heading">${esc(section.heading)}</p>
         <p class="summary-text">${esc(section.content).replace(/\n/g, "<br />")}</p>`
    )
    .join("");
  // The save gesture from a Pam card (editing session, 2026-07-16):
  // persist, then land on the Desk editor - by hand or with Dwight.
  state.pamSummaries.push(summary);
  return `
    <div class="pam-template">
      <p class="tpl-label">${esc(label.toUpperCase())}</p>
      ${sections}
      <div class="card-actions">
        <button class="btn btn-primary" data-save-pam="${state.pamSummaries.length - 1}"
          title="Persist this document and edit it - by hand or with Dwight.">Save and edit</button>
      </div>
    </div>`;
}

async function submitPam(event) {
  event.preventDefault();
  const input = document.getElementById("pam-input");
  const button = document.getElementById("pam-submit");
  const thread = document.getElementById("pam-thread");
  button.disabled = true;
  thread.insertAdjacentHTML("beforeend", managerBubble(input.value));
  thread.insertAdjacentHTML("beforeend", `<p class="thinking" id="pam-wait">Pam is remembering</p>`);
  try {
    const result = await api("/pam/query", {
      method: "POST",
      body: JSON.stringify({ question: input.value }),
    });
    const template = result.summary ? pamSummaryCard(result.summary) : "";
    const sources = result.sources.length
      ? `<p class="sources-title">Sources</p>` + result.sources.map(sourceRow).join("")
      : "";
    document.getElementById("pam-wait").outerHTML =
      `<div class="answer-card">${esc(result.answer)}</div>${template}${sources}`;
    input.value = "";
    input.placeholder = "Anything else to ask Pam?";
    thread.lastElementChild.scrollIntoView({ block: "nearest" });
  } catch (error) {
    document.getElementById("pam-wait").outerHTML =
      `<div class="error-banner">${esc(error.message)}</div>`;
  } finally {
    button.disabled = false;
  }
}

/* --- Manager: Dashboard --- */

const MOODS = [
  { level: "flow", label: "In the zone", emoji: "\u{1F680}" },
  { level: "ctrl", label: "Under control", emoji: "\u{1F642}" },
  { level: "pretzel_day", label: "So-so", emoji: "\u{1F968}" },
  { level: "press", label: "Under pressure", emoji: "\u{1F605}" },
  { level: "stuck", label: "Stuck", emoji: "\u{1F616}" },
  { level: "danger", label: "Not okay", emoji: "\u{1F198}" },
];
const MOOD_META = Object.fromEntries(MOODS.map((mood) => [mood.level, mood]));

function moodDisplay(level) {
  const meta = MOOD_META[level];
  return meta ? `${meta.emoji} ${meta.label}` : level;
}

function moodDots(checkins) {
  if (!checkins.length) return `<span class="silent">no check-in</span>`;
  return checkins
    .slice(-7)
    .map((point) =>
      `<span class="dot mood-${point.mood_level}"
             title="${point.at.slice(0, 10)}: ${MOOD_META[point.mood_level]?.label || point.mood_level}"></span>`)
    .join("");
}

async function loadDashboard() {
  show("dashboard-body", `<p class="thinking">Assembling the picture</p>`);
  try {
    const [overview, catalog] = await Promise.all([
      api("/toby/overview?days=7"),
      api("/summaries"),
    ]);
    const signals = overview.signals.length;
    const moodboard = overview.members
      .map(
        (member) => `
        <div class="mood-row">
          <span class="mn">${esc(member.full_name)}</span>
          <span class="dots">${moodDots(member.checkins)}</span>
          <button class="linklike" data-goto="toby">signals &rarr;</button>
        </div>`
      )
      .join("");
    show(
      "dashboard-body",
      `<div class="cards-row">
         <div class="mcard"><div class="ml">Team</div><div class="mv">${state.members.length}</div><div class="ms">active members</div></div>
         <div class="mcard"><div class="ml">Projects</div><div class="mv">${(catalog.targets.project || []).length}</div><div class="ms">in the memory</div></div>
         <div class="mcard ${signals ? "alert" : ""}" data-goto="toby" role="button" tabindex="0"
              title="Open ${esc(character("toby").display_name)}">
           <div class="ml">Weak signals</div><div class="mv">${signals}</div>
           <div class="ms">${signals ? `open ${esc(character("toby").display_name)} &rarr;` : "all quiet"}</div></div>
       </div>
       ${ritualCard()}
       <p class="sources-title">Pretzel Day - moodboard this week</p>
       ${moodboard || `<p class="placeholder">No check-ins yet.</p>`}`
    );
    document.getElementById("dashboard-body").onclick = (event) => {
      const button = event.target.closest("[data-goto]");
      if (button) switchView(button.dataset.goto);
    };
  } catch (error) {
    show("dashboard-body", `<div class="error-banner">${esc(error.message)}</div>`);
  }
}

/* --- Manager: Michael's Desk (1:1s and meetings, on the summary engine) --- */

function deskBlock(id, title, description, controls) {
  return `
    <div class="desk-item" id="desk-${id}">
      <div class="desk-head">
        <div><div class="desk-title">${esc(title)}</div>
        <p class="view-sub">${esc(description)}</p></div>
        <div class="desk-controls">${controls}</div>
      </div>
      <div class="desk-output" id="desk-out-${id}"></div>
    </div>`;
}

async function loadDesk() {
  const memberOptions = state.members
    .map((m) => `<option value="${m.id}">${esc(m.full_name)}</option>`)
    .join("");
  show(
    "desk-body",
    deskBlock("agenda", "Next team meeting",
      "Pam drafts the agenda from everything validated. Never from scratch.",
      `<button class="btn btn-primary" data-desk="meeting_agenda" data-out="agenda">Draft the agenda</button>`) +
    deskBlock("radar", "Team radar - the 360",
      "Workload, signals and equity material, aggregated. Never a ranking.",
      `<button class="btn btn-primary" data-desk="team_radar" data-out="radar">Assemble</button>`) +
    deskBlock("one-on-one", "1:1 preparation",
      "Everything the memory holds about one person, ready for the conversation.",
      `<select id="desk-member">${memberOptions}</select>
       <button class="btn btn-primary" data-desk="team_member_file" data-out="one-on-one" data-target="desk-member">Brief me</button>
       <button class="btn btn-ghost" data-desk="annual_review" data-out="one-on-one" data-target="desk-member">Annual review material</button>`) +
    deskBlock("mydocs", "My documents",
      "Saved snapshots you made your own. The memory keeps moving; they never change on their own.",
      "")
  );
  document.getElementById("desk-body").onclick = async (event) => {
    try {
      if (await handleEditorClick(event.target)) return;
    } catch (error) {
      alert(error.message);
      return;
    }
    const save = event.target.closest("[data-save-doc]");
    if (save) {
      const result = state.deskSummaries[save.dataset.saveDoc];
      if (!result) return;
      save.disabled = true;
      try {
        const doc = await saveSummaryAsDocument(result);
        await openEditor(doc.id);
        document.getElementById("desk-mydocs").scrollIntoView({ block: "start" });
      } catch (error) {
        save.disabled = false;
        alert(error.message);
      }
      return;
    }
    const button = event.target.closest("[data-desk]");
    if (!button) return;
    const targetSelect = button.dataset.target
      ? document.getElementById(button.dataset.target)
      : null;
    await renderSummaryInto(
      `desk-out-${button.dataset.out}`,
      button.dataset.desk,
      targetSelect ? Number(targetSelect.value) : null,
      button
    );
  };
  await loadMyDocs();
  if (state.editorOpenId) {
    // A Pam-card save lands here: the Desk opens straight on the doc.
    const docId = state.editorOpenId;
    state.editorOpenId = null;
    await openEditor(docId);
    document.getElementById("desk-mydocs").scrollIntoView({ block: "start" });
  }
}

async function renderSummaryInto(containerId, templateId, targetId, button) {
  button.disabled = true;
  show(containerId, `<p class="thinking">Dwight and Pam are assembling</p>`);
  try {
    const query = targetId ? `?target_id=${targetId}` : "";
    const result = await api(`/summaries/${templateId}${query}`);
    const subtitle = [
      result.target_label,
      result.window_days ? `last ${result.window_days} days` : "full history",
      new Date(result.generated_at).toLocaleString(),
    ].filter(Boolean).join(" - ");
    const sections = result.sections
      .map(
        (section) =>
          `<p class="summary-heading">${esc(section.heading)}</p>
           <p class="summary-text">${esc(section.content).replace(/\n/g, "<br />")}</p>`
      )
      .join("");
    const sources = result.sources.length
      ? `<p class="sources-title">Sources (${result.sources.length})</p>` +
        result.sources.map(sourceRow).join("")
      : "";
    // Send Angela: plain download links, name from the character map.
    const angela = character("angela");
    const exportBase = `${API}/angela/export/${templateId}${query}${query ? "&" : "?"}format=`;
    // The save gesture (editing session, 2026-07-16): this generation
    // becomes a persisted document the manager edits and owns.
    state.deskSummaries[containerId] = result;
    show(
      containerId,
      `<div class="answer-card summary-card">
         <p class="summary-subtitle">${esc(subtitle)}</p>
         ${sections}
       </div>
       <div class="export-row">
         <button class="btn btn-primary" data-save-doc="${containerId}"
                 title="Persist this generation and edit it - by hand or with Dwight.">Save and edit</button>
         <img class="bubble-avatar" src="assets/${esc(angela.avatar_asset)}" alt="" />
         <a class="btn btn-ghost" href="${exportBase}md" download>${esc(angela.display_name)} - .md</a>
         <a class="btn btn-ghost" href="${exportBase}html" download>printable .html</a>
       </div>
       ${sources}`
    );
  } catch (error) {
    show(containerId, `<div class="error-banner">${esc(error.message)}</div>`);
  } finally {
    button.disabled = false;
  }
}

/* --- Edited documents (the editing engine's surface, 2026-07-16) ---
 *
 * Templates stay living; a saved document is the manager's clean
 * notebook. It never changes on its own: the delta with the moving
 * memory arrives as PROPOSALS, Dwight revises as a pure reviser, and
 * every change he proposes shows as a computed diff - validate at a
 * glance (owner request). Same engine for Desk and Pam cards; Oscar
 * will consume it too. */

function mdFromSummary(result) {
  return result.sections
    .map((section) => `## ${section.heading}\n\n${section.content}`)
    .join("\n\n");
}

/* Markdown -> folding sections. Native <details> is the accordion:
 * fold a section once it is covered in the 1:1 (owner request). */
function renderDocBody(md) {
  const parts = md.split(/^## /m);
  const intro = parts[0].trim()
    ? `<p class="summary-text">${esc(parts[0].trim()).replace(/\n/g, "<br />")}</p>`
    : "";
  const sections = parts
    .slice(1)
    .map((part) => {
      const newline = part.indexOf("\n");
      const heading = newline === -1 ? part : part.slice(0, newline);
      const body = newline === -1 ? "" : part.slice(newline + 1).trim();
      return `
        <details class="doc-section" open>
          <summary>${esc(heading.trim())}</summary>
          <p class="summary-text">${esc(body).replace(/\n/g, "<br />")}</p>
        </details>`;
    })
    .join("");
  return intro + sections;
}

/* The review diff, computed server-side (difflib): insertions
 * highlighted, deletions struck through. Never stored. */
function renderDiff(spans) {
  return spans
    .map((span) => {
      const text = esc(span.text).replace(/\n/g, "<br />");
      if (span.op === "insert") return `<span class="diff-ins">${text}</span>`;
      if (span.op === "delete") return `<span class="diff-del">${text}</span>`;
      return text;
    })
    .join("");
}

async function saveSummaryAsDocument(result) {
  const title = [result.title, result.target_label].filter(Boolean).join(" - ");
  return api("/documents", {
    method: "POST",
    body: JSON.stringify({
      title,
      template_key: result.template_id,
      target_entity_type: result.target_type,
      target_entity_id: result.target_id,
      content_md: mdFromSummary(result),
      generated_at: result.generated_at,
    }),
  });
}

async function loadMyDocs() {
  const container = document.getElementById("desk-out-mydocs");
  if (!container) return;
  try {
    const docs = await api("/documents");
    if (!docs.length) {
      show("desk-out-mydocs",
        `<p class="silent-line">Nothing saved yet - generate a document above and keep it.</p>`);
      return;
    }
    show(
      "desk-out-mydocs",
      docs
        .map((doc) => {
          const news = doc.news_count
            ? `<span class="chip news">${doc.news_count} new since your edit</span>`
            : "";
          return `
            <div class="doc-row doc-open" data-open-doc="${doc.id}" role="button" tabindex="0">
              <span class="source-text"><strong>${esc(doc.title)}</strong></span>
              ${news}
              <span class="source-date">edited ${doc.updated_at.slice(0, 10)}</span>
            </div>`;
        })
        .join("")
    );
  } catch (error) {
    show("desk-out-mydocs", `<div class="error-banner">${esc(error.message)}</div>`);
  }
}

function newsRow(segment, index) {
  return `
    <div class="doc-row">
      <input type="checkbox" checked data-news-pick value="${segment.segment_id}"
             id="news-${index}" />
      <label class="source-text" for="news-${index}">${esc(segment.content)}</label>
      <span class="source-date">${segment.created_at.slice(0, 10)}</span>
    </div>`;
}

async function openEditor(docId) {
  const container = document.getElementById("desk-out-mydocs");
  show("desk-out-mydocs", `<p class="thinking">Opening your document</p>`);
  try {
    const [doc, delta] = await Promise.all([
      api(`/documents/${docId}`),
      api(`/documents/${docId}/delta`),
    ]);
    state.editorDoc = doc;
    const dwight = character("dwight");
    const news = delta.segments.length
      ? `<div class="news-panel">
           <p class="sources-title">The memory moved since your edit - ${delta.segments.length} validated point${delta.segments.length > 1 ? "s" : ""} about this subject</p>
           ${delta.segments.map(newsRow).join("")}
           <div class="form-row">
             <input type="text" id="news-instruction"
                    placeholder="Optional: where or how to weave them in" />
             <button class="btn btn-primary" data-doc-weave>Weave in with ${esc(dwight.display_name)}</button>
             <button class="btn btn-ghost" data-doc-dismiss
                     title="They stay in the team memory - they just stop knocking here.">Dismiss</button>
           </div>
         </div>`
      : "";
    show(
      "desk-out-mydocs",
      `<div class="editor-head">
         <button class="linklike" data-doc-back>&larr; My documents</button>
         <p class="summary-subtitle">${esc(doc.title)} - saved ${doc.updated_at.slice(0, 10)}.
           Your document: it never changes on its own.</p>
       </div>
       ${news}
       <div class="answer-card summary-card" id="doc-body">${renderDocBody(doc.content_md)}</div>
       <div id="doc-proposal"></div>
       <div class="form-row" id="doc-actions">
         <input type="text" id="doc-instruction"
                placeholder="What should ${esc(dwight.display_name)} change?" />
         <button class="btn btn-primary" data-doc-revise>Edit with ${esc(dwight.display_name)}</button>
         <button class="btn btn-ghost" data-doc-manual>Edit manually</button>
       </div>
       <div id="doc-manual" hidden>
         <textarea id="doc-manual-text" rows="14"></textarea>
         <div class="form-row">
           <button class="btn btn-primary" data-doc-manual-save>Save</button>
           <button class="btn btn-ghost" data-doc-manual-cancel>Cancel</button>
         </div>
       </div>`
    );
    document.getElementById("doc-manual-text").value = doc.content_md;
  } catch (error) {
    show("desk-out-mydocs", `<div class="error-banner">${esc(error.message)}</div>`);
  }
}

function renderProposal(revision, fromNews) {
  state.editorProposal = { content_md: revision.content_md, fromNews };
  const dwight = character("dwight");
  show(
    "doc-proposal",
    `<div class="answer-card proposal-card">
       <p class="sources-title">${esc(dwight.display_name)}'s proposal - his changes, computed, nothing saved yet</p>
       <p class="summary-text diff-text">${renderDiff(revision.diff)}</p>
       <div class="card-actions">
         <button class="btn btn-validate" data-doc-keep>Keep it</button>
         <button class="btn btn-reject" data-doc-discard>Discard</button>
       </div>
     </div>`
  );
}

async function reviseDocument(instruction, segmentIds, button) {
  const dwight = character("dwight");
  button.disabled = true;
  show("doc-proposal", `<p class="thinking">${esc(dwight.display_name)} is revising</p>`);
  try {
    const revision = await api(`/documents/${state.editorDoc.id}/revise`, {
      method: "POST",
      body: JSON.stringify({ instruction, include_segment_ids: segmentIds }),
    });
    renderProposal(revision, segmentIds.length > 0);
  } catch (error) {
    show("doc-proposal", `<div class="error-banner">${esc(error.message)}</div>`);
  } finally {
    button.disabled = false;
  }
}

/* One delegated handler for every editor gesture (desk-body onclick
 * routes here). Returns true when the click was an editor action. */
async function handleEditorClick(target) {
  if (target.matches("[data-open-doc]")) {
    await openEditor(Number(target.dataset.openDoc));
    return true;
  }
  if (target.matches("[data-doc-back]")) {
    state.editorDoc = null;
    await loadMyDocs();
    return true;
  }
  if (target.matches("[data-doc-dismiss]")) {
    target.disabled = true;
    await api(`/documents/${state.editorDoc.id}/mark-reviewed`, { method: "POST" });
    await openEditor(state.editorDoc.id);
    return true;
  }
  if (target.matches("[data-doc-weave]")) {
    const picked = [...document.querySelectorAll("[data-news-pick]:checked")]
      .map((box) => Number(box.value));
    if (!picked.length) return true;
    const instruction =
      document.getElementById("news-instruction").value.trim() ||
      "Weave the selected new points into the right sections.";
    await reviseDocument(instruction, picked, target);
    return true;
  }
  if (target.matches("[data-doc-revise]")) {
    const instruction = document.getElementById("doc-instruction").value.trim();
    if (!instruction) return true;
    await reviseDocument(instruction, [], target);
    return true;
  }
  if (target.matches("[data-doc-keep]")) {
    target.disabled = true;
    const proposal = state.editorProposal;
    await api(`/documents/${state.editorDoc.id}/save`, {
      method: "POST",
      body: JSON.stringify({ content_md: proposal.content_md }),
    });
    if (proposal.fromNews) {
      // The woven news is triaged: advance the bookmark in the same
      // gesture, the rest of the delta was the manager's to leave out.
      await api(`/documents/${state.editorDoc.id}/mark-reviewed`, { method: "POST" });
    }
    await openEditor(state.editorDoc.id);
    return true;
  }
  if (target.matches("[data-doc-discard]")) {
    state.editorProposal = null;
    show("doc-proposal", "");
    return true;
  }
  if (target.matches("[data-doc-manual]")) {
    document.getElementById("doc-manual").hidden = false;
    document.getElementById("doc-actions").hidden = true;
    return true;
  }
  if (target.matches("[data-doc-manual-cancel]")) {
    document.getElementById("doc-manual").hidden = true;
    document.getElementById("doc-actions").hidden = false;
    return true;
  }
  if (target.matches("[data-doc-manual-save]")) {
    target.disabled = true;
    await api(`/documents/${state.editorDoc.id}/save`, {
      method: "POST",
      body: JSON.stringify({
        content_md: document.getElementById("doc-manual-text").value,
      }),
    });
    await openEditor(state.editorDoc.id);
    return true;
  }
  return false;
}

/* --- Manager: Meet Toby (team health) --- */

function moodChip(level) {
  return level
    ? `<span class="chip mood-${level}">${moodDisplay(level)}</span>`
    : `<span class="chip">no check-in</span>`;
}

function signalCard(signal) {
  return `
    <div class="card signal">
      <div class="card-meta">
        <span class="chip signal-${signal.type}">${signal.type.replace(/_/g, " ")}</span>
        <strong>${esc(signal.member_name)}</strong>
      </div>
      <p class="signal-detail">${esc(signal.detail)}</p>
    </div>`;
}

function trendChart(points) {
  if (!points.length) return `<p class="placeholder">No check-ins in the window yet.</p>`;
  const columns = points
    .map((point) => {
      const height = Math.max(8, (point.average_mood_index / 5) * 100);
      const day = point.day.slice(5).replace("-", "/");
      return `<div class="trend-col" title="${point.day}: team average ${point.average_mood_index}/5 over ${point.checkins} check-in(s)">
                <div class="trend-bar" style="height:${height}%"></div>
                <span class="trend-day">${day}</span>
              </div>`;
    })
    .join("");
  // A readable scale (owner, QA 2026-07-14): axis ends labeled with the
  // palette words, one column per day - averages of MOODS, never people.
  return `
    <div class="trend-wrap">
      <div class="trend-axis"><span>${moodDisplay("flow")}</span><span>${moodDisplay("danger")}</span></div>
      <div class="trend">${columns}</div>
    </div>
    <p class="trend-caption">One bar per day: the average of that day's team check-ins,
      from ${moodDisplay("danger")} (bottom) to ${moodDisplay("flow")} (top). Hover a bar for detail.</p>`;
}

/* The drill-down (recadrage): what each person actually SAID, dated
 * and quoted - never just dots with a thousand possible causes. */
function voicedRow(item) {
  const kind = item.kind === "checkin_note" ? "check-in" : "observation";
  const sensitivity = item.sensitivity_level ? sensitivityDots(item.sensitivity_level) : "";
  return `
    <div class="voiced">
      <span class="vd">${item.at.slice(0, 10)}</span>
      <span class="vq">"${esc(item.text)}"</span>
      <span class="chip">${kind}</span>${sensitivity}
    </div>`;
}

/* What the member chose to declare in their Pretzel Day space: the
 * manager READS it here, never edits it. Access, not ownership. */
function declaredChips(memberId) {
  const member = state.members.find((m) => m.id === memberId);
  const chips = [];
  if (member?.birthday) chips.push(`birthday: ${formatBirthday(member.birthday)}`);
  if (member?.personal_profile) {
    chips.push(member.personal_profile.split("\n")[0].slice(0, 70));
  }
  if (!chips.length) {
    return `<div class="declared"><span>has shared nothing - that's their right</span></div>`;
  }
  return `<div class="declared">${chips.map((chip) => `<span>${esc(chip)}</span>`).join("")}</div>`;
}

function tobyMemberCard(member) {
  const voiced = member.voiced.length
    ? member.voiced.map(voicedRow).join("")
    : `<p class="silent-line">Nothing verbalized in the window - sometimes the silence is the signal.</p>`;
  return `
    <div class="card toby-member">
      <div class="member-row">
        <div class="member-id">
          <strong>${esc(member.full_name)}</strong>
          <span class="member-role">${esc(member.role || "")}</span>
        </div>
        <div class="dots">${moodDots(member.checkins)}</div>
        ${moodChip(member.latest_mood)}
      </div>
      ${voiced}
      ${declaredChips(member.team_member_id)}
    </div>`;
}

async function loadToby() {
  show("toby-body", `<p class="thinking">Toby is aggregating</p>`);
  const overview = await api("/toby/overview?days=30");
  const signals = overview.signals.length
    ? overview.signals.map(signalCard).join("")
    : `<p class="placeholder">No weak signal in the window. Good.</p>`;
  show(
    "toby-body",
    `<p class="sources-title">Weak signals</p>${signals}
     <p class="sources-title">Team mood - last ${overview.window_days} days</p>
     ${trendChart(overview.team_trend)}
     <p class="sources-title">Member by member - in their words</p>
     ${overview.members.map(tobyMemberCard).join("")}`
  );
}

/* --- Team member: My board --- */

async function loadMyBoard() {
  show("myboard-body", `<p class="thinking">Loading your board</p>`);
  try {
    const overview = await api("/toby/overview?days=1");
    const me = overview.members.find((m) => m.team_member_id === state.selfId);
    const member = state.members.find((m) => m.id === state.selfId) || {};
    const moodCard = me?.latest_mood
      ? `<div class="mv mood-text">${moodDisplay(me.latest_mood)}</div><div class="ms">today</div>`
      : `<div class="mv mood-text">-</div><div class="ms">no check-in yet today</div>`;
    show(
      "myboard-body",
      `<div class="cards-row two">
         <div class="mcard accent"><div class="ml">Pretzel Day</div>${moodCard}</div>
         <div class="mcard"><div class="ml">About me</div>
           <div class="ms about-snippet">${esc(member.personal_profile || "Nothing shared yet - your call, always.")}</div></div>
       </div>
       <div class="card">
         <p class="card-content">Your mood and what you choose to share live in
           <strong>Pretzel Day</strong> - your space, visible to your manager only.</p>
         <div class="card-actions">
           <button class="btn btn-primary" data-goto="pretzel">Open Pretzel Day</button>
         </div>
       </div>
       <p class="view-sub">Personal notes and actions arrive with multi-user capture (V2).</p>`
    );
    document.getElementById("myboard-body").onclick = (event) => {
      const button = event.target.closest("[data-goto]");
      if (button) switchView(button.dataset.goto);
    };
  } catch (error) {
    show("myboard-body", `<div class="error-banner">${esc(error.message)}</div>`);
  }
}

/* --- Team member: Pretzel Day (my mood + what I share about me) --- */

const moodState = { level: null };

async function loadPretzel() {
  const member = state.members.find((m) => m.id === state.selfId) || {};
  const [, month, day] = (member.birthday || "--").split("-");
  const dayOptions = ['<option value="">-</option>']
    .concat(Array.from({ length: 31 }, (_, i) =>
      `<option value="${i + 1}" ${Number(day) === i + 1 ? "selected" : ""}>${i + 1}</option>`))
    .join("");
  const monthOptions = ['<option value="">-</option>']
    .concat(MONTHS.map((name, i) =>
      `<option value="${i + 1}" ${Number(month) === i + 1 ? "selected" : ""}>${name}</option>`))
    .join("");
  moodState.level = null;
  show(
    "pretzel-body",
    `<div class="pd-grid">
       <div class="checkin">
         <div class="pd-head">
           <img class="pd-icon" src="assets/pretzelday.jpg" alt="Pretzel Day" />
           <div><h2>How is the day going?</h2>
           <p class="view-sub">30 seconds. Your mood, your words.</p></div>
         </div>
         <div class="palette" id="mood-palette">
           ${MOODS.map(
             (mood) =>
               `<button type="button" class="mood-btn mood-${mood.level}" data-level="${mood.level}">
                  <span class="mood-swatch"></span>
                  <span class="mood-emoji">${mood.emoji}</span>${mood.label}
                </button>`
           ).join("")}
         </div>
         <input id="mood-note" type="text" placeholder="Optional note - one line is plenty" />
         <div class="form-row">
           <button class="btn btn-primary" id="mood-submit" disabled>Check in</button>
           <span id="mood-feedback" class="thinking-none"></span>
         </div>
         <p class="sources-title">My last 30 days - visible to you and your manager</p>
         <div id="my-moods"><p class="thinking">Loading</p></div>
       </div>
       <div class="share-box">
         <h2>About me - shared on purpose</h2>
         <p class="who">Visible by your manager, and only them - so they can help
           the team feel good. Everything here is optional and stays yours.</p>
         <label class="field-label">Birthday - day and month. Your age is nobody's business here.</label>
         <div class="birthday-row">
           <select data-bd-day>${dayOptions}</select>
           <select data-bd-month>${monthOptions}</select>
         </div>
         <label class="field-label">What I enjoy, what is good to know about me</label>
         <textarea rows="4" data-profile
           placeholder="Interests, passions, favorites - whatever you want known.">${esc(member.personal_profile || "")}</textarea>
         <div class="card-actions">
           <button class="btn btn-primary" id="share-save">Save what I share</button>
           <span class="thinking-none" id="share-feedback"></span>
         </div>
       </div>
     </div>`
  );

  document.getElementById("mood-palette").onclick = (event) => {
    const button = event.target.closest(".mood-btn");
    if (!button) return;
    moodState.level = button.dataset.level;
    document.querySelectorAll("#mood-palette .mood-btn")
      .forEach((b) => b.classList.toggle("selected", b === button));
    document.getElementById("mood-submit").disabled = false;
  };
  document.getElementById("mood-submit").onclick = submitMood;
  document.getElementById("share-save").onclick = saveShare;
  loadMyMoodHistory();
}

/* The member's own history - their personal Toby (owner, QA 2026-07-14):
 * a check-in must not vanish into a manager-only view. */
async function loadMyMoodHistory() {
  const container = document.getElementById("my-moods");
  if (!container) return;
  try {
    const checkins = await api("/mood/checkins?days=30");
    const mine = checkins
      .filter((checkin) => checkin.team_member_id === state.selfId)
      .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
    if (!mine.length) {
      container.innerHTML = `<p class="silent-line">No check-ins yet - this stays yours to read.</p>`;
      return;
    }
    container.innerHTML = mine
      .slice(0, 14)
      .map(
        (checkin) => `
        <div class="voiced">
          <span class="vd">${checkin.created_at.slice(0, 10)}</span>
          <span class="dot mood-${checkin.mood_level}"></span>
          <span class="vq">${moodDisplay(checkin.mood_level)}${checkin.note ? ` - "${esc(checkin.note)}"` : ""}</span>
        </div>`
      )
      .join("");
  } catch (error) {
    container.innerHTML = `<p class="silent-line">${esc(error.message)}</p>`;
  }
}

async function submitMood() {
  const button = document.getElementById("mood-submit");
  button.disabled = true;
  try {
    const note = document.getElementById("mood-note").value.trim();
    // Always yourself: identity is picked at the top, never a proxy.
    await api("/mood/checkins", {
      method: "POST",
      body: JSON.stringify({
        team_member_id: state.selfId,
        mood_level: moodState.level,
        note: note || null,
      }),
    });
    document.getElementById("mood-feedback").textContent = "Recorded. Thanks for saying it.";
    document.getElementById("mood-note").value = "";
    loadMyMoodHistory();
    twss();
  } catch (error) {
    document.getElementById("mood-feedback").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function saveShare() {
  const button = document.getElementById("share-save");
  button.disabled = true;
  try {
    const body = document.getElementById("pretzel-body");
    const day = body.querySelector("[data-bd-day]").value;
    const month = body.querySelector("[data-bd-month]").value;
    // The year is a placeholder (2000), erased server-side anyway.
    const birthday =
      day && month
        ? `2000-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`
        : null;
    const updated = await api(`/team/members/${state.selfId}/profile`, {
      method: "PUT",
      body: JSON.stringify({
        personal_profile: body.querySelector("[data-profile]").value.trim() || null,
        birthday,
      }),
    });
    const cached = state.members.find((m) => m.id === state.selfId);
    if (cached) Object.assign(cached, updated);
    document.getElementById("share-feedback").textContent = "Saved. Shared with your manager only.";
  } catch (error) {
    document.getElementById("share-feedback").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

/* --- Maire de Scranton (birthday ritual, manager dashboard) --- */

/* One Maire surface only (owner, QA 2026-07-14): the ritual card on
 * the dashboard. The celebration still fires once per page load. */
async function loadMayor() {
  if (!CELEBRATIONS) {
    // Paused with the rest of the celebrations: no popin, no ritual
    // card, not even the fetch. The backend endpoint stays live.
    state.mayorOverview = { mayor: null, upcoming: [] };
    return;
  }
  try {
    state.mayorOverview = await api("/team/mayor");
  } catch {
    state.mayorOverview = { mayor: null, upcoming: [] };
  }
  const { mayor } = state.mayorOverview;
  if (mayor && !state.celebrated) {
    state.celebrated = true;
    setTimeout(
      () =>
        twss({
          mayor: true,
          title: "MAIRE DE SCRANTON",
          quote: `${mayor.full_name} runs this town today. Their day, their rules.`,
          signature: "- By order of the Office of the Mayor",
        }),
      900
    );
  }
}

function ritualCard() {
  const { mayor, upcoming } = state.mayorOverview || { mayor: null, upcoming: [] };
  if (!mayor && !upcoming.length) return "";
  const mayorLine = mayor
    ? `<p class="card-content"><strong>${esc(mayor.full_name)}</strong> is Maire de Scranton today.</p>`
    : "";
  const reminders = upcoming
    .map((item) => {
      const inspiration = item.member.personal_profile
        ? ` They love: ${esc(item.member.personal_profile)}`
        : "";
      return `<p class="signal-detail"><strong>${esc(item.member.full_name)}</strong>'s birthday is in ${item.in_days} day${item.in_days > 1 ? "s" : ""}. Want to prepare something with the team?${inspiration}</p>`;
    })
    .join("");
  return `
    <div class="card ritual">
      <div class="card-meta"><span class="chip mayor">maire de scranton</span></div>
      ${mayorLine}
      ${reminders}
    </div>`;
}

/* --- That's What She Said (completion reward) --- */

/* Original Michael-Scott-flavoured lines, written for this demo - not
 * verbatim show quotes (IP caution, see PRODUCT_ROADMAP section 8). */
const TWSS_QUOTES = [
  "You miss 100% of the notes you don't take. Wayne Gretzky never said that.",
  "That was so efficient it should be illegal in at least four states.",
  "Somewhere, a spreadsheet just shed a single tear of joy.",
  "You are the Springsteen of paperwork. The Boss.",
  "I would promote you right now, if promotions were mine to give. They are not.",
  "This is what peak management looks like. Take a mental picture.",
  "Great managers are made of moments like this. And free pretzels.",
  "If caring about your team were a crime, you would be in so much trouble.",
  "The team's memory just got one segment stronger. Beautiful.",
  "Declared: today is now officially a good day. No takebacks.",
  "You did not drop the ball. You dunked it.",
  "World's best boss behaviour detected.",
  "That note will outlive us all. Legacy: secured.",
  "Somewhere in Scranton, a bell just rang for you.",
  "One small click for you, one giant leap for team morale.",
  "Filed, remembered, never lost. That is the dream.",
  "You just out-managed 94% of managers. Statistic invented, feeling real.",
  "Pretzel Day energy. Keep it going.",
];

let twssTimer = null;

function twss(options = {}) {
  if (!CELEBRATIONS) return;
  const overlay = document.getElementById("twss");
  const title = options.title || "THAT'S WHAT SHE SAID";
  const quote =
    options.quote || TWSS_QUOTES[Math.floor(Math.random() * TWSS_QUOTES.length)];
  document.getElementById("twss-title").textContent = title;
  document.getElementById("twss-quote").textContent = quote;
  document.getElementById("twss-sig").textContent =
    options.signature || "- Michael Scott, probably";
  document.getElementById("twss-card").classList.toggle("mayor", Boolean(options.mayor));
  overlay.hidden = false;
  clearTimeout(twssTimer);
  // Reading time, not a fixed beat (tuning pass): a comfortable pace
  // over the whole card, floored at 4s. A click still closes it early.
  const words = `${title} ${quote}`.trim().split(/\s+/).length;
  const duration = options.duration || Math.max(4000, 1800 + words * 330);
  twssTimer = setTimeout(() => { overlay.hidden = true; }, duration);
}

/* --- boot --- */

async function init() {
  const [config, members, catalog] = await Promise.all([
    api("/config/ui"),
    api("/team/members"),
    api("/summaries"),
  ]);
  state.characters = config.characters;
  state.members = members.filter((m) => m.is_active);
  // Human labels for tags: names resolved once, from the seams.
  state.labels.team_member = Object.fromEntries(state.members.map((m) => [m.id, m.full_name]));
  for (const kind of ["project", "client"]) {
    state.labels[kind] = Object.fromEntries(
      (catalog.targets[kind] || []).map((t) => [t.id, t.name]));
  }

  renderChrome();
  bindOverlays();
  bindDwightOverlay();
  bindPamArchive();
  document.getElementById("pam-form").addEventListener("submit", submitPam);
  document.getElementById("pam-thread").addEventListener("click", async (event) => {
    if (event.target.matches("[data-open-dwight]")) {
      // One sheet at a time: Dwight was opening BEHIND Pam (QA 2026-07-14).
      document.getElementById("pam-overlay").hidden = true;
      openOverlay("dwight-overlay");
    }
    if (event.target.matches("[data-save-pam]")) {
      const summary = state.pamSummaries[Number(event.target.dataset.savePam)];
      if (!summary) return;
      event.target.disabled = true;
      try {
        const doc = await saveSummaryAsDocument(summary);
        // Land on the Desk, editor open: one sheet at a time here too.
        document.getElementById("pam-overlay").hidden = true;
        state.editorOpenId = doc.id;
        switchView("desk");
      } catch (error) {
        event.target.disabled = false;
        alert(error.message);
      }
    }
  });
  // One listener for every preview trigger: the strip, the bin, Pam's
  // sources and the Desk summaries all render [data-doc-preview].
  // Document-level and bound once, so dynamic content never rebinds.
  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-doc-preview]");
    if (trigger) openDocPreview(trigger.dataset.docPreview);
  });
  document.getElementById("twss").addEventListener("click", (event) => {
    event.currentTarget.hidden = true;
  });
  // Mayor data first, so the dashboard's ritual card renders on the
  // very first paint (the banner duplicate is gone).
  await loadMayor();
  switchRole("manager");
}

init();
