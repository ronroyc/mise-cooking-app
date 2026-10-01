// Recipe detail page: recipe.html?id=12
// Uses textContent everywhere, which is always safe: the browser never treats it as HTML.

const recipeId = getIdFromUrl();
const statusEl = document.getElementById("page-status");
const articleEl = document.getElementById("recipe");

const MAX_SERVINGS = 100; // same limit as the API
let baseServings = null;  // what the recipe was written for
let servings = null;      // what's shown now
let latestLoad = 0;       // ignore an older response that arrives after a newer one

const STATUS_LABELS = { have: "Have", short: "Not enough", expired: "Expired", staple: "Staple", missing: "Missing" };

function showStatus(message, isError) {
  statusEl.textContent = message;
  statusEl.className = isError ? "alert alert-error" : "";
  statusEl.hidden = false;
}

function renderRecipe(recipe) {
  document.title = `${recipe.title} · Mise`;
  document.getElementById("recipe-title").textContent = recipe.title;

  const descriptionEl = document.getElementById("recipe-description");
  descriptionEl.textContent = recipe.description || "";
  descriptionEl.hidden = !recipe.description;

  document.getElementById("fact-cuisine").textContent = recipe.cuisine || "Not set";
  document.getElementById("fact-prep").textContent = formatMinutes(recipe.prep_time);
  document.getElementById("fact-cook").textContent = formatMinutes(recipe.cook_time);
  document.getElementById("fact-total").textContent = formatMinutes(recipe.total_time);

  // Instructions are stored one step per line.
  const steps = recipe.instructions.split("\n").map((s) => s.trim()).filter(Boolean);
  document.getElementById("step-list").replaceChildren(
    ...steps.map((step) => {
      const li = document.createElement("li");
      li.textContent = step;
      return li;
    })
  );

  document.getElementById("edit-link").href = `/recipe-form.html?id=${recipe.id}`;
  document.getElementById("pin-slot").replaceChildren(pinButton(recipe));
  renderPhoto(recipe);
  renderSource(recipe);
  renderCookStats(recipe);

  statusEl.hidden = true;
  articleEl.hidden = false;
}

// ---------- Ingredients, scaled and checked against the inventory ----------

// "Cooked 3 times, last on Sep 20 · Your rating: 4.5 out of 5"
function renderCookStats(recipe) {
  const statsEl = document.getElementById("cook-stats");
  statsEl.hidden = recipe.times_cooked === 0;
  if (recipe.times_cooked === 0) return;
  const times = recipe.times_cooked === 1 ? "once" : `${recipe.times_cooked} times`;
  const parts = [`Cooked ${times}, last on ${formatDate(recipe.last_cooked)}`];
  if (recipe.average_rating !== null) parts.push(`Your rating: ${recipe.average_rating} out of 5`);
  statsEl.textContent = parts.join(" · ");
}

function renderServings() {
  document.getElementById("fact-servings").textContent = servings;
  document.getElementById("servings-down").disabled = servings <= 1;
  document.getElementById("servings-up").disabled = servings >= MAX_SERVINGS;
  document.getElementById("base-servings").textContent =
    `${baseServings} ${baseServings === 1 ? "serving" : "servings"}`;
  document.getElementById("scale-note").hidden = servings === baseServings;
  document.getElementById("cooked-servings").textContent =
    `${servings} ${servings === 1 ? "serving" : "servings"}`;
}

