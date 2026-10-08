# Slice'd: a walkthrough of everything

This explains every part of Slice'd: the libraries it uses and why, what each file does, how
the main algorithms work (with worked examples), and the decisions behind them.

How to read it: section 1 gives the big picture; section 2 covers the libraries; sections
3 to 5 go file by file; section 6 works through the algorithms; section 7 covers the
tests; section 8 lists the decisions and trade-offs; section 9 has questions to check your
understanding.

---

## 1. The big picture

Slice'd is one Python server that does two jobs:

```
Browser ──HTTP──▶ FastAPI server (backend/app/main.py)
                   ├── /api/...  JSON API → api/ (routes) → services/ (logic) → models/ (tables) → SQLite file
                   └── /...      the HTML, CSS, JS, and font files in frontend/
```

**What happens when you open the Recipes page**, start to finish:

1. Safari asks the server for `/recipes.html`. FastAPI's static-file handler sends the file
   from `frontend/`.
2. The HTML loads `css/style.css`, `js/common.js`, and `js/recipes.js`.
3. `recipes.js` calls `apiGet("/recommendations")`, which is `fetch("/api/recommendations")`.
4. FastAPI finds the matching route in `api/recommendations.py`. Before running it, FastAPI
   calls `get_db()`, which opens a database session, and checks the query parameters
   (`?search=`, `?cuisine=`...) against their declared types.
5. The route calls `services/recommendations.recommend()`. That loads the inventory once,
   learns your taste once, then for every recipe: matches ingredients against the inventory
   (`services/matching.py`), works out its flavor (`services/flavors.py`), and scores it.
6. The result is a Pydantic object (`schemas/recommendation.py`). FastAPI turns it into JSON.
7. Back in the browser, `recipes.js` builds a card for each recipe and lays out the grid.

**The layers**, and why they're separate:

| Folder | Job | Knows about HTTP? | Knows about the database? |
|---|---|---|---|
| `api/` | Read the request, call a service, return a response or an error code | Yes | Only by passing the session along |
| `services/` | The actual logic: matching, scoring, importing, planning | No | Yes |
| `models/` | What the tables look like | No | Yes (they *are* the tables) |
| `schemas/` | What data may come in, and what goes out | Shapes of requests and responses | No |

Keeping the logic in `services/` means it can be tested without HTTP and reused anywhere
(the seed and demo scripts call the same services the API does).

---

## 2. Every library, and why it's here

### Python packages (`requirements.txt`)

Versions are pinned (exact numbers) so the app installs the same way on any machine.

**FastAPI** (web framework)
- Turns Python functions into HTTP routes: `@router.get("/recipes")` above a function means
  "run this for GET /api/recipes".
- Reads the function's type hints and does the boring work: `max_total_time: Optional[int]`
  makes FastAPI read `?max_total_time=30` from the URL, check it's a number, and send a 422
  error if it isn't. A parameter typed as a Pydantic model (like `data: RecipeCreate`) is
  read from the JSON body and validated.
- **Dependencies:** `db: Session = Depends(get_db)` tells FastAPI "before running this route,
  call `get_db()` and pass in what it gives." That's how every route gets a database session
  that's always closed afterwards.
- Generates interactive API docs at `/docs` for free.
- Built on **Starlette**, which Slice'd uses directly for serving static files (`StaticFiles`),
  file responses (`FileResponse` for photos), and middleware (the cache header).
- Why FastAPI over Flask or Django: validation and docs from type hints with little code;
  Django would bring a whole framework (templates, admin, its own ORM) Slice'd doesn't need.

**Uvicorn** (the server program)
- FastAPI describes *what* to do with a request; Uvicorn is the program that listens on a
  port (8000), speaks HTTP, and hands requests to FastAPI. `uvicorn app.main:app --reload`
  means "run the `app` object in `app/main.py`, restart when a file changes."
- `[standard]` adds faster optional parts (for example a faster event loop).

**SQLAlchemy** (database toolkit, ORM)
- Lets Python classes stand for tables. `class Recipe(Base)` with
  `title: Mapped[str] = mapped_column(String(200))` *is* the `recipes` table.
- Relationships: `recipe.ingredients` gives the recipe's ingredient rows without writing
  SQL joins. `cascade="all, delete-orphan"` means deleting a recipe deletes its ingredient
  rows too.
- Queries are Python: `select(Recipe).where(Recipe.pinned_at.is_not(None))`. SQLAlchemy
  writes the SQL and keeps values safely separated from the query (no SQL injection).
- A **session** is one conversation with the database: add or change objects, then
  `db.commit()` saves them all at once, or nothing is saved if something fails.
- Why an ORM: less hand-written SQL, and the same code would work on PostgreSQL later.

