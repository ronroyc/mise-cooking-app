# Slice'd

[![Tests](https://github.com/ronroyc/sliced/actions/workflows/tests.yml/badge.svg)](https://github.com/ronroyc/sliced/actions/workflows/tests.yml)

**What should I cook with what I already have?**

Slice'd is a cooking app built around one idea: *ingredient-aware recipe discovery*. It compares your recipes against what's actually in your kitchen, shows what you can cook tonight and what you're missing, learns what you like from your ratings, and turns the rest into a grocery list.

![The Slice'd home page: a large headline, four kitchen numbers, tonight's three recipe picks with covers and reasons, and a numbered list of the next recipes](docs/screenshots/home.png)

## What it does

**Your kitchen, matched against your recipes**
- **Inventory** for pantry, fridge, and freezer, with amounts and expiration dates.
- **Ingredient matching** on every recipe: have, not enough, expired, or missing. "Eggs" matches "egg", "scallions" match "green onion", and 2 cups compares with 1 tbsp.
- **Every recipe is an order ticket** with a colored corner and a rubber stamp: green READY (you have everything), mustard NEEDS 2 (at least half), red NEEDS 5 (less than half).
- **Recipe scaling** with kitchen fractions and unit conversion (6 tsp becomes 2 tbsp).

**Deciding what to cook**
- **Explainable recommendations.** Every recipe gets a score out of 100, with the reasons in plain words: up to 70 points for the ingredients you have, 20 for using food before it expires, and 10 for fitting your taste.
- **Taste learned from ratings.** The meals you rate 4 or 5 are compared with your whole recipe collection to find what you lean toward (for example salty and savory), and similar recipes rank higher: "Fits your taste: salty and umami."
- **Substitutions.** About 60 classic swaps, checked against your kitchen ("Swap: use your linguine, same amount"). An optional AI assistant covers anything else.
- **Profile.** Stats, a hand-drawn radar chart of your flavor profile, your most-used ingredients, and "Slice'd knows..." observations that only appear when the numbers back them up.

**Planning and shopping**
- **Meal prep.** Pick several recipes: Slice'd adds up what they need *together*, checks your kitchen once, and lists what to prep in one go ("Cook 13 cups rice once").
- **Grocery list** grouped by store section, which fills itself from recipes, combines amounts, moves bought items into the inventory, and shares to your phone.
- **Cooking history and leftovers.** Log a meal, rate it, take what you used out of the inventory, and save leftovers to the fridge with a 4-day date.

**Getting recipes in**
- **Import from recipe websites** by reading the recipe data they publish (schema.org JSON-LD) and parsing each ingredient line into amount, unit, name, and note, with plain code and no AI. For sites that block apps, a "Save to Slice'd" Safari bookmark reads the recipe from the page you're on.
- **Photos** you upload, or the site's photo for imported recipes, on a Pinterest-style grid.

## Screenshots

| Recipes as order tickets | A recipe |
|---|---|
| ![A grid of recipe tickets on a rail, each with a colored corner and a READY or NEEDS stamp](docs/screenshots/recipes.png) | ![A recipe page with a board of facts, an ingredient ticket with swaps, and numbered steps](docs/screenshots/recipe.png) |
| **Profile** | **Meal prep** |
| ![The profile page with stats, a flavor radar chart, and observations](docs/screenshots/profile.png) | ![Meal prep with chosen recipes, prep-together steps, and a combined shopping list](docs/screenshots/meal-prep.png) |
| **Inventory** | **Grocery list** |
| ![The inventory as ruled lists by fridge, freezer, and pantry](docs/screenshots/inventory.png) | ![The grocery list by store section](docs/screenshots/grocery.png) |

Every page works on a phone: [home page on a phone](docs/screenshots/home-phone.png). The screenshots use the demo data (see below).

## How it's built

| Layer      | Choice                                                      |
|------------|-------------------------------------------------------------|
| Frontend   | HTML, CSS, vanilla JavaScript (no framework, no build step) |
| Backend    | Python, FastAPI                                             |
| Database   | SQLite via SQLAlchemy                                       |
| Validation | Pydantic                                                    |
| Testing    | pytest (about 470 tests), plus WebKit checks with Playwright |
| AI         | Anthropic API, optional (ingredient recognition, substitution ideas) |

```
Browser ──HTTP──▶ FastAPI (one server)
                   ├── /api/*   → JSON API routes → services (the logic) → SQLAlchemy → SQLite
                   └── /*       → static frontend files (frontend/)
```

Design decisions worth knowing:
- **Deterministic first.** Matching, units, scoring, taste, flavors, meal prep, and the recipe importer are plain code, so the same kitchen always gives the same answer and every number can be explained. AI is only used where rules can't work (identifying an unfamiliar ingredient, creative substitutions), and the app works fully without it.
- **Private by default.** Everything lives in one SQLite file and a photos folder on your computer. Fonts are served by Slice'd itself, so pages make no outside requests.
- **A design with a concept.** The interface is a restaurant kitchen line: recipes are order tickets on a rail, stamped READY or NEEDS 2; short lists are chalkboards; numbers sit on a board. Steel gray, ticket white, black, and tomato red, with Barlow Condensed for headings and IBM Plex Mono and Sans for the rest.
- **Accessible.** WCAG AA color contrast (checked by tests), keyboard focus, screen-reader labels, and color never used alone (every colored corner has a stamp in words).

More detail: [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md) explains every part of the code and every library, [docs/GLOSSARY.md](docs/GLOSSARY.md) defines every term, and [docs/CHANGES.md](docs/CHANGES.md) tells the story change by change.

## How this was built

I designed and directed Slice'd, and used [Claude Code](https://claude.com/claude-code) as an AI coding tool to write much of the implementation. The project and its decisions are mine: what Slice'd is for (ingredient-aware cooking, not another recipe social network), the product framework and which features to build, cut, or shrink, what the recipe colors mean, keeping personal data private and local, holding off on paid AI until the end, and the kitchen-line design. I reviewed and tested every change, including in Safari, and I can walk through any part of the code. The whole process, including the decisions and the bugs, is in [docs/CHANGES.md](docs/CHANGES.md).

## Running locally

Requires Python 3.9+.

```bash
git clone https://github.com/ronroyc/sliced.git
cd sliced

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env       # optional: add ANTHROPIC_API_KEY to turn on the AI features

cd backend
python -m app.database.seed   # load the sample recipes and inventory (safe to run again)
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. Interactive API docs (generated by FastAPI): http://127.0.0.1:8000/docs

### Demo mode

To see every feature with data behind it (a stocked kitchen, pinned recipes, and two weeks of rated meals), build a separate demo database. It never touches your own:

```bash
cd backend
python -m app.database.demo ../data/demo.db
DATABASE_URL=sqlite:///../data/demo.db uvicorn app.main:app --port 8001
```

## Database

```
recipes ──< recipe_ingredients >── ingredients ──< inventory_items
```

Recipes and ingredients are many-to-many, so a join table (`recipe_ingredients`) connects them and stores the quantity, unit, and prep note for each pairing. Inventory items point at the same `ingredients` rows, one item per ingredient. See [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md) for the full explanation.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Server and database status |
| GET | `/api/recipes` | List recipes (`?search=`, `?cuisine=`, `?max_total_time=`, `?pinned=true`) |
| GET | `/api/recipes/cuisines` | Cuisines in use |
| GET | `/api/recipes/{id}` | One recipe with ingredients (`?servings=` to scale it) |
| GET | `/api/recipes/{id}/match` | Which ingredients are in the inventory: have, short, expired, missing (`?servings=`) |
| POST | `/api/recipes` | Create a recipe |
| PATCH | `/api/recipes/{id}` | Update a recipe |
| DELETE | `/api/recipes/{id}` | Delete a recipe (and its photo) |
| POST | `/api/recipes/import` | Read a recipe from a website (`{"url": ...}`) into a draft for the form; nothing is saved |
| POST | `/api/recipes/import-data` | The same, from recipe data the "Save to Slice'd" Safari button read from the page |
| POST | `/api/recipes/{id}/photo/from-url` | Download a photo for a recipe (used for imported recipes) |
| POST | `/api/recipes/{id}/substitutes` | AI ideas for replacing one ingredient (`{"ingredient": ...}`, `?servings=`); explains itself when no API key is set |
| GET | `/api/ai/status` | Whether AI features are on (an API key is set) |
| POST | `/api/meal-prep/plan` | Several recipes at once (`{"recipes": [{"id": 3, "servings": 4}]}`): one combined shopping list checked against the inventory, and what to prep together |
| POST | `/api/meal-prep/grocery` | Put that combined shopping list on the grocery list |
| GET | `/api/profile` | Stats, flavor profile, most-used ingredients, and "Slice'd knows..." observations (each only with enough data) |
| GET | `/api/recipes/{id}/flavor` | A recipe's flavor on 8 scales, and which ingredients each comes from |
| PUT / DELETE | `/api/recipes/{id}/pin` | Pin or unpin a recipe |
| PUT / DELETE | `/api/recipes/{id}/photo` | Upload a photo (the request body is the image: JPEG, PNG, WebP, or HEIC, up to 15 MB) or remove it |
| GET | `/api/photos/{filename}` | A recipe photo (stored in `data/photos`) |
| GET | `/api/recommendations` | Recipes ranked by what's in the kitchen, with score and reasons and a green/yellow/red color (`?search=`, `?cuisine=`, `?max_total_time=`, `?limit=`, `?pinned=true`) |
| GET | `/api/grocery` | Grocery list, unchecked first, grouped by store section |
| GET | `/api/grocery/text` | What's left to buy as plain text, one item per line (for the Reminders Shortcut in `docs/REMINDERS_SHORTCUT.md`) |
| POST | `/api/grocery` | Add an item (combines with the same ingredient when the units convert) |
| PATCH | `/api/grocery/{id}` | Check it off or change the amount |
| DELETE | `/api/grocery/{id}` | Remove an item |
| POST | `/api/grocery/from-recipe/{recipe_id}` | Add what a recipe needs that you don't have (`?servings=`) |
| POST | `/api/grocery/stock-checked` | Move checked items into the inventory |
| DELETE | `/api/grocery/checked` | Remove checked items without stocking them |
| POST | `/api/recipes/{id}/cooked` | Log a cooked recipe; optionally subtract what it used from the inventory |
| GET | `/api/history` | Everything cooked, newest first (`?recipe_id=`) |
| PATCH | `/api/history/{id}` | Rate it, or change the notes or date |
| DELETE | `/api/history/{id}` | Remove a history entry |
| GET | `/api/inventory` | List inventory (`?search=`, `?location=`, `?expires_within=`) |
| GET | `/api/inventory/{id}` | One inventory item |
| POST | `/api/inventory` | Add an item (409 with `existing_id` if that ingredient is already there, even spelled differently) |
| PATCH | `/api/inventory/{id}` | Update an item |
| DELETE | `/api/inventory/{id}` | Remove an item |
| GET | `/api/ingredients` | All known ingredient names |
| POST | `/api/ingredients/identify` | AI suggestion for a new ingredient name (saves nothing) |

## Environment variables

| Name                | Required | Purpose                                         |
|---------------------|----------|-------------------------------------------------|
| `DATABASE_URL`      | No       | Defaults to `sqlite:///data/sliced.db`            |
| `ANTHROPIC_API_KEY` | No       | Turns on the AI features: ingredient recognition and substitution ideas |
| `PHOTOS_DIR`        | No       | Where recipe photos are stored. Defaults to `data/photos`   |

Secrets go in `.env`, which is git-ignored. Never commit real keys.

## Running tests

From the project root, with the virtual environment active:

```bash
pytest
```

Tests use a temporary database, so they never touch `data/sliced.db`, and a fake AI client, so they never call the Anthropic API. On GitHub, `.github/workflows/tests.yml` runs them on every push.

## Project structure

```
sliced/
├── backend/
│   ├── app/
│   │   ├── api/          # HTTP routes: read request, call service, return response
│   │   ├── models/       # SQLAlchemy tables
│   │   ├── schemas/      # Pydantic validation for API input/output
│   │   ├── services/     # business logic and database queries
│   │   ├── database/     # engine, sessions, seed and demo scripts, column migrations
│   │   ├── config.py     # settings from environment variables
│   │   └── main.py       # creates the FastAPI app, error handlers
│   └── tests/
├── frontend/             # HTML pages, css/, js/, fonts/ (Barlow Condensed, IBM Plex, self-hosted)
├── docs/                 # walkthrough, product direction, Reminders Shortcut, screenshots
├── .github/workflows/    # runs the tests on every push
├── data/                 # seed_recipes.json, seed_inventory.json + SQLite database (db not committed)
├── requirements.txt
└── DEVELOPMENT_PLAN.md
```
