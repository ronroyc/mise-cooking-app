// Recipe list page: search + filters + a grid of recipe cards, sorted A to Z or by best match.
// Each card has a colored corner for how much of the recipe is in the kitchen, and a Pin button.

const filtersForm = document.getElementById("filters");
const listEl = document.getElementById("recipe-list");
const countEl = document.getElementById("result-count");

// Each search gets a number. If an older, slower response arrives after a newer
// one, we ignore it so the list always matches what's in the search box.
let latestRequest = 0;

// recipes.html?sort=match (the dashboard links here) starts in best-match order,
// and ?show=pinned starts with pinned recipes.
const startParams = new URLSearchParams(window.location.search);
if (startParams.get("sort") === "match") filtersForm.elements.sort.value = "match";
if (startParams.get("show") === "pinned") filtersForm.elements.show.value = "pinned";

async function loadCuisines() {
  try {
    const cuisines = await apiGet("/recipes/cuisines");
    const select = filtersForm.elements.cuisine;
    for (const cuisine of cuisines) {
      select.add(new Option(cuisine, cuisine));
    }
  } catch (error) {
    console.error(error); // the list still works without the cuisine dropdown
  }
}

async function loadRecipes() {
  const params = new URLSearchParams();
  const search = filtersForm.elements.search.value.trim();
  const cuisine = filtersForm.elements.cuisine.value;
  const maxTime = filtersForm.elements.max_total_time.value;
  if (search) params.set("search", search);
  if (cuisine) params.set("cuisine", cuisine);
  if (maxTime) params.set("max_total_time", maxTime);
  if (filtersForm.elements.show.value === "pinned") params.set("pinned", "true");

  const byMatch = filtersForm.elements.sort.value === "match";
  const requestNumber = ++latestRequest;
  try {
    // Recommendations come best match first, and each one says how much of the recipe
    // is in the kitchen, which every card needs for its corner color.
    const result = await apiGet(`/recommendations?${params}`);
    if (requestNumber !== latestRequest) return;
    const recipes = result.recommendations.map((rec) => ({ ...rec.recipe, match: rec }));
    if (!byMatch) recipes.sort((a, b) => a.title.localeCompare(b.title));
    renderRecipes(recipes, byMatch);
  } catch (error) {
    if (requestNumber !== latestRequest) return;
    listEl.replaceChildren();
    countEl.textContent = `Couldn't load recipes. ${error.message}`;
    countEl.className = "alert alert-error";
  }
}

function renderRecipes(recipes, byMatch) {
  countEl.className = "result-count";
  const pinnedOnly = filtersForm.elements.show.value === "pinned";
  if (recipes.length === 0) {
    countEl.textContent = pinnedOnly && !hasOtherFilters()
      ? "No pinned recipes yet. Pin one to keep it here."
      : "No recipes match those filters.";
  } else {
    countEl.textContent = recipes.length === 1 ? "1 recipe" : `${recipes.length} recipes`;
  }
  listEl.replaceChildren(...recipes.map((recipe) => renderCard(recipe, byMatch)));
  layoutGrid();
}

function hasOtherFilters() {
  const f = filtersForm.elements;
  return Boolean(f.search.value.trim() || f.cuisine.value || f.max_total_time.value);
}

function renderCard(recipe, byMatch) {
  const li = document.createElement("li");
  li.className = "recipe-card";
  colorTicket(li, recipe.match);
  const cover = recipeCover(recipe, () => layoutCard(li));

  const body = document.createElement("div");
  body.className = "recipe-card-body";

  // Ticket header: what it is and how long, then how many it serves.
  const head = document.createElement("p");
  head.className = "ticket-head";
  const what = document.createElement("span");
  what.textContent = [recipe.cuisine, recipeTime(recipe)].filter(Boolean).join(" · ");
  const serves = document.createElement("span");
  serves.textContent = servesText(recipe);
  head.append(what, serves);

  const heading = document.createElement("h2");
  const link = document.createElement("a");
  link.href = `/recipe.html?id=${recipe.id}`;
  link.textContent = recipe.title;
  heading.append(link);
  body.append(head, heading, matchLine(recipe.match, byMatch));

  if (recipe.times_cooked) {
    const cooked = document.createElement("p");
    cooked.className = "hint";
    cooked.textContent = `Cooked ${recipe.times_cooked === 1 ? "once" : `${recipe.times_cooked} times`}` +
      (recipe.average_rating !== null ? `, rated ${recipe.average_rating}` : "");
    body.append(cooked);
  }
  if (recipe.description) {
    const description = document.createElement("p");
    description.className = "recipe-card-description";
    description.textContent = recipe.description;
    body.append(description);
  }
  body.append(pinButton(recipe, () => {
    // Unpinned while looking at pinned recipes: it no longer belongs in the list.
    if (!recipe.pinned && filtersForm.elements.show.value === "pinned") loadRecipes();
  }));

  li.append(...(cover ? [cover] : []), body, recipeStamp(recipe.match));
  return li;
}

// "You have 6 of 8 ingredients", plus the score when sorted by best match.
// This line says in words what the corner says in color.
function matchLine(match, byMatch) {
  const p = document.createElement("p");
  p.className = `match-line match-${match.color}`;
  const noun = match.required_count === 1 ? "ingredient" : "ingredients";
  let text = match.ready ? "You have everything" : `You have ${match.have_count} of ${match.required_count} ${noun}`;
  if (!match.ready && match.swap_count) text += `, ${match.swap_count} more with a swap`;
  if (byMatch) text += ` · ${match.score} ${match.score === 1 ? "point" : "points"}`;
  p.textContent = text;
  return p;
}

// ---------- Pinterest-style grid ----------
// The grid has 1px rows. Each card spans as many rows as it is tall (plus the gap),
// so cards of different heights pack into columns instead of leaving holes, while
// the list keeps its order for screen readers and the keyboard.

// Measure every card first, then set every span. Alternating the two makes the browser
// redo the page layout once per card: with 800 recipes that took several seconds.
function layoutCards(cards) {
  const gap = parseFloat(getComputedStyle(listEl).columnGap) || 0;
  const heights = cards.map((card) => card.getBoundingClientRect().height);
  cards.forEach((card, i) => {
    card.style.gridRowEnd = `span ${Math.ceil(heights[i] + gap)}`;
  });
}

const layoutCard = (card) => layoutCards([card]);

// Cards change height when the window resizes (text wraps) or a photo loads.
const cardResizes = new ResizeObserver((entries) => layoutCards(entries.map((entry) => entry.target)));

function layoutGrid() {
  cardResizes.disconnect();
  const cards = [...listEl.children];
  layoutCards(cards);
  cards.forEach((card) => cardResizes.observe(card));
}

// Search as you type, but wait until typing pauses for 250ms.
let searchTimer;
filtersForm.elements.search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadRecipes, 250);
});
filtersForm.elements.cuisine.addEventListener("change", loadRecipes);
filtersForm.elements.max_total_time.addEventListener("change", loadRecipes);
filtersForm.elements.sort.addEventListener("change", loadRecipes);
filtersForm.elements.show.addEventListener("change", loadRecipes);
filtersForm.addEventListener("submit", (event) => {
  event.preventDefault(); // pressing Enter shouldn't reload the page
  loadRecipes();
});

loadCuisines();
loadRecipes();
