"""Import a recipe from a website, with plain code (no AI).

Most recipe sites embed a machine-readable copy of the recipe for search engines:
a <script type="application/ld+json"> block with schema.org Recipe data (name,
ingredients, steps, times, yield, photo). This reads that block and turns it into
a draft for the recipe form. Nothing is saved here: the cook checks the draft first.

Ingredient lines are still free text ("1 (14 oz) can crushed tomatoes"), so
parse_ingredient_line() splits them into amount, unit, name, and note as well as
it can, and anything it isn't sure about is listed in the draft's warnings.
"""
import html
import json
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlparse

from app.schemas.recipe import normalize_name
from app.services import units
from app.services.names import match_key

MAX_PAGE_BYTES = 5 * 1024 * 1024
TIMEOUT_SECONDS = 15
# Some sites refuse requests that don't look like a browser.
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Version/18.0 Safari/605.1.15")


class ImportFailed(Exception):
    """Raised with a message that can be shown to the cook as it is."""


# ---------- Fetching ----------

def check_url(url: str) -> str:
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ImportFailed("Enter a full web address, starting with https://")
    return url


def fetch(url: str, max_bytes: int) -> bytes:
    """Download a page or image. The site sees an ordinary request from this computer."""
    request = urllib.request.Request(check_url(url), headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = response.read(max_bytes + 1)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403, 429):
            raise ImportFailed("That site didn't let Slice'd read the page. You can still type the recipe in.")
        if error.code == 404:
            raise ImportFailed("That page doesn't exist (the site says 404). Check the address.")
        raise ImportFailed(f"The site answered with an error ({error.code}). Try again later.")
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ImportFailed("Couldn't reach that site. Check the address and your internet connection.")
    if len(data) > max_bytes:
        raise ImportFailed("That file is too big to import.")
    return data


def fetch_page(url: str) -> str:
    data = fetch(url, MAX_PAGE_BYTES)
    return data.decode("utf-8", errors="replace")


# ---------- Finding the recipe data in the page ----------

class _JsonLdCollector(HTMLParser):
    """Collects the text of every <script type="application/ld+json"> block."""

    def __init__(self):
        super().__init__()
        self.blocks = []
        self._inside = False

    def handle_starttag(self, tag, attrs):
        if tag == "script" and (dict(attrs).get("type") or "").strip().lower() == "application/ld+json":
            self._inside = True
            self.blocks.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self._inside = False

    def handle_data(self, data):
        if self._inside:
            self.blocks[-1] += data


def _is_recipe(node) -> bool:
    kind = node.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    return "Recipe" in kinds


def _walk(node):
    """Every dict inside a JSON-LD value: top level, lists, and "@graph"."""
    if isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in node:
                yield from _walk(node[key])


def find_recipe_data(page: str) -> Optional[dict]:
    collector = _JsonLdCollector()
    collector.feed(page)
    for block in collector.blocks:
        try:
            data = json.loads(block, strict=False)  # strict=False allows raw newlines inside strings
        except ValueError:
            continue  # a broken block elsewhere on the page shouldn't stop the import
        for node in _walk(data):
            if _is_recipe(node):
                return node
    return None


# ---------- Cleaning values ----------

def clean_text(value) -> str:
    """Strip HTML tags and entities: '<b>Salt &amp; pepper</b>' -> 'Salt & pepper'."""
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(clean_text(v) for v in value)
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = html.unescape(html.unescape(text))  # some sites escape twice: &amp;amp;
    text = " ".join(text.split())
    return re.sub(r" ([.,;:!?])", r"\1", text)  # "<b>garlicky</b>." left "garlicky ."


def _first_text(value) -> str:
    if isinstance(value, list):
        return clean_text(value[0]) if value else ""
    return clean_text(value)


DURATION = re.compile(r"^P(?:(\d+(?:\.\d+)?)D)?(?:T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?)?$")


def parse_minutes(value) -> Optional[int]:
    """ISO 8601 durations, as schema.org uses: 'PT1H30M' -> 90, 'PT45M' -> 45, 'P0DT20M' -> 20."""
    match = DURATION.match(clean_text(value).upper()) if value else None
    if not match or not any(match.groups()):
        return None
    days, hours, minutes, seconds = (float(g) if g else 0.0 for g in match.groups())
    return round(days * 1440 + hours * 60 + minutes + seconds / 60)