// `match` is null when the inventory check failed: the recipe still shows, just without labels.
function renderIngredients(recipe, match) {
  const statusById = new Map();
  if (match) {
    recipe.ingredients.forEach((item, i) => statusById.set(item.id, match.ingredients[i]));
  }

  document.getElementById("ingredient-list").replaceChildren(
    ...recipe.ingredients.map((item) => {
      const li = document.createElement("li");
      const text = document.createElement("span");
      text.textContent = formatIngredient(item);
      if (item.optional) {
        const label = document.createElement("span");
        label.className = "optional-label";
        label.textContent = " (optional)";
        text.append(label);
      }
      li.append(text);

      const found = statusById.get(item.id);
      if (found) {
        li.className = "has-status";
        const status = document.createElement("span");
        status.className = `ingredient-status ingredient-status-${found.status}`;
        status.textContent = STATUS_LABELS[found.status];
        li.append(status);
        if (found.note) {
          const note = document.createElement("p");
          note.className = "ingredient-note";
          note.textContent = found.note;
          li.append(note);
        }
        if (!["have", "staple"].includes(found.status)) {
          const swaps = renderSwaps(found);
          if (swaps) li.append(swaps);
        }
      }
      return li;
    })
  );

  // Only offer the grocery button when there's something to buy.
  const needsShopping = match && match.ingredients.some((m) => !m.optional && ["short", "expired", "missing"].includes(m.status));
  document.getElementById("grocery-button").hidden = !needsShopping;
  document.getElementById("grocery-actions").hidden = !needsShopping;

  const summaryEl = document.getElementById("match-summary");
  summaryEl.hidden = !match;
  if (match) {
    summaryEl.textContent = match.ready
      ? "You have everything you need."
      : `You have ${match.have_count} of ${match.required_count} ${match.required_count === 1 ? "ingredient" : "ingredients"}.` +
        (match.swap_count ? ` ${match.swap_count} more ${match.swap_count === 1 ? "has a swap" : "have swaps"} you can make.` : "");
    summaryEl.classList.toggle("is-ready", match.ready);
  }
}

// Pass `recipe` when it's already loaded at the current size, to skip fetching it again.
async function loadIngredients(recipe) {
  const loadNumber = ++latestLoad;
  const query = servings === baseServings ? "" : `?servings=${servings}`;
  const [scaled, match] = await Promise.all([
    recipe || apiGet(`/recipes/${recipeId}${query}`),
    apiGet(`/recipes/${recipeId}/match${query}`).catch((error) => {
      console.error(error); // the recipe is still useful without the inventory check
      return null;
    }),
  ]);
  if (loadNumber !== latestLoad) return;
  renderIngredients(scaled, match);
}

// ---------- Grocery list and cooking history ----------

function showResult(el, heading, lines) {
  const title = document.createElement("p");
  title.textContent = heading;
  el.replaceChildren(title);
  if (lines.length) {
    const list = document.createElement("ul");
    list.replaceChildren(
      ...lines.map((line) => {
        const li = document.createElement("li");
        li.textContent = line;
        return li;
      })
    );
    el.append(list);
  }
  el.hidden = false;
}

async function addMissingToGrocery() {
  const button = document.getElementById("grocery-button");
  const resultEl = document.getElementById("grocery-result");
  button.disabled = true;
  try {
    const query = servings === baseServings ? "" : `?servings=${servings}`;
    const result = await apiPost(`/grocery/from-recipe/${recipeId}${query}`);
    showResult(resultEl, result.message, result.added.map((item) => `${capitalize(item.name)}: ${item.amount_text}`));
    const link = document.createElement("a");
    link.href = "/grocery.html";
    link.textContent = "Go to grocery list";
    resultEl.append(link);
  } catch (error) {
    showResult(resultEl, `Couldn't add to your grocery list. ${error.message}`, []);
  } finally {
    button.disabled = false;
  }
}

function todayIso() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

