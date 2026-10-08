// Shared helpers used by every page: talking to the API, safe HTML, and formatting.

// ---------- API ----------
// The frontend and backend are served from the same server, so paths like
// "/api/recipes" go straight to FastAPI. No hardcoded hostnames needed.

async function apiRequest(method, path, body) {
  const options = { method, headers: {} };
  if (body instanceof Blob) {
    // A file (a recipe photo) is sent as it is, not as JSON.
    options.headers["Content-Type"] = body.type || "application/octet-stream";
    options.body = body;
  } else if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`/api${path}`, options);
  } catch (networkError) {
    throw new Error("Can't reach the server. Is it running?");
  }

  if (response.status === 204) return null; // "No Content", e.g. after a delete

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    // The backend always sends {"detail": "message"} or {"detail": ["message", ...]}.
    const detail = data && data.detail;
    const message = Array.isArray(detail) ? detail.join("\n") : detail;
    const error = new Error(message || `Request failed (status ${response.status})`);
    error.status = response.status; // lets pages react to specific cases, like 409 Conflict
    error.data = data; // extra fields, e.g. existing_id on a 409
    throw error;
  }
  return data;
}

const apiGet = (path) => apiRequest("GET", path);
const apiPost = (path, body) => apiRequest("POST", path, body);
const apiPatch = (path, body) => apiRequest("PATCH", path, body);
const apiPut = (path, body) => apiRequest("PUT", path, body);
const apiDelete = (path) => apiRequest("DELETE", path);

// ---------- Safe HTML ----------
// Recipe titles etc. are typed by users. If we put them into innerHTML as-is,
// a title like <img src=x onerror=alert(1)> would run as code (an XSS attack).
// escapeHtml turns < > & " ' into harmless text.

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

// ---------- Formatting ----------

function formatMinutes(minutes) {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} hr ${rest} min` : `${hours} hr`;
}

// Some imported recipes only estimate their times and servings (TheMealDB lists neither):
// "about 45 min", or "" when the recipe gives no times at all.
function recipeTime(recipe, minutes = recipe.total_time) {
  if (recipe.time_status === "unknown") return "";
  return recipe.time_status === "estimated" ? `about ${formatMinutes(minutes)}` : formatMinutes(minutes);
}

function servesText(recipe) {
  return `Serves ${recipe.servings_estimated ? "about " : ""}${recipe.servings}`;
}

// The API sends amounts ready to show (amount_text: "1 1/2 cups"), so fractions
// and plurals are worked out in one place: backend/app/services/units.py.

// "1 1/2 cups rice", "3 cloves garlic, minced", "2 eggs", "salt, to taste"
function formatIngredient(item) {
  let text = item.amount_text ? `${item.amount_text} ${item.display_name}` : item.display_name;
  if (item.quantity === null) text += ", to taste";
  if (item.preparation_note) text += `, ${item.preparation_note}`;
  return text;
}

// Inventory amounts: "4 cups", "6 eggs", or "Some" when the amount isn't tracked.
function formatAmount(item) {
  return capitalize(item.amount_text);
}

function capitalize(text) {
  return text ? text[0].toUpperCase() + text.slice(1) : "";
}

// "2026-10-03" -> "Oct 3". Built from parts because new Date("2026-10-03") means
// midnight UTC, which is still the previous day in US time zones.
function formatDate(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Uses days_until_expiration from the API: "Expired 2 days ago", "Expires today", "Expires Oct 3".
function formatExpiration(item) {
  const days = item.days_until_expiration;
  if (days === null) return "No expiration date";
  if (days < -1) return `Expired ${-days} days ago`;
  if (days === -1) return "Expired yesterday";
  if (days === 0) return "Expires today";
  if (days === 1) return "Expires tomorrow";
  if (days <= 14) return `Expires in ${days} days`;
  return `Expires ${formatDate(item.expiration_date)}`;
}

// Page-level load errors: a missing recipe gets its own wording, anything else says what failed.
function recipeLoadError(error) {
  if (error.status === 404) return "This recipe doesn't exist. It may have been deleted.";
  return `Couldn't load this recipe. ${error.message}`;
}

