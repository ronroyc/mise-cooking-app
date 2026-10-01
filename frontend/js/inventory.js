// Inventory page: add, edit, and remove what's in the kitchen.
// The same form adds new items (POST) and edits existing ones (PATCH).
// When you type an ingredient Slice'd doesn't know yet, the AI suggests what it is.

const form = document.getElementById("item-form");
const formHeading = document.getElementById("item-form-heading");
const errorsEl = document.getElementById("form-errors");
const noticeEl = document.getElementById("form-notice");
const aiPanel = document.getElementById("ai-panel");
const saveButton = document.getElementById("save-button");
const cancelButton = document.getElementById("cancel-edit");
const filtersForm = document.getElementById("filters");
const listEl = document.getElementById("item-list");
const summaryEl = document.getElementById("summary");

const LOCATION_LABELS = { pantry: "Pantry", fridge: "Fridge", freezer: "Freezer" };

let items = [];          // the list currently shown
let editingId = null;    // null = adding a new item
let latestRequest = 0;   // ignore slow responses to old searches (same idea as recipes.js)
let knownIngredients = new Map(); // name -> category, from /api/ingredients
let suggestion = null;   // the AI's answer for the name currently in the form
let latestLookup = 0;    // same trick as latestRequest, for AI lookups

// ---------- Loading + rendering ----------

async function loadItems() {
  const params = new URLSearchParams();
  const search = filtersForm.elements.search.value.trim();
  const location = filtersForm.elements.location.value;
  if (search) params.set("search", search);
  if (location) params.set("location", location);

  const requestNumber = ++latestRequest;
  try {
    const result = await apiGet(`/inventory?${params}`);
    if (requestNumber !== latestRequest) return;
    items = result;
    renderItems();
  } catch (error) {
    if (requestNumber !== latestRequest) return;
    listEl.replaceChildren();
    summaryEl.textContent = `Couldn't load your inventory. ${error.message}`;
    summaryEl.className = "alert alert-error";
  }
}

function renderSummary() {
  summaryEl.className = "result-count";
  const filtered = filtersForm.elements.search.value.trim() || filtersForm.elements.location.value;
  if (items.length === 0) {
    summaryEl.textContent = filtered ? "No items match those filters." : "Your inventory is empty. Add the first item above.";
    return;
  }
  const expired = items.filter((i) => i.expiration_status === "expired").length;
  const soon = items.filter((i) => i.expiration_status === "expiring_soon").length;
  const parts = [items.length === 1 ? "1 item" : `${items.length} items`];
  if (expired) parts.push(`${expired} expired`);
  if (soon) parts.push(`${soon} expiring soon`);
  summaryEl.textContent = parts.join(" · ");
}

function renderItem(item) {
  const li = document.createElement("li");
  li.className = "inventory-item";

  const main = document.createElement("div");
  main.className = "inventory-main";
  const name = document.createElement("p");
  name.className = "inventory-name";
  name.textContent = capitalize(item.name);
  const meta = document.createElement("p");
  meta.className = "meta";
  meta.textContent = formatAmount(item);
  main.append(name, meta);

  const expiry = document.createElement("span");
  expiry.className = `chip chip-${item.expiration_status || "none"}`;
  expiry.textContent = formatExpiration(item);

  const actions = document.createElement("div");
  actions.className = "inventory-actions";
  const edit = document.createElement("button");
  edit.type = "button";
  edit.className = "button button-secondary button-small";
  edit.textContent = "Edit";
  edit.setAttribute("aria-label", `Edit ${item.name}`);
  edit.addEventListener("click", () => startEditing(item));
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "link-button is-danger";
  remove.textContent = "Remove";
  remove.setAttribute("aria-label", `Remove ${item.name}`);
  remove.addEventListener("click", () => removeItem(item, remove));
  actions.append(edit, remove);

  li.append(main, expiry, actions);
  return li;
}

// One section per place (fridge, freezer, pantry), each still soonest-to-expire first.
function renderItems() {
  renderSummary();
  const sections = ["fridge", "freezer", "pantry"]
    .map((location) => ({ location, items: items.filter((i) => i.location === location) }))
    .filter((section) => section.items.length);
  listEl.replaceChildren(
    ...sections.map((section) => {
      const wrapper = document.createElement("section");
      wrapper.className = "list-section";
      const heading = document.createElement("h2");
      heading.textContent = `${LOCATION_LABELS[section.location]} `;
      const count = document.createElement("span");
      count.className = "section-count";
      count.textContent = section.items.length;
      heading.append(count);
      const ul = document.createElement("ul");
      ul.className = "inventory-list";
      ul.replaceChildren(...section.items.map(renderItem));
      wrapper.append(heading, ul);
      return wrapper;
    })
  );
}

