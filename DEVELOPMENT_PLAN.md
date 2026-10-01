# Slice'd Development Plan

How Slice'd was planned and built: the rules it follows, the milestones, the decisions behind
them, and what was learned along the way. For the story change by change, see
[docs/CHANGES.md](docs/CHANGES.md).

## Privacy rule

Slice'd keeps personal data on the computer it runs on. The code is public on GitHub, but the
database (`data/*.db`), recipe photos (`data/photos/`), and secrets (`.env`) are git-ignored
and never uploaded; screenshots and demos use a separate demo database. Slice'd isn't deployed:
the server only listens on `127.0.0.1`.

## Design rules (apply to every milestone)

Never include:
- gradients of any kind (including purple-to-blue, gradient text, grain over gradients)
- emojis, anywhere in the UI or copy
- em or en dashes in site copy
- italic text (including serif italic)
- Inter, Space Grotesk, or Instrument Serif fonts
- glassmorphism (blurred translucent cards) or colored-border cards
- rows of 3 icon boxes, badges above headlines, Lucide icons, or AI-generated images
- animations: fade-in on scroll, scroll effects, cursor-following effects, hover fades (no CSS `transition`)
- generic buzzword copy ("seamless", "revolutionize", "supercharge", "unlock"...). Write plainly.

Always:
- use only the `--space-*` scale in `style.css` for margins, padding, and gaps
- keep text contrast at WCAG AA (4.5:1) or better; if a dark mode is ever added, it must meet the same bar
- include the favicon and the footer with Terms and Privacy links on every page
- keep `privacy.html` accurate whenever Slice'd starts storing or sending something new.

`backend/tests/test_design_rules.py` enforces the rules that can be checked automatically.

## Status

All planned milestones except deployment are complete, and so is the build order for the
new product direction (below), followed by a full redesign and taste-based recommendations.
The code is public on GitHub, with tests running on every push.

Deliberately left for later:
- **Testing the AI features against the real Anthropic API.** Both AI features are built
  and covered by tests with a fake client; the real-API test waits until the end of the
  project to avoid paying for API calls during development.
- **Deployment (M8).** Slice'd runs locally. Hosting it would need accounts, per-user data,
  and a decision about privacy.

## Build order for the new direction

From [docs/PRODUCT_DIRECTION.md](docs/PRODUCT_DIRECTION.md). Three decisions came first:
the recipe corner color means "what I have" (not difficulty), with a key; photos are my own
uploads, with a plain colored cover otherwise; and this order.

1. **Grocery list to phone.** A Share button (share sheet, or copy where sharing isn't
   available) and `GET /api/grocery/text` for an Apple Reminders Shortcut
   ([docs/REMINDERS_SHORTCUT.md](docs/REMINDERS_SHORTCUT.md)).
2. **Feed v1.** A Pinterest-style grid (1px grid rows, each card spanning its own height),
   colored corners from `matching.match_color` with the same fact in words, pins and a
   Pinned filter, and photo uploads (type checked by the file's first bytes, 15 MB limit,
   stored in `data/photos`). `app/database/migrate.py` adds new nullable columns to an
   existing database at startup.
3. **Import from recipe websites.** `services/recipe_import.py` reads schema.org JSON-LD
   and parses ingredient lines with plain code; a "Save to Slice'd" Safari bookmarklet handles
   sites that block apps.
4. **Substitution assistant (M6).** About 60 hand-written swaps checked against the kitchen,
   plus optional AI ideas (`services/substitute_ai.py`); shared AI setup in `services/ai.py`.
5. **Profile v1.** Stats, a flavor profile drawn as a hand-made SVG radar chart, most-used
   ingredients, and "Slice'd knows..." observations that need enough data before appearing.
   Flavors come from an ingredient table (`services/flavors.py`).
6. **Leftovers.** Saved to the fridge in the inventory, good for 4 days from the cooking day.
7. **Meal prep.** Needs added up across recipes and checked against the inventory once,
   plus "prep together" steps (`services/meal_prep.py`).

After the build order:
- **Redesign** in a cookbook style: paper and ink colors, Newsreader headings served
  locally, rules instead of boxes, figures, numbered picks and steps.
- **Taste-based recommendations** (`services/taste.py`): the score became 70 (ingredients)
  + 20 (use soon) + 10 (taste), with taste learned from meals rated 4 or 5.