**SQLite** (the database itself, built into Python)
- The whole database is one file, `data/sliced.db`. No database server to install or run.
- Perfect for one person on one computer. A multi-user website would move to PostgreSQL;
  thanks to SQLAlchemy that's mostly a change of `DATABASE_URL`.

**Pydantic** (data validation)
- Classes that describe what data must look like: `servings: int = Field(gt=0, le=100)`.
  Anything that doesn't fit is rejected with a readable error *before* it reaches the
  database.
- Validators clean data on the way in: ingredient names are lowercased and trimmed, units
  are normalized ("Tablespoons" becomes "tbsp").
- Output schemas control exactly what the API returns, including computed fields like
  `amount_text` ("1 1/2 cups").
- Also used to describe the structured answer the AI must return (section 4.7).

**python-dotenv**
- Reads the `.env` file into environment variables at startup, so secrets like
  `ANTHROPIC_API_KEY` stay out of the code and out of git (`.env` is git-ignored).

**anthropic** (the Claude API's official Python library)
- Used only by the two AI features. Version 0.x because 1.x needs Python 3.10 and the Mac
  has 3.9.
- Slice'd uses `client.beta.messages.parse(...)`, which sends a question and returns the answer
  already checked against a Pydantic class. It also turns on the server-side refusal
  fallback (if a safety check declines, the API retries on a fallback model).

**pytest** (testing)
- Finds every `test_*.py` file and runs every `test_*` function; a failed `assert` fails
  the test.
- **Fixtures** are reusable setup: a test that asks for `client` gets a fake browser wired
  to a fresh, empty database (section 7).
- `@pytest.mark.parametrize` runs one test with many inputs (the ingredient-parser test runs
  about 30 real ingredient lines through the same check).

**httpx**
- An HTTP client. FastAPI's `TestClient` uses it to send requests to the app inside the
  test, with no real server running.

### Tools used during development (not installed with Slice'd)

- **Playwright with WebKit:** WebKit is Safari's engine. Playwright drives it from a script:
  opens pages, clicks, types, takes screenshots. Used to check every page the way Safari
  shows it, at desktop and phone widths, on a *copy* of the database. It lives in a
  throwaway environment, not in `requirements.txt`, because the app doesn't need it to run.
- **git:** version control. Every milestone is a commit with a message explaining it.

### Python's standard library (built in, nothing to install)

| Module | Used for |
|---|---|
| `urllib.request` | Downloading recipe pages and photos for import |
| `html.parser` | Finding `<script type="application/ld+json">` blocks in a recipe page |
| `json` | Reading those blocks, and the seed data files |
| `re` (regular expressions) | Parsing ingredient lines ("1 1/2 cups...") and ISO durations ("PT1H30M") |
| `fractions` | Showing amounts as kitchen fractions (0.333 becomes "1/3") |
| `secrets` | Random photo file names |
| `dataclasses` | Small data holders like `Need` in meal prep and `Taste` |
| `math` | Square roots for cosine similarity |
| `datetime` | Expiration dates, "cooked on" dates, leftovers' 4 days |
| `sqlite3` | Turning on foreign keys for every connection |
| `pathlib` | File paths (data folder, photos folder) |

### In the browser (no JavaScript libraries at all)

Slice'd uses no frameworks and no build step: the browser runs the files exactly as written.
Browser features it relies on:

| Feature | Used for |
|---|---|
| `fetch` | Every API call (`apiRequest` in `common.js`) |
| DOM methods (`createElement`, `textContent`, `replaceChildren`) | Building the page. `textContent` never interprets HTML, so a recipe titled `<script>` can't run code |
| SVG | The radar chart, drawn by hand in `profile.js` |
| `ResizeObserver` | Re-measuring recipe cards for the Pinterest-style grid |
| Web Share API (`navigator.share`) | The grocery list's Share button |
| Clipboard API | Copying the grocery list where sharing isn't available |
| `history.replaceState` | Removing imported data from the address bar after the Safari button |
| A `javascript:` bookmark | The "Save to Slice'd" Safari button |

### Fonts

- **Barlow Condensed** for headings (like kitchen signage), **IBM Plex Mono** for ticket
  details and numbers, and **IBM Plex Sans** for reading. All SIL Open Font License (see
  `frontend/fonts/OFL-*.txt`), stored inside Slice'd so no page contacts a font service.

---

## 3. The backend, file by file

### 3.1 Starting up: `main.py` and `config.py`

**`config.py`** reads settings from environment variables (and `.env`): where the data
folder is, `DATABASE_URL`, `PHOTOS_DIR`, and `ANTHROPIC_API_KEY` (or None).

**`main.py`** builds the app:
- **Startup (`lifespan`):** `create_all` makes any missing tables, then
  `add_missing_columns` adds columns that are newer than your database file (section 3.2).
- **Error handlers:** every error reaches the browser as `{"detail": "readable message"}`,
  never a stack trace. Validation errors are rewritten from Pydantic's format into sentences
  like "ingredients 2 name: field required". Database errors are logged and answered with a
  generic message.
- **Cache middleware:** adds `Cache-Control: no-cache` to every page, CSS, and JS response, so
  the browser checks for a new version each time. HTML pages also load files as
  `style.css?v=22`: bumping the number forces even an old cached copy to be replaced. A test
  checks every page uses the same number.
- **Routes:** every router is mounted under `/api`, then the `frontend/` folder is mounted
  at `/` last, so API paths always win.

### 3.2 The database: `database/`

**`db.py`** creates the SQLAlchemy engine (the connection to the SQLite file), the session
factory, the `Base` class every table inherits from, and `get_db()`, the dependency that
gives each request its own session and always closes it. It also turns on
`PRAGMA foreign_keys=ON` for every connection, because SQLite ignores foreign keys otherwise.

**`migrate.py`** handles a real problem: `create_all` creates missing *tables* but never
changes existing ones. When pins and photos were added, your existing `recipes` table had
no `pinned_at` column, and every query would have failed. `add_missing_columns` compares
each table in the code with the table in the file and runs `ALTER TABLE ... ADD COLUMN` for
missing columns. It only adds columns that can be empty (existing rows get NULL) and refuses
anything riskier. A real project would use a migration tool (Alembic); this covers the one
case Slice'd needs.

**`seed.py`** loads the 21 sample recipes and sample inventory from `data/*.json`, through
the same services and schemas as user input, so seed data is validated too. It only fills
empty tables, so running it twice is safe.

**`demo.py`** builds a *separate* demo database: the seed data plus 4 pins, 12 rated meals
over two weeks, and a few grocery items, so every feature has something to show. It
refuses to write over an existing file, so it can't touch your data.

### 3.3 The tables: `models/`

```
recipes ──< recipe_ingredients >── ingredients ──< inventory_items
   │                                    └────────< grocery_items
   └──< cooking_logs
```

**`recipe.py`**
- `Recipe`: title, description, servings, prep and cook minutes, cuisine, instructions (one
  step per line), `pinned_at` (a date, or empty when not pinned), `photo_filename`,
  `source_url`, timestamps. Computed properties: `total_time`, `times_cooked`,
  `average_rating`, `pinned`, `photo_url`.
- `Ingredient`: one row per distinct ingredient name ("garlic"), shared by everything.
- `RecipeIngredient`: the **join table**. Recipes and ingredients are many-to-many (a recipe
  has many ingredients; garlic is in many recipes), so each row pairs one recipe with one
  ingredient and holds what belongs to the pairing: quantity, unit, optional, preparation
  note. A unique constraint stops a recipe listing the same ingredient twice.

**`inventory.py`**: `InventoryItem` points at an `Ingredient` (unique, so one row per
ingredient), with quantity (empty means "some"), unit, location (pantry, fridge, freezer),
and expiration date. `expiration_status()` returns expired, expiring soon (3 days or less),
fresh, or none.

**`grocery.py`**: `GroceryItem` (ingredient, quantity, unit, checked, and which recipes it's
for). Several rows for one ingredient are allowed, because 2 lb of flour and 1 cup of flour
can't be added together.

**`history.py`**: `CookingLog` (which recipe, date, servings, rating 1 to 5, notes). The
recipe's title is copied in, and the recipe link becomes empty (`ondelete="SET NULL"`) if
the recipe is deleted, so your history survives.

### 3.4 Validation: `schemas/`

Each area has "in" schemas (what the browser may send) and "out" schemas (what the API
returns):
- `recipe.py`: `RecipeCreate` and `RecipeUpdate` check every field; ingredient names are
  normalized, units cleaned, duplicate ingredients rejected ("eggs" and "egg" count as the
  same), and `source_url` must start with http(s) so a link can't run code. Out:
  `RecipeSummary`, `RecipeOut`, `RecipeMatchOut` (with the corner `color` and `swap_count`),
  plus the import draft schemas.
- `inventory.py`, `grocery.py`, `history.py`: the same idea for those areas. `PATCH` schemas
  make every field optional and only change the fields actually sent.
- `recommendation.py`: the score and each of its parts, the reasons, and what's missing.

### 3.5 The routes: `api/`

Each file is thin: read the request, call a service, turn service errors into HTTP codes
(404 not found, 409 conflict, 413 too big, 422 invalid). The README lists every route.
Worth knowing:
- `recipes.py`: CRUD, `/match`, pin and unpin, and import. Import routes are plain `def`, not
  `async def`: FastAPI then runs them on a worker thread, so waiting on a slow website
  doesn't block other requests.
- `photos.py`: the upload reads the *raw* request body (the image file itself) instead of a
  multipart form, which would have needed another package.
- `inventory.py`: `POST /ingredients/identify` always answers 200, even without a key or when
  the AI fails, because the form still works without a suggestion.
- `substitutes.py`, `profile.py`, `meal_prep.py`, `grocery.py`, `history.py`,
  `recommendations.py`, `health.py` (`SELECT 1` against the database).

### 3.6 The logic: `services/`

This is where the interesting code is. Section 6 works through the algorithms in detail.

| File | What it does |
|---|---|
| `names.py` | `match_key()`: turns any ingredient name into a comparison key ("Large Eggs" and "egg" both become "egg"; "scallions" becomes "green onion") |
| `units.py` | Normalizes units, converts within volume and within weight, tidies amounts (6 tsp becomes 2 tbsp), and formats kitchen fractions |
| `recipes.py` | Recipe CRUD, search, pins, and **scaling** a recipe to a new number of servings |
| `matching.py` | Compares a recipe with the inventory: have, short, expired, staple, or missing, plus the corner color and the swaps you own |
| `recommendations.py` | Scores and ranks every recipe (70 ingredients + 20 use soon + 10 taste) with reasons |
| `taste.py` | Learns what you like from meals rated 4 or 5, and how well a recipe fits it |
| `flavors.py` | An ingredient-to-flavor table (8 flavors, about 250 ingredients) and a recipe's flavor |
| `profile.py` | Everything on the Profile page, each part only with enough data |
| `inventory.py` | Inventory CRUD, one row per ingredient (a duplicate gives 409 with the existing id) |
| `grocery.py` | Adding and combining grocery items, "add missing from recipe", moving bought items into the inventory, plain-text list for the Shortcut |
| `history.py` | Logging a cooked meal, subtracting what it used from the inventory, saving leftovers |
| `meal_prep.py` | Planning several recipes: combined needs, one inventory check, prep-together steps |
| `substitutions.py` | About 60 hand-written swaps, checked against the kitchen |
| `ai.py` | The shared Claude client, model, and error messages |
| `ingredient_ai.py` | AI ingredient recognition |
| `substitute_ai.py` | AI substitution ideas |
| `recipe_import.py` | Reading recipes from websites, including the ingredient-line parser |
| `photos.py` | Saving, replacing, deleting, and checking photo files |

---

## 4. Feature by feature (how the pieces connect)

### 4.1 Inventory
Page `inventory.html` + `inventory.js` → `/api/inventory` → `services/inventory.py`. Adding
"eggs" when "egg" exists gives a 409 with the existing item's id, and the page offers to
edit that item instead, because the inventory keeps one row per ingredient so "how much do
I have?" has one answer. Typing an unfamiliar name can ask the AI for a suggestion (4.7).

### 4.2 Recipes, the grid, and corners
`recipes.js` loads `/api/recommendations` (every recipe with its match and score), sorts A
to Z in the browser unless "Best match" is chosen, and builds each recipe as an order ticket
with helpers from `common.js`: `recipeCover()` (the photo, or nothing, so a recipe without a
photo is a plain ticket), `colorTicket()` (the colored corner), and `recipeStamp()` (READY,
or NEEDS 3). The color comes from `match_color()`: green (everything), yellow (at least
half), red (less than half). The stamp says the same in words, so color is never the only
signal.

### 4.3 A recipe page
`recipe-detail.js` loads the recipe, then `/match` for the ingredient labels and swaps,
`/flavor` for the Flavor section, the history for "Your history with this recipe", and
`/ai/status` to decide whether to show "Ask AI for ideas". Changing servings reloads the
scaled recipe and its match. "I cooked this" posts to `/cooked` with optional leftovers.

### 4.4 Grocery list
Items are grouped by store section (the ingredient's category). "Put checked items in
inventory" moves bought items into the right place (produce and dairy to the fridge, frozen
to the freezer, everything else to the pantry), adding to amounts you already have when the
units convert. **Share list** builds the text in the browser from what's already on the page,
because Safari only allows opening the share sheet straight after a click. `GET
/api/grocery/text` feeds the Apple Reminders Shortcut (`docs/REMINDERS_SHORTCUT.md`).

### 4.5 History, ratings, leftovers
Logging a meal can subtract what the recipe used (only measured amounts in units that
convert; items that run out are removed). Leftovers become an inventory item called
"leftover <recipe>" in the fridge, good for 4 days from the day you cooked. More leftovers of
the same recipe add up and keep the earlier date, since the older portion goes bad first.

### 4.6 Profile and taste
`/api/profile` returns stats, the flavor profile (meals cooked, weighted by rating, plus
pins), top ingredients, the taste line, and "Slice'd knows..." observations. Each part has a
minimum amount of data before it says anything: 3 sources for the flavor chart, 5 meals for
observations, 6 rated meals for rating-based ones, 3 meals rated 4 or 5 for taste.
Observations also need a clear gap (half a star, 40% of meals), and there are at most 5.

### 4.7 The AI features (optional)
`services/ai.py` holds the shared part: the client (30-second timeout, one retry), the
model (`claude-opus-5`), the refusal fallback, and turning every API failure (bad key, rate
limit, no internet, server error) into a sentence you can show. Both features:
- ask for a **structured** answer (a Pydantic class), not free text to pick apart,
- treat everything sent as data, never instructions (the prompt says so),
- check the answer against reality: a "matches an existing ingredient" or "you have it"
  claim is dropped if that name isn't really in your list,
- only suggest; nothing is saved without you.

Ingredient recognition uses low effort (a quick lookup); substitution ideas use medium
(judging what works in a dish takes more thought). Neither runs without a key, and tests use
a fake client, so no test ever calls the real API.

### 4.8 Importing recipes
Paste an address → `recipe_import.import_recipe()` downloads the page, finds the recipe data
most sites publish for search engines (section 6.8), and returns a draft that fills the form.
Nothing is saved until you click Save. Sites that block apps work through the Safari
bookmark: it runs *in* the page you're viewing, finds the same data, keeps only the fields
Slice'd uses, and opens `recipe-form.html#import=<data>`. The form posts that to
`/api/recipes/import-data`, and `history.replaceState` removes it from the address bar so a
reload doesn't import twice.

TheMealDB's catalog comes in a different way: a command, not a page.
`python -m app.database.mealdb` (in `database/`) asks TheMealDB for every recipe, one request
per first letter, and `services/mealdb.py` converts each one. TheMealDB already keeps the
amount apart from the name ("3/4 cup" + "soy sauce"), so only the amount needs parsing
(`recipe_import.parse_amount`). It has no times or servings: cook time is the sum of the
times written in the steps, prep is 2 minutes per ingredient, and `time_status` records that
they're estimates ("estimated", or "unknown" when the steps mention no times). The pages show
these as "about 45 min" (`recipeTime()` in `common.js`). Each recipe's `source_url` is its
TheMealDB page, which is how a second run knows what's already there.

### 4.9 Photos
Uploads are checked by their first bytes ("magic numbers": JPEG starts `FF D8 FF`, PNG with
`\x89PNG`), not by file name, so a renamed text file can't pass as a photo. The limit is
15 MB. Each upload gets a new random file name, so browsers can cache photos forever
without showing an old one. The new file is saved before the old one is deleted, so a failure
never leaves a recipe without a photo. A photo that fails to load falls back to the letter
cover.

### 4.10 Meal prep
`meal-prep.js` starts with pinned recipes checked and plans them on load. See section 6.9.

---

## 5. The frontend

### 5.1 Pages and scripts
Each page is an HTML file with its own script, plus the shared `common.js`:

| Page | Script | Main job |
|---|---|---|
| `index.html` | `dashboard.js` | Figures, tonight's picks, the numbered list, use soon, to buy. Each part loads on its own, so one failure doesn't blank the page |
| `recipes.html` | `recipes.js` | Filters, the grid, pins, the corner key |
| `recipe.html` | `recipe-detail.js` | One recipe: scaling, ingredient labels, swaps, flavor, cooking log, photo, pin |
| `recipe-form.html` | `recipe-form.js` | New or edit, import from a website, the Safari bookmark |
| `inventory.html` | `inventory.js` | Add, edit, search, group by place, AI suggestions |
| `grocery.html` | `grocery.js` | The list, checking off, Share, stocking bought items |
| `meal-prep.html` | `meal-prep.js` | Choosing recipes and showing the plan |
| `history.html` | `history.js` | Every meal cooked, rate later, notes |
| `profile.html` | `profile.js` | Figures, radar chart, flavor bars, taste line, observations |

**`common.js`** holds what every page needs:
- `apiRequest` (and `apiGet`, `apiPost`, `apiPut`, `apiPatch`, `apiDelete`): calls the API,
  sends JSON (or a raw file for photo uploads), and turns error responses into JavaScript
  errors with the server's readable message.
- Formatting helpers (minutes, dates, expiration labels).
- `recipeCover`, `pinButton`, and `flavorBar`, shared by several pages.
- `showCurrentMenuItem`: on phones the menu is one line you scroll sideways; this scrolls it
  so the current page's link is visible.

**Safety:** pages build HTML with `createElement` and `textContent`, never by gluing strings
into `innerHTML`, so text from the database or a website is always shown as text and can't
run as code (no cross-site scripting).

### 5.2 The Pinterest-style grid
CSS grid can't pack cards of different heights into columns by itself. The trick in
`recipes.js`: the grid has rows only 1px tall, and each card is told to span as many rows as
it is tall (`grid-row-end: span 312`). The browser then packs cards into the shortest column.
A `ResizeObserver` re-measures a card when its size changes (a photo loads, the window
resizes). Unlike CSS columns, this keeps the cards in order for keyboard and screen-reader
users. `layoutCards()` measures every card first and only then sets the spans: measuring
right after a change forces the browser to redo the whole layout, and doing that once per
card took several seconds with 800 recipes ("layout thrashing").

### 5.3 The radar chart
Drawn by hand as SVG in `profile.js`, with no chart library. Each of the 8 flavors is an
angle around a circle (flavor *i* of *n* sits at `2πi/n`, starting at the top); a value from
0 to 1 is the distance from the center. The helper `point(i, n, v)` turns that into x, y
with cosine and sine. Four rings and eight spokes are the grid; the shape is one polygon
through the eight points. Each point has a bigger invisible circle as its hover and keyboard
target, with a tooltip and a screen-reader label. The same numbers appear as bars
underneath, so the chart is never the only way to read them.

### 5.4 The design system (`css/style.css`)
- **Tokens** in `:root`: colors (steel, ticket white, ink, tomato, the stamp colors, the
  chalkboard), the three font families, the spacing scale (`--space-1` to `--space-9`), and
  page width. Rules use tokens, never one-off values, so the look stays consistent.
- **The kitchen-line look**: sections and recipes are white
  order tickets with a dashed tear edge and a paper edge; recipes hang on a rail and carry a
  colored corner and a rubber stamp; short lists are chalkboards; numbers sit on a board with
  heavy black lines; headings are condensed uppercase signage; ticket details are mono;
  corners are square.
- **Design rules** (from `DEVELOPMENT_PLAN.md`, several checked by tests): no gradients, no
  emoji, no italics, no animations or transitions, no em dashes, no labels above headlines,
  WCAG AA contrast.
- **Responsive:** grids collapse to one column on phones; the menu becomes a sideways-scrolling
  line.

---

## 6. The algorithms, with worked examples

### 6.1 Ingredient names (`names.match_key`)
Steps: lowercase, hyphens to spaces, strip punctuation, fix spellings ("chilli" to "chili"),
drop leading describing words ("fresh", "large", "freshly"), make the last word singular
(the noun is usually last: "cherry tomatoes"), then apply synonyms.
- "Large Eggs" → "large eggs" → "eggs" → "egg"
- "Scallions" → "scallion" → synonym → "green onion"
- "Freshly ground black pepper" → "ground black pepper" → synonym → "black pepper"

Keys are only for comparing; the names you typed are what's shown.

### 6.2 Units (`units.py`)
Every volume unit has a size in milliliters and every weight unit a size in grams, so
converting is `quantity × size_of_from / size_of_to`. Volume and weight never convert into
each other (a cup of flour and a cup of honey weigh different amounts), and that returns None
instead of a guess.
- `convert(3, "tsp", "tbsp")` = 3 × 4.93 / 14.79 = 1.0
- `tidy(6, "tsp")` → (2, "tbsp"): after scaling, pick the unit where the amount is a clean
  kitchen number.
- `format_quantity(1.5)` → "1 1/2": the nearest kitchen fraction (eighths, thirds).

### 6.3 Matching a recipe (`matching.py`)
For each ingredient, look up its match key in the inventory:
- not there: **staple** if it's salt, black pepper, or water, otherwise **missing**
- there but past its date: **expired**
- there, and amounts comparable: **short** if you have less than needed (1% tolerance, so
  2.9999 cups counts as 3), otherwise **have**
- there, amounts not comparable (you have "some", or pounds vs cups): **have**, with a note.
  Trusting the cook beats inventing a conversion.

`have_count` counts have and staple. The color: green if everything, yellow if at least
half, red otherwise.

### 6.4 The recommendation score (`recommendations.py`)
Example: a stir-fry needs rice (have), 4 eggs (you have 2: short), ginger (missing), salt
(staple).
- Coverage: have 1 + short 0.5 + missing 0 + staple 1 = 2.5 of 4 = 0.625 → 70 × 0.625 = **44**
- Use soon: 10 points per ingredient it uses that expires within 3 days, up to 2 → **0**
- Taste: **0 to 10** (6.5)

Ties go to fewer missing ingredients, then the quicker recipe, then the title. Every part
becomes a reason: "You have 2 of 4 ingredients. Not enough egg. Missing ginger."

### 6.5 Taste (`taste.py`)
1. Each recipe has a flavor vector: 8 numbers from 0 to 1 (6.6).
2. **Baseline** = the average vector of all your recipes. **Liked** = the average of meals you
   rated 4 or 5.
3. **Your lean** = liked − baseline. Subtracting matters: almost every recipe is somewhat
   salty, so salty only shows up in your lean if the meals you *liked* are saltier than your
   recipes in general.
4. For a recipe, its own lean = its vector − baseline.
5. **Fit** = cosine similarity of the two leans:
   `(a · b) / (|a| × |b|)`, which is 1 when they point the same way, 0 when unrelated, and
   negative when opposite. Points = 10 × fit, negatives count as 0.

Why cosine: it compares *direction* (which flavors stand out), not size, so a mildly and a
strongly seasoned version of the same idea both fit. A real example from the tests: you love
Garlic Noodles (garlic, soy sauce). Garlic Fried Rice fits (salty, savory, garlicky), but
Garlic Bread doesn't, even though it has garlic: it leans buttery and creamy instead.

### 6.6 Flavors (`flavors.py`)
Each known ingredient has scores, like soy sauce = salty 0.9, umami 0.7. A recipe combines
its ingredients per flavor with `1 − (1 − a)(1 − b)(1 − c)...`:
- one strong ingredient makes the recipe strong: garlic 0.95 → 0.95
- several medium ones add up: two ingredients at 0.5 → 1 − 0.5 × 0.5 = 0.75
- it never goes past 1

Amounts are ignored (a pinch of chili counts like a spoonful) and optional ingredients are
skipped. Ingredients not in the table are listed as unknown instead of guessed. The lookup
also tries the end of a name ("unsalted butter" → "butter") and the start ("salmon fillet" →
"salmon").

### 6.7 Scaling (`recipes.scale_recipe`)
factor = new servings ÷ original servings; each quantity × factor, then `tidy` picks a
friendly unit. A recipe for 2 with 1 tbsp soy sauce, scaled to 8: 4 tbsp → tidy → 1/4 cup.

### 6.8 Importing a recipe (`recipe_import.py`)
1. **Find the data.** Most recipe sites publish the recipe for search engines as JSON-LD:
   JSON inside `<script type="application/ld+json">`, using the schema.org `Recipe` format.
   The HTML parser collects those blocks; the code walks them (they can be lists, or nested
   under `@graph`) until it finds one whose `@type` is `Recipe`.
2. **Convert fields.** Times are ISO 8601 durations ("PT1H30M" = 90 minutes), read with a
   regular expression. Servings take the first whole number from "Makes 6 to 8". Steps can be
   one string, a list, `HowToStep` objects, or `HowToSection` groups of steps, and all become
   one step per line. HTML tags and entities (`&amp;`) are stripped.
3. **Parse each ingredient line** into amount, unit, name, and note. For
   "1½ cups plus 1 Tbsp. all-purpose flour (200 g), sifted":
   - unicode fractions become text: "1 1/2"
   - the amount at the start: 1.5 (ranges like "2 to 3" take the larger)
   - the unit: "cups" → cup; then "plus 1 Tbsp." is converted and added: 1.5625 cups
   - parentheses become notes, counting depth so "((Note 2))" and unclosed ones work
   - after a comma, it's a note only if it starts like one ("sifted", "finely chopped", "to
     taste"); "boneless, skinless chicken thighs" stays one name
   - prep words at the start move to the note ("toasted pine nuts" → pine nuts, toasted), so
     the name matches your inventory
   - result: name "all-purpose flour", 1.5625 cup, note "200 g, sifted"
4. **Merge duplicates** (salt for the dough and salt for the filling) and turn "salt and
   pepper" into two staples. Anything uncertain becomes a warning shown on the form.

Every rule came from a real line on a real site; the tests keep those lines.

### 6.9 Meal prep (`meal_prep.py`)
1. **Add up needs** across recipes per ingredient. Amounts in units that convert are summed
   (2 tbsp + 1/4 cup butter = 6 tbsp); others stay separate ("3 cloves + 1 tbsp garlic").
2. **Check the inventory once** against the total. This is the point: two recipes each
   needing 1 cup of rice with 1 1/2 cups at home each look covered alone, but together need
   2 cups, so you buy 1/2 cup.
3. **Prep together:** ingredients used by 2 or more recipes that need real prep: things you
   cook in a batch (rice, pasta, beans) or a cut read from the notes ("finely minced" →
   Mince). If recipes want different cuts, it says "Prep" and lists them. Sauces and oils are
   left out: there's nothing to do ahead.

### 6.10 Substitutions (`substitutions.py`)
A dictionary from ingredient to swaps, each with what it uses, how much, and what changes.
For each ingredient you don't have, swaps you can make (every part in your kitchen, not
expired) come first. `swap_count` counts required ingredients with a swap you own. A swap
never changes the recipe or its color: it's advice.

