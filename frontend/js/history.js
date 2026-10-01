// History page: everything cooked, newest first, with ratings and notes you can change.

const listEl = document.getElementById("history-list");
const summaryEl = document.getElementById("summary");

const RATING_OPTIONS = [
  ["", "Not rated"],
  ["5", "5, loved it"],
  ["4", "4, really good"],
  ["3", "3, fine"],
  ["2", "2, not great"],
  ["1", "1, wouldn't make again"],
];

async function loadHistory() {
  try {
    const logs = await apiGet("/history");
    summaryEl.className = "result-count";
    summaryEl.textContent = logs.length === 0
      ? 'Nothing logged yet. Open a recipe and use "I cooked this" after you make it.'
      : `${logs.length} ${logs.length === 1 ? "meal" : "meals"} cooked`;
    listEl.replaceChildren(...logs.map(renderLog));
  } catch (error) {
    summaryEl.textContent = `Couldn't load your history. ${error.message}`;
    summaryEl.className = "alert alert-error";
  }
}

function renderLog(log) {
  const li = document.createElement("li");
  li.className = "history-entry";

  // The recipe may have been deleted since; then the title is plain text.
  const title = document.createElement(log.recipe_id ? "a" : "span");
  title.className = "history-title";
  title.textContent = log.recipe_title;
  if (log.recipe_id) title.href = `/recipe.html?id=${log.recipe_id}`;

  const meta = document.createElement("p");
  meta.className = "meta";
  meta.textContent = [
    formatDate(log.cooked_on),
    `${log.servings} ${log.servings === 1 ? "serving" : "servings"}`,
    log.recipe_id ? null : "recipe deleted",
  ].filter(Boolean).join(" · ");

  // Rating: changes save as soon as you pick one.
  const ratingField = document.createElement("div");
  ratingField.className = "field history-rating";
  const ratingId = `rating-${log.id}`;
  const ratingLabel = document.createElement("label");
  ratingLabel.htmlFor = ratingId;
  ratingLabel.textContent = "Rating";
  const rating = document.createElement("select");
  rating.id = ratingId;
  for (const [value, text] of RATING_OPTIONS) rating.add(new Option(text, value));
  rating.value = log.rating ? String(log.rating) : "";
  rating.addEventListener("change", () => saveChange(log, { rating: rating.value ? Number(rating.value) : null }, rating));
  ratingField.append(ratingLabel, rating);

  const notes = renderNotes(log);

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "link-button";
  remove.textContent = "Delete entry";
  remove.setAttribute("aria-label", `Delete the ${formatDate(log.cooked_on)} entry for ${log.recipe_title}`);
  remove.addEventListener("click", () => deleteLog(log, remove));

  notes.querySelector(".history-links").append(remove);
  const heading = document.createElement("div");
  heading.className = "history-heading-block";
  heading.append(title, meta);
  li.append(heading, ratingField, notes);
  return li;
}

// Notes show as text with an "Edit note" button that swaps in a small form.
function renderNotes(log) {
  const wrapper = document.createElement("div");
  wrapper.className = "history-notes";

  const text = document.createElement("p");
  text.textContent = log.notes || "No notes.";
  if (!log.notes) text.className = "hint";

  const edit = document.createElement("button");
  edit.type = "button";
  edit.className = "link-button";
  edit.textContent = log.notes ? "Edit note" : "Add a note";

  const form = document.createElement("form");
  form.className = "form-stack";
  form.hidden = true;
  const label = document.createElement("label");
  label.className = "visually-hidden";
  label.htmlFor = `notes-${log.id}`;
  label.textContent = `Notes for ${log.recipe_title}`;
  const area = document.createElement("textarea");
  area.id = `notes-${log.id}`;
  area.maxLength = 2000;
  area.value = log.notes || "";
  const actions = document.createElement("div");
  actions.className = "actions";
  const save = document.createElement("button");
  save.type = "submit";
  save.className = "button button-primary";
  save.textContent = "Save note";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "button button-secondary";
  cancel.textContent = "Cancel";
  actions.append(save, cancel);
  form.append(label, area, actions);

  edit.addEventListener("click", () => {
    form.hidden = false;
    text.hidden = links.hidden = true;
    area.focus();
  });
  cancel.addEventListener("click", () => {
    form.hidden = true;
    text.hidden = links.hidden = false;
    area.value = log.notes || "";
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    saveChange(log, { notes: area.value.trim() || null }, save);
  });

  const links = document.createElement("div");
  links.className = "history-links";
  links.append(edit);
  wrapper.append(text, links, form);
  return wrapper;
}

async function saveChange(log, changes, control) {
  control.disabled = true;
  try {
    await apiPatch(`/history/${log.id}`, changes);
    await loadHistory();
  } catch (error) {
    window.alert(`Couldn't save. ${error.message}`);
    control.disabled = false;
  }
}

async function deleteLog(log, button) {
  if (!window.confirm(`Delete the ${formatDate(log.cooked_on)} entry for ${log.recipe_title}? This doesn't put anything back in your inventory.`)) return;
  button.disabled = true;
  try {
    await apiDelete(`/history/${log.id}`);
    await loadHistory();
  } catch (error) {
    window.alert(`Couldn't delete the entry. ${error.message}`);
    button.disabled = false;
  }
}

loadHistory();
