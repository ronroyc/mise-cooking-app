// Profile page: stats, flavor profile (radar chart + bars), "Slice'd knows...", and top ingredients.
// Every number comes from GET /api/profile, which only fills a section once there's enough data.

const statusEl = document.getElementById("page-status");

function setText(id, text) {
  document.getElementById(id).textContent = text;
}

function renderStats(stats) {
  setText("stat-meals", stats.meals_cooked);
  setText("stat-pinned", stats.recipes_pinned);
  setText("stat-rating", stats.average_rating === null ? "Not rated yet" : `${stats.average_rating} of 5`);
  setText("stat-minutes", stats.average_minutes === null ? "No meals yet" : formatMinutes(stats.average_minutes));
  // Words instead of a number ("Not rated yet") are set smaller than the figures.
  document.getElementById("stat-rating").classList.toggle("is-text", stats.average_rating === null);
  document.getElementById("stat-minutes").classList.toggle("is-text", stats.average_minutes === null);
}

// ---------- Radar chart, hand-drawn in SVG ----------
// One shape: how strong each flavor is, from 0 (center) to 100 (edge).
// Gridlines are thin and gray; values also appear in the bars below, so the chart
// is never the only way to read them.

const SVG_NS = "http://www.w3.org/2000/svg";
const RADIUS = 110;
const RINGS = [0.25, 0.5, 0.75, 1];

function svg(tag, attributes) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attributes)) el.setAttribute(name, value);
  return el;
}

// Point for flavor i of n at value v: the first flavor points straight up, then clockwise.
function point(i, n, v) {
  const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
  return [Math.cos(angle) * RADIUS * v, Math.sin(angle) * RADIUS * v];
}

const score = (value) => Math.round(value * 100);

function renderRadar(values) {
  const n = values.length;
  const chart = document.getElementById("radar");
  const summary = values.map((v) => `${v.label} ${score(v.value)}`).join(", ");
  const root = svg("svg", { viewBox: "-190 -148 380 296", role: "img", "aria-label": `Flavor profile out of 100: ${summary}` });

  for (const ring of RINGS) {
    const points = values.map((_, i) => point(i, n, ring).join(",")).join(" ");
    root.append(svg("polygon", { points, class: "radar-grid" }));
  }
  values.forEach((_, i) => {
    const [x, y] = point(i, n, 1);
    root.append(svg("line", { x1: 0, y1: 0, x2: x, y2: y, class: "radar-grid" }));
  });

  const shape = values.map((v, i) => point(i, n, v.value).join(",")).join(" ");
  root.append(svg("polygon", { points: shape, class: "radar-shape" }));

  const tooltip = document.createElement("div");
  tooltip.className = "chart-tooltip";
  tooltip.hidden = true;

  values.forEach((v, i) => {
    const [lx, ly] = point(i, n, 1.16);
    const anchor = Math.abs(lx) < 1 ? "middle" : lx > 0 ? "start" : "end";
    const label = svg("text", { x: lx, y: ly, "text-anchor": anchor, "dominant-baseline": "middle", class: "radar-label" });
    label.textContent = v.label;
    root.append(label);

    const [x, y] = point(i, n, v.value);
    root.append(svg("circle", { cx: x, cy: y, r: 4.5, class: "radar-dot" }));
    // A bigger, invisible circle is the hover and keyboard target.
    const target = svg("circle", {
      cx: x, cy: y, r: 14, class: "radar-hit", tabindex: 0,
      "aria-label": `${v.label}: ${score(v.value)} out of 100`,
    });
    const show = () => {
      tooltip.replaceChildren();
      const strong = document.createElement("strong");
      strong.textContent = score(v.value);
      tooltip.append(strong, ` ${v.label}`);
      const box = root.getBoundingClientRect();
      const scale = box.width / 380;
      tooltip.style.left = `${(x + 190) * scale}px`;
      tooltip.style.top = `${(y + 148) * scale}px`;
      tooltip.hidden = false;
    };
    const hide = () => { tooltip.hidden = true; };
    target.addEventListener("pointerenter", show);
    target.addEventListener("focus", show);
    target.addEventListener("pointerleave", hide);
    target.addEventListener("blur", hide);
    root.append(target);
  });

  chart.replaceChildren(root, tooltip);
}

