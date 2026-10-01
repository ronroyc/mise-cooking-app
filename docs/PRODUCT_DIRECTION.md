# Slice'd Product Direction

Written September 25, 2026. Part 2 is the product framework I wrote for the app's next stage, word for word. Part 1 is the plan that came out of reviewing it critically: every idea sorted into build now, build a smaller version, or cut and defer. Where the two disagree, Part 1 wins, because it's the edited version.

**Status (October 2026):** the whole build order below is done. See [DEVELOPMENT_PLAN.md](../DEVELOPMENT_PLAN.md).

---

# Part 1: The plan (the reviewed framework)

## Already built

Sections 3, 4, and 5 of the framework (quantity-aware matching, "have some but not enough", adding only the missing amount to the grocery list) were built and tested in M3 to M5. The framework's garam masala example (have 0.5 tbsp, need 2 tbsp, buy 1.5 tbsp) is exactly what the app does today. What's missing there is visual: the corner tab and pinning.

## Decisions (settled Sep 27, 2026)

1. **What the corner color means: "what I have", not difficulty.** The framework used green/yellow/red for both "can I make this with what I have?" and difficulty. "What I have" won: the data already exists (`/api/recipes/{id}/match`) and updates live as the inventory changes, while difficulty data doesn't exist and would have to be guessed from time, step count, and ingredient count, or entered by hand. There's **no separate "cookability" section**: just the colored corner on each recipe card, plus a key explaining the colors.
   - The rules: **green** = every required ingredient on hand in enough quantity; **yellow** = at least half on hand; **red** = less than half. The framework's "red = none of the ingredients" would almost never trigger, because salt, pepper, and water count as staples.
2. **Photos.** Recipe photos are what make it feel like Pinterest. The design rules ban AI-generated images, so photos are my own uploads (stored locally on the Mac). Recipes without a photo get a plain colored cover.
3. **The build order below.**

## Build now (great ideas)

| Idea | Why |
|---|---|
| Green/yellow/red corner tab + key on every recipe card | Cheap, visual, and makes the app feel alive. Uses existing matching. |
| Pin / unpin | One small table. Makes the feed personal and feeds grocery lists and meal prep. |
| Recipe photos (user uploads) | The actual gap between Slice'd and Pinterest. |
| Import from recipe websites | Most recipe sites embed a structured copy of the recipe (schema.org Recipe data in JSON-LD). Slice'd can read it with plain code: no AI, no cost. |
| Flavor profiles, profile page, radar chart | The showpiece. Start deterministic: an ingredient-to-flavor table, and a recipe's flavor is the combination of its ingredients. Radar chart hand-drawn in SVG, no chart library. |
| "Slice'd knows..." observations | Only when backed by real numbers. Say nothing when there isn't enough data. |

## Build a smaller version (edited ideas)

- **Meal prep mode.** Keep the smart part: cook shared things once. Cut the cost estimate, budget, and nutrition: Slice'd has no price or nutrition data, so those numbers would be invented. **v1:** pick some pinned recipes, get one combined grocery list (the combining logic already exists in `services/grocery.py`), and a "prep together" list such as "Cook 5 cups rice once, used by 3 recipes." Reusing prepared components across different meals (one batch of chicken becomes a burrito, a salad, and fried rice) needs recipes split into components: much later.
- **Import from TikTok, Instagram, Pinterest, YouTube.** These block scraping, and the recipe usually lives in the video or caption. Realistic version: "paste the caption or description text", and AI structures it. This uses the paid API, so it waits with the other real-AI work.
- **Leftovers.** Simple version: after cooking, "Save 2 servings as leftovers" creates an inventory item (for example "leftover chicken tikka") that expires in about 4 days and shows under "Use soon". Recommending "Chicken Tikka Wrap" would need recipes that list leftovers as ingredients, and none do.
- **"Random stuff I have" / recipe adaptation.** Mostly exists already: the Best match sort ranks recipes by the kitchen. The adaptation part (explained substitutions like Parmesan to Pecorino) is the M6 substitution assistant. Merge it into M6.
- **Nearby stores.** No paid maps API (it costs money and shares location). Instead, a "Find a store" link that opens Apple Maps' search for grocery stores nearby. One line of code, most of the value. Live store inventory stays out of scope.
- **Taste profile learning.** Fine, but be realistic about data: cooking a few times a week gives roughly 5 to 10 ratings a month. The profile shows "needs 5 rated meals" until there's enough, rather than guessing.