async function saveCooked(event) {
  event.preventDefault();
  const form = event.target;
  const errorsEl = document.getElementById("cooked-errors");
  const cookedOn = form.elements.cooked_on.value;
  const leftoverText = form.elements.leftover_servings.value.trim();
  const leftovers = leftoverText === "" ? null : Number(leftoverText);
  let problem = null;
  if (!cookedOn || cookedOn > todayIso()) problem = "Pick the day you cooked it (today or earlier).";
  else if (leftovers !== null && !(Number.isInteger(leftovers) && leftovers >= 1 && leftovers <= 50)) {
    problem = "Servings left over must be a whole number from 1 to 50, or empty.";
  }
  if (problem) {
    errorsEl.textContent = problem;
    errorsEl.hidden = false;
    errorsEl.focus();
    return;
  }
  const button = document.getElementById("cooked-button");
  button.disabled = true;
  try {
    const result = await apiPost(`/recipes/${recipeId}/cooked`, {
      servings,
      cooked_on: cookedOn,
      rating: form.elements.rating.value ? Number(form.elements.rating.value) : null,
      notes: form.elements.notes.value.trim() || null,
      update_inventory: form.elements.update_inventory.checked,
      leftover_servings: leftovers,
    });
    errorsEl.hidden = true;
    form.reset();
    form.elements.cooked_on.value = todayIso();
    const heading = result.inventory_changes.length
      ? "Saved. Your inventory is updated:"
      : "Saved to your history.";
    showResult(document.getElementById("cooked-result"), heading, result.inventory_changes);
    // Stats, history, and the inventory labels all changed.
    const [recipe] = await Promise.all([apiGet(`/recipes/${recipeId}`), loadHistory(), loadIngredients()]);
    renderCookStats(recipe);
  } catch (error) {
    errorsEl.textContent = `Couldn't save. ${error.message}`;
    errorsEl.hidden = false;
  } finally {
    button.disabled = false;
  }
}

async function loadHistory() {
  const listEl = document.getElementById("recipe-history");
  try {
    const logs = await apiGet(`/history?recipe_id=${recipeId}`);
    document.getElementById("recipe-history-empty").hidden = logs.length > 0;
    listEl.hidden = logs.length === 0;
    listEl.replaceChildren(...logs.map(renderLog));
  } catch (error) {
    console.error(error); // the recipe is still useful without its history
  }
}

// "Sep 20 · 4 servings · Rated 4 out of 5" with notes underneath. Shared idea with history.js.
function renderLog(log) {
  const li = document.createElement("li");
  const line = document.createElement("p");
  line.className = "meta";
  const parts = [formatDate(log.cooked_on), `${log.servings} ${log.servings === 1 ? "serving" : "servings"}`];
  parts.push(log.rating ? `Rated ${log.rating} out of 5` : "Not rated");
  line.textContent = parts.join(" · ");
  li.append(line);
  if (log.notes) {
    const notes = document.createElement("p");
    notes.textContent = log.notes;
    li.append(notes);
  }
  return li;
}

async function setServings(value) {
  servings = Math.min(MAX_SERVINGS, Math.max(1, value));
  renderServings();
  try {
    await loadIngredients();
  } catch (error) {
    showStatus(`Couldn't resize the recipe. ${error.message}`, true);
    articleEl.hidden = true;
  }
}

async function deleteRecipe() {
  const title = document.getElementById("recipe-title").textContent;
  if (!window.confirm(`Delete "${title}"? This can't be undone.`)) return;

  const button = document.getElementById("delete-button");
  const errorEl = document.getElementById("delete-error");
  button.disabled = true;
  errorEl.hidden = true;
  try {
    await apiDelete(`/recipes/${recipeId}`);
    window.location.href = "/recipes.html";
  } catch (error) {
    errorEl.textContent = `Couldn't delete the recipe. ${error.message}`;
    errorEl.hidden = false;
    button.disabled = false;
  }
}

// ---------- Swaps for ingredients you don't have ----------

let aiAvailable = false; // set in init() from /api/ai/status

const lowerFirst = (text) => text.charAt(0).toLowerCase() + text.slice(1);

function paragraph(text, className) {
  const p = document.createElement("p");
  if (className) p.className = className;
  p.textContent = text;
  return p;
}