function renderFlavor(profile) {
  const missingEl = document.getElementById("flavor-missing");
  const bodyEl = document.getElementById("flavor-body");
  missingEl.hidden = Boolean(profile.flavor);
  bodyEl.hidden = !profile.flavor;
  if (!profile.flavor) {
    missingEl.textContent = profile.flavor_missing;
    return;
  }
  renderRadar(profile.flavor.values);
  document.getElementById("flavor-bars").replaceChildren(...profile.flavor.values.map((v) => flavorBar(v)));
  setText("flavor-basis", profile.flavor.basis);
}

// What recommendations follow, or how many ratings until they do (services/taste.py).
function renderTaste(profile) {
  const noteEl = document.getElementById("taste-note");
  if (profile.taste && profile.taste.likes.length) {
    const likes = profile.taste.likes.slice(0, 3).map((f) => f.toLowerCase());
    const list = likes.length > 1 ? `${likes.slice(0, -1).join(", ")} and ${likes[likes.length - 1]}` : likes[0];
    noteEl.textContent = `Recommendations lean toward ${list} food, learned from the ${profile.taste.liked_meals} meals you rated 4 or 5.`;
  } else {
    const more = profile.taste_needed;
    noteEl.textContent = more > 0
      ? `Rate ${more} more ${more === 1 ? "meal" : "meals"} 4 or 5 and recommendations will start following your taste.`
      : "Your top-rated meals don't lean toward any flavor yet, so recommendations don't use taste.";
  }
}

function renderObservations(profile) {
  const list = document.getElementById("observations");
  list.replaceChildren(
    ...profile.observations.map((o) => {
      const li = document.createElement("li");
      const title = document.createElement("p");
      title.className = "observation-title";
      title.textContent = o.title;
      const detail = document.createElement("p");
      detail.className = "hint";
      detail.textContent = o.detail;
      li.append(title, detail);
      return li;
    })
  );
  list.hidden = profile.observations.length === 0;
  const emptyEl = document.getElementById("observations-empty");
  emptyEl.hidden = profile.observations.length > 0;
  if (profile.observations_needed > 0) {
    const more = profile.observations_needed;
    emptyEl.textContent = `Not enough to go on yet. Log ${more} more ${more === 1 ? "meal" : "meals"} (and rate them) and Slice'd will start noticing patterns, only ones it can back up with numbers.`;
  } else {
    emptyEl.textContent = "Nothing stands out yet. Slice'd only says something when the numbers clearly show it.";
  }
}

function renderIngredients(profile) {
  const { source, items } = profile.ingredients;
  setText("ingredients-heading", source === "meals" ? "You cook with" : "Your recipes use");
  const most = items.length ? items[0].count : 1;
  document.getElementById("top-ingredients").replaceChildren(
    ...items.map((item) => {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = capitalize(item.name);
      const track = document.createElement("span");
      track.className = "bar-track";
      const fill = document.createElement("span");
      fill.className = "bar-fill";
      fill.style.width = `${(item.count / most) * 100}%`;
      track.append(fill);
      const count = document.createElement("span");
      count.className = "hint";
      const noun = source === "meals" ? "meal" : "recipe";
      count.textContent = `${item.count} ${item.count === 1 ? noun : noun + "s"}`;
      li.append(name, track, count);
      return li;
    })
  );
  setText("ingredients-note", source === "meals"
    ? "Counted across the meals you've logged. Salt, pepper, and water are left out."
    : "Across all your saved recipes, until you've logged 3 meals. Salt, pepper, and water are left out.");
}

async function init() {
  try {
    const profile = await apiGet("/profile");
    renderStats(profile.stats);
    renderFlavor(profile);
    renderTaste(profile);
    renderObservations(profile);
    renderIngredients(profile);
    statusEl.hidden = true;
    document.getElementById("profile").hidden = false;
  } catch (error) {
    statusEl.textContent = `Couldn't load your profile. ${error.message}`;
    statusEl.className = "alert alert-error";
  }
}

init();