def parse_servings(value) -> Optional[int]:
    """'4', 4, ['4', '4 servings'], 'Makes 6 to 8 servings' -> the first whole number."""
    for text in value if isinstance(value, list) else [value]:
        match = re.search(r"\d+", clean_text(text))
        if match and int(match.group()) > 0:
            return int(match.group())
    return None


def parse_steps(value) -> list:
    """recipeInstructions comes as one string, a list of strings, HowToStep objects,
    or HowToSection objects that hold steps. Returns one step per item."""
    if value is None:
        return []
    if isinstance(value, str):
        text = html.unescape(value)
        # Keep line breaks and paragraphs as step breaks; drop other tags.
        text = re.sub(r"<\s*(br|/p|/li)\s*/?>", "\n", text, flags=re.IGNORECASE)
        return [line for line in (clean_text(part) for part in text.split("\n")) if line]
    if isinstance(value, list):
        return [step for item in value for step in parse_steps(item)]
    if isinstance(value, dict):
        if "itemListElement" in value:  # a HowToSection
            return parse_steps(value["itemListElement"])
        return parse_steps(value.get("text") or value.get("name"))
    return []


def image_url(value) -> Optional[str]:
    """image comes as a URL, a list of URLs, or ImageObject(s) with a "url".
    From a list: the widest when sizes are given, otherwise the first (usually full size)."""
    if isinstance(value, list):
        def width(item):
            try:
                return int(item.get("width") or 0) if isinstance(item, dict) else 0
            except (TypeError, ValueError):
                return 0
        value = max(value, key=width) if value else None  # max keeps the first on ties
    if isinstance(value, dict):
        value = value.get("url") or value.get("contentUrl")
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value
    return None


# ---------- Ingredient lines ----------

UNICODE_FRACTIONS = {"½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4", "⅛": "1/8",
                     "⅜": "3/8", "⅝": "5/8", "⅞": "7/8", "⅕": "1/5", "⅙": "1/6"}
NUMBER = r"\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?"
QUANTITY = re.compile(rf"^({NUMBER})(?:\s*(?:-|to|or)\s*({NUMBER}))?\s*")
SIZES = {"small", "medium", "large", "extra-large", "heaping", "level", "big", "heaped"}


def _number(text: str) -> float:
    total = 0.0
    for part in text.split():
        if "/" in part:
            top, bottom = part.split("/")
            total += int(top) / int(bottom) if int(bottom) else 0
        else:
            total += float(part)
    return total


def _unit_at_start(text: str):
    """('tbsp', rest) if the text starts with a unit Slice'd knows, else (None, text)."""
    words = text.split(" ")
    for size in (2, 1):  # "fl oz" and "fluid ounces" before "oz"
        candidate = " ".join(words[:size])
        if len(words) < size:
            continue
        if size == 1 and candidate == "T":
            return "tbsp", " ".join(words[1:])  # capital T is tablespoon in recipe shorthand
        key = candidate.lower().rstrip(".,")
        if key in units.ALIASES:
            return units.ALIASES[key], " ".join(words[size:])
    return None, text


def _pull_parentheses(text: str):
    """('onion', ['4 oz, 113 g; peeled']) from 'onion ((4 oz, 113 g; peeled))'.

    Counts depth, so nested and doubled parentheses (some recipe plugins write
    "((Note 1))") come out whole. An unclosed "(" makes the rest of the line a note.
    """
    kept, notes, current, depth = [], [], "", 0
    for char in text:
        if char == "(":
            current = "" if depth == 0 else current + " "
            depth += 1
        elif char == ")":
            if depth == 0:
                continue  # a stray ")"
            depth -= 1
            if depth == 0:
                notes.append(current)
            else:
                current += " "
        elif depth:
            current += char
        else:
            kept.append(char)
    if depth:
        notes.append(current)
    cleaned = [" ".join(note.split()).strip(" ,;") for note in notes]
    return "".join(kept), [note for note in cleaned if note]


# After a comma, these start a note ("garlic, finely chopped"), not more of the name
# ("boneless, skinless chicken thighs"). Words ending in -ed or -ly count too.
NOTE_WORDS = {"to", "for", "at", "plus", "cut", "torn", "beaten", "about", "or", "as", "and", "room", "if",
              "such", "preferably", "optional", "frozen", "fresh", "ground", "see", "note", "divided", "into"}
