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
