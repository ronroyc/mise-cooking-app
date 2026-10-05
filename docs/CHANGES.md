# How Slice'd was built, change by change

Every change, in order: what it was, why, the decisions behind it, and what went wrong
along the way. Terms are explained in [GLOSSARY.md](GLOSSARY.md); how the code works is in
[WALKTHROUGH.md](WALKTHROUGH.md).

---

## Sep 23: the foundation

### Project setup (Milestone 0)
- **What:** a FastAPI server with a `/api/health` route that checks the database with
  `SELECT 1`; a SQLite database set up through SQLAlchemy; a frontend shell served by the
  same server; pytest with a separate test database; README and development plan.
- **Why:** get the skeleton right before any features: one server, one database file, and
  tests from day one.
- **Decisions:** Python + FastAPI + SQLite + vanilla JS (small, understandable, nothing to
  install beyond Python); frontend and API from one server, so no CORS setup; tests never
  touch real data.
- **Privacy:** keep the project private and local, with nothing deployed. That became the
  privacy rule.
- **Also:** the design rules (no gradients, emoji, italics, animations, banned fonts...) and a
  test that enforces them; Terms and Privacy pages; the favicon.

### Recipes (Milestone 1)
- **What:** three tables (`recipes`, `ingredients`, and the `recipe_ingredients` join table),
  full create/read/update/delete, search and filters, the recipe list, detail, and form
  pages, and 21 sample recipes across 9 cuisines.
- **Why a join table:** recipes and ingredients are many-to-many, and the amount belongs to the
  pairing. It also means every feature later refers to the same `ingredients` rows.
- **Layers introduced:** `schemas/` (validation) → `api/` (routes) → `services/` (logic) →
  `models/` (tables).
- **Bugs found:** SQLAlchemy warned about a half-built object while saving ingredients (fixed
  by looking up all ingredients first; warnings now fail the tests). Search results sorted
  "Chicken Teriyaki" before "Chicken and Vegetable Stir-Fry" because uppercase sorts first
  (fixed by sorting on the lowercase title, with a regression test).

---

## Sep 25: the kitchen and the core logic

### Inventory (Milestone 2)
- **What:** `inventory_items` (pointing at the same ingredients), pantry, fridge, and freezer,
  amounts, expiration dates, and the Inventory page. Expiration status is computed when read,
  never stored, so it can't go stale overnight.
- **Decision:** one inventory row per ingredient, so "how much rice do I have?" has one answer.
  Adding a duplicate returns 409 Conflict.

### Stale-cache crash fix, demo data cleared, AI ingredient recognition
- **Bug:** Safari showed "Can't find variable: capitalize". It had kept an old cached
  `common.js` while loading a new `inventory.js`. Fix: every frontend file is sent with
  `Cache-Control: no-cache`.
- **Bug:** the 22 sample inventory items blocked adding real garlic and eggs (one row per
  ingredient). Removed them from the working database; real items were kept.
- **Friendlier duplicates:** adding something already in the inventory opens it for editing.
- **AI ingredient recognition:** a new name ("Momofuku Chili Crunch", "muktuk") can be
  identified by Claude with a structured answer. It only suggests, and everything works
  without a key.

### Versioned file addresses
- **What:** pages load `style.css?v=2` and so on, so even a browser that cached files before the
  fix gets fresh ones. A test keeps every page on the same version.

### Handoff notes and product ideas
- **Process:** session notes so each working session picks up where the last one stopped.
  Also saved: ideas for making Slice'd a product someday (freemium AI tier, grocery partnerships,
  no ads or data selling).

### Core intelligence (Milestone 3)
- **Name matching:** `match_key()` so "Eggs" is "egg" and "scallions" is "green onion".
- **Units:** cleaned on input, converted within volume or weight, never between them (that
  would need each ingredient's density).
- **Scaling:** `?servings=` rescales a recipe, with amounts moved to a cleaner unit.
- **Matching:** have, short, expired, or missing for every ingredient, with a servings control
  on the recipe page.

### Recommendations (Milestone 4)
- **What:** a 0 to 100 score (80 for ingredients on hand, 20 for using food that expires
  within 3 days) with reasons in plain words; a "Best match" sort.
- **Decision:** a fixed formula, not AI: same kitchen, same ranking, every point explainable,
  free.
- **Staples:** salt, pepper, and water count as on hand unless they're tracked (otherwise every
  recipe is "missing salt"). A sensible default, still worth revisiting.

