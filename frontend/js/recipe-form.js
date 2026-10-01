// Create or edit a recipe.
//   recipe-form.html                -> new recipe  (POST /api/recipes)
//   recipe-form.html?id=12          -> edit recipe (PATCH /api/recipes/12)
//   recipe-form.html#import=<data>  -> new recipe, filled from the "Save to Slice'd" Safari button

const editingId = getIdFromUrl();
const form = document.getElementById("recipe-form");
const rowsEl = document.getElementById("ingredient-rows");
const rowTemplate = document.getElementById("ingredient-row-template");
const errorsEl = document.getElementById("form-errors");
const saveButton = document.getElementById("save-button");

// Each row's inputs need unique ids so every <label for="..."> points at its own input.
let rowCounter = 0;

function addIngredientRow(item = {}) {
  const row = rowTemplate.content.firstElementChild.cloneNode(true);
  rowCounter += 1;

  for (const input of row.querySelectorAll("[data-field]")) {
    const field = input.dataset.field;
    input.id = `ingredient-${rowCounter}-${field}`;
    input.closest(".field").querySelector("label").htmlFor = input.id;

    if (field === "optional") input.checked = Boolean(item.optional);
    else if (item[field] !== undefined && item[field] !== null) input.value = item[field];
  }

  row.querySelector(".remove-ingredient").addEventListener("click", () => {
    if (rowsEl.children.length > 1) row.remove();
    else row.querySelectorAll("input").forEach((input) => (input.type === "checkbox" ? (input.checked = false) : (input.value = "")));
  });

  rowsEl.append(row);
  return row;
}

// Turn the form into the JSON the API expects.
function readForm() {
  const numberOrNull = (value) => (value.trim() === "" ? null : Number(value));
  const textOrNull = (value) => value.trim() || null;

  const ingredients = [...rowsEl.children]
    .map((row) => {
      const get = (field) => row.querySelector(`[data-field="${field}"]`);
      return {
        name: get("name").value.trim(),
        quantity: numberOrNull(get("quantity").value),
        unit: textOrNull(get("unit").value),
        preparation_note: textOrNull(get("preparation_note").value),
        optional: get("optional").checked,
      };
    })
    .filter((item) => item.name || item.quantity !== null || item.unit); // skip fully empty rows

  return {
    title: form.elements.title.value.trim(),
    description: textOrNull(form.elements.description.value),
    cuisine: textOrNull(form.elements.cuisine.value),
    servings: numberOrNull(form.elements.servings.value),
    prep_time: numberOrNull(form.elements.prep_time.value),
    cook_time: numberOrNull(form.elements.cook_time.value),
    instructions: form.elements.instructions.value.trim(),
    ingredients,
    // Only sent for imports; leaving it out keeps an edited recipe's link as it was.
    ...(imported ? { source_url: imported.source_url } : {}),
  };
}

// Quick checks in the browser for fast feedback. The backend checks everything
// again, because anyone can send requests to the API without using this form.
function checkForm(data) {
  const problems = [];
  if (!data.title) problems.push("Title is required.");
  if (!Number.isInteger(data.servings) || data.servings < 1) problems.push("Servings must be a whole number of at least 1.");
  if (!Number.isInteger(data.prep_time) || data.prep_time < 0) problems.push("Prep time must be a whole number of minutes.");
  if (!Number.isInteger(data.cook_time) || data.cook_time < 0) problems.push("Cook time must be a whole number of minutes.");
  if (data.ingredients.length === 0) problems.push("Add at least one ingredient.");
  data.ingredients.forEach((item, i) => {
    if (!item.name) problems.push(`Ingredient ${i + 1} needs a name.`);
    if (item.quantity !== null && !(item.quantity > 0)) problems.push(`Ingredient ${i + 1}: quantity must be more than 0.`);
  });
  if (!data.instructions) problems.push("Instructions are required.");
  return problems;
}

function showErrors(messages) {
  errorsEl.textContent = messages.join("\n");
  errorsEl.hidden = false;
  errorsEl.focus(); // moves screen readers and keyboard users to the errors
}

async function handleSubmit(event) {
  event.preventDefault();
  errorsEl.hidden = true;

  const data = readForm();
  const problems = checkForm(data);
  if (problems.length) {
    showErrors(problems);
    return;
  }

  saveButton.disabled = true;
  saveButton.textContent = "Saving...";
  try {
    const saved = editingId === null
      ? await apiPost("/recipes", data)
      : await apiPatch(`/recipes/${editingId}`, data);
    if (imported && imported.image_url && document.getElementById("import-photo").checked) {
      saveButton.textContent = "Saving the photo...";
      try {
        await apiPost(`/recipes/${saved.id}/photo/from-url`, { url: imported.image_url });
      } catch (error) {
        window.alert(`The recipe is saved, but the photo couldn't be downloaded. ${error.message} You can add one on the recipe page.`);
      }
    }
    window.location.href = `/recipe.html?id=${saved.id}`;
  } catch (error) {
    showErrors(error.message.split("\n"));
    saveButton.disabled = false;
    saveButton.textContent = "Save recipe";
  }
}

async function loadCuisineSuggestions() {
  try {
    const cuisines = await apiGet("/recipes/cuisines");
    document.getElementById("cuisine-options").replaceChildren(...cuisines.map((c) => new Option(c)));
  } catch (error) {
    console.error(error); // suggestions are a nice-to-have
  }
}