# Endings of a name that are really notes: "oil plus extra for frying", "lemon wedges to serve".
NAME_TAIL = re.compile(r"\s+((?:plus|to serve|to taste|for serving|for garnish|for frying|for greasing|"
                       r"at room temperature)\b.*)$", flags=re.IGNORECASE)


# How it's prepared, at the start of a name: "toasted pine nuts" is pine nuts, toasted.
# Moved to the note so the name matches the inventory. ("Ground" and "crushed" stay:
# ground beef and crushed tomatoes are things you buy.)
PREP_PREFIX = re.compile(
    r"^((?:(?:finely|roughly|coarsely|thinly|freshly)\s+)?"
    r"(?:chopped|minced|diced|sliced|grated|toasted|melted|softened|packed|shredded|crumbled|cubed|peeled|beaten))"
    r"\s+(.+)$",
    flags=re.IGNORECASE,
)


def _starts_note(text: str) -> bool:
    words = text.split()
    first = words[0].lower().strip(".;:") if words else ""
    return first in NOTE_WORDS or first.endswith(("ed", "ly"))


def parse_ingredient_line(line: str) -> dict:
    """'1 1/2 cups all-purpose flour, sifted' ->
    {"name": "all-purpose flour", "quantity": 1.5, "unit": "cup", "preparation_note": "sifted", "optional": False}
    """
    text = clean_text(line)
    for symbol, fraction in UNICODE_FRACTIONS.items():
        text = re.sub(rf"(\d)\s*{symbol}", rf"\1 {fraction}", text)  # "1½" -> "1 1/2"
        text = text.replace(symbol, fraction)
    text = text.replace("⁄", "/").lstrip("-•* ").strip()
    text = re.sub(r"([a-zA-Z])\s*/\s*(\d)", r"\1 / \2", text)  # "200g/6oz" -> "200g / 6oz"

    notes = []
    optional = bool(re.search(r"\(?\boptional\b\)?", text, flags=re.IGNORECASE))
    if optional:
        text = re.sub(r",?\s*\(?\boptional\b\)?", "", text, flags=re.IGNORECASE).strip()

    quantity = None
    match = QUANTITY.match(text)
    if match:
        low = _number(match.group(1))
        high = _number(match.group(2)) if match.group(2) else None
        quantity = high if high and high > low else low  # "2 to 3 cloves": buy for 3
        if high and high > low:
            notes.append(f"{match.group(1)} to {match.group(2)}")
        text = text[match.end():]
        # "1 (14 oz) can tomatoes": the size in parentheses is a note.
        size = re.match(r"^\(([^)]*)\)\s*", text)
        if size:
            notes.append(size.group(1).strip())
            text = text[size.end():]

    unit = None
    if quantity is not None:
        words = text.split(" ", 1)
        if words[0].lower() in SIZES and len(words) > 1:  # "2 large eggs": size is a note
            notes.append(words[0].lower())
            text = words[1]
        unit, text = _unit_at_start(text)
        # "200 g / 6 oz chicken": the second measurement is the same amount again.
        text = re.sub(r"^/\s*[\d./ ]+\s*[a-zA-Z]+\.?\s*", "", text)
        # "1 1/2 cups plus 1 tbsp flour": add the second amount when the units convert.
        plus = re.match(rf"^plus\s+({NUMBER})\s*", text, flags=re.IGNORECASE)
        if plus:
            extra_unit, rest = _unit_at_start(text[plus.end():])
            extra = units.convert(_number(plus.group(1)), extra_unit, unit)
            if extra is not None:
                quantity = round(quantity + extra, 4)
                text = rest
        text = re.sub(r"^of\s+", "", text, flags=re.IGNORECASE)

    # Parentheses are notes: "onion (about 1 cup)".
    text, inside = _pull_parentheses(text)
    notes.extend(inside)

    # After a comma: a note ("garlic, minced"), or more name ("boneless, skinless chicken").
    parts = [part.strip() for part in text.split(",")]
    name_parts = [parts[0]]
    for index, part in enumerate(parts[1:], start=1):
        if _starts_note(part):
            notes.append(", ".join(p for p in parts[index:] if p))
            break
        name_parts.append(part)
    name = " ".join(" ".join(name_parts).split())
    tail = NAME_TAIL.search(name)
    if tail:
        notes.append(tail.group(1))
        name = name[:tail.start()]

    name = name.strip(" .;:-/")
    prep = PREP_PREFIX.match(name)
    if prep:
        notes.insert(0, prep.group(1).lower())
        name = prep.group(2)

    notes = list(dict.fromkeys(n for n in notes if n))  # drop repeats, keep the order
    return {
        "name": name[:100],
        "quantity": quantity if quantity and quantity <= 10000 else None,
        "unit": unit if quantity else None,
        "preparation_note": ", ".join(notes)[:200] or None,
        "optional": optional,
    }