## Cut or defer

- **Community and social network** (framework sections 2 and 24; public posting, likes, comments, follows, community stats). The biggest trap. It needs accounts, passwords, hosting, image storage, and moderation, and it breaks the "keep it private" rule. A community of one is empty, and faked community numbers aren't allowed. Revisit only after deployment, with real people using it.
- **Taste evolution / "Spotify Wrapped".** Needs months of data. Revisit in about 6 months.
- **Streaks, most common cooking day and time.** Filler stats and the gamification the framework itself warns against.
- **Recipe versions** and **fridge-photo recognition.** Agreed: later.
- **Emoji in "Flavor DNA".** The design rules ban emoji. Use plain words and small bars instead.

## The reframe

"Pinterest-style social platform" and "keep it local and private" contradict each other. For now Slice'd is **Pinterest for your own kitchen**: more achievable and more believable. Social comes after deployment, if ever.

## Build order

1. **Share button + Apple Reminders Shortcut** for the grocery list (already agreed; see below).
2. **Feed v1:** corner tabs + key, pin/unpin, a "Pinned" filter, photo uploads, a Pinterest-style grid.
3. **Import from recipe websites** (JSON-LD, plain code, no AI).
4. **M6 substitution assistant + "cook with what I have"** (fake AI client until the key is added at the end).
5. **Profile v1:** stats, most-used ingredients, deterministic flavor profiles, radar chart, "Slice'd knows...".
6. **Leftovers** (simple version).
7. **Meal prep v1:** pinned recipes to one combined grocery list plus a "prep together" list.

Later, together with the API key and deployment decisions: paste-caption import, AI-assisted flavor profiles, a home-screen app on the phone.

## Grocery list to phone (agreed before the framework review)

- **Share button** on the Groceries page: opens the iPhone/Mac share sheet (Web Share API, with a copy-to-clipboard fallback) with the list as text grouped by store section. Works with Notes, Reminders, Messages. About 30 minutes of work; nothing leaves the Mac unless I send it.
- **Apple Reminders via a Mac Shortcut:** a Shortcut on the Mac reads `http://127.0.0.1:8000/api/grocery` and adds each unchecked item to a "Groceries" list in Reminders, which syncs to the iPhone through iCloud. Keeps Slice'd private. Limitation: one-way; checking items off in Reminders doesn't update Slice'd. Step-by-step instructions are in [REMINDERS_SHORTCUT.md](REMINDERS_SHORTCUT.md).
- **Notion / Todoist:** skip unless already in use. Needs an account and token, and the list goes to their servers.
- **Calendar:** wrong tool for groceries; useful later for meal planning (for example an .ics export of "Cook Oyakodon, Tuesday").
- **Mobile app:** no App Store app (weeks of work, $99 a year). Later, a home-screen web app reached privately over Tailscale; only as a deliberate decision, since it changes the local-only rule and needs the Mac running.

## Principles from the framework that still apply

- Keep the stack: HTML/CSS/vanilla JS, FastAPI, SQLite, SQLAlchemy, Pydantic, pytest, Anthropic API. No React, TypeScript, microservices, or extra infrastructure.
- Don't use AI for anything normal code can do (quantities, matching, scoring).
- Every recommendation stays explainable.
- Everything connects: recipes, ingredients, quantities, inventory, history, ratings, and flavor all feed each other.
- It should look like a motivated freshman who genuinely learned this built it, not an enterprise architecture.

---

# Part 2: The original framework (verbatim)

# Slice'd — Updated Product Direction

## IMPORTANT

This document updates the original Slice'd project direction.

The core idea is now:

> **Slice'd is a Pinterest-style social recipe discovery platform that understands your kitchen.**

Users discover and pin recipes, maintain an inventory, and Slice'd continuously compares recipes against what they actually have. Pinned recipes can turn into grocery lists, meal-prep plans, and eventually personalized recommendations based on the user's actual cooking behavior and taste.

Do NOT turn this into an overengineered enterprise application. It should still feel like a project a motivated freshman built: polished, technically thoughtful, useful, and understandable.

Continue using the existing beginner-friendly stack:

* Frontend: HTML/CSS/vanilla JavaScript
* Backend: Python + FastAPI
* Database: SQLite
* ORM/database layer: SQLAlchemy
* Validation: Pydantic
* Testing: pytest
* AI: Anthropic API
* Git/GitHub
* Simple deployment
* No TypeScript
* No React/Next.js
* No microservices
* No Kubernetes
* No GraphQL
* No unnecessary infrastructure

---

# 1. PINTEREST-STYLE RECIPE DISCOVERY SHOULD BECOME THE MAIN EXPERIENCE

The main part of Slice'd should feel like **Pinterest, but specifically for recipes**.

Users should be able to scroll through a visual feed of recipes.

Each recipe card should ideally contain:

* Recipe image
* Recipe name
* Short description
* Cuisine/category information where appropriate
* Author/community information when applicable
* Pin/save button
* Inventory status indicator

The user should be able to:

* Discover recipes
* Pin/save recipes
* Unpin recipes
* Search recipes
* Filter recipes
* Open a recipe's full detail page
* Eventually discover recipes posted by other users

The important difference from Pinterest is that Slice'd actually understands the recipe's ingredients and connects that information to the user's inventory.

---

# 2. COMMUNITY RECIPES

Slice'd should eventually support a community where users can post recipes.

Users should eventually be able to:

* Create recipes
* Add recipe photos
* Add descriptions
* Add ingredients and quantities
* Add cooking instructions
* Tag recipes
* Publish recipes publicly
* Keep recipes private if desired
* Pin/save recipes posted by other people
* Like recipes
* Eventually comment/interact with recipes
* Follow creators/users eventually

However, do NOT let the social system overwhelm the initial project.

A major goal is to eventually make this workflow possible:

1. Someone posts a recipe.
2. Another user sees it in their Slice'd feed.
3. They pin it.
4. Slice'd understands its ingredients.
5. Slice'd compares it against their inventory.
6. Slice'd tells them what they already have and what they're missing.
7. They can add the missing ingredients to their grocery list.
8. They cook it.
9. Slice'd updates their cooking history and inventory.

Full public community functionality can be implemented later if authentication, deployment, moderation, image uploads, etc. become too large for the initial version.

---

# 3. INVENTORY SHOULD DIRECTLY AFFECT THE RECIPE FEED

The inventory should not be an isolated CRUD feature.

It should actively affect what recipes the user sees.

When the user adds, removes, or changes quantities in their inventory, recipe ingredient matching should update accordingly.

For every recipe, Slice'd should determine:

### Green corner tab

The user has ALL required ingredients in sufficient quantities.

Example:

Recipe requires:

* 2 cups flour
* 1 cup milk
* 2 eggs

Inventory:

* 3 cups flour
* 2 cups milk
* 4 eggs

→ GREEN

### Yellow corner tab

The user has some/all ingredients but is missing something or has insufficient quantities.

Example:

Recipe requires:

* 2 cups flour
* 1 cup milk
* 2 eggs

Inventory:

* 2 cups flour
* 0.5 cups milk
* 2 eggs

→ YELLOW

The system should explicitly understand that 0.5 cups is NOT enough for a recipe requiring 1 cup.

### Red corner tab

The user has none of the required ingredients, or does not have sufficient quantities for the recipe in a meaningful way.

→ RED

The exact visual implementation can be refined later, but the important part is that the status should update dynamically as inventory changes.

Do NOT simply check whether an ingredient exists.

Quantities matter.

---

# 4. INGREDIENT QUANTITY MATCHING

Slice'd needs to understand:

> "I own this ingredient"

versus:

> "I own enough of this ingredient."

For example:

Recipe:

* 2 cups flour

Inventory:

* 0.5 cups flour

Slice'd should determine:

* Ingredient exists
* Quantity insufficient
* User needs another 1.5 cups

This information should feed directly into grocery lists.

Unit normalization/conversion should therefore continue to be part of the backend.

---

# 5. PINNED RECIPES + AUTOMATIC GROCERY LISTS

If a recipe is yellow and the user pins it, Slice'd should be able to determine exactly what the user needs to buy.

For example:

## Chicken Alfredo

The user already has:

* Chicken — sufficient
* Pasta — sufficient
* Garlic — sufficient
* Salt — sufficient

The user needs:

* Heavy cream — 1 cup
* Parmesan — ½ cup

Slice'd should allow:

> Add missing ingredients to grocery list