### Grocery list, history, ratings (Milestone 5)
- **Grocery list:** combines amounts when units convert, fills from a recipe's missing items,
  and moves bought items into the inventory.
- **History:** logging a meal can subtract what it used; ratings and notes; a History page.
  Deleting a recipe keeps its history.

### Design pass and accessibility (Milestone 7)
- **Order:** polish came before the AI milestone, so the core app felt finished first.
- **What:** a warmer look, consistent form controls, a skip link, contrast tests for every color
  pair, clear error messages when anything fails, and README screenshots.
- **Lesson:** screenshots catch what tests can't (mismatched control heights, an overflowing
  phone menu, a sentence that read "green onions, which expires").

---

## Sep 26 to 27: a new direction, and the feed

### The product direction
- **The framework:** "Pinterest for recipes that understands your kitchen", with a community,
  flavor profiles, meal prep, and more. A critical review sorted every idea: build now, build
  smaller, cut or defer. The biggest cut: the social network (accounts, moderation, hosting, and it
  conflicts with keeping Slice'd private). Saved in `docs/PRODUCT_DIRECTION.md`.

### Three decisions
- The corner color means **what I have** (not difficulty), with a key and no separate
  section.
- Photos are **my own uploads**; recipes without one get a plain colored cover.
- The **build order** is confirmed.

### Step 1: grocery list to the phone
- **Share button:** opens the share sheet with the list grouped by store section, or copies
  it. The text is built on the page because Safari only allows sharing right after a click.
- **Reminders Shortcut:** `GET /api/grocery/text` plus step-by-step instructions in
  `docs/REMINDERS_SHORTCUT.md`.

### Step 2: the feed
- **Colored corners** (green, yellow, red) with a key and the same fact in words.
- **Pins** and a Pinned filter.
- **Photos:** type checked by the file's first bytes, 15 MB limit, a new random name per
  upload.
- **Pinterest grid:** 1px rows with row spans, so cards pack into columns but keep their order.
- **Migration:** existing databases get the new columns at startup, with all data kept.

---

## Sep 28: import, substitutions, profile, leftovers, redesign

### Step 3: import from websites
- **How:** read the schema.org recipe data sites publish; parse each ingredient line with plain
  code; show a draft to check before saving.
- **Tested on real sites:** Just One Cookbook, BBC Good Food, RecipeTin Eats, Bon Appétit, Love
  and Lemons. Each broke the first parser in a new way (nested parentheses, "boneless, skinless",
  "200 g / 6 oz", "plus 1 Tbsp."), and every broken line became a test.
- **Blocked sites** (Allrecipes, Serious Eats, Budget Bytes, Maangchi) refuse anything but a real
  browser. Solution: the "Save to Slice'd" Safari bookmark, which runs in the page you're already on.

### Step 4: substitution assistant (Milestone 6)
- **Free layer:** about 60 hand-written classic swaps, checked against the kitchen.
- **AI layer:** "Ask AI for ideas", hidden until an API key is added. Built and tested with a fake
  client only.
- **Cost:** the paid API key waits until the end, so no money is spent while building.
- **Refactor:** the shared Anthropic API code moved to `services/ai.py`.

### Step 5: profile
- **Flavors:** a table scores ingredients on 8 flavors; a recipe combines them.
- **Profile:** stats, a hand-drawn SVG radar chart, "You cook with", and "Slice'd knows..."
  observations that only appear with enough data. First draft had 9 observations with awkward
  wording ("heat food"); trimmed to the clearest 5 with proper words ("spicy").
- **Fix:** the phone menu cut off "Profile"; it now scrolls to the current page.

### Step 6: leftovers, and simpler flavor numbers
- **Leftovers:** saved to the fridge for 4 days from the day the meal was cooked.
- **Flavor numbers:** shown as plain numbers, without "Low / Medium / High".

### Redesign, phase 1
- **Goal:** a look that feels well made and distinctive, not generic.
- **Chosen:** the cookbook editorial direction (over "precise kitchen tool" and "bold and
  playful"), Home and Recipes first.
- **What:** paper and ink colors, Newsreader headings (served by Slice'd itself so no request
  goes to Google), a big headline, figures between rules, numbered picks, letter covers.
- **Contrast fix:** the accent was deepened slightly to stay readable on the new paper color.

---

## Sep 29: the rest of the redesign, meal prep, taste

### Redesign, phase 2
- Every page in the cookbook look: sections are a heavy rule and a serif title (no boxes),
  ruled lists, large serif step numbers on recipes, and old unused styles removed.

### Step 7: meal prep
- **The key idea:** add up what the recipes need together, then check the kitchen once, so two
  recipes can't both count the same rice.
- **Prep together:** only real prep (batch cooking, or a cut from the recipe's notes). A bug
  found by a test: "finely minced" was read as "chop"; the cut is now read from the whole note.

### Taste, demo mode, README, CI
- **Why:** the profile only displayed taste; now taste drives recommendations. Liked meals
  versus the recipe collection's average, compared by cosine
  similarity, worth up to 10 points. Ingredients went from 80 to 70 points so the total stays
  100.
- **A test that taught something:** Garlic Bread didn't count as a taste match even though
  Garlic Noodles were rated highly. It's buttery and creamy, not salty and savory. The math was right; the
  test was wrong.
- **Demo mode:** a separate sample database for screenshots and public demos.
- **CI:** GitHub Actions runs the tests on every push.

### The walkthrough
- `docs/WALKTHROUGH.md`: every library and file explained.

---

## Sep 30 to Oct 1: on GitHub

### Before uploading
- **Choices:** a public repo named `sliced`, with commits under GitHub's private
  noreply email.
- **Checked:** the database, photos, and `.env` were never committed.
- **History rewrite:** all commits switched to the noreply email while nothing was uploaded
  yet (safe then; rewriting history after pushing causes trouble for anyone who cloned it).

### Upload
- Published as a single commit of the finished project; the development history above is
  the record of how it got there.
- GitHub CLI installed (the download checked against its published SHA-256), then signed in;
  the repo was created and pushed. The first upload was refused until the CLI was granted the
  `workflow` permission, which GitHub requires for automation files.
- The tests ran on GitHub's servers: all 474 passed. README got the clone address and the
  green tests badge.

---

## Oct 2: a design with a concept

- **Why:** the cookbook look (cream paper, a book serif, a terracotta accent) read as
  generic. It's the default style AI tools produce, so the app looked machine-made even
  though it was tidy. A new palette on the same layout wouldn't fix that; a concept would.
- **Directions compared:** three mockups of the same page with real data: a restaurant
  kitchen line, grocery store signage, and a Swiss poster. **Chosen:** the kitchen line,
  because it fits a cooking app, with plain wording everywhere
  rather than kitchen slang.
- **What:** recipes are order tickets hanging on a rail, each with a colored corner and a
  READY / NEEDS stamp; short lists (use soon, to buy, prep together) are chalkboards;
  numbers sit on a black-lined board; steel gray, ticket white, black, and tomato red;
  Barlow Condensed, IBM Plex Mono, and IBM Plex Sans, served locally; square corners.
  Recipes without a photo are plain tickets instead of fake colored covers.
- **Fixes along the way:** the colored corners briefly disappeared mid-redesign (styles
  changed before the scripts); ticket headers ran under the corner; clips floated between
  grid rows. The tomato red and green were checked for contrast on the steel background.

---

## Oct 4: commit messages

- **What:** removed the `Co-Authored-By` lines from the two published commits, so Claude
  Code no longer appears in the repo's contributors list. The README still names it as the
  AI coding tool used to build Slice'd.
- **How:** rewrote the commit messages and force-pushed. Rewriting published history is
  normally risky, but here no one else had cloned the repo.