- **Ready to share:** a demo database builder, new screenshots, the README, a GitHub Actions
  workflow, and the docs: [WALKTHROUGH](docs/WALKTHROUGH.md), [GLOSSARY](docs/GLOSSARY.md),
  and [CHANGES](docs/CHANGES.md).

## Milestones

- [x] **M0: Project foundation.** Structure, FastAPI app, frontend shell, SQLite config, Git, README, `.env.example`, health endpoint
- [x] **M1: Recipe system.** Database models, recipe CRUD API, basic recipe UI, seed data
- [x] **M2: Inventory.** Inventory model, API, UI, expiration tracking
- [x] **M3: Core intelligence.** Ingredient normalization, unit conversion, recipe scaling, ingredient matching
- [x] **M4: Recommendations.** Deterministic scoring, recommendation UI, score explanations
- [x] **M5: Grocery + history.** Grocery list, cooking history, ratings
- [x] **M6: AI.** Substitution assistant, graceful failure handling (the Anthropic integration itself landed early, with ingredient recognition in M2). Real-API test still waits for the key at the end.
- [x] **M7: Polish.** UI, accessibility, error/loading states, responsive design, test cleanup, screenshots
- [ ] **M8: Deployment.** Production config, deploy, custom domain, final README, final verification (not planned yet; see Status)

## Completed milestone notes

### M0: Project foundation
- FastAPI app in `backend/app/main.py`, serving both `/api/*` and the static frontend
- `GET /api/health` runs `SELECT 1` against the database; returns 503 if the DB is unreachable
- SQLAlchemy engine + session setup in `backend/app/database/db.py`
- Frontend shell: dashboard (calls the health endpoint) plus placeholder pages for Recipes, Inventory, Grocery
- 4 pytest tests: health OK, health with DB failure, frontend served, unknown API route → 404
- Verified by running uvicorn and requesting every page and endpoint with curl
- Design pass: added spacing scale, removed italics, added hand-drawn SVG favicon, footer, Terms and Privacy pages, and automated design-rule tests (17 tests total). All color pairs checked against WCAG AA.

### M1: Recipe system
- Tables: `recipes`, `ingredients`, `recipe_ingredients` (join table with quantity, unit, optional, preparation note). Foreign keys enforced in SQLite via `PRAGMA foreign_keys=ON`.
- Layers: `schemas/recipe.py` (Pydantic validation) → `api/recipes.py` (HTTP routes) → `services/recipes.py` (database logic) → `models/recipe.py` (tables)
- Endpoints: `GET/POST /api/recipes`, `GET/PATCH/DELETE /api/recipes/{id}`, `GET /api/recipes/cuisines`
- List supports `?search=` (title, description, or ingredient name), `?cuisine=`, `?max_total_time=`
- Errors always come back as `{"detail": ...}` with readable messages; no stack traces reach the browser
- Frontend: recipe list with live search and filters, recipe detail page, create/edit form with dynamic ingredient rows, delete with confirmation
- 21 seed recipes across 9 cuisines in `data/seed_recipes.json` (written for this project), loaded with `python -m app.database.seed`
- 55 tests total. Verified on the live server with curl (create, read, update, delete, filters, error cases); JS syntax and helper functions checked with macOS's built-in JavaScriptCore. Not yet clicked through in a real browser at this point.

### M2: Inventory
- Table: `inventory_items` (ingredient_id, quantity, unit, location, expiration_date). `ingredient_id` points at the same `ingredients` rows recipes use and is unique, so each ingredient appears in the inventory once.
- Layers follow M1: `schemas/inventory.py` -> `api/inventory.py` -> `services/inventory.py` -> `models/inventory.py`
- Endpoints: `GET/POST /api/inventory`, `GET/PATCH/DELETE /api/inventory/{id}`, `GET /api/ingredients` (autocomplete)
- List is sorted soonest expiration first, undated items last. Filters: `?search=`, `?location=` (pantry, fridge, freezer), `?expires_within=N` (includes already expired items)
- Expiration status is computed, not stored: `expired`, `expiring_soon` (today through 3 days out), `fresh`, or none. `expiration_status()` takes `today` as an argument so it can be tested with fixed dates.
- Adding an ingredient that's already in the inventory, or renaming an item to one, returns **409 Conflict** with a readable message
- `quantity = null` means "some" (not measured). Clearing the quantity also clears the unit; a unit with no quantity is rejected on create and PATCH
- Frontend: inventory page with one form for add and edit, live search, location filter, summary line (items, expired, expiring soon), remove with confirmation. Dashboard has a "Use soon" card.
- 22 demo inventory items in `data/seed_inventory.json`, with expiration dates relative to the day you seed (one expired, three expiring soon). Every name matches a seed recipe ingredient, checked by a test.
- 98 tests total. Verified on the live server with curl (list, filters, 409 duplicate, 422 errors, PATCH, DELETE, pages served); JS syntax and formatting helpers checked with JavaScriptCore. Not yet clicked through in a real browser at this point.