def _split_salt_and_pepper(item: dict) -> list:
    """'salt and pepper, to taste' is two ingredients, and both are staples."""
    if normalize_name(item["name"]) in {"salt and pepper", "salt and black pepper", "kosher salt and pepper",
                                        "salt and freshly ground black pepper", "salt & pepper"}:
        return [dict(item, name="salt", quantity=None, unit=None),
                dict(item, name="black pepper", quantity=None, unit=None)]
    return [item]


def parse_ingredients(lines: list) -> tuple:
    """(ingredients, warnings). Merges an ingredient listed twice (salt for the dough
    and salt for the filling), since a recipe lists each ingredient once in Slice'd."""
    ingredients, warnings, by_key = [], [], {}
    for line in lines:
        original = clean_text(line)
        if not original:
            continue
        for item in _split_salt_and_pepper(parse_ingredient_line(original)):
            if not item["name"]:
                warnings.append(f"Skipped \"{original}\": couldn't find an ingredient name.")
                continue
            key = match_key(normalize_name(item["name"]))
            if key not in by_key:
                by_key[key] = item
                ingredients.append(item)
                continue
            first = by_key[key]
            added = (units.convert(item["quantity"], item["unit"], first["unit"])
                     if first["quantity"] and item["quantity"] else None)
            if added is not None:
                first["quantity"] = round(first["quantity"] + added, 4)
            elif first["quantity"] or item["quantity"]:
                warnings.append(f"\"{item['name']}\" is listed more than once. Slice'd kept the first amount; check it.")
    return ingredients, warnings


# ---------- The whole recipe ----------

def to_draft(data: dict, source_url: str) -> dict:
    warnings = []
    ingredient_lines = data.get("recipeIngredient") or data.get("ingredients") or []
    if isinstance(ingredient_lines, str):
        ingredient_lines = [ingredient_lines]
    ingredients, ingredient_warnings = parse_ingredients(ingredient_lines)

    prep = parse_minutes(data.get("prepTime"))
    cook = parse_minutes(data.get("cookTime"))
    total = parse_minutes(data.get("totalTime"))
    if cook is None and total is not None:
        cook = max(total - (prep or 0), 0)
    if prep is None and cook is None:
        warnings.append("The site didn't give cooking times. Fill them in.")

    servings = parse_servings(data.get("recipeYield"))
    if servings is None:
        warnings.append("The site didn't say how many servings. Slice'd guessed 2.")

    steps = parse_steps(data.get("recipeInstructions"))
    if not steps:
        warnings.append("The site didn't include the steps. Add them before saving.")
    if not ingredients:
        warnings.append("The site didn't include ingredients. Add them before saving.")

    cuisine = _first_text(data.get("recipeCuisine"))
    return {
        "title": clean_text(data.get("name"))[:200],
        "description": clean_text(data.get("description"))[:1000] or None,
        "cuisine": cuisine[:50] or None,
        "servings": min(servings or 2, 100),
        "prep_time": min(prep or 0, 1440),
        "cook_time": min(cook or 0, 1440),
        "instructions": "\n".join(steps)[:10000],
        "ingredients": ingredients,
        "image_url": image_url(data.get("image")),
        "source_url": source_url,
        "warnings": warnings + ingredient_warnings,
    }


def draft_from_data(data, url: str) -> dict:
    """For the Safari button: the browser already read the recipe data from the page."""
    url = check_url(url)
    if not isinstance(data, dict) or not _is_recipe(data):
        raise ImportFailed("That page's recipe data couldn't be read. You can still type the recipe in.")
    return to_draft(data, url)


def import_recipe(url: str) -> dict:
    url = check_url(url)
    data = find_recipe_data(fetch_page(url))
    if data is None:
        raise ImportFailed("That page doesn't include recipe data Slice'd can read. You can still type the recipe in.")
    return to_draft(data, url)
