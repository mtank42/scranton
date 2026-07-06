/* Scranton UI - vanilla JS, no framework (stack decision, SCRANTON_CONTEXT §4).
 *
 * Character names and avatars are FETCHED from /api/v1/config/ui, never
 * hardcoded: the character map stays the single rebrand seam. The only
 * literal feature name below is "Pretzel Day", which has no character.
 */

const API = "/api/v1";

const state = {
  characters: {},
  entryId: null, // the entry currently discussed in the Dwight view
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
  // Data containers start life with the centered 'placeholder' style;
  // real content must not inherit it.
  element.classList.remove("placeholder");
  element.innerHTML = html;
}

/* --- navigation --- */

const NAV = [
  { view: "dwight", character: "dwight" },
  { view: "pam", character: "pam" },
  { view: "mood", character: null, label: "Pretzel Day", dot: "" },
  { view: "toby", character: "toby" },
  { view: "team", character: null, label: "Team", dot: "team" },
];

function renderNav() {
  const nav = document.getElementById("nav");
  nav.innerHTML = NAV.map((item) => {
    const character = item.character ? state.characters[item.character] : null;
    const label = character ? character.display_name : item.label;
    const icon = character
      ? `<img src="assets/${esc(character.avatar_asset)}" alt="" />`
      : `<span class="nav-dot ${item.dot || ""}"></span>`;
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
  if (view === "team") loadTeam();
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

/* --- Tell Dwight: capture, clarification thread, rework loop --- */

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
  const character = state.characters.dwight || {};
  return `
    <div class="bubble-row">
      <img class="bubble-avatar" src="assets/${esc(character.avatar_asset || "")}" alt="" />
      <div class="bubble dwight">${esc(text)}</div>
    </div>`;
}

function managerBubble(text) {
  return `<div class="bubble-row manager"><div class="bubble manager">${esc(text)}</div></div>`;
}

function replyForm() {
  return `
    <form id="reply-form" class="reply-form">
      <input id="reply-input" type="text" placeholder="Your answer to Dwight..." required />
      <button type="submit" class="btn btn-primary">Answer</button>
    </form>`;
}

function renderSegments(segments) {
  return (
    `<p class="sources-title">Proposed segments - you decide</p>` +
    segments.map(segmentCard).join("")
  );
}

/* --- profile suggestions (V1 human profile) --- */

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
    state.entryId = result.entry_id;
    if (result.clarification) {
      // The dialogue starts: the note and the question become a thread.
      show(
        "dwight-result",
        `<div class="thread" id="dwight-thread">
           ${managerBubble(input.value)}
           ${dwightBubble(result.clarification)}
         </div>
         ${replyForm()}`
      );
      bindReplyForm();
    } else {
      show(
        "dwight-result",
        renderSegments(result.segments) + renderSuggestions(result.profile_suggestions)
      );
      input.value = "";
    }
  } catch (error) {
    show("dwight-result", `<div class="error-banner">${esc(error.message)}</div>`);
  } finally {
    button.disabled = false;
  }
}

function bindReplyForm() {
  document.getElementById("reply-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.getElementById("reply-input");
    const answer = input.value;
    const thread = document.getElementById("dwight-thread");
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
        document.getElementById("reply-form").remove();
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
  });
}