### M2 follow-up (before M3)
- **Fixed:** the inventory page crashed in Safari with "Can't find variable: capitalize" (see lessons). Frontend files are now served with `Cache-Control: no-cache`.
- **Fixed:** the 22 demo inventory items blocked adding real ones (one row per ingredient, so "garlic" was taken). Removed them from the local database; real items were kept. The seed file still exists for a fresh setup.
- **Friendlier duplicates:** adding something already in the inventory now opens that item for editing, with a note, instead of just showing an error.
- **AI ingredient recognition** (`services/ingredient_ai.py`, `POST /api/ingredients/identify`): when a typed name isn't a known ingredient, Claude through the Anthropic API (`claude-opus-5`, low effort, structured output) returns a clean name, category, usual storage spot, typical shelf life, a one-line description, whether it's actually food, and whether it's the same as a known ingredient ("scallions" -> "green onion"). The form shows it as a suggestion with "Use these details" / "Keep what I typed". Nothing is saved without the user confirming.
- Known ingredients never go to the AI. No key, a network error, a rejected key, rate limits, or a refusal all return 200 with a plain message, and the form keeps working.
- Server-side refusal fallbacks are turned on (`fallbacks: "default"`), so a safety false positive on an unusual food gets retried on another model.
- The model can only "match" names Slice'd sent it; anything else is dropped. The ingredient name is wrapped in tags and the prompt says it's data, not instructions.
- `privacy.html` updated to say exactly what's sent and when.
- 120 tests. AI tests use a fake client, so they never call the real API. An offline request build confirmed the SDK produces the expected model, schema, effort, and fallback settings. **Not yet tried against the real API** (no key in `.env` yet) and not yet clicked through in a browser.

### M3: Core intelligence
- **Name matching** (`services/names.py`): `match_key()` turns a name into a comparison key: lowercase, no punctuation or hyphens, a few descriptor words dropped ("fresh", "large"), last word made singular, then a small synonym table ("scallion" -> "green onion", "garbanzo bean" -> "chickpea"). Two names are the same ingredient when their keys are equal. Stored names don't change.
- `find_ingredient()` looks up by exact name, then by key, so adding "Eggs" to a recipe or the inventory reuses the existing "egg" row. A recipe listing "egg" and "eggs" is rejected with a readable 422. A deliberate rename ("scallion" -> "green onion" on an inventory item) keeps the new spelling.
- The AI lookup (`/ingredients/identify`) uses the same lookup, so plurals and known synonyms never cost an AI call. The inventory form says "Slice'd already knows this as egg" and, after saving, "Saved as egg".
- A duplicate inventory item's 409 now includes `existing_id`, so the form opens the right item even when it's spelled differently.
- A test checks that no two seed ingredients share a key (otherwise one would swallow the other).
- **Units** (`services/units.py`): typed units are cleaned on input ("Tablespoons" -> "tbsp", "lbs" -> "lb"; unknown units kept as typed). `convert()` handles volume (tsp through gallon, ml, l) and weight (g, kg, oz, lb). Volume and weight aren't converted into each other; that would need a density per ingredient.
- **Display text from the API:** each recipe ingredient has `amount_text` ("1 1/2 cups") and `display_name` ("eggs" for 2 of them), and each inventory item has `amount_text` ("6 eggs", "some"). Formatting lives in one tested place; the JS just shows it. US units use kitchen fractions and metric units use decimals.
- **Scaling:** `GET /api/recipes/{id}?servings=N` (1 to 100). `base_servings` says what the recipe was written for. After scaling, amounts move to a cleaner unit when there is one (6 tsp -> 2 tbsp, 24 oz -> 1 1/2 lb; cups only in real measuring-cup sizes, so 6 tbsp stays 6 tbsp, not 3/8 cup). At the original size nothing is rewritten. "To taste" stays as is. Scaling never changes the saved recipe.
- **Matching:** `GET /api/recipes/{id}/match?servings=N` gives each ingredient a status: `have`, `short` (with "You have 2 eggs; this needs 3 eggs."), `expired`, or `missing`, plus `have_count`, `required_count`, and `ready`. Optional ingredients are listed but not counted. "Some" in the inventory, "to taste" in the recipe, and amounts in different kinds of units (2 lb flour vs 1 cup) all count as `have`; the last gets a "Check it's enough" note.
- **Recipe page:** a servings control (minus/plus, "Scaled from 4 servings. Back to original"), a summary ("You have 5 of 8 ingredients." / "You have everything you need."), and a text label plus note on each ingredient. If the inventory check fails, the recipe still shows without labels.
- 248 tests. Checked in WebKit on a throwaway server with a copy of the database: scaling up, down, and back; the status labels; "Eggs" opening the existing "egg" item; desktop and 390px phone widths. No page errors.