// "Swap: use your pecorino, same amount. Also hard, aged, and salty."
// Swaps you can make come first; others are listed as ideas. Nothing changes the recipe.
function renderSwaps(found) {
  const have = found.swaps.filter((s) => s.have);
  const other = found.swaps.filter((s) => !s.have);
  if (!have.length && !other.length && !aiAvailable) return null;

  const box = document.createElement("div");
  box.className = "swaps";
  for (const swap of have) {
    const p = document.createElement("p");
    const label = document.createElement("span");
    label.className = "swap-have";
    label.textContent = `Swap: use your ${swap.uses.join(" + ")}`;
    p.append(label, `, ${lowerFirst(swap.amount)}. ${swap.note}`);
    box.append(p);
  }
  if (other.length) {
    const ideas = other.map((s) => `${s.uses.join(" + ")} (${lowerFirst(s.amount)})`).join("; ");
    box.append(paragraph(`${have.length ? "Or" : "Swaps you'd need to buy"}: ${ideas}`, "hint"));
  }
  if (aiAvailable) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "link-button";
    button.textContent = "Ask AI for ideas";
    button.addEventListener("click", () => askAI(found.name, box, button));
    box.append(button);
  }
  return box;
}

async function askAI(name, box, button) {
  button.disabled = true;
  button.textContent = "Asking...";
  const status = paragraph("", "hint");
  status.setAttribute("role", "status");
  try {
    const result = await apiPost(`/recipes/${recipeId}/substitutes?servings=${servings}`, { ingredient: name });
    if (!result.ideas.length) {
      status.textContent = result.message || "The AI didn't have any ideas for this one.";
      box.append(status);
      button.textContent = "Ask AI for ideas";
      button.disabled = false;
      return;
    }
    const list = document.createElement("ul");
    list.className = "ai-ideas";
    list.replaceChildren(
      ...result.ideas.map((idea) => {
        const li = document.createElement("li");
        const kitchen = idea.uses_from_kitchen ? " (you have it)" : "";
        li.textContent = `${idea.substitute}${kitchen}: ${lowerFirst(idea.amount)}. ${idea.how_it_changes}`;
        return li;
      })
    );
    box.append(paragraph("Ideas from AI", "ai-heading"), list);
    if (result.can_leave_out) {
      box.append(paragraph(`You could also leave it out.${result.leave_out_note ? ` ${result.leave_out_note}` : ""}`, "hint"));
    }
    button.remove();
  } catch (error) {
    status.textContent = `Couldn't get ideas. ${error.message}`;
    box.append(status);
    button.textContent = "Ask AI for ideas";
    button.disabled = false;
  }
}

// ---------- Flavor ----------

// Only flavors that are really there (Low or stronger), strongest first, each with
// the ingredients it comes from. Optional ingredients don't count.
async function loadFlavor() {
  try {
    const flavor = await apiGet(`/recipes/${recipeId}/flavor`);
    const shown = flavor.values.filter((v) => v.value >= 0.15).sort((a, b) => b.value - a.value);
    document.getElementById("flavor-bars").replaceChildren(...shown.map((v) => flavorBar(v)));
    const unknownEl = document.getElementById("flavor-unknown");
    unknownEl.hidden = flavor.unknown.length === 0;
    unknownEl.textContent = `Mise doesn't know the flavor of ${flavor.unknown.join(", ")} yet, so ${flavor.unknown.length === 1 ? "it isn't" : "they aren't"} counted.`;
    document.getElementById("flavor-card").hidden = shown.length === 0 && flavor.unknown.length === 0;
  } catch (error) {
    console.error(error); // the recipe works without its flavor
  }
}

async function loadAIStatus() {
  try {
    aiAvailable = (await apiGet("/ai/status")).available;
  } catch (error) {
    aiAvailable = false; // the page works without AI
  }
}

