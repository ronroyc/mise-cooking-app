// Grocery list page: add items, tick them off, share the list, and move bought items into the inventory.

const form = document.getElementById("add-form");
const errorsEl = document.getElementById("form-errors");
const listEl = document.getElementById("list");
const summaryEl = document.getElementById("summary");
const checkedActions = document.getElementById("checked-actions");
const stockResult = document.getElementById("stock-result");
const shareButton = document.getElementById("share-button");
const shareStatus = document.getElementById("share-status");

let items = [];

// ---------- Loading and showing the list ----------

async function loadItems() {
  try {
    items = await apiGet("/grocery");
    renderList();
  } catch (error) {
    summaryEl.textContent = `Couldn't load your grocery list. ${error.message}`;
    summaryEl.className = "alert alert-error";
  }
}

function renderList() {
  const toBuy = items.filter((i) => !i.checked);
  const inCart = items.filter((i) => i.checked);

  summaryEl.className = "result-count";
  if (items.length === 0) {
    summaryEl.textContent = "Your list is empty.";
  } else {
    summaryEl.textContent = `${toBuy.length} to buy · ${inCart.length} checked`;
  }

  shareButton.hidden = toBuy.length === 0;
  const sections = groupBySection(toBuy);
  if (inCart.length) sections.push({ title: "Checked", items: inCart });

  listEl.replaceChildren(
    ...sections.map((section) => {
      const wrapper = document.createElement("section");
      wrapper.className = "list-section";
      const heading = document.createElement("h2");
      heading.textContent = `${section.title} `;
      const count = document.createElement("span");
      count.className = "section-count";
      count.textContent = section.items.length;
      heading.append(count);
      const ul = document.createElement("ul");
      ul.className = "grocery-list";
      ul.replaceChildren(...section.items.map(renderItem));
      wrapper.append(heading, ul);
      return wrapper;
    })
  );
  checkedActions.hidden = inCart.length === 0;
  document.getElementById("stock-button").hidden = false;
  document.getElementById("clear-button").hidden = false;
}

// Unchecked items grouped by store section (the API already sorts them that way).
function groupBySection(toBuy) {
  const sections = [];
  for (const item of toBuy) {
    const title = item.category || "Other";
    if (!sections.length || sections[sections.length - 1].title !== title) sections.push({ title, items: [] });
    sections[sections.length - 1].items.push(item);
  }
  return sections;
}

function renderItem(item) {
  const li = document.createElement("li");
  li.className = item.checked ? "grocery-item is-checked" : "grocery-item";

  const label = document.createElement("label");
  const box = document.createElement("input");
  box.type = "checkbox";
  box.checked = item.checked;
  box.addEventListener("change", () => setChecked(item, box));
  const text = document.createElement("span");
  const name = document.createElement("span");
  name.className = "grocery-name";
  name.textContent = capitalize(item.name);
  const amount = document.createElement("span");
  amount.className = "meta";
  amount.textContent = item.quantity_text ? ` ${item.quantity_text}` : ""; // "Eggs 6", "Rice 2 cups"
  text.append(name, amount);
  label.append(box, text);

  const details = document.createElement("div");
  details.className = "grocery-details";
  if (item.for_recipes) {
    const forText = document.createElement("span");
    forText.className = "hint";
    forText.textContent = `For ${item.for_recipes}`;
    details.append(forText);
  }
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "link-button";
  remove.textContent = "Remove";
  remove.setAttribute("aria-label", `Remove ${item.name}`);
  remove.addEventListener("click", () => removeItem(item, remove));
  details.append(remove);

  li.append(label, details);
  return li;
}

// ---------- Sharing ----------

// Plain text for Notes, Messages, or Reminders:
//   Produce
//   - Onion (2)
function listAsText() {
  const sections = groupBySection(items.filter((i) => !i.checked));
  const blocks = sections.map((section) => {
    const lines = section.items.map((item) => {
      const amount = item.quantity_text ? ` (${item.quantity_text})` : "";
      return `- ${capitalize(item.name)}${amount}`;
    });
    return [section.title, ...lines].join("\n");
  });
  return ["Grocery list", ...blocks].join("\n\n");
}

