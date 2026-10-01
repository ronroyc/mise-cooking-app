// Home: a few numbers about the kitchen, tonight's picks, what to use soon,
// and what's on the grocery list. Each part loads on its own, so one failure doesn't blank the page.

function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

function setStat(id, text) {
  document.getElementById(id).textContent = text;
}

// Only speaks up when something's wrong: a healthy backend needs no announcement.
async function checkBackend() {
  try {
    await apiGet("/health");
  } catch (error) {
    const alertEl = document.getElementById("backend-alert");
    alertEl.textContent = "Can't reach the Slice'd server, so nothing below can load. Is it running?";
    alertEl.hidden = false;
  }
}

// "Monday, September 28. Recipes ranked by..." as the intro line.
function showDate() {
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
  document.getElementById("dash-intro").textContent =
    `${today}. Recipes ranked by what's already in your kitchen.`;
}

// ---------- Recommendations ----------
// The top 3 are "Tonight's picks" with covers; the next 5 are a numbered index,
// like the contents page of a cookbook.

const PICKS = 3;
const INDEX_LENGTH = 5;

const number = (n) => String(n).padStart(2, "0");

async function showRecommendations() {
  const statusEl = document.getElementById("recs-status");
  try {
    const result = await apiGet("/recommendations");
    const ready = result.recommendations.filter((rec) => rec.ready).length;
    setStat("stat-ready", ready);

    if (result.recommendations.length === 0) {
      statusEl.textContent = "No recipes yet. Add one on the Recipes page.";
      return;
    }
    if (result.inventory_count === 0) {
      statusEl.textContent =
        "Your inventory is empty, so every recipe needs shopping. Add what's in your kitchen to rank them.";
    } else {
      statusEl.hidden = true;
    }
    const recs = result.recommendations;
    const picksEl = document.getElementById("picks");
    picksEl.replaceChildren(...recs.slice(0, PICKS).map((rec, i) => renderPick(rec, i + 1)));
    picksEl.hidden = false;
    const rest = recs.slice(PICKS, PICKS + INDEX_LENGTH);
    const indexEl = document.getElementById("recs-list");
    indexEl.replaceChildren(...rest.map((rec, i) => renderIndexRow(rec, PICKS + i + 1)));
    indexEl.hidden = rest.length === 0;
  } catch (error) {
    setStat("stat-ready", "?");
    statusEl.textContent = `Couldn't rank your recipes. ${error.message}`;
    statusEl.className = "alert alert-error";
  }
}

// "Have 5 of 8 ingredients" or "Ready to cook", plus "1 more with a swap".
function haveText(rec) {
  if (rec.ready) return "Ready to cook";
  let text = `Have ${rec.have_count} of ${plural(rec.required_count, "ingredient", "ingredients")}`;
  if (rec.swap_count) text += `, ${rec.swap_count} more with a swap`;
  return text;
}

function recipeLink(rec) {
  const link = document.createElement("a");
  link.href = `/recipe.html?id=${rec.recipe.id}`;
  link.textContent = rec.recipe.title;
  return link;
}

function renderPick(rec, n) {
  const li = document.createElement("li");
  li.className = "pick";
  li.append(recipeCover(rec.recipe, rec));

  const heading = document.createElement("h3");
  const numeral = document.createElement("span");
  numeral.className = "pick-number";
  numeral.textContent = number(n);
  heading.append(numeral, recipeLink(rec));

  const meta = document.createElement("p");
  meta.className = "label";
  meta.textContent = [rec.recipe.cuisine, formatMinutes(rec.recipe.total_time)].filter(Boolean).join(" · ");

  const have = document.createElement("p");
  have.className = `pick-have match-${rec.color}`;
  have.textContent = `${haveText(rec)} · ${plural(rec.score, "point", "points")}`;

  li.append(heading, meta, have);
  // The first reason repeats the "have" line, so only the ones after it are shown.
  const extra = rec.reasons.slice(1, 3);
  if (extra.length) {
    const reasons = document.createElement("p");
    reasons.className = "hint";
    reasons.textContent = extra.join(" ");
    li.append(reasons);
  }
  return li;
}

