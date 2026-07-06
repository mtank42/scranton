/* Scranton UI - vanilla JS, no framework (stack decision, SCRANTON_CONTEXT §4).
 *
 * Character names and avatars are FETCHED from /api/v1/config/ui, never
 * hardcoded: the character map stays the single rebrand seam. The only
 * literal feature name below is "Pretzel Day", which has no character.
 */

const API = "/api/v1";

const state = {
  characters: {},
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
  document.getElementById(container).innerHTML = html;
}

/* --- navigation --- */

const NAV = [
  { view: "dwight", character: "dwight" },
  { view: "pam", character: "pam" },
  { view: "mood", character: null, label: "Pretzel Day" },
  { view: "toby", character: "toby" },
];

function renderNav() {
  const nav = document.getElementById("nav");
  nav.innerHTML = NAV.map((item) => {
    const character = item.character ? state.characters[item.character] : null;
    const label = character ? character.display_name : item.label;
    const icon = character
      ? `<img src="assets/${esc(character.avatar_asset)}" alt="" />`
      : `<span class="nav-dot"></span>`;
    return `<button class="nav-item" data-view="${item.view}">${icon}${esc(label)}</button>`;
  }).join("");
  nav.addEventListener("click", (event) => {
    const button = event.target.closest(".nav-item");
    if (button) switchView(button.dataset.view);
  });
}

function switchView(view) {
  document.querySelectorAll(".view").forEach((section) => {
    section.hidden = section.id !== `view-${view}`;
  });
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  // Data views refresh on entry so the picture is never stale.
  if (view === "mood") loadMood();
  if (view === "toby") loadToby();
}

function applyCharacterHeaders() {
  for (const key of ["dwight", "pam", "toby"]) {
    const character = state.characters[key];
    if (!character) continue;
    const title = document.getElementById(`${key}-title`);
    const avatar = document.getElementById(`${key}-avatar`);
    if (title) title.textContent = character.display_name;
    if (avatar) avatar.src = `assets/${character.avatar_asset}`;
  }
}

/* --- Tell Dwight --- */

function sensitivityDots(level) {
  const dots = [1, 2, 3, 4, 5]
    .map((step) => `<span class="${step <= level ? "on" : ""}">&#9679;</span>`)
    .join("");
  return `<span class="sensitivity" title="sensitivity ${level}/5">${dots}</span>`;
}

function tagChip(tag) {
  const target = tag.view_type
    ? `view:${tag.view_type}`
    : `${tag.entity_type}#${tag.entity_id}`;
  return `<span class="chip tag">${esc(target)}</span>`;
}

