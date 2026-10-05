# Slice'd glossary

Every term used in building Slice'd, in plain words, with where it shows up in the project.
Grouped by topic; within a topic, simpler ideas come first. For how the pieces fit
together, see [WALKTHROUGH.md](WALKTHROUGH.md). For what changed when, see
[CHANGES.md](CHANGES.md).

---

## 1. How the web works

**Client and server.** The client asks, the server answers. Safari is the client; the
Python program running Slice'd is the server.

**Frontend and backend.** The frontend is what runs in the browser (HTML, CSS,
JavaScript in `frontend/`). The backend is what runs on the server (Python in `backend/`).
"Full-stack" means building both.

**HTTP.** The language browsers and servers use to talk. Every request has a method, a path,
headers, and sometimes a body; every response has a status code, headers, and a body.

**URL, path, query string.** In `http://127.0.0.1:8000/api/recipes?cuisine=Thai`, the path
is `/api/recipes` and the query string is `?cuisine=Thai` (named values after `?`, joined by
`&`).

**localhost / 127.0.0.1.** The address that means "this same computer". The app's server
listens only there, so nothing outside your Mac can reach it.

**Port.** A numbered door on a computer. Slice'd uses 8000; the test copies used 8765 and 8766
so they never touch the real one.

**HTTP methods.** What a request wants to do:
- **GET**: read (`GET /api/recipes`)
- **POST**: create or trigger something (`POST /api/recipes`, `POST /api/meal-prep/plan`)
- **PUT**: set something to a value (`PUT /api/recipes/3/pin`, upload a photo)
- **PATCH**: change some fields (`PATCH /api/inventory/5` with just the quantity)
- **DELETE**: remove (`DELETE /api/grocery/7`)