function renderIndexRow(rec, n) {
  const li = document.createElement("li");
  li.className = "index-row";
  const numeral = document.createElement("span");
  numeral.className = "index-number";
  numeral.textContent = number(n);
  const title = document.createElement("span");
  title.className = "index-title";
  title.append(recipeLink(rec));
  const meta = document.createElement("span");
  meta.className = "label index-meta";
  meta.textContent = [rec.recipe.cuisine, formatMinutes(rec.recipe.total_time)].filter(Boolean).join(" · ");
  title.append(meta);
  const have = document.createElement("span");
  have.className = `index-have match-${rec.color}`;
  have.textContent = haveText(rec);
  const score = document.createElement("span");
  score.className = "index-score";
  score.textContent = rec.score;
  score.title = plural(rec.score, "point", "points");
  li.append(numeral, title, have, score);
  return li;
}

// ---------- Inventory: counts and what to use soon ----------

async function showKitchen() {
  const statusEl = document.getElementById("use-soon-status");
  const listEl = document.getElementById("use-soon-list");
  try {
    const items = await apiGet("/inventory");
    // Expired or expiring within 3 days; the API already sorts soonest first.
    const soon = items.filter((i) => i.expiration_status === "expired" || i.expiration_status === "expiring_soon");
    setStat("stat-kitchen", items.length);
    setStat("stat-soon", soon.length);

    if (items.length === 0) {
      statusEl.textContent = "Nothing in your inventory yet.";
      return;
    }
    if (soon.length === 0) {
      statusEl.textContent = "Nothing is about to expire.";
      return;
    }
    statusEl.hidden = true;
    listEl.replaceChildren(
      ...soon.map((item) => {
        const li = document.createElement("li");
        const name = document.createElement("span");
        name.textContent = capitalize(item.name);
        const amount = document.createElement("span");
        amount.className = "meta";
        amount.textContent = ` ${item.amount_text}`;
        name.append(amount);
        const expiry = document.createElement("span");
        expiry.className = `chip chip-${item.expiration_status}`;
        expiry.textContent = formatExpiration(item);
        li.append(name, expiry);
        return li;
      })
    );
    listEl.hidden = false;
  } catch (error) {
    setStat("stat-kitchen", "?");
    setStat("stat-soon", "?");
    statusEl.textContent = `Couldn't load your inventory. ${error.message}`;
    statusEl.className = "alert alert-error";
  }
}

// ---------- Grocery list preview ----------

const GROCERY_PREVIEW = 6;

async function showGrocery() {
  const statusEl = document.getElementById("grocery-status");
  const listEl = document.getElementById("grocery-list");
  try {
    const items = (await apiGet("/grocery")).filter((i) => !i.checked);
    setStat("stat-grocery", items.length);
    if (items.length === 0) {
      statusEl.textContent = 'Nothing to buy. Use "Add missing to grocery list" on a recipe.';
      return;
    }
    listEl.replaceChildren(
      ...items.slice(0, GROCERY_PREVIEW).map((item) => {
        const li = document.createElement("li");
        const name = document.createElement("span");
        name.textContent = capitalize(item.name);
        const amount = document.createElement("span");
        amount.className = "meta";
        amount.textContent = item.quantity_text;
        li.append(name, amount);
        return li;
      })
    );
    listEl.hidden = false;
    statusEl.hidden = true;
    const more = items.length - GROCERY_PREVIEW;
    if (more > 0) {
      const moreEl = document.getElementById("grocery-more");
      moreEl.textContent = `And ${plural(more, "more item", "more items")}.`;
      moreEl.hidden = false;
    }
  } catch (error) {
    setStat("stat-grocery", "?");
    statusEl.textContent = `Couldn't load your grocery list. ${error.message}`;
    statusEl.className = "alert alert-error";
  }
}

showDate();
checkBackend();
showRecommendations();
showKitchen();
showGrocery();