async function loadRecipeForEditing() {
  const statusEl = document.getElementById("page-status");
  form.hidden = true;
  statusEl.textContent = "Loading recipe...";
  statusEl.hidden = false;

  try {
    const recipe = await apiGet(`/recipes/${editingId}`);
    document.title = `Edit ${recipe.title} · Slice'd`;
    document.getElementById("form-heading").textContent = `Edit ${recipe.title}`;
    document.getElementById("back-link").href = `/recipe.html?id=${recipe.id}`;
    document.getElementById("back-link").textContent = "Back to recipe";
    document.getElementById("cancel-link").href = `/recipe.html?id=${recipe.id}`;

    for (const field of ["title", "description", "cuisine", "servings", "prep_time", "cook_time", "instructions"]) {
      form.elements[field].value = recipe[field] ?? "";
    }
    recipe.ingredients.forEach((item) => addIngredientRow(item));

    statusEl.hidden = true;
    form.hidden = false;
  } catch (error) {
    statusEl.textContent = recipeLoadError(error);
    statusEl.className = "alert alert-error";
  }
}

// ---------- Importing from a website ----------

let imported = null; // the last import's source_url and image_url, saved with the recipe

function fillForm(draft) {
  for (const field of ["title", "description", "cuisine", "servings", "prep_time", "cook_time", "instructions"]) {
    form.elements[field].value = draft[field] ?? "";
  }
  rowsEl.replaceChildren();
  draft.ingredients.forEach((item) => addIngredientRow(item));
  if (draft.ingredients.length === 0) addIngredientRow();
}

function showImport(draft) {
  imported = { source_url: draft.source_url, image_url: draft.image_url };
  fillForm(draft);

  const site = new URL(draft.source_url).hostname.replace(/^www\./, "");
  const heading = document.createElement("p");
  heading.textContent = `Imported from ${site}. Check everything below, especially the ingredients, then save.`;
  const warnings = document.createElement("ul");
  warnings.replaceChildren(
    ...draft.warnings.map((warning) => {
      const li = document.createElement("li");
      li.textContent = warning;
      return li;
    })
  );
  const resultEl = document.getElementById("import-result");
  resultEl.replaceChildren(heading, ...(draft.warnings.length ? [warnings] : []));
  resultEl.hidden = false;
  document.getElementById("import-error").hidden = true;
  document.getElementById("import-photo-row").hidden = !draft.image_url;
}

function showImportError(message) {
  const errorEl = document.getElementById("import-error");
  errorEl.textContent = message;
  errorEl.hidden = false;
  document.getElementById("import-result").hidden = true;
}

async function importFromUrl(event) {
  event.preventDefault();
  const url = document.getElementById("import-url").value.trim();
  if (!url) {
    showImportError("Paste the address of a recipe page first.");
    return;
  }
  const button = document.getElementById("import-button");
  button.disabled = true;
  button.textContent = "Importing...";
  try {
    showImport(await apiPost("/recipes/import", { url }));
  } catch (error) {
    showImportError(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Import";
  }
}

// The Safari button opens recipe-form.html#import=<the page's recipe data>.
async function importFromHash() {
  const data = window.location.hash.slice("#import=".length);
  history.replaceState(null, "", window.location.pathname); // a reload shouldn't import again
  try {
    const { url, recipe } = JSON.parse(decodeURIComponent(data));
    document.getElementById("import-url").value = url;
    showImport(await apiPost("/recipes/import-data", { url, recipe }));
  } catch (error) {
    showImportError(error instanceof SyntaxError ? "The recipe data from Safari was incomplete. Try the button again." : error.message);
  }
}

// The "Save to Slice'd" bookmark. Safari runs it on the recipe page: it finds the page's
// schema.org Recipe data, keeps the fields Slice'd uses, and opens this form with it.
function bookmarkletCode() {
  const code = `(() => {
    const walk = (n) => Array.isArray(n) ? n.flatMap(walk)
      : n && typeof n === "object" ? [n, ...walk(n["@graph"] || []), ...walk(n.mainEntity || [])] : [];
    let recipe;
    for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
      try { recipe = walk(JSON.parse(s.textContent)).find((n) => [].concat(n["@type"]).includes("Recipe")); } catch (e) {}
      if (recipe) break;
    }
    if (!recipe) { alert("Slice'd didn't find a recipe on this page."); return; }
    const keep = {"@type": "Recipe"};
    for (const k of ["name", "description", "image", "recipeYield", "prepTime", "cookTime", "totalTime",
                     "recipeCuisine", "recipeIngredient", "recipeInstructions"]) {
      if (recipe[k] !== undefined) keep[k] = recipe[k];
    }
    window.open("${window.location.origin}/recipe-form.html#import=" +
      encodeURIComponent(JSON.stringify({ url: location.href, recipe: keep })));
  })();`;
  return `javascript:${code.replace(/\s*\n\s*/g, " ")}`;
}

function setUpImport() {
  document.getElementById("import-card").hidden = false;
  document.getElementById("import-form").addEventListener("submit", importFromUrl);
  const bookmarklet = document.getElementById("bookmarklet");
  bookmarklet.href = bookmarkletCode();
  bookmarklet.addEventListener("click", (event) => {
    event.preventDefault(); // here it would only look for a recipe on this page
    window.alert("Drag this button to Safari's Favorites bar, then click it on a recipe page.");
  });
  if (window.location.hash.startsWith("#import=")) importFromHash();
}

document.getElementById("add-ingredient").addEventListener("click", () => {
  addIngredientRow().querySelector('[data-field="name"]').focus();
});
form.addEventListener("submit", handleSubmit);

loadCuisineSuggestions();
if (editingId === null) {
  for (let i = 0; i < 3; i++) addIngredientRow();
  setUpImport();
} else {
  loadRecipeForEditing();
}