function segmentCard(segment) {
  const decided = segment.validation_status !== "proposed";
  const statusChip = decided
    ? `<span class="chip status-${segment.validation_status}">${segment.validation_status}</span>`
    : "";
  const actions = decided
    ? ""
    : `<div class="card-actions">
         <button class="btn btn-validate" data-segment="${segment.id}" data-decision="validated">Validate</button>
         <button class="btn btn-reject" data-segment="${segment.id}" data-decision="rejected">Reject</button>
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

async function submitDwight(event) {
  event.preventDefault();
  const input = document.getElementById("dwight-input");
  const button = document.getElementById("dwight-submit");
  button.disabled = true;
  show("dwight-result", `<p class="thinking">Dwight is structuring</p>`);
  try {
    const result = await api("/dwight/entries", {
      method: "POST",
      body: JSON.stringify({
        raw_content: input.value,
        source_type: document.getElementById("dwight-source").value,
      }),
    });
    if (result.clarification) {
      show(
        "dwight-result",
        `<div class="callout"><span class="chip">clarification</span>
           <p>${esc(result.clarification)}</p></div>`
      );
    } else {
      show(
        "dwight-result",
        `<p class="sources-title">Proposed segments - you decide</p>` +
          result.segments.map(segmentCard).join("")
      );
      input.value = "";
    }
  } catch (error) {
    show("dwight-result", `<div class="error-banner">${esc(error.message)}</div>`);
  } finally {
    button.disabled = false;
  }
}

async function decideSegment(segmentId, decision) {
  const segment = await api(`/dwight/segments/${segmentId}/validate`, {
    method: "POST",
    body: JSON.stringify({ status: decision }),
  });
  document.getElementById(`segment-${segmentId}`).outerHTML = segmentCard(segment);
  // Completion moment: a validated segment just entered the memory.
  if (decision === "validated") twss();
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

function twss() {
  const overlay = document.getElementById("twss");
  document.getElementById("twss-quote").textContent =
    TWSS_QUOTES[Math.floor(Math.random() * TWSS_QUOTES.length)];
  overlay.hidden = false;
  clearTimeout(twssTimer);
  twssTimer = setTimeout(() => { overlay.hidden = true; }, 3200);
}

/* --- Pretzel Day (mood check-in) --- */

const MOODS = [
  { level: "flow", label: "Flow" },
  { level: "ctrl", label: "Ctrl" },
  { level: "pretzel_day", label: "Pretzel Day" },
  { level: "press", label: "Press" },
  { level: "stuck", label: "Stuck" },
  { level: "danger", label: "Danger" },
];

const moodState = { memberId: null, level: null };

async function loadMood() {
  const overview = await api("/toby/overview?days=1");
  const members = overview.members;
  moodState.memberId = members.length ? members[0].team_member_id : null;
  moodState.level = null;
  show(
    "mood-body",
    `<div class="checkin">
       <select id="mood-member">
         ${members
           .map(
             (member) =>
               `<option value="${member.team_member_id}">${esc(member.full_name)}</option>`
           )
           .join("")}
       </select>
       <div class="palette" id="mood-palette">
         ${MOODS.map(
           (mood) =>
             `<button type="button" class="mood-btn mood-${mood.level}" data-level="${mood.level}">
                <span class="mood-swatch"></span>${mood.label}
              </button>`
         ).join("")}
       </div>
       <input id="mood-note" type="text" placeholder="Optional note - one line is plenty" />
       <div class="form-row">
         <button class="btn btn-primary" id="mood-submit" disabled>Check in</button>
         <span id="mood-feedback" class="thinking-none"></span>
       </div>
     </div>`
  );
  document.getElementById("mood-member").addEventListener("change", (event) => {
    moodState.memberId = Number(event.target.value);
  });
  document.getElementById("mood-palette").addEventListener("click", (event) => {
    const button = event.target.closest(".mood-btn");
    if (!button) return;
    moodState.level = button.dataset.level;
    document
      .querySelectorAll(".mood-btn")
      .forEach((b) => b.classList.toggle("selected", b === button));
    document.getElementById("mood-submit").disabled = false;
  });
  document.getElementById("mood-submit").addEventListener("click", submitMood);
}

async function submitMood() {
  const button = document.getElementById("mood-submit");
  button.disabled = true;
  try {
    const note = document.getElementById("mood-note").value.trim();
    await api("/mood/checkins", {
      method: "POST",
      body: JSON.stringify({
        team_member_id: moodState.memberId,
        mood_level: moodState.level,
        note: note || null,
      }),
    });
    document.getElementById("mood-feedback").textContent = "Recorded.";
    document.getElementById("mood-note").value = "";
    twss();
  } catch (error) {
    document.getElementById("mood-feedback").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

/* --- Meet Toby (team health) --- */

function moodChip(level) {
  return level
    ? `<span class="chip mood-${level}">${level}</span>`
    : `<span class="chip">no check-in</span>`;
}

function signalCard(signal) {
  return `
    <div class="card signal">
      <div class="card-meta">
        <span class="chip signal-${signal.type}">${signal.type}</span>
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
  const dots = member.checkins
    .map(
      (point) =>
        `<span class="dot mood-${point.mood_level}" title="${point.at.slice(0, 10)}: ${point.mood_level}"></span>`
    )
    .join("");
  return `
    <div class="member-row">
      <div class="member-id">
        <strong>${esc(member.full_name)}</strong>
        <span class="member-role">${esc(member.role || "")}</span>
      </div>
      <div class="dots">${dots}</div>
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

/* --- Ask Pam --- */

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
  button.disabled = true;
  show("pam-result", `<p class="thinking">Pam is remembering</p>`);
  try {
    const result = await api("/pam/query", {
      method: "POST",
      body: JSON.stringify({ question: input.value }),
    });
    const sources = result.sources.length
      ? `<p class="sources-title">Sources</p>` + result.sources.map(sourceRow).join("")
      : "";
    show("pam-result", `<div class="answer-card">${esc(result.answer)}</div>${sources}`);
  } catch (error) {
    show("pam-result", `<div class="error-banner">${esc(error.message)}</div>`);
  } finally {
    button.disabled = false;
  }
}

/* --- boot --- */

async function init() {
  const config = await api("/config/ui");
  state.characters = config.characters;
  renderNav();
  applyCharacterHeaders();
  switchView("dwight");

  document.getElementById("dwight-form").addEventListener("submit", submitDwight);
  document.getElementById("pam-form").addEventListener("submit", submitPam);
  document.getElementById("twss").addEventListener("click", (event) => {
    event.currentTarget.hidden = true;
  });
  document.getElementById("dwight-result").addEventListener("click", async (event) => {
    const button = event.target.closest("[data-segment]");
    if (!button) return;
    button.disabled = true;
    try {
      await decideSegment(button.dataset.segment, button.dataset.decision);
    } catch (error) {
      button.disabled = false;
      alert(error.message);
    }
  });
}

init();
