// Meal prep: choose recipes (pinned ones start checked), then see one combined shopping
// list and what to prep once. Everything is worked out by POST /api/meal-prep/plan.

const form = document.getElementById("plan-form");
const choicesEl = document.getElementById("choices");
const errorsEl = document.getElementById("plan-errors");

let lastPlan = null; // the recipes behind the plan on screen, for "Add all to grocery list"

function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

// ---------- Choosing recipes ----------

function renderChoice(recipe) {
  const li = document.createElement("li");
  li.className = "choice";
  const label = document.createElement("label");
  label.className = "checkbox-row";
  const box = document.createElement("input");
  box.type = "checkbox";
  box.value = recipe.id;
  box.checked = recipe.pinned;
  const title = document.createElement("span");
  title.textContent = recipe.title;
  label.append(box, title);
  if (recipe.pinned) {
    const pinned = document.createElement("span");
    pinned.className = "label";
    pinned.textContent = "Pinned";
    label.append(pinned);
  }

  const servings = document.createElement("input");
  servings.type = "number";
  servings.min = "1";
  servings.max = "100";
  servings.step = "1";
  servings.value = recipe.servings;
  servings.className = "servings-input";
  servings.setAttribute("aria-label", `Servings of ${recipe.title}`);
  const servingsLabel = document.createElement("span");
  servingsLabel.className = "hint";
  servingsLabel.textContent = "servings";
  const servingsBox = document.createElement("span");
  servingsBox.className = "choice-servings";
  servingsBox.append(servings, servingsLabel);

  li.append(label, servingsBox);
  return li;
}

async function loadChoices() {
  const statusEl = document.getElementById("choices-status");
  try {
    const recipes = await apiGet("/recipes");
    if (recipes.length === 0) {
      statusEl.textContent = "No recipes yet. Add some on the Recipes page first.";
      document.getElementById("plan-button").hidden = true;
      return;
    }
    // Pinned first, then the rest; each group A to Z (the API already sorts by title).
    const sorted = [...recipes.filter((r) => r.pinned), ...recipes.filter((r) => !r.pinned)];
    choicesEl.replaceChildren(...sorted.map(renderChoice));
    choicesEl.hidden = false;
    const pinned = recipes.filter((r) => r.pinned).length;
    statusEl.textContent = pinned
      ? `Your ${plural(pinned, "pinned recipe", "pinned recipes")} ${pinned === 1 ? "is" : "are"} checked to start.`
      : "Check the recipes you're making. Pin recipes to have them checked here next time.";
    if (pinned) await makePlan();
  } catch (error) {
    statusEl.textContent = `Couldn't load your recipes. ${error.message}`;
    statusEl.className = "alert alert-error";
  }
}

function readChoices() {
  const chosen = [];
  const problems = [];
  for (const li of choicesEl.children) {
    const box = li.querySelector('input[type="checkbox"]');
    if (!box.checked) continue;
    const servings = Number(li.querySelector(".servings-input").value);
    if (!Number.isInteger(servings) || servings < 1 || servings > 100) {
      problems.push(`Servings for ${li.querySelector(".checkbox-row span").textContent} must be a whole number from 1 to 100.`);
    }
    chosen.push({ id: Number(box.value), servings });
  }
  if (!chosen.length) problems.push("Check at least one recipe.");
  if (chosen.length > 14) problems.push("Pick up to 14 recipes at a time.");
  return { chosen, problems };
}

// ---------- The plan ----------

async function makePlan(event) {
  if (event) event.preventDefault();
  const { chosen, problems } = readChoices();
  if (problems.length) {
    errorsEl.textContent = problems.join("\n");
    errorsEl.hidden = false;
    errorsEl.focus();
    return;
  }
  errorsEl.hidden = true;
  const button = document.getElementById("plan-button");
  button.disabled = true;
  try {
    renderPlan(await apiPost("/meal-prep/plan", { recipes: chosen }));
    lastPlan = chosen;
    document.getElementById("grocery-result").hidden = true;
  } catch (error) {
    errorsEl.textContent = `Couldn't make the plan. ${error.message}`;
    errorsEl.hidden = false;
  } finally {
    button.disabled = false;
  }
}

function listItem(title, ...details) {
  const li = document.createElement("li");
  const main = document.createElement("div");
  const strong = document.createElement("p");
  strong.className = "prep-title";
  strong.textContent = title;
  main.append(strong);
  for (const detail of details.filter(Boolean)) {
    const p = document.createElement("p");
    p.className = "hint";
    p.textContent = detail;
    main.append(p);
  }
  li.append(main);
  return li;
}

function renderPlan(plan) {
  document.getElementById("fig-recipes").textContent = plan.recipes.length;
  document.getElementById("fig-servings").textContent = plan.total_servings;
  document.getElementById("fig-prep").textContent = plan.prep_together.length;
  document.getElementById("fig-buy").textContent = plan.shopping.length;

  document.getElementById("prep-list").replaceChildren(
    ...plan.prep_together.map((step) =>
      listItem(step.instruction, step.notes.length > 1 ? `As the recipes say: ${step.notes.join("; ")}` : null,
        `For ${step.recipes.join(", ")}`)
    )
  );
  document.getElementById("prep-empty").hidden = plan.prep_together.length > 0;

  document.getElementById("buy-list").replaceChildren(
    ...plan.shopping.map((item) => {
      const li = listItem(capitalize(item.name), item.reason, `For ${item.recipes.join(", ")}`);
      const amount = document.createElement("span");
      amount.className = "prep-amount";
      amount.textContent = item.amount_text;
      li.append(amount);
      return li;
    })
  );
  document.getElementById("buy-empty").hidden = plan.shopping.length > 0;
  document.getElementById("buy-actions").hidden = plan.shopping.length === 0;

  document.getElementById("covered").textContent = plan.covered.length
    ? `Already in your kitchen: ${plan.covered.join(", ")}.`
    : "";
  document.getElementById("plan").hidden = false;
}

async function addToGrocery() {
  if (!lastPlan) return;
  const button = document.getElementById("grocery-button");
  const resultEl = document.getElementById("grocery-result");
  button.disabled = true;
  try {
    const rows = await apiPost("/meal-prep/grocery", { recipes: lastPlan });
    resultEl.textContent = `Added to your grocery list: ${plural(rows.length, "item", "items")}. Items already on it were combined.`;
    resultEl.className = "alert alert-info";
  } catch (error) {
    resultEl.textContent = `Couldn't update your grocery list. ${error.message}`;
    resultEl.className = "alert alert-error";
  } finally {
    resultEl.hidden = false;
    button.disabled = false;
  }
}

form.addEventListener("submit", makePlan);
document.getElementById("grocery-button").addEventListener("click", addToGrocery);
loadChoices();