---

## 7. The tests (about 520)

**How they're set up (`conftest.py`):**
- `session_factory`: a brand-new SQLite file in a temporary folder for every test, so tests
  never touch your data and never affect each other.
- `client`: FastAPI's `TestClient`, with `get_db` swapped for one that uses the test database
  (FastAPI's `dependency_overrides`).
- `photos_dir` (automatic): points photo storage at a temporary folder too.

**The fake AI client:** tests replace `ai._client` with an object that records what was sent
and returns a canned answer or raises a chosen error. So tests check the prompt contents, the
model, the structured-output class, and every error path, for free and without internet.
Website imports are tested the same way, with a fake `fetch` returning saved pages.

**What's covered**, by file: recipes (CRUD, validation, search), inventory (duplicates, 409s,
dates), names and units (conversions, fractions, plurals), scaling and matching,
recommendations, grocery and history (combining, stocking, subtracting), leftovers, feed
(colors, pins, photos, migrations), recipe import (about 30 real ingredient lines, JSON-LD
shapes, errors), substitutions, profile and flavors, taste, meal prep, demo, the AI features,
and **design rules**: a test scans every frontend file for banned patterns (gradients,
emoji, italics, transitions, em dashes...), checks every page has the favicon and legal
links, checks every page uses the same cache version, and computes WCAG contrast for every
color pairing the pages use.