The grocery list should contain the **actual missing quantity**, not simply:

> "Buy heavy cream."

It should say something like:

> Heavy cream — 1 cup

or whatever amount is actually necessary based on the user's inventory.

If the user has some but not enough, only the missing amount should be added.

Example:

Recipe requires:

> 2 tbsp garam masala

Inventory:

> 0.5 tbsp garam masala

Grocery list:

> Garam masala — 1.5 tbsp needed

Do not tell the user to buy an ingredient they already have enough of.

---

# 6. EVENTUALLY: WHERE TO BUY THE MISSING INGREDIENTS

For missing grocery-list ingredients, eventually Slice'd should be able to show nearby places where the user can potentially buy them.

For example:

> Heavy cream
>
> QFC — 0.7 mi
> Safeway — 1.1 mi
> Fred Meyer — 1.8 mi

This should use location permission / location services when appropriate.

IMPORTANT:

Do not make exact live retailer inventory a requirement for the initial version.

There is a major difference between:

> "This store sells heavy cream"

and:

> "This exact store currently has this exact product in stock."

The latter requires substantially more external data/integrations.

Start with nearby stores/location functionality later if appropriate.

---

# 7. MEAL PREP MODE

Add a future **Meal Prep Mode**.

This should be more intelligent than simply selecting five recipes.

The user should eventually be able to specify things such as:

* Number of days
* Number of meals
* Number of people
* Budget
* Desired nutrition/preferences
* Variety preferences
* Existing inventory

Example:

> 5 days
> Lunch + dinner
> ~$60
> High protein
> Don't eat the exact same meal every day

Slice'd should select a collection of meals that work together.

The important concept:

## Optimize preparation, not just recipes.

Instead of:

> Cook five completely unrelated meals.

Slice'd should recognize shared ingredients and shared preparation steps.

Example:

* Cook chicken once
* Cook rice once
* Roast vegetables once

Then reuse those components across several different meals:

* Chicken rice bowl
* Chicken burrito
* Chicken salad
* Chicken fried rice

The user gets variety without having to prepare ten completely separate dishes.

Eventually Meal Prep Mode should be able to produce:

### Shopping

What the user already has and what they need to buy.

### Batch preparation

What should be cooked/prepared together.

### Portioning

How much should go into each meal/container.

### Meal assignment

Which prepared components go into which meals.

The goal is:

> **Slice'd plans the meal prep. The user just has to cook it.**

---

# 8. MEAL-PREP OPTIMIZATION

A more advanced version of Meal Prep Mode should consider:

* Ingredient overlap
* Existing inventory
* Package/ingredient quantities
* Number of meals
* Variety
* Preparation time
* Budget
* Waste
* Reuse of prepared components

Example:

The user pins:

* Korean beef bowl
* Chicken burrito
* Chicken tikka
* Chicken salad

Slice'd could recognize that these recipes share ingredients or preparation components.

It could say something like:

> These 4 recipes require 27 unique ingredients.
>
> Slice'd can reduce that to 16 shared ingredients with compatible substitutions/meal-prep combinations.
>
> Estimated prep: 1h 40m
> Estimated cost: $48
> Meals: 12

This is a long-term direction. Do not overengineer the first implementation.

---

# 9. TASTE PROFILE / PERSONALIZATION

Slice'd should eventually learn the user's taste preferences based on what they actually cook and rate.

Do NOT simply ask the user:

> "Do you like spicy food?"

Instead, learn from behavior.

Slice'd should eventually consider:

* Recipes the user cooks
* Recipe ratings
* Recipes the user pins
* Recipes the user repeatedly cooks
* Potentially modifications they make to recipes
* Ingredients they commonly use
* Flavor characteristics of recipes

The system should gradually build a representation of the user's flavor preferences.

---

# 10. RECIPE FLAVOR PROFILES

Recipes should eventually have structured flavor profiles.

Possible dimensions include:

* Heat/spicy
* Sweet
* Sour/acidic
* Salty
* Bitter
* Umami
* Savory
* Garlicky
* Creamy
* Smoky
* Herby

These can be represented numerically, such as values from 0–1.

Example:

```json
{
  "spicy": 0.82,
  "sweet": 0.31,
  "sour": 0.42,
  "umami": 0.91,
  "savory": 0.84,
  "garlicky": 0.93,
  "creamy": 0.15
}
```

