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

const state = {
  characters: {},
  role: "manager",
  selfId: null, // who I am, in the team-member role (identity, not proxy)
  members: [],
  labels: { team_member: {}, project: {}, client: {} },
  entryId: null, // the entry currently discussed in the Dwight overlay
  suggestions: [],
  mayorOverview: null,
  celebrated: false, // Maire celebration: once per page load
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
  overlay.querySelector("textarea, input")?.focus();
}

function bindOverlays() {
  document.querySelectorAll(".overlay").forEach((overlay) => {
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay || event.target.matches("[data-close]")) {
        overlay.hidden = true;
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

/* --- profile suggestions (member-owned data, manager only relays) --- */

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

function suggestionCard(suggestion, index) {
  const birthday = suggestion.birthday
    ? `<span class="chip profile">birthday: ${esc(formatBirthday(suggestion.birthday))}</span>`
    : "";
  return `
    <article class="card profile-suggestion" id="suggestion-${index}">
      <p class="card-content">For <strong>${esc(suggestion.member_name)}</strong>: ${esc(suggestion.text)}</p>
      <div class="card-meta">
        <span class="chip profile">personal - member-owned</span>
        ${birthday}
      </div>
      <div class="card-actions">
        <button class="btn btn-validate" data-profile-add="${index}">Add to profile</button>
        <button class="btn btn-ghost" data-profile-dismiss="${index}">Dismiss</button>
      </div>
    </article>`;
}

function renderSuggestions(suggestions) {
  state.suggestions = suggestions || [];
  if (!state.suggestions.length) return "";
  return (
    `<p class="sources-title">Profile suggestions - their data, your call</p>` +
    state.suggestions.map(suggestionCard).join("")
  );
}

async function addSuggestionToProfile(index) {
  const suggestion = state.suggestions[index];
  const members = await api("/team/members");
  const member = members.find((m) => m.id === suggestion.team_member_id);
  if (!member) throw new Error("Member not found.");
  // Append, never overwrite: the profile grows one observed fact at a time.
  const merged = member.personal_profile
    ? `${member.personal_profile}\n${suggestion.text}`
    : suggestion.text;
  await api(`/team/members/${member.id}/profile`, {
    method: "PUT",
    body: JSON.stringify({
      personal_profile: merged,
      birthday: suggestion.birthday || member.birthday,
    }),
  });
  const card = document.getElementById(`suggestion-${index}`);
  card.classList.add("decided");
  card.querySelector(".card-actions").outerHTML =
    `<p class="thinking-none">Added to ${esc(suggestion.member_name)}'s profile.</p>`;
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
    const answer = await api("/dwight/entries", {
      method: "POST",
      body: JSON.stringify({
        raw_content: input.value,
        source_type: document.getElementById("dwight-source").value,
      }),
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
      block.innerHTML =
        renderSegments(answer.segments) + renderSuggestions(answer.profile_suggestions);
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
      thread.insertAdjacentHTML(
        "afterend",
        renderSegments(result.segments) + renderSuggestions(result.profile_suggestions)
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
    if (target.matches("[data-profile-add]")) {
      target.disabled = true;
      try {
        await addSuggestionToProfile(Number(target.dataset.profileAdd));
      } catch (error) {
        target.disabled = false;
        alert(error.message);
      }
      return;
    }
    if (target.matches("[data-profile-dismiss]")) {
      document.getElementById(`suggestion-${target.dataset.profileDismiss}`).remove();
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
  return `
    <div class="source-row">
      <span class="source-num">[${index + 1}]</span>
      <span class="source-text">${esc(source.content)}</span>
      <span class="chip ${source.data_type}">${source.data_type}</span>
      <span class="source-date">${date}</span>
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
    const sources = result.sources.length
      ? `<p class="sources-title">Sources</p>` + result.sources.map(sourceRow).join("")
      : "";
    document.getElementById("pam-wait").outerHTML =
      `<div class="answer-card">${esc(result.answer)}</div>${sources}`;
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
         <div class="mcard ${signals ? "alert" : ""}"><div class="ml">Weak signals</div><div class="mv">${signals}</div>
           <div class="ms">${signals ? `see ${esc(character("toby").display_name)}` : "all quiet"}</div></div>
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
       <button class="btn btn-ghost" data-desk="annual_review" data-out="one-on-one" data-target="desk-member">Annual review material</button>`)
  );
  document.getElementById("desk-body").onclick = async (event) => {
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
    show(
      containerId,
      `<div class="answer-card summary-card">
         <p class="summary-subtitle">${esc(subtitle)}</p>
         ${sections}
       </div>
       <div class="export-row">
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
  return `
    <div class="trend">
      ${points
        .map((point) => {
          const height = Math.max(8, (point.average_mood_index / 5) * 100);
          return `<div class="trend-col" title="${point.day}: ${point.average_mood_index} (${point.checkins} check-ins)">
                    <div class="trend-bar" style="height:${height}%"></div>
                  </div>`;
        })
        .join("")}
    </div>`;
}

function memberRow(member) {
  return `
    <div class="member-row">
      <div class="member-id">
        <strong>${esc(member.full_name)}</strong>
        <span class="member-role">${esc(member.role || "")}</span>
      </div>
      <div class="dots">${moodDots(member.checkins)}</div>
      ${moodChip(member.latest_mood)}
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
     <p class="sources-title">Members</p>
     ${overview.members.map(memberRow).join("")}`
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
       </div>
       <div class="share-box">
         <h2>About me - shared on purpose</h2>
         <p class="who">Visible by your manager, and only them - so they can help
           the team feel good. Everything here is optional and stays yours.</p>
         <label class="field-label">Birthday - day and month only, never the year</label>
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

async function loadMayor() {
  try {
    state.mayorOverview = await api("/team/mayor");
  } catch {
    state.mayorOverview = { mayor: null, upcoming: [] };
  }
  const banner = document.getElementById("mayor-banner");
  const { mayor, upcoming } = state.mayorOverview;
  if (mayor) {
    banner.innerHTML =
      `<span class="mayor-title">MAIRE DE SCRANTON</span>${esc(mayor.full_name)}, today`;
    banner.hidden = false;
    if (!state.celebrated) {
      state.celebrated = true;
      // The ritual fires on its own on the day: once per page load.
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
  } else if (upcoming.length) {
    const next = upcoming[0];
    banner.innerHTML =
      `<span class="mayor-title">UPCOMING</span>${esc(next.member.full_name)}'s birthday in ${next.in_days} day${next.in_days > 1 ? "s" : ""}`;
    banner.hidden = false;
  } else {
    banner.hidden = true;
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
  document.getElementById("pam-form").addEventListener("submit", submitPam);
  document.getElementById("twss").addEventListener("click", (event) => {
    event.currentTarget.hidden = true;
  });
  switchRole("manager");
  loadMayor();
}

init();