async function decideSegment(segmentId, decision) {
  const segment = await api(`/dwight/segments/${segmentId}/validate`, {
    method: "POST",
    body: JSON.stringify({ status: decision }),
  });
  document.getElementById(`segment-${segmentId}`).outerHTML = segmentCard(segment);
  checkReportComplete();
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

/* End of a report: the reward rules (owner decisions, 2026-07-06).
 * - Every segment decided = the report is filed, whatever the mix of
 *   validates and rejects.
 * - First report of the day: Pretzel Day appears inline; the reward
 *   comes only if a mood is actually given ('Rather not say' = none).
 * - Later reports: the reward fires directly. */
function checkReportComplete() {
  // Profile suggestions are optional extras: they never hold the report open.
  const undecided = document.querySelectorAll(
    "#dwight-result .card:not(.decided):not(.pretzel-inline):not(.profile-suggestion)"
  ).length;
  if (undecided > 0) return;
  maybePretzelThenReward();
}

async function maybePretzelThenReward() {
  try {
    const today = new Date().toISOString().slice(0, 10);
    const recent = await api("/mood/checkins?days=1");
    const doneToday = recent.some((checkin) => checkin.created_at.slice(0, 10) === today);
    if (doneToday) {
      twss();
      return;
    }
    renderInlinePretzel();
  } catch {
    // The mood layer must never block the capture flow.
    twss();
  }
}

async function renderInlinePretzel() {
  if (document.getElementById("pd-inline")) return;
  const overview = await api("/toby/overview?days=1");
  const options = overview.members
    .map((member) => `<option value="${member.team_member_id}">${esc(member.full_name)}</option>`)
    .join("");
  document.getElementById("dwight-result").insertAdjacentHTML(
    "beforeend",
    `<div class="card pretzel-inline" id="pd-inline">
       <p class="card-content">Report filed. One last thing - how is the day going?</p>
       <div class="checkin-inline">
         <select data-pd-member>${options}</select>
         <div class="palette compact">
           ${MOODS.map(
             (mood) =>
               `<button type="button" class="mood-btn mood-${mood.level}" data-pd-level="${mood.level}" title="${mood.label}">
                  <span class="mood-emoji">${mood.emoji}</span>${mood.label}
                </button>`
           ).join("")}
         </div>
         <button class="btn btn-ghost" data-pd-skip>Rather not say</button>
       </div>
     </div>`
  );
}

async function inlineCheckin(level) {
  const panel = document.getElementById("pd-inline");
  const memberId = Number(panel.querySelector("[data-pd-member]").value);
  await api("/mood/checkins", {
    method: "POST",
    body: JSON.stringify({ team_member_id: memberId, mood_level: level, note: null }),
  });
  panel.querySelector(".checkin-inline").outerHTML =
    `<p class="thinking-none">Recorded. Thanks for saying it.</p>`;
  panel.classList.add("decided");
  twss();
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
  document.getElementById("twss-title").textContent =
    options.title || "THAT'S WHAT SHE SAID";
  document.getElementById("twss-quote").textContent =
    options.quote || TWSS_QUOTES[Math.floor(Math.random() * TWSS_QUOTES.length)];
  document.getElementById("twss-sig").textContent =
    options.signature || "- Michael Scott, probably";
  document.getElementById("twss-card").classList.toggle("mayor", Boolean(options.mayor));
  overlay.hidden = false;
  clearTimeout(twssTimer);
  twssTimer = setTimeout(() => { overlay.hidden = true; }, options.duration || 3200);
}

/* --- Maire de Scranton (birthday ritual) --- */

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
    // The ritual fires on its own on the day (BACKLOG spec): one
    // celebration per page load, a beat after the app settles.
    setTimeout(
      () =>
        twss({
          mayor: true,
          title: "MAIRE DE SCRANTON",
          quote: `${mayor.full_name} runs this town today. Their day, their rules.`,
          signature: "- By order of the Office of the Mayor",
          duration: 5200,
        }),
      900
    );
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

/* --- Pretzel Day (standalone mood view) --- */

/* First-degree labels + emoji (owner feedback, 2026-07-06): the palette
 * values stay the data model vocabulary; only the display changes.
 * Emoji here is the explicit exception granted for the mood palette. */
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
      .querySelectorAll("#mood-palette .mood-btn")
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
    ? `<span class="chip mood-${level}">${moodDisplay(level)}</span>`
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
        `<span class="dot mood-${point.mood_level}" title="${point.at.slice(0, 10)}: ${MOOD_META[point.mood_level]?.label || point.mood_level}"></span>`
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

/* --- Team (roster + human profile) --- */

function memberProfileCard(member) {
  const [, month, day] = (member.birthday || "--").split("-");
  const dayOptions = ['<option value="">-</option>']
    .concat(Array.from({ length: 31 }, (_, i) =>
      `<option value="${i + 1}" ${Number(day) === i + 1 ? "selected" : ""}>${i + 1}</option>`))
    .join("");
  const monthOptions = ['<option value="">-</option>']
    .concat(MONTHS.map((name, i) =>
      `<option value="${i + 1}" ${Number(month) === i + 1 ? "selected" : ""}>${name}</option>`))
    .join("");
  const isMayor = state.mayorOverview?.mayor?.id === member.id;
  return `
    <div class="card member-profile" data-member="${member.id}">
      <div class="member-head">
        <strong>${esc(member.full_name)}</strong>
        <span class="member-role">${esc(member.role || "")}</span>
        ${isMayor ? '<span class="chip mayor">maire today</span>' : ""}
      </div>
      <label class="field-label">Birthday - day and month only, never the year</label>
      <div class="birthday-row">
        <select data-bd-day>${dayOptions}</select>
        <select data-bd-month>${monthOptions}</select>
      </div>
      <label class="field-label">What they love</label>
      <textarea rows="3" data-profile
        placeholder="Interests, passions, favorites - what you would know after three months of truly listening."
      >${esc(member.personal_profile || "")}</textarea>
      <div class="card-actions">
        <button class="btn btn-primary" data-profile-save="${member.id}">Save</button>
        <span class="thinking-none" data-feedback></span>
      </div>
    </div>`;
}

async function loadTeam() {
  show("team-body", `<p class="thinking">Loading the roster</p>`);
  const members = await api("/team/members");
  show("team-body", ritualCard() + members.map(memberProfileCard).join(""));
  // onclick (not addEventListener): the container survives view switches,
  // so a cumulative listener would fire once per past visit.
  document.getElementById("team-body").onclick = async (event) => {
    const button = event.target.closest("[data-profile-save]");
    if (!button) return;
    const card = button.closest(".member-profile");
    button.disabled = true;
    try {
      const day = card.querySelector("[data-bd-day]").value;
      const month = card.querySelector("[data-bd-month]").value;
      // The year is a placeholder (2000), erased server-side anyway.
      const birthday =
        day && month
          ? `2000-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`
          : null;
      await api(`/team/members/${button.dataset.profileSave}/profile`, {
        method: "PUT",
        body: JSON.stringify({
          personal_profile: card.querySelector("[data-profile]").value.trim() || null,
          birthday,
        }),
      });
      card.querySelector("[data-feedback]").textContent = "Saved.";
    } catch (error) {
      card.querySelector("[data-feedback]").textContent = error.message;
    } finally {
      button.disabled = false;
    }
  };
}

/* --- boot --- */

async function init() {
  const config = await api("/config/ui");
  state.characters = config.characters;
  renderNav();
  applyCharacterHeaders();
  switchView("dwight");
  loadMayor();

  document.getElementById("dwight-form").addEventListener("submit", submitDwight);
  document.getElementById("pam-form").addEventListener("submit", submitPam);
  document.getElementById("twss").addEventListener("click", (event) => {
    event.currentTarget.hidden = true;
  });

  // One delegated handler for everything inside the Dwight result area:
  // segment decisions, the rework loop, and the inline Pretzel panel.
  document.getElementById("dwight-result").addEventListener("click", async (event) => {
    const target = event.target;

    if (target.matches("[data-reject-open]")) {
      // Rejecting opens the dialogue, it does not decide anything yet.
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
    if (target.matches("[data-pd-level]")) {
      try {
        await inlineCheckin(target.dataset.pdLevel);
      } catch (error) {
        alert(error.message);
      }
      return;
    }
    if (target.matches("[data-pd-skip]")) {
      // Rather not say: nothing stored, no reward - and that is fine.
      document.getElementById("pd-inline").remove();
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
      // Dismissed: the suggestion evaporates - it was never stored.
      document.getElementById(`suggestion-${target.dataset.profileDismiss}`).remove();
    }
  });
}

init();