The exact dimensions can be refined.

---

# 11. HOW SLICE'D DETERMINES FLAVOR PROFILES

There are several possible approaches.

### Initial/simple approach

Use an ingredient → flavor mapping.

For example:

* Jalapeño → spicy
* Garlic → garlicky
* Soy sauce → savory/umami
* Honey → sweet
* Lemon → acidic

Then calculate a recipe's approximate flavor profile from its ingredients.

### AI-assisted approach

Use the Anthropic API to analyze the recipe and return structured flavor-profile values.

The AI should output structured data, not a paragraph that needs to be manually interpreted.

Example:

```json
{
  "spicy": 0.82,
  "sweet": 0.31,
  "sour": 0.42,
  "umami": 0.91
}
```

### Long-term hybrid approach

Combine deterministic ingredient information with AI recipe-level analysis.

The ingredient data provides grounded information while the AI can account for how the complete recipe balances its ingredients.

For example:

Jalapeño may technically be very spicy, but a recipe containing substantial cream, cheese, or other balancing ingredients may have a lower perceived heat level.

Do not make this unnecessarily complicated in the initial version.

---

# 12. PERSONAL RECOMMENDATION ENGINE

Eventually, Slice'd can compare:

> Recipe flavor profile

against:

> User's learned taste profile.

For example, if the user consistently rates recipes highly that are:

* High umami
* High savory
* High garlic
* Moderately spicy

then a new recipe with a similar flavor vector should receive a stronger recommendation.

A basic mathematical approach could eventually use something like cosine similarity between the recipe's flavor vector and the user's preference vector.

This should be explainable.

For example:

> **Why Slice'd recommended this**
>
> You rated 8 similar spicy/garlicky recipes 4★ or higher.
>
> This recipe has a similar savory + garlic + heat profile.

Do NOT make recommendations a mysterious black box.

---

# 13. PROFILE SECTION

Slice'd should eventually have a dedicated user profile page that is much more interesting than a standard account page.

The profile should represent:

> **"What Slice'd knows about how I cook and what I like."**

Potential top-level information:

* Recipes cooked
* Recipes pinned
* Average recipe rating
* Favorite/most-used ingredients
* Cooking habits
* Flavor profile

Example:

> 47 recipes cooked
> 17 pinned
> 4.3★ average rating

---

# 14. PROFILE: FLAVOR PROFILE VISUALIZATION

The user's personal flavor profile should be displayed visually.

Use a **radar/spider chart** rather than a generic square if practical.

Potential axes:

* Heat
* Salty
* Sour
* Sweet
* Umami
* Savory
* Herby
* Smoky
* Creamy

The user's profile becomes a shape based on their learned flavor preferences.

For example, someone who loves spicy/umami/garlic-heavy food would have the shape extend further toward those dimensions.

Color/intensity can be used to communicate strength.

The user should be able to visually understand:

> "This is the kind of food I tend to like."

---

# 15. PROFILE: "YOUR FLAVOR DNA"

Under the visualization, show a readable summary.

Example:

## Your Flavor DNA

🧄 Garlic — Very High
🍄 Umami — Very High
🌶️ Heat — High
🍋 Acidity — Medium
🍯 Sweetness — Low

This should be based on actual cooking/rating behavior rather than manual user input.

---

# 16. PROFILE: COMMON INGREDIENTS

Show the ingredients the user uses most often.

Example:

## You Cook With...

1. Garlic — 37 recipes
2. Chicken — 31 recipes
3. Soy sauce — 24 recipes
4. Rice — 22 recipes
5. Onion — 21 recipes

This could eventually use visual elements such as ingredient bubbles, with bubble size representing usage frequency.

Also show:

## Your Pantry Staples

For example:

> Garlic · Eggs · Rice · Soy Sauce · Olive Oil

These can potentially inform inventory/recommendation logic later.

---

# 17. PROFILE: COOKING HABITS

Eventually show statistics such as:

* Average cooking time
* Most commonly cooked meal type
* Most-cooked cuisine
* Number of recipes cooked
* Average recipe rating
* Longest cooking streak
* Most common cooking day
* Most common cooking time

Do not turn the profile into a ridiculous gamification system.

The purpose is to show the user's cooking personality and useful patterns.

---

# 18. PROFILE: "SLICE'D KNOWS..."

This should be a particularly interesting profile section.