**Browser checks:** before calling a frontend change done, each page was opened in WebKit
(Safari's engine) with Playwright at 1280px and 390px, on a *copy* of the database: clicking
through the feature, checking for script errors and sideways scrolling, and looking at
screenshots.

---

## 8. Decisions and trade-offs

- **Deterministic before AI.** Matching, scoring, taste, flavors, importing, and meal prep are
  plain code: free, instant, the same answer every time, and explainable line by line. AI is
  only where rules can't work, and the app works fully without it.
- **One server, same origin.** No CORS setup, one thing to run.
- **Vanilla JS, no framework.** No build step; every file runs as written. The cost is some
  repetition (building DOM by hand); for 9 pages that's fine.
- **SQLite.** Zero setup and one file to back up. The limit is many users at once, which
  Slice'd doesn't have. SQLAlchemy keeps PostgreSQL an easy switch.
- **Honest when data is thin.** Every profile section and the taste score have minimum data
  requirements, and say what's missing instead of guessing.
- **Suggestions, never silent changes.** AI answers, imports, and swaps are shown for you to
  accept; nothing edits a recipe behind your back.
- **Private by default.** Local database, local photos, self-hosted fonts, and pages that make
  no outside requests.
- **Known simplifications:** flavor ignores amounts; volume and weight don't convert; the
  column migration only adds nullable columns; one inventory row per ingredient.

---

## 9. Questions to check your understanding

1. *Walk me through what happens when the Recipes page loads.* (Section 1.)
2. *Why is there a `recipe_ingredients` table?* Many-to-many, and the amount belongs to the
   pairing.
3. *How does Slice'd know "eggs" in your fridge matches "egg" in a recipe?* `match_key` (6.1).
4. *How do you convert 3 tsp to tbsp, and what if a recipe says cups but you have pounds?*
   (6.2.) Different kinds return None, and matching trusts the cook.
5. *How is the recommendation score calculated? Why is taste only 10 points?* (6.4, 6.5.) So
   it reorders what you can cook instead of pushing what you can't.
6. *What's cosine similarity, and why subtract the baseline?* (6.5.)
7. *How does importing work on a site you've never seen?* JSON-LD (6.8). *And one that
   blocks you?* The Safari bookmark runs in the user's browser.
8. *How do you stop a fake photo or a malicious link?* Magic bytes, size limit, random names;
   `source_url` must be http(s); `textContent` everywhere.
9. *How do you test the AI features without paying?* The fake client (7).
10. *What happens when you add a column to a table that already has data?* `migrate.py` (3.2),
    and when you'd reach for Alembic instead.
11. *How does the Pinterest grid keep cards in order?* 1px rows and spans (5.2).
12. *What would you change to support many users?* Accounts and auth, PostgreSQL, photo
    storage in the cloud, per-user data on every table, deployment, and rate limits on the
    AI features.