// Suggest names the app already knows, so inventory items line up with recipe ingredients.
async function loadIngredientOptions() {
  try {
    const ingredients = await apiGet("/ingredients");
    knownIngredients = new Map(ingredients.map((i) => [i.name, i.category]));
    document.getElementById("ingredient-options").replaceChildren(
      ...ingredients.map((ingredient) => new Option(ingredient.name))
    );
  } catch (error) {
    console.error(error); // the form still works without suggestions
  }
}

// ---------- AI ingredient recognition ----------

// Same rule as the backend: "  Soy   SAUCE " -> "soy sauce".
function normalizeName(name) {
  return name.toLowerCase().split(/\s+/).filter(Boolean).join(" ");
}

function formatShelfLife(days) {
  if (days < 14) return days === 1 ? "about a day" : `about ${days} days`;
  if (days < 60) return `about ${Math.round(days / 7)} weeks`;
  if (days < 365) return `about ${Math.round(days / 30)} months`;
  return "a year or more";
}

// Today plus some days, as "YYYY-MM-DD" in local time (what <input type="date"> uses).
function isoDateFromToday(days) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function hideAiPanel() {
  aiPanel.hidden = true;
  aiPanel.replaceChildren();
}

function aiParagraph(text, className) {
  const p = document.createElement("p");
  p.textContent = text;
  if (className) p.className = className;
  return p;
}