Slice'd can generate observations based on the user's actual behavior.

Examples:

> **You really like garlic.**
>
> You've rated 8 of your last 10 garlic-heavy recipes 4★ or higher.

> **You tend to prefer spicy food.**
>
> Your highest-rated recipes average a high heat score.

> **You don't love long recipes.**
>
> Recipes under 30 minutes have a higher average rating for you.

These should be based on actual data and have reasonable explanations behind them.

Avoid pretending the system knows something when there isn't enough data.

---

# 19. TASTE PROFILE EVOLUTION

Eventually, the profile should be able to show how the user's tastes change over time.

For example:

### Taste evolution

Three months ago:

> Heat: 0.35

Now:

> Heat: 0.72

This could be visualized over time.

The goal is something like:

> **Spotify Wrapped for your cooking habits**

but based on actual Slice'd data.

---

# 20. LEFTOVERS AS INVENTORY

Eventually, cooked food should be able to become an inventory item.

Example:

The user makes:

> Chicken Tikka — 4 servings

After eating two servings:

> 2 servings of leftover Chicken Tikka remain.

Slice'd can then recommend recipes that reuse that leftover food.

Examples:

* Chicken Tikka Wrap
* Chicken Tikka Quesadilla
* Chicken Tikka Rice Bowl
* Chicken Tikka Salad

The important conceptual idea is:

> **Food does not disappear after a recipe is cooked. It can become an ingredient for the next meal.**

This creates a continuous loop between recipes and inventory.

---

# 21. "RANDOM STUFF I HAVE" / RECIPE ADAPTATION

Eventually, the user should be able to say something like:

> "I have eggs, tortillas, spinach, leftover rice, half an avocado, and a bunch of sauces."

Slice'd should use those exact ingredients to suggest meals.

If an existing recipe is close but requires an ingredient the user does not have, Slice'd could eventually offer an adapted version.

Example:

> Original recipe:
> Korean Fried Rice
>
> Slice'd adaptation:
> Uses the ingredients you currently have.

The system should explain substitutions rather than silently changing the recipe.

For example:

> Original: Parmesan
> Available: Pecorino
> Reason: similar salty/umami profile

This is a future AI feature, not something that needs to be perfect immediately.

---

# 22. RECIPE IMPORTING FROM THE INTERNET

Eventually, users should be able to paste a recipe URL from places such as:

* Pinterest
* Instagram
* TikTok
* YouTube
* Recipe websites

Slice'd should ideally extract/convert the recipe into structured data:

* Recipe name
* Ingredients
* Quantities
* Units
* Servings
* Instructions
* Image where legally/technically appropriate
* Source

Then Slice'd can immediately analyze it.

Example workflow:

1. User sees a recipe online.
2. User pastes the link into Slice'd.
3. Slice'd imports the recipe.
4. Slice'd structures the ingredients.
5. Slice'd compares it against inventory.
6. User gets the green/yellow/red status.
7. User pins it.
8. Missing ingredients can be added to the grocery list.

This is a major part of the long-term Pinterest-like experience.

---

# 23. RECIPE MODIFICATIONS / VERSIONS — FUTURE

Eventually, users could modify recipes they cook.

Example:

Original:

> 2 cloves garlic

User's version:

> 5 cloves garlic

or:

> Added chili crisp
> Reduced soy sauce
> Used chicken instead of beef

Slice'd could remember the user's personal version.

Eventually the user could publish that modified version to the community.

This would create:

> Original recipe → Your version → Community versions

However, this is a later feature.

It is NOT necessary for the first version.

---

# 24. COMMUNITY RECIPE FEEDBACK — FUTURE

If community functionality becomes large enough, eventually Slice'd could show information such as:

> 23 people cooked this recipe.

and potentially:

> Common substitutions:
>
> Chicken → tofu: 8 people
> Spinach → bok choy: 5 people

This should only be implemented once there is enough real community data to make it meaningful.

Do not fabricate community statistics.

---

# 25. LOCATION-BASED GROCERY DISCOVERY — FUTURE

Eventually, when a grocery list contains missing ingredients, Slice'd could help users find nearby stores.

Potential workflow:

> Grocery list
>
> Heavy cream
> Parmesan
> Cilantro

Then:

> Nearby stores

with approximate distance.

This may require user location permission and external location/business APIs.

Do not make exact live inventory a core requirement.