**Status codes.** The number on every response. The ones Slice'd uses:
- **200** OK, **201** Created, **204** No Content (deleted, nothing to send back)
- **304** Not Modified (the browser's copy is still current)
- **404** Not Found (no recipe with that id)
- **409** Conflict (that ingredient is already in the inventory)
- **413** Payload Too Large (photo over 15 MB)
- **422** Unprocessable Entity (the data didn't pass validation)
- **500** / **503** server errors (503 from the health check when the database is down)

**Header.** Extra information on a request or response, like `Content-Type: application/json`
or `Cache-Control: no-cache`.

**Body.** The main content of a request or response: JSON for most of the app's API, the raw
image for a photo upload.

**API (Application Programming Interface).** A set of addresses a program can call to get or
change data. The app's API is everything under `/api/`.

**REST / RESTful.** A common style for APIs: addresses name things (`/recipes/3`), and the
HTTP method says what to do with them. Slice'd follows it loosely.

**Endpoint / route.** One address plus method in the API, like `GET /api/recipes/{id}`.
`{id}` is a **path parameter**: part of the path that changes.

**JSON (JavaScript Object Notation).** The text format the API speaks:
`{"title": "Oyakodon", "servings": 2}`. Objects in braces, lists in brackets.

**CRUD.** Create, Read, Update, Delete: the four basic things you do with stored data.
Recipes, inventory, and grocery items all have full CRUD.

**Same origin / CORS.** Browsers limit a page from one address calling an API at a different
address; CORS is the setup that allows it. Slice'd avoids the whole issue by serving the pages
and the API from the same server (the same origin).

**Static files.** Files sent as they are, without code running for each request: HTML, CSS,
JS, fonts, images.

**Cache / caching.** Keeping a copy to avoid fetching again. Browsers cache files; that
caused the app's "Can't find variable" bug (see CHANGES.md, Sep 25).

**Cache-busting (`?v=22`).** Adding a version number to a file's address so a changed file
has a new address the browser has never cached.

**MIME type / content type.** A label saying what kind of data a body is: `text/html`,
`application/json`, `image/jpeg`, `font/woff2`.

**Deploy / hosting.** Putting an app on a server on the internet so others can use it. Slice'd
isn't deployed; it runs on your Mac.

---

## 2. Python and the backend

**Python virtual environment (`.venv`).** A private folder of installed packages for one
project, so projects don't interfere. Created with `python3 -m venv .venv`.

**pip / requirements.txt.** pip installs packages; `requirements.txt` lists exactly which
versions (**pinned** versions like `fastapi==0.128.8`) so every install is the same.

**Package / module / import.** A module is one `.py` file; a package is a folder of them
(with `__init__.py`). `from app.services import matching` loads one.

**Standard library.** Modules that come with Python (json, re, datetime...). No install
needed.

**Type hints.** Labels on variables and parameters: `def scale(quantity: float) -> float`.
Python doesn't enforce them by itself, but FastAPI and Pydantic read them to validate data.

**`Optional[str]`.** "A string, or None." Slice'd uses this spelling because Python 3.9 doesn't
understand the newer `str | None`.

**None.** Python's "no value". In Slice'd, a quantity of None means "to taste" or "some".

**Function, argument, return value.** A named piece of code, the values passed in, and the
value it gives back.

**Class and object (instance).** A class is a blueprint (`class Recipe`); an object is one
thing made from it (the Oyakodon recipe).

**Decorator.** A line starting with `@` above a function that wraps or registers it:
`@router.get("/recipes")` registers the function as a route.

**Dataclass.** A class that mainly holds data, with the boring code written for you
(`@dataclass class Need` in meal prep).

**Exception / raise / try-except.** How Python signals an error (`raise ImportFailed(...)`)
and handles one (`try: ... except ImportFailed: ...`). Slice'd defines its own exceptions like
`AIError` and `InvalidPhotoError`.

**Dictionary (dict) and list.** `{"heat": 0.7, "sweet": 0.2}` maps keys to values;
`[1, 2, 3]` is an ordered list. The flavor table and the swap table are dictionaries.

**List comprehension.** A compact way to build a list:
`[m for m in matches if not m.optional]`.

**Regular expression (regex).** A pattern language for matching text, from the `re` module.
The ingredient parser uses one to find "1 1/2" or "2 to 3" at the start of a line.

**f-string.** Text with values inside: `f"You have {count} items"`.

**Environment variable / `.env`.** Settings passed to a program from outside its code
(`DATABASE_URL`, `ANTHROPIC_API_KEY`). `.env` is a file holding them, never committed.

**Async / await / event loop.** A way for one program to wait on many slow things (like
network calls) without freezing. FastAPI supports it; the app's slow website fetches use plain
functions instead, which FastAPI runs on a separate **thread** so they don't block others.

**Web framework.** A library that handles the web plumbing so you write the app logic.
FastAPI is the app's.

**ASGI server.** The program that runs a Python web app and speaks HTTP. Uvicorn is the app's.

**Router.** A group of routes. Each file in `api/` has one, and `main.py` mounts them all
under `/api`.

**Dependency injection (`Depends`).** Telling FastAPI "this route needs X; get it for me".
Every route gets its database session this way (`db: Session = Depends(get_db)`), which
also lets tests swap in a test database (a **dependency override**).

**Middleware.** Code that runs on every request or response. The app's adds the
`Cache-Control` header.

**Lifespan / startup.** Code that runs once when the server starts: creating tables and
adding missing columns.

**Validation.** Checking that incoming data is acceptable (servings is a whole number from
1 to 100) before using it.

**Schema.** A description of what data must look like. In Slice'd, Pydantic classes in
`schemas/`.

**Serialization.** Turning objects into text to send (a Recipe object into JSON), and back
(**deserialization**).

**Service layer.** The folder of plain functions holding the app's logic (`services/`),
separate from HTTP (`api/`) and storage (`models/`).

**Separation of concerns.** Each part has one job. It's why Slice'd splits api, services,
models, and schemas.

**Idempotent.** Doing it twice has the same effect as once. Pinning a recipe twice leaves it
pinned once; seeding twice adds nothing.

**Worker thread.** A second line of execution in the same program, so a slow task doesn't
hold up the rest.

**Logging.** Writing messages about what the server is doing (errors, AI failures) to the
terminal, not to the user.

---

## 3. Databases

**Database.** Organized, lasting storage for data. The app's is SQLite.

**SQL.** The language for asking databases questions: `SELECT title FROM recipes WHERE
servings > 2`.

**SQLite.** A database that lives in one file (`data/sliced.db`), with no separate server.

**PostgreSQL.** A full database server, the usual choice for multi-user websites.

**Table, row, column.** A table is like a spreadsheet (recipes); a row is one entry (one
recipe); a column is one field (title).

**Primary key (`id`).** A column that uniquely identifies each row.

**Foreign key.** A column pointing at another table's primary key
(`recipe_ingredients.recipe_id` → `recipes.id`). SQLite only enforces them with
`PRAGMA foreign_keys=ON`, which Slice'd sets.

**PRAGMA.** A SQLite-specific setting command.

**Relationship types.** One-to-many (a recipe has many cooking logs); many-to-many (recipes
and ingredients), which needs a **join table** (`recipe_ingredients`).

**Unique constraint.** A rule that a value (or combination) can appear only once: one
inventory row per ingredient; one row per recipe-ingredient pair.

**NULL / nullable.** SQL's "no value". A nullable column may be empty.

**Cascade.** Automatic follow-on changes: deleting a recipe deletes its ingredient rows
(`cascade="all, delete-orphan"`). **ON DELETE SET NULL** does the opposite for history: the
log stays and its recipe link becomes empty.

**ORM (Object-Relational Mapper).** A library that lets code use classes instead of SQL.
SQLAlchemy is the app's ORM; `models/` are its classes.

**Model.** A class that stands for a table (`class Recipe(Base)`).

**Engine / connection / session.** The engine knows how to reach the database; a session is
one unit of work in which you read and change objects.

**Commit / rollback / transaction.** A transaction groups changes; commit saves them all at
once, rollback throws them all away. Nothing is half-saved.

**Flush.** Sending pending changes to the database inside a transaction without committing
yet (used so new rows get their ids).

**Query / filter / order by.** Asking for rows, narrowing them (`where`), and sorting.

**Migration.** A change to the database's structure (like adding a column) that keeps
existing data. The app's `migrate.py` handles the simplest kind; **Alembic** is the standard tool
for full migrations.

**Seed data.** Starter data loaded into an empty database (`data/seed_recipes.json`).

**Demo database.** A separate file with sample data for screenshots and demos
(`python -m app.database.demo`).

**SQL injection.** An attack where typed text is run as SQL. Using an ORM with parameters
prevents it.

---

## 4. Frontend: HTML, CSS, JavaScript

**HTML.** The structure of a page: headings, lists, forms, buttons.

**Element / tag / attribute.** `<a href="/recipes.html">` is an `a` element; `href` is an
attribute.

**Semantic HTML.** Using elements for what they mean (`<nav>`, `<main>`, `<button>`,
`<ol>`) so browsers and screen readers understand the page.

**CSS.** The styling: colors, fonts, spacing, layout.

**Selector / rule / property.** `.recipe-card h2 { font-size: 1.4rem; }`: the selector picks
elements, the property sets one style.

**Class / id.** Labels for elements: classes are reusable (`.card`), ids are unique
(`#recipe-title`).

**CSS custom properties (variables) / design tokens.** Named values like `--accent:
#ad4f2c`, defined once in `:root` and reused everywhere, so the look stays consistent.

**Box model.** Every element is content, padding, border, and margin.

**Flexbox.** A CSS layout for lining things up in a row or column (the header, list rows).

**CSS Grid.** A CSS layout in rows and columns (the recipe grid, the home picks, forms).

**Masonry layout.** Cards of different heights packed into columns (the Pinterest look).
Slice'd builds it with 1px grid rows and row spans.

**Media query.** CSS that applies only at some screen sizes: `@media (max-width: 40rem)`
for phones.

**Responsive design.** One page that works at every screen width.

**rem / px.** Units of size. `1rem` is the root font size (16px); rem scales with the
user's text settings.

**Specificity / `!important`.** Rules for which CSS wins when two conflict. Slice'd uses
`!important` once, so `hidden` always hides.

**JavaScript (JS).** The programming language of the browser; it makes pages interactive.

**Vanilla JS.** Plain JavaScript without a framework like React.

**DOM (Document Object Model).** The page as objects JavaScript can change:
`document.getElementById("recipe-title")`.

**Event / event listener.** Something that happens (a click, a form submit) and the function
that responds (`button.addEventListener("click", ...)`).

**fetch / Promise / async-await.** `fetch` calls the API; it returns a Promise (a future
value); `await` waits for it without freezing the page.

**textContent vs innerHTML.** `textContent` shows text as text; `innerHTML` reads it as
HTML. Slice'd uses `textContent` so recipe text can never run as code.

**XSS (cross-site scripting).** An attack where text shows up on a page as working code.
Prevented by `textContent`.

**SVG.** A format for drawing shapes with code (lines, polygons, circles). The radar chart
and the favicon are SVG.

**Web font / @font-face / woff2.** A font file the page loads, declared with `@font-face`.
woff2 is the compressed format. Slice'd serves its fonts itself.

**Favicon.** The little icon in the browser tab (`favicon.svg`).

**Bookmarklet.** A bookmark whose address is JavaScript (`javascript:...`); clicking it runs
the code on the current page. The "Save to Slice'd" button.

**Web Share API / Clipboard API.** Browser features for opening the share sheet
(`navigator.share`) and copying text.

**ResizeObserver.** A browser feature that tells you when an element's size changes.

**localStorage.** Small storage in the browser. Slice'd doesn't use it; everything lives on the
server.

---

## 5. Accessibility and design

**Accessibility (a11y).** Making the app usable by everyone, including people using screen
readers, keyboards, or with low vision or color blindness.

**WCAG / AA.** The web's accessibility guidelines; AA is the common target level.

**Contrast ratio.** How different two colors' brightness is. AA needs 4.5:1 for normal text
and 3:1 for shapes and borders. The app's tests compute these.

**Screen reader / VoiceOver.** Software that reads pages aloud. VoiceOver is Apple's.

**ARIA attributes.** Extra labels for assistive tech: `aria-label`, `aria-pressed` (on the
Pin toggle), `aria-current="page"` (the menu item for this page), `role="list"`,
`role="status"` (messages that are read out when they change).

**Focus / focus-visible / skip link.** Focus is where keyboard input goes; `:focus-visible`
draws the outline; the skip link jumps past the menu.

**Color alone.** Never using color as the only signal. Every colored corner has the same
fact in words.

**Design system.** The shared set of tokens, components, and rules that keep every page
consistent.

**Serif / sans-serif / monospace / condensed.** Fonts with and without small strokes at
letter ends; monospace fonts give every letter the same width (like a receipt printer);
condensed fonts are narrow. Slice'd uses a condensed sans (Barlow Condensed) for headings, a
monospace (IBM Plex Mono) for ticket details, and a sans (IBM Plex Sans) for reading.

**Design concept.** The idea a whole look grows from. Slice'd's is a restaurant kitchen line:
order tickets, stamps, chalkboards, a rail.

**Rule (in design).** A thin line separating content.

**AI slop.** Generic, templated-looking design (gradients, glassy cards, rows of three icon
boxes). The app's design rules ban the usual tells.

---

## 6. Testing and quality

**Automated test.** Code that checks other code and fails loudly if something is wrong.

**Unit test / integration test.** A unit test checks one small piece (`match_color`); an
integration test checks pieces together (a request through the API into the database).

**pytest / assert.** The app's test runner; `assert x == y` fails the test if it's false.

**Fixture.** Reusable setup for tests (`client`, `db`, `photos_dir` in `conftest.py`).

**Parametrize.** Running one test with many inputs.

**Test isolation.** Each test gets a fresh database, so tests can't affect each other.

**Mock / fake / stub / monkeypatch.** Replacing a real thing with a pretend one in a test.
The app's fake AI client and fake website fetch; `monkeypatch` swaps them in.

**Regression test.** A test added after fixing a bug, so it can't come back.

**Test coverage.** How much of the code the tests exercise.

**End-to-end / browser testing.** Driving the real page in a browser. Slice'd used Playwright
with WebKit.

**Headless browser.** A browser running without a window, for scripts.

**WebKit.** The engine inside Safari.

**CI (Continuous Integration) / GitHub Actions.** Automatically running the tests on every
push. `.github/workflows/tests.yml`; the green badge on the README.

**Linting.** Automatic style and mistake checks (the app's closest equivalent is the
design-rules test).

**Refactor.** Changing how code is organized without changing what it does (moving the
shared AI code into `ai.py`).

**Edge case.** An unusual input that might break things: an empty inventory, "salt and
pepper" on one line, a photo file that's actually text.

---

## 7. Git and GitHub

**Git / repository (repo).** Git records every version of the project; the repo is the
project plus its history.

**Commit / commit message.** A saved snapshot with a note explaining it.

**Branch.** A line of history (`main`).

**Remote / origin / push / pull / clone.** A remote is a copy elsewhere (GitHub, named
`origin`); push uploads commits, pull downloads them, clone copies a repo.

**`.gitignore`.** Files git never tracks: `.env`, `data/*.db`, `data/photos/`, `.venv/`.

**Co-authored-by.** A line in a commit message crediting another author.

**noreply email.** A private address GitHub gives you so commits don't show your real email.

**Rewriting history.** Changing past commits. Done twice: to switch the email before
anything was pushed, and later to remove co-author lines from the published commits.

**Force push.** Replacing the history on GitHub with a rewritten local one. Safe only when
no one else has a copy of the old history.

**GitHub CLI (`gh`).** GitHub's command-line tool; used to create the repo.

**OAuth / scope.** How `gh` got permission without your password; a scope is one permission
(the `workflow` scope was needed to upload the CI file).

**Badge.** A small image in the README showing a live status (tests passing).

---

## 8. AI and the Claude API

**LLM (large language model).** An AI model trained on text that writes text. Claude is one.

**API key.** A secret that identifies you to a paid API. Kept in `.env`.

**Model.** A specific version of the AI (`claude-opus-5`).

**Prompt / system prompt.** The instructions sent with a request; the system prompt sets the
AI's role and rules.

**Structured output.** Asking the AI to answer in an exact shape (a Pydantic class) instead
of free text.

**Effort.** A setting for how much the model thinks: low for quick lookups, medium for
substitutions.

**Token.** The unit AI text is measured and billed in (roughly three-quarters of a word).

**Rate limit.** A cap on requests per minute; Slice'd shows "The AI is busy" when hit.

**Refusal / fallback.** When the AI declines to answer; the fallback retries on another
model.

**Prompt injection.** Text trying to trick an AI into following it as instructions. The app's
prompts wrap user text in tags and say it's data.

**Hallucination.** The AI stating something false with confidence. Slice'd checks answers
against real data (dropping a "you have it" that isn't in your inventory).

**Deterministic.** Always gives the same output for the same input. The app's core logic is
deterministic; AI isn't.

**SDK (Software Development Kit).** A library for using a service from code (the `anthropic`
package).

---

## 9. Math and algorithms in Slice'd

**Algorithm.** A step-by-step method for solving a problem.

**Heuristic.** A rule of thumb that's usually right (after a comma, words ending in "-ed"
are a note).

**Normalization.** Turning variants into one standard form ("Tablespoons" → "tbsp";
"Eggs" → "egg").

**Match key.** The app's normalized comparison form of an ingredient name.

**Singularize / pluralize.** Converting between "tomatoes" and "tomato".

**Synonym table.** A lookup of names meaning the same thing ("scallion" → "green onion").

**Unit conversion.** Changing an amount between units of the same kind via a base unit
(milliliters for volume, grams for weight).

**Tolerance.** An allowed tiny difference, so 2.9999 cups counts as 3 (1% in matching).

**Scaling factor.** New servings ÷ original servings.

**Weighted average.** An average where some values count more (rated meals count
rating ÷ 3 in the flavor profile).

**Vector.** A list of numbers describing something; each recipe's flavor is an 8-number
vector.

**Baseline.** The "normal" to compare against (the average flavor of all your recipes).

**Dot product / magnitude.** Multiply matching entries and add them up; magnitude is a
vector's length (square root of the sum of squares).

**Cosine similarity.** Dot product ÷ (product of magnitudes): 1 means same direction, 0
unrelated, −1 opposite. How taste fit is measured.

**Probabilistic OR / complement product.** `1 − (1 − a)(1 − b)...`: combines strengths so
they add up but never exceed 1. How recipe flavors combine.

**Threshold.** A minimum before something counts (3 liked meals for taste, 5 meals for
observations).

**ISO 8601 duration.** A standard time format: "PT1H30M" means 1 hour 30 minutes.

**Parsing / parser.** Reading text into structured data (the ingredient-line parser).

**Web scraping.** Reading data out of web pages. Slice'd reads the structured data sites
publish instead of the visible page.

**JSON-LD / schema.org / structured data.** A standard way for sites to describe their
content for search engines; recipe sites publish a schema.org `Recipe` in JSON-LD, which the
importer reads.

**User agent.** The name a program gives websites about itself; the importer says it's
Safari.

**Magic bytes / file signature.** The first bytes that identify a file's real type (JPEG
starts `FF D8 FF`).

**Checksum / SHA-256.** A fingerprint of a file used to prove it wasn't changed (used to
verify the GitHub CLI download).