### M4: Recommendations
- `services/recommendations.py` scores every recipe that passes the filters: **up to 80 points for coverage** (share of required ingredients on hand; "have" and "staple" count fully, "short" half, "expired" and "missing" zero) plus **10 points per ingredient that expires within 3 days, up to 20**. Optional ingredients don't count. Ties go to fewer missing ingredients, then the quicker recipe, then the title.
- Every score comes with plain-language `reasons`: "You have 5 of 8 ingredients.", "Uses your chicken thigh, which expires tomorrow.", "Not enough egg.", "Past its date: milk.", "Missing dashi, mirin, and sugar." Long lists end with "and 2 more". The response also has the point breakdown (`coverage_points`, `use_soon_points`) and the lists of names.
- `GET /api/recommendations` takes the same filters as the recipe list plus `?limit=`, and reports `inventory_count` so the page can explain an empty kitchen.
- **Staples:** salt, black pepper, and water are assumed on hand (status `staple`, labeled "Staple" on the recipe page) unless the inventory lists them, in which case the inventory item decides (an expired salt is "expired").
- Matching now returns `expires_in_days` for each ingredient's inventory item.
- **Dashboard:** "Recommended for you" shows the top 5 with points, cuisine and time, and the reasons, plus a one-line explanation of how scoring works and a link to the full ranked list.
- **Recipes page:** a Sort menu (A to Z / Best match). Best match uses the recommendations endpoint with the same filters and adds "You have 5 of 8 · 60 points" to each card. `recipes.html?sort=match` opens in that order. The four filters now fit on one row on desktop.
- 262 tests. Checked in WebKit on database copies: an empty inventory (explains itself), a stocked one (Chicken Fried Rice first at 90 because it uses chicken expiring tomorrow), sort switching with search, and desktop and phone widths. No page errors. The endpoint answers in about 20 ms for 21 recipes.