function aiButton(label, style, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `button ${style}`;
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

function showAiPanel(...children) {
  aiPanel.replaceChildren(...children);
  aiPanel.hidden = false;
}

function applySuggestion() {
  form.elements.name.value = suggestion.name;
  form.elements.location.value = suggestion.typical_location;
  if (suggestion.shelf_life_days && !form.elements.expiration_date.value) {
    form.elements.expiration_date.value = isoDateFromToday(suggestion.shelf_life_days);
  }
  showAiPanel(aiParagraph("Details filled in. Check them, then add the item.", "hint"));
}

function renderSuggestion(typed) {
  const s = suggestion;
  const actions = document.createElement("div");
  actions.className = "actions";

  if (!s.is_food) {
    actions.append(aiButton("Dismiss", "button-secondary", hideAiPanel));
    showAiPanel(aiParagraph("This doesn't look like a food or cooking ingredient. You can still add it."), actions);
    return;
  }

  const facts = [s.category, `usually kept in the ${s.typical_location}`];
  if (s.shelf_life_days) facts.push(`lasts ${formatShelfLife(s.shelf_life_days)}`);

  if (s.matches_existing) {
    actions.append(
      aiButton(`Use "${s.name}"`, "button-primary", applySuggestion),
      aiButton(`Keep "${typed}"`, "button-secondary", hideAiPanel)
    );
    showAiPanel(
      aiParagraph(`This looks like ${s.name}, which Slice'd already knows.`, "ai-title"),
      aiParagraph(s.description),
      aiParagraph(`Using the same name keeps it matched to your recipes.`, "hint"),
      actions
    );
    return;
  }

  actions.append(
    aiButton("Use these details", "button-primary", applySuggestion),
    aiButton("Keep what I typed", "button-secondary", hideAiPanel)
  );
  const title = s.name === typed ? capitalize(s.name) : `${capitalize(s.name)} (you typed "${typed}")`;
  showAiPanel(
    aiParagraph(title, "ai-title"),
    aiParagraph(s.description),
    aiParagraph(capitalize(facts.join(", ")) + ".", "meta"),
    actions
  );
}

// Runs when you leave the name field. Known ingredients skip the AI entirely.
async function lookUpIngredient() {
  const typed = normalizeName(form.elements.name.value);
  suggestion = null;
  if (!typed || knownIngredients.has(typed)) {
    hideAiPanel();
    return;
  }

  const lookupNumber = ++latestLookup;
  showAiPanel(aiParagraph(`Looking up "${typed}"...`, "hint"));
  try {
    const result = await apiPost("/ingredients/identify", { name: typed });
    if (lookupNumber !== latestLookup) return;
    if (result.known && result.name !== typed) {
      showAiPanel(aiParagraph(`Slice'd already knows this as "${result.name}" and will save it under that name.`, "hint"));
    } else if (result.known) {
      hideAiPanel();
    } else if (result.suggestion) {
      suggestion = { ...result.suggestion, typed };
      renderSuggestion(typed);
    } else {
      showAiPanel(aiParagraph(result.message, "hint"));
    }
  } catch (error) {
    if (lookupNumber !== latestLookup) return;
    // Recognition is a bonus: if it fails, the form still works.
    showAiPanel(aiParagraph(`Couldn't look this up. ${error.message}`, "hint"));
  }
}

// The AI's category, if the name being saved is the one it described (or what was typed).
function categoryFor(name) {
  if (!suggestion || !suggestion.is_food) return undefined;
  return name === suggestion.name || name === suggestion.typed ? suggestion.category : undefined;
}

// ---------- Add / edit form ----------

function readForm() {
  const quantity = form.elements.quantity.value.trim();
  return {
    name: form.elements.name.value.trim(),
    quantity: quantity === "" ? null : Number(quantity),
    unit: form.elements.unit.value.trim() || null,
    location: form.elements.location.value,
    expiration_date: form.elements.expiration_date.value || null,
  };
}

// Quick checks for instant feedback. The backend validates everything again.
function checkForm(data) {
  const problems = [];
  if (!data.name) problems.push("Enter an item name.");
  if (data.quantity !== null && !(data.quantity > 0)) problems.push("Amount must be more than 0.");
  if (data.unit && data.quantity === null) problems.push("Add an amount to go with the unit, or clear the unit.");
  // A half-typed date makes the date input's value empty, which would silently clear the date.
  if (!form.elements.expiration_date.value && form.elements.expiration_date.validity.badInput) {
    problems.push("Enter a complete expiration date, or clear it.");
  }
  return problems;
}

function showErrors(messages) {
  errorsEl.textContent = messages.join("\n");
  errorsEl.hidden = false;
  noticeEl.hidden = true;
  errorsEl.focus();
}

function resetForm() {
  const location = form.elements.location.value; // keep it: people often add several fridge items in a row
  form.reset();
  form.elements.location.value = editingId === null ? location : "pantry";
  editingId = null;
  formHeading.textContent = "Add an item";
  saveButton.textContent = "Add item";
  cancelButton.hidden = true;
  errorsEl.hidden = true;
  noticeEl.hidden = true;
  suggestion = null;
  latestLookup += 1; // an AI answer still on its way is for the old form: ignore it
  hideAiPanel();
}

function startEditing(item) {
  editingId = item.id;
  form.elements.name.value = item.name;
  form.elements.quantity.value = item.quantity ?? "";
  form.elements.unit.value = item.unit ?? "";
  form.elements.location.value = item.location;
  form.elements.expiration_date.value = item.expiration_date ?? "";
  formHeading.textContent = `Edit ${item.name}`;
  saveButton.textContent = "Save changes";
  cancelButton.hidden = false;
  errorsEl.hidden = true;
  noticeEl.hidden = true;
  suggestion = null;
  latestLookup += 1; // an AI answer still on its way is for the old form: ignore it
  hideAiPanel();
  form.scrollIntoView({ block: "start" });
  form.elements.name.focus();
}

async function saveItem(event) {
  event.preventDefault();
  const data = readForm();
  const problems = checkForm(data);
  if (problems.length) {
    showErrors(problems);
    return;
  }

  saveButton.disabled = true;
  try {
    let saved;
    if (editingId === null) {
      const category = categoryFor(normalizeName(data.name));
      saved = await apiPost("/inventory", category ? { ...data, category } : data);
    } else {
      saved = await apiPatch(`/inventory/${editingId}`, data);
    }
    resetForm();
    // "eggs" is saved under the ingredient Slice'd already has ("egg"), so recipes match it.
    if (saved.name !== normalizeName(data.name)) {
      noticeEl.textContent = `Saved as "${saved.name}", the name Slice'd already uses for it.`;
      noticeEl.hidden = false;
    }
    form.elements.name.focus();
    await Promise.all([loadItems(), loadIngredientOptions()]);
  } catch (error) {
    if (error.status === 409 && editingId === null && (await openExistingItem(error.data))) return;
    showErrors([error.message]);
  } finally {
    saveButton.disabled = false;
  }
}

// Adding something you already have opens that item for editing instead of failing.
// The 409 names the item, which may be spelled differently ("eggs" -> your "egg").
async function openExistingItem(conflict) {
  if (!conflict || !conflict.existing_id) return false;
  try {
    const existing = await apiGet(`/inventory/${conflict.existing_id}`);
    startEditing(existing);
    noticeEl.textContent = `You already have ${existing.name} (${formatAmount(existing).toLowerCase()}). Update it here instead.`;
    noticeEl.hidden = false;
    return true;
  } catch (error) {
    return false;
  }
}

async function removeItem(item, button) {
  if (!window.confirm(`Remove ${item.name} from your inventory?`)) return;
  button.disabled = true;
  try {
    await apiDelete(`/inventory/${item.id}`);
    if (editingId === item.id) resetForm();
    await loadItems();
  } catch (error) {
    button.disabled = false;
    summaryEl.textContent = `Couldn't remove ${item.name}. ${error.message}`;
    summaryEl.className = "alert alert-error";
  }
}

// ---------- Events ----------

form.addEventListener("submit", saveItem);
form.elements.name.addEventListener("change", lookUpIngredient);
cancelButton.addEventListener("click", resetForm);

let searchTimer;
filtersForm.elements.search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadItems, 250);
});
filtersForm.elements.location.addEventListener("change", loadItems);
filtersForm.addEventListener("submit", (event) => {
  event.preventDefault();
  loadItems();
});

loadItems();
loadIngredientOptions();