---

## 10. Slice'd's own terms

**Inventory.** What's in your kitchen: pantry, fridge, freezer.

**Staple.** Salt, black pepper, and water: assumed on hand unless the inventory says
otherwise.

**Have / short / expired / missing.** An ingredient's status against the inventory.

**Coverage.** The share of a recipe's required ingredients you have.

**Use soon.** Inventory items expiring within 3 days.

**Corner color and stamp.** Green, mustard, or red on each recipe ticket, from coverage,
with a READY or NEEDS stamp saying the same in words.

**Score / reasons.** The 0 to 100 recommendation number and the plain-words explanation.

**Taste / lean / fit.** What you like (learned from 4 and 5 star meals), measured as a lean
away from your recipe collection's average, and how well a recipe points the same way.

**Flavor profile / flavor DNA.** Your average flavor across meals and pins, shown as the
radar chart and bars.

**Swap.** A substitute from the hand-written table.

**Pin.** Marking a recipe to keep it close (and to start it checked in meal prep).

**Leftovers.** Cooked servings saved to the fridge in the inventory, good for 4 days.

**Prep together.** A shared prep task in meal prep ("Cook 13 cups rice once").

**Design rules.** The list of banned patterns and required qualities in
`DEVELOPMENT_PLAN.md`, partly enforced by tests.