---

# 26. IMPORTANT FEATURE PRIORITY

Do NOT attempt to build every future feature at once.

The strongest initial product loop is:

**Discover recipes**
↓
**Pin recipes**
↓
**Maintain inventory**
↓
**Compare recipes against inventory and quantities**
↓
**Show green/yellow/red recipe state**
↓
**Pin a recipe**
↓
**Generate exactly what is missing**
↓
**Add missing ingredients to grocery list**
↓
**Cook**
↓
**Update inventory**
↓
**Eventually meal prep**
↓
**Rate recipes**
↓
**Slice'd learns taste preferences**
↓
**Profile reflects the user's cooking personality**
↓
**Recommendations become increasingly personalized**

That loop should be the foundation.

---

# 27. FEATURES EXPLICITLY DEFERRED

Do NOT prioritize the following during the initial build:

### Fridge/pantry image recognition

The idea is eventually allowing the user to photograph their fridge/pantry and have Slice'd identify ingredients.

This is cool, but it is a later feature because computer vision makes the project substantially more complicated.

### "Use this before it dies" as a standalone feature

Do not create a separate major feature around expiration/waste optimization right now.

Expiration information can remain part of inventory and existing recipe logic, but do not turn it into another huge system yet.

### Full social network

Do not immediately build a massive Instagram/Pinterest-style social infrastructure.

Accounts, authentication, moderation, image hosting, comments, following, etc. can come later.

### Recipe versioning

Keep it as a future direction.

### Exact live grocery-store inventory

Do not make this a requirement.

---

# 28. PRODUCT PHILOSOPHY

Slice'd should NOT feel like:

> "I added AI to a recipe database."

It should feel like:

> **"Slice'd understands my kitchen, my recipes, and how I cook."**

The important technical idea is that the same underlying structured data powers many different parts of the product:

### Recipe data

→ discovery

### Ingredient data

→ inventory matching

### Quantities

→ exact grocery requirements

### Inventory

→ personalized recipe availability

### Cooking history

→ personalization

### Recipe ratings

→ taste profile

### Flavor profiles

→ recommendation engine

### Meal relationships

→ meal prep optimization

### User behavior

→ profile insights

Everything should connect.

---

# 29. DO NOT OVERUSE AI

AI should be used where it provides actual value.

Good AI uses:

* Structured flavor-profile analysis
* Ingredient substitution reasoning
* Recipe adaptation
* Natural-language cooking assistance
* Potential recipe importing/normalization where appropriate

Do NOT use an LLM for deterministic tasks that normal code can handle.

For example:

Do NOT ask an LLM:

> "Does the user have 2 cups of flour?"

Use normal backend logic.

Do NOT ask an LLM:

> "Does 0.5 cups satisfy 2 cups?"

Use normal math.

AI should complement the engineering rather than replace it.

---

# 30. KEEP THE ENGINEERING BELIEVABLE

This is still a freshman-level project.

The goal is NOT to build every feature immediately.

Build the core system cleanly first.

Prioritize:

* Good database design
* Correct ingredient matching
* Correct quantity handling
* Clean API design
* Good frontend state updates
* Meaningful tests
* Explainable recommendation logic
* Good error handling
* Secure API key handling
* Clean Git history
* Good README/documentation

Then progressively add the more ambitious systems.

The project should look like:

> "A freshman who genuinely learned web development, databases, APIs, recommendation systems, and AI built this."

Not:

> "An AI generated a 200-service enterprise architecture."

---

# 31. THE LONG-TERM VISION

The ideal long-term Slice'd workflow is:

> I open Slice'd.

I see a Pinterest-style feed of recipes.

I pin something.

Slice'd already knows what's in my kitchen.

The recipe immediately shows whether I can make it.

I add a few missing ingredients to my grocery list.

Slice'd can eventually tell me where nearby I could buy them.

I pin several recipes.

I enter Meal Prep Mode.

Slice'd figures out how to prepare those meals efficiently while reusing ingredients.

I cook them.

My inventory updates.

I rate the recipes.

Slice'd learns what flavors I actually like.

My profile updates.

My flavor-profile visualization changes.

My future recipe recommendations get better.

Then I come back tomorrow and Slice'd is already different because **my kitchen and my tastes have changed.**

That is the product direction.

Do not lose that underlying loop while implementing individual features.