// "From bbcgoodfood.com", for imported recipes. The API only accepts http(s) links.
function renderSource(recipe) {
  const sourceEl = document.getElementById("recipe-source");
  sourceEl.hidden = !recipe.source_url;
  if (!recipe.source_url) return;
  const link = document.getElementById("source-link");
  link.href = recipe.source_url;
  link.textContent = new URL(recipe.source_url).hostname.replace(/^www\./, "");
}

// ---------- Photo ----------

const MAX_PHOTO_BYTES = 15 * 1024 * 1024; // same limit as the API

function renderPhoto(recipe) {
  const img = document.getElementById("recipe-photo");
  img.hidden = !recipe.photo_url;
  if (recipe.photo_url) {
    // A small photo (some sites only offer 440px) is shown at its own size, not stretched blurry.
    img.style.maxWidth = "";
    img.onload = () => {
      if (img.naturalWidth < img.clientWidth) img.style.maxWidth = `${img.naturalWidth}px`;
    };
    img.src = recipe.photo_url;
    img.alt = `Photo of ${recipe.title}`;
  } else {
    img.removeAttribute("src");
  }
  document.getElementById("photo-button").textContent = recipe.photo_url ? "Change photo" : "Add a photo";
  document.getElementById("photo-remove").hidden = !recipe.photo_url;
}

function showPhotoError(message) {
  const errorEl = document.getElementById("photo-error");
  errorEl.textContent = message;
  errorEl.hidden = !message;
}

async function uploadPhoto() {
  const input = document.getElementById("photo-input");
  const file = input.files[0];
  input.value = ""; // picking the same file again should still upload it
  if (!file) return;
  if (file.size > MAX_PHOTO_BYTES) {
    showPhotoError("That photo is too big. The limit is 15 MB.");
    return;
  }
  const button = document.getElementById("photo-button");
  button.disabled = true;
  button.textContent = "Uploading...";
  showPhotoError("");
  try {
    renderPhoto(await apiPut(`/recipes/${recipeId}/photo`, file));
  } catch (error) {
    showPhotoError(`Couldn't upload the photo. ${error.message}`);
    button.textContent = document.getElementById("recipe-photo").hidden ? "Add a photo" : "Change photo";
  } finally {
    button.disabled = false;
  }
}

async function removePhoto() {
  if (!window.confirm("Remove this recipe's photo?")) return;
  const button = document.getElementById("photo-remove");
  button.disabled = true;
  showPhotoError("");
  try {
    renderPhoto(await apiDelete(`/recipes/${recipeId}/photo`));
  } catch (error) {
    showPhotoError(`Couldn't remove the photo. ${error.message}`);
  } finally {
    button.disabled = false;
  }
}

async function init() {
  if (recipeId === null) {
    showStatus("No recipe selected. Go back to the recipe list and pick one.", true);
    return;
  }
  try {
    const [recipe] = await Promise.all([apiGet(`/recipes/${recipeId}`), loadAIStatus()]);
    baseServings = servings = recipe.base_servings;
    renderRecipe(recipe);
    renderServings();
    document.getElementById("cooked-on").value = todayIso();
    document.getElementById("cooked-on").max = todayIso();
    loadHistory();
    loadFlavor();
    await loadIngredients(recipe);
  } catch (error) {
    showStatus(recipeLoadError(error), true);
    articleEl.hidden = true;
  }
}

document.getElementById("delete-button").addEventListener("click", deleteRecipe);
document.getElementById("servings-down").addEventListener("click", () => setServings(servings - 1));
document.getElementById("servings-up").addEventListener("click", () => setServings(servings + 1));
document.getElementById("servings-reset").addEventListener("click", () => setServings(baseServings));
document.getElementById("grocery-button").addEventListener("click", addMissingToGrocery);
document.getElementById("cooked-form").addEventListener("submit", saveCooked);
document.getElementById("photo-button").addEventListener("click", () => document.getElementById("photo-input").click());
document.getElementById("photo-input").addEventListener("change", uploadPhoto);
document.getElementById("photo-remove").addEventListener("click", removePhoto);
init();