### M5: Grocery list, cooking history, ratings
- New tables `grocery_items` and `cooking_logs`, created automatically at startup (`create_all` only adds missing tables, so existing data wasn't touched). Neither changes an existing table.
- **Grocery list** (`services/grocery.py`, `api/grocery.py`, `grocery.html`):
  - Items point at the shared `ingredients` rows. Adding the same ingredient again combines amounts when the units convert (1 cup + 4 tbsp butter = 1 1/4 cups), using match keys ("eggs" joins "egg"). Otherwise it gets its own row (2 lb and 1 cup flour). Checked items are never combined into.
  - `POST /grocery/from-recipe/{id}?servings=` adds the full amount for missing or expired ingredients and the difference for short ones. It skips optional ingredients (and says how many) and staples. `for_recipes` records which recipes an item is for.
  - The page groups unchecked items by store section (the ingredient category), with checked items last.
  - "Put checked items in inventory": new items go to the fridge (Produce, Dairy & Eggs, Meat & Seafood), freezer (Frozen), or pantry (anything else). Existing items get the amount added. An expired item is replaced and its date cleared. Amounts that don't convert are left as they are, with a message saying so. The page lists what happened, one sentence per item.
- **Cooking history** (`services/history.py`, `api/history.py`, `history.html`):
  - `POST /recipes/{id}/cooked` with servings (the current scale), date (not in the future), optional 1 to 5 rating, notes, and `update_inventory`. It subtracts measured amounts that convert, removes items that run out, and leaves "some", "to taste", optional ingredients, and non-converting units alone. It returns plain sentences like "Used 2 tbsp butter; 6 tbsp left." Amounts are shown in clean units without changing the stored unit.
  - Deleting a recipe keeps its history (`recipe_id` becomes NULL, and `recipe_title` is a copy).
  - Recipes now report `times_cooked`, `last_cooked`, and `average_rating`. These show on the recipe page and on recipe cards.
- **Recipe page:** an "Add missing to grocery list" button (only shown when something is needed; it uses the current servings), an "I cooked this" form, and "Your history with this recipe".
- **History page:** every entry newest first. Change the rating in place, add or edit a note, or delete an entry (this doesn't restore inventory). "History" was added to the nav on every page.
- Ratings are shown but don't affect recommendation scores yet (see below).
- 291 tests. Checked in WebKit on a copy of the database: added a recipe's missing items, added a manual item, checked items off and stocked them, cooked at half size with a rating and note, then re-rated and edited the note on the History page. Desktop and phone widths. No page errors.

### M7: Polish (done before M6, by choice)
- **Look:** warmer, more finished, still within the design rules (no gradients, emoji, italics, animations, or banned fonts). Headings use Iowan Old Style (built into macOS and iOS) with Georgia as the fallback. Cards have a larger radius and a faint shadow. New tokens: `--accent-soft`, `--ok-bg`, `--warn-bg`, `--radius-lg`, `--shadow`, `--control-height`.
- **Form controls:** every input, select, and button is the same height (`--control-height`). Selects and search boxes are drawn by the page instead of Safari (custom chevron), number fields have no spinner arrows, checkboxes use the accent color, and placeholders meet 4.5:1 contrast.
- **Header:** the current page is a soft tinted pill instead of a solid orange block. Nav labels are shorter ("Home", "Groceries") so all five fit on one line on a phone; the menu scrolls sideways if it ever has to.
- **Home page:** the developer "System status" card is gone; a red banner appears only if the server can't be reached. Added a strip of four numbers (ready to cook, in your kitchen, use soon, to buy), each a link. Two columns on wide screens: recommendations on the left, with a coverage bar ("Have 5 of 8 ingredients" or "Ready to cook") and a big score; "Use soon" and a grocery preview on the right.
- **Inventory:** grouped into Fridge, Freezer, and Pantry sections with counts. Expiry is a tinted label (text plus color). Edit is a small button and Remove a text link, so rows are lighter.
- **Recipe page:** facts (cuisine, servings, times) sit in one strip like the home page numbers. The grocery button row hides completely when nothing is needed.
- **Recipe form:** ingredient rows read like a table on wide screens (labels on the first row only; later labels are hidden visually but still read by screen readers). Remove is a text link. The instructions box is taller.
- **History:** each entry is compact, with the rating beside the title and "Edit note · Delete entry" on one line.
- **Accessibility:** a "Skip to content" link on every page, `id="main"` on every `<main>`, and new contrast tests: every text/background token pair must reach 4.5:1, white button text 4.5:1, and input borders 3:1 (`test_design_rules.py`).
- **Error states:** checked every page with all API calls failing: each shows a plain message and nothing is stuck on "Loading...". Recipe pages now say "This recipe doesn't exist" for a 404.
- Reason text changed from "which expires" to "expiring" so plurals read right ("Uses your green onions, expiring in 2 days.").
- **Screenshots** for the README are in `docs/screenshots/`.
- 308 tests. Re-ran the main actions in WebKit after the redesign (edit a recipe, scale, edit and remove inventory, check a grocery item, edit a history note). No page errors.

## Architectural decisions

| Decision | Why |
|----------|-----|
| FastAPI serves the frontend too (`StaticFiles` mounted at `/`) | One server to run and deploy; browser and API share an origin, so no CORS config |
| All API routes under `/api` | Keeps API paths from colliding with page URLs |
| `get_db` dependency gives each request its own DB session | Sessions are always closed, and tests can swap in a test database via `dependency_overrides` |
| Tests use a fresh temp SQLite file per test | Tests are independent and never touch real data |
| Dependencies pinned in `requirements.txt` | Same versions install on every machine and on the deploy host |
| Code targets Python 3.9 | That's the Python on the development Mac (see lessons) |
| `models/`, `schemas/`, `services/` created only when needed | Avoid empty folders/files with nothing in them |
| `recipe_ingredients` join table instead of storing ingredients as text on the recipe | Lets matching, grocery lists, and inventory all refer to the same `ingredients` rows |
| Ingredient names stored lowercase with extra spaces removed | "Soy Sauce" and "soy  sauce" become the same ingredient |
| `quantity = null` means "to taste" | Honest about ingredients that can't be measured or scaled |
| PATCH with `ingredients` replaces the whole list | Simpler and less error-prone than diffing individual rows |
| Time filter uses total time (prep + cook), labeled "Ready in" | Answers the real question: how long until I can eat? |
| Services layer separate from API routes | Seed script and future features reuse the same logic; can be tested without HTTP |
| Frontend inserts user text with `textContent` or `escapeHtml()` | Prevents XSS (user text being run as HTML/JS) |
| Units are free text for now (with suggestions) | Unit validation/normalization belongs to M3 |
| One inventory row per ingredient (unique `ingredient_id`) | "How much rice do I have?" has one answer; matching in M3 stays a simple lookup |
| Expiration status computed on read, not stored | A stored status would go stale overnight |
| "Expiring soon" = within 3 days | Short enough to mean "cook this now", long enough to plan a meal |
| Location is a fixed list (pantry, fridge, freezer) | Covers a home kitchen; free text would split "Fridge" and "refrigerator" |
| Inventory form offers known ingredient names | Picking "green onion" instead of typing "scallion" keeps inventory and recipes matched |
| AI identifies only *new* ingredient names, on leaving the name field | No cost or delay for known items; one call per new item instead of one per keystroke |
| AI suggests, the user confirms | A wrong guess never silently changes data |
| `/ingredients/identify` always returns 200 | AI trouble isn't a failure of the request; the form should carry on |
| anthropic SDK 0.125.0, not 1.x | 1.x needs Python 3.10+; the Mac has 3.9 |
| Ingredient names matched by a computed key, not stored | Keeps stored names as the user wrote them; the key rules can improve without a data migration |
| Keys computed in Python over the whole ingredients table | One row per distinct ingredient keeps the table small; add a stored key column if it ever gets slow |
| No volume-to-weight conversion | Needs a density per ingredient; a wrong guess is worse than "check it's enough" |
| Amount text built by the API, not the JS | One implementation of fractions and plurals, covered by pytest |
| Scaled amounts only move to "clean" units, and not at the original size | The recipe reads as its author wrote it; scaled amounts read like a cook would write them |
| Expired inventory doesn't count as "have" | Recommending a recipe that relies on spoiled milk would be wrong |
| Recommendation score is a fixed formula, not AI | Same inventory, same ranking; every point is explainable; costs nothing |
| Coverage dominates the score (70 of 100; was 80 before taste was added) | "Can I cook this now?" matters more than using up one item or matching taste |
| Short ingredients count half | Having some chicken beats having none, but isn't enough |
| Staples assumed unless tracked | Otherwise nearly every recipe is "missing salt"; tracking one overrides the assumption |
| Best match is a sort on the recipes page, not a separate page | Same filters, same cards; one less page to maintain |
| Grocery rows combine only when units convert | Adding "2 lb" to "1 cup" of flour would need a density; two rows is honest |
| Cooking subtracts only what can be measured | Guessing how much of "some" soy sauce was used would make the inventory wrong |
| History keeps a copy of the recipe title | Deleting a recipe shouldn't erase what you cooked |
| Bought items get a location from their category | Most chicken belongs in the fridge; the Inventory page can move it |
| No UI framework or component library, even for the redesign | Plain HTML/CSS keeps the app small and dependency-free; the component libraries offered target React/Tailwind |
| Fonts served by Slice'd itself (Newsreader for headings, the system font for text) | Loading fonts from Google would contact a third party, which the privacy page says Slice'd doesn't do |
| Status shown as text plus color everywhere | Color alone fails color-blind users; the words carry the meaning |
| Frontend files served with `Cache-Control: no-cache` | Browser always checks for a newer file (cheap 304 if unchanged), so pages never mix old and new JS |

## Known bugs and limits

- Recipes imported from meal-kit sites can read "2 unit sweet potatoes": the importer
  doesn't yet treat "unit" as a count.
- Flavor profiles ignore amounts (a pinch of chili counts like a spoonful).
- Volume and weight don't convert into each other (that needs a density per ingredient).

## Ideas for later

- Recommendations could skip recipes cooked in the last few days, explained in `reasons`.
- The AI's `shelf_life_days` could set a default expiration date when adding items, which
  would feed the use-soon points.
- An editable staples list (salt, black pepper, and water are fixed today).
- A full migration tool (Alembic) once a change needs more than adding a nullable column.
- A shared header include, so the menu isn't repeated in every HTML page.
- Categories for ingredients added by hand (only seed data and the AI set them now).
- Cleaning up ingredients nothing uses anymore.
- Several inventory rows per ingredient (two cartons of milk with different dates).

## Someday: making it a product

Not planned, just ideas from Sep 25, 2026 so they aren't lost. Only relevant if Slice'd is ever opened to other people, which would also mean rethinking the privacy rule above.

**Ways to make money**
- **Freemium subscription (best fit):** core app free; AI features (ingredient recognition, substitutions, smart recommendations) in a paid tier around $3 to $5/month. Matches cost to usage, since AI is the main running cost.
- **One-time purchase:** simpler, like Paprika, but AI costs keep going after the sale.
- **Grocery partnerships:** "send this list to Instacart / Walmart" from the M5 grocery list, earning referral fees. Free for users.
- **Avoid ads and selling data:** it contradicts `privacy.html` ("no tracking, no sharing"), which is a selling point worth keeping.

**What would have to change**
- User accounts and logins (Slice'd is single-person today)
- Hosting (roughly $5 to $25/month to start) and a multi-user database (e.g. Postgres instead of one SQLite file)
- Payments (e.g. Stripe)
- Proper Terms and Privacy pages; per-user AI usage limits so costs can't run away

**Competition:** Paprika, Mealime, SuperCook, Samsung Food. Slice'd's angle: ingredient-aware recommendations plus AI that understands niche and cultural ingredients.

## Lessons learned

- **Screenshots find what tests can't (M7).** Mismatched select heights in Safari, labels repeated on every ingredient row, a menu that overflowed on a phone, and a reason that read "green onions, which expires" were all invisible to pytest and curl. Screenshot every page at 1280px and 390px after visual changes.

- The Mac's built-in Python is 3.9.6. Python 3.9 doesn't support the `str | None` type-hint syntax, so this project uses `Optional[str]` from `typing` instead. Homebrew isn't installed, so upgrading Python wasn't a quick option.
- **SQLAlchemy warning while building recipes.** The first version created each `RecipeIngredient` and then looked up the next ingredient; that lookup flushed the session while a half-attached object existed, and SQLAlchemy warned about it. Fix: look up all ingredients first, then build the link rows. pytest now treats SQLAlchemy warnings as failures (`pytest.ini`) so this kind of issue can't slip by.
- **Case-sensitive sorting.** SQLite sorted "Chicken Teriyaki" before "Chicken and Vegetable Stir-Fry" because uppercase letters sort before lowercase. Found by checking the live search results. Fixed by sorting on `lower(title)`, with a regression test.
- **Browser mixed old and new JavaScript (M2).** After M2, Safari showed "Can't find variable: capitalize". It had kept its cached copy of the old `common.js` (no `capitalize`) and loaded the new `inventory.js` that calls it. My tests and curl checks always fetched fresh files, so they couldn't catch it. Fixed by sending `Cache-Control: no-cache` on every frontend file, with a test.
- **Demo data got in the way of real data (M2).** Seeding 22 demo inventory items into the real database meant real garlic, eggs, and so on couldn't be added, because each ingredient can only appear once. Lesson: demo data and one-per-thing rules clash; keep demo data out of a database someone actually uses, or make it easy to clear.
- **`hidden` attribute overridden by CSS.** Any class that sets `display` (like `display: grid`) beats the browser's built-in `[hidden] { display: none }`, so hidden elements would still show. Caught while reviewing the form code. Fixed with a global `[hidden] { display: none !important; }` rule.