// Opens the share sheet where the browser has one (Safari does), otherwise copies the list.
// The text is built from the list already on the page, so nothing waits on the server
// between the click and the share sheet; Safari only allows sharing straight after a click.
async function shareList() {
  const text = listAsText();
  shareStatus.textContent = "";
  if (navigator.share) {
    try {
      await navigator.share({ title: "Grocery list", text });
      return;
    } catch (error) {
      if (error.name === "AbortError") return; // closed the share sheet
      console.error(error); // try copying instead
    }
  }
  try {
    await navigator.clipboard.writeText(text);
    shareStatus.textContent = "Copied your list. Paste it into Notes, Reminders, or a message.";
  } catch (error) {
    shareStatus.textContent = "Couldn't share or copy the list from this browser.";
  }
}

// ---------- Changing the list ----------

async function setChecked(item, box) {
  box.disabled = true;
  try {
    await apiPatch(`/grocery/${item.id}`, { checked: box.checked });
    stockResult.hidden = true;
    await loadItems();
  } catch (error) {
    box.checked = !box.checked;
    box.disabled = false;
    window.alert(`Couldn't update ${item.name}. ${error.message}`);
  }
}

async function removeItem(item, button) {
  button.disabled = true;
  try {
    await apiDelete(`/grocery/${item.id}`);
    await loadItems();
  } catch (error) {
    button.disabled = false;
    window.alert(`Couldn't remove ${item.name}. ${error.message}`);
  }
}

function readForm() {
  const quantity = form.elements.quantity.value.trim();
  return {
    name: form.elements.name.value.trim(),
    quantity: quantity === "" ? null : Number(quantity),
    unit: form.elements.unit.value.trim() || null,
  };
}

function showErrors(problems) {
  errorsEl.textContent = problems.join("\n");
  errorsEl.hidden = false;
  errorsEl.focus();
}

async function addItem(event) {
  event.preventDefault();
  const data = readForm();
  const problems = [];
  if (!data.name) problems.push("Enter an item name.");
  if (data.quantity !== null && !(data.quantity > 0)) problems.push("Amount must be more than 0.");
  if (data.unit && data.quantity === null) problems.push("Add an amount to go with the unit, or clear the unit.");
  if (problems.length) {
    showErrors(problems);
    return;
  }

  const button = document.getElementById("add-button");
  button.disabled = true;
  try {
    await apiPost("/grocery", data);
    form.reset();
    errorsEl.hidden = true;
    form.elements.name.focus();
    await loadItems();
  } catch (error) {
    showErrors([error.message]);
  } finally {
    button.disabled = false;
  }
}

async function stockChecked() {
  const button = document.getElementById("stock-button");
  button.disabled = true;
  try {
    const result = await apiPost("/grocery/stock-checked");
    const list = document.createElement("ul");
    list.replaceChildren(
      ...result.messages.map((message) => {
        const li = document.createElement("li");
        li.textContent = message;
        return li;
      })
    );
    const heading = document.createElement("p");
    heading.textContent = "Your inventory is updated:";
    stockResult.replaceChildren(heading, list);
    stockResult.hidden = false;
    await loadItems();
    checkedActions.hidden = false; // keep the result visible even though nothing is checked now
    document.getElementById("stock-button").hidden = true;
    document.getElementById("clear-button").hidden = true;
  } catch (error) {
    window.alert(`Couldn't update your inventory. ${error.message}`);
  } finally {
    button.disabled = false;
  }
}

async function clearChecked() {
  if (!window.confirm("Remove every checked item without adding it to your inventory?")) return;
  try {
    await apiDelete("/grocery/checked");
    await loadItems();
  } catch (error) {
    window.alert(`Couldn't remove checked items. ${error.message}`);
  }
}

async function loadIngredientOptions() {
  try {
    const ingredients = await apiGet("/ingredients");
    document.getElementById("ingredient-options").replaceChildren(
      ...ingredients.map((ingredient) => new Option(ingredient.name))
    );
  } catch (error) {
    console.error(error); // the form still works without suggestions
  }
}

form.addEventListener("submit", addItem);
shareButton.addEventListener("click", shareList);
document.getElementById("stock-button").addEventListener("click", stockChecked);
document.getElementById("clear-button").addEventListener("click", clearChecked);
loadItems();
loadIngredientOptions();