// Read ?id=12 from the current URL. Returns null if it's missing or not a whole number.
function getIdFromUrl() {
  const id = new URLSearchParams(window.location.search).get("id");
  return id && /^\d+$/.test(id) ? Number(id) : null;
}

// ---------- Menu ----------

// On phones the menu is one line you scroll sideways. If the current page's link
// is past the right edge (Profile, the last one), scroll the menu so it shows.
function showCurrentMenuItem() {
  const nav = document.querySelector(".site-nav");
  const current = nav && nav.querySelector('a[aria-current="page"]');
  if (!current || nav.scrollWidth <= nav.clientWidth) return;
  const overflow = current.getBoundingClientRect().right - nav.getBoundingClientRect().right;
  if (overflow > 0) nav.scrollLeft += overflow + 8;
}
showCurrentMenuItem();

// ---------- Recipe tickets: photo, colored corner, and stamp ----------

// The photo at the top of a recipe ticket, or null when there's no photo (the ticket is
// then just paper). A photo file that fails to load is removed instead of showing a
// broken-image icon.
function recipeCover(recipe, onPhotoLoad) {
  if (!recipe.photo_url) return null;
  const cover = document.createElement("div");
  cover.className = "recipe-cover";
  const img = document.createElement("img");
  img.src = recipe.photo_url;
  img.alt = "";
  img.loading = "lazy";
  if (onPhotoLoad) img.addEventListener("load", onPhotoLoad);
  img.addEventListener("error", () => {
    cover.remove();
    if (onPhotoLoad) onPhotoLoad();
  });
  cover.append(img);
  return cover;
}

// Turns a ticket's element into a colored-corner ticket: green, yellow (mustard), or red,
// by how much of the recipe is in the kitchen (matching.match_color on the server).
function colorTicket(element, match) {
  element.classList.add(`color-${match.color}`);
}

// The rubber stamp: READY, or NEEDS 3 (required ingredients not on hand), in the corner's
// color. It says in words what the corner says in color.
function recipeStamp(match) {
  const stamp = document.createElement("span");
  stamp.className = `stamp stamp-${match.color}`;
  stamp.textContent = match.ready ? "Ready" : `Needs ${match.required_count - match.have_count}`;
  return stamp;
}

// ---------- Pins ----------

// A "Pin" / "Pinned" toggle for a recipe (list cards and the recipe page).
// It updates recipe.pinned, then calls onChange so the page can react.
function pinButton(recipe, onChange) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "button button-secondary button-small pin-button";
  const label = document.createElement("span");
  const title = document.createElement("span");
  title.className = "visually-hidden";
  title.textContent = ` ${recipe.title}`; // screen readers hear "Pin Garlic Butter Salmon"
  button.append(label, title);
  const show = () => {
    label.textContent = recipe.pinned ? "Pinned" : "Pin";
    button.setAttribute("aria-pressed", String(recipe.pinned));
    button.classList.toggle("is-pinned", recipe.pinned);
  };
  show();
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const updated = recipe.pinned
        ? await apiDelete(`/recipes/${recipe.id}/pin`)
        : await apiPut(`/recipes/${recipe.id}/pin`);
      recipe.pinned = updated.pinned;
      show();
      if (onChange) onChange(recipe);
    } catch (error) {
      window.alert(`Couldn't update ${recipe.title}. ${error.message}`);
    } finally {
      button.disabled = false;
    }
  });
  return button;
}

// ---------- Flavor ----------

// One row of a flavor profile: "Garlicky [bar] 95", and, on recipe pages,
// "From garlic, green onion" underneath. The number is out of 100.
function flavorBar(value) {
  const li = document.createElement("li");
  li.className = "flavor-bar";
  const label = document.createElement("span");
  label.textContent = value.label;
  const track = document.createElement("span");
  track.className = "bar-track";
  const fill = document.createElement("span");
  fill.className = "bar-fill";
  fill.style.width = `${Math.round(value.value * 100)}%`;
  track.append(fill);
  const level = document.createElement("span");
  level.className = "flavor-level";
  level.textContent = Math.round(value.value * 100);
  li.append(label, track, level);
  if (value.because && value.because.length) {
    const from = document.createElement("span");
    from.className = "flavor-because hint";
    from.textContent = `From ${value.because.join(", ")}`;
    li.append(from);
  }
  return li;
}
