"""Automated checks for the design rules in DEVELOPMENT_PLAN.md.

These catch banned patterns (gradients, animations, emojis, em dashes...) if they
ever sneak into the frontend. Rules that need human judgment are not checked here.
"""
import re

import pytest

from app.config import FRONTEND_DIR

FRONTEND_FILES = sorted(
    p for p in FRONTEND_DIR.rglob("*") if p.suffix in {".html", ".css", ".js", ".svg"}
)

# Each rule: (description, regex). A match anywhere in the frontend is a failure.
BANNED = [
    ("em or en dash", r"[—–]|&mdash;|&ndash;"),
    ("emoji", r"[\U0001F300-\U0001FAFF☀-➿]"),
    ("gradient", r"gradient\("),
    ("italic text", r"font-style:\s*italic|<em>|<i>"),
    ("Inter / Space Grotesk / Instrument Serif font", r"\bInter\b|Space Grotesk|Instrument Serif"),
    ("CSS transition (hover fades)", r"\btransition\s*:"),
    ("CSS animation", r"\banimation\s*:|@keyframes"),
    ("glassmorphism blur", r"backdrop-filter"),
    ("Lucide icons", r"lucide"),
]


@pytest.mark.parametrize("description,pattern", BANNED, ids=[b[0] for b in BANNED])
def test_frontend_has_no_banned_patterns(description, pattern):
    offenders = []
    for path in FRONTEND_FILES:
        for line_no, line in enumerate(path.read_text().splitlines(), start=1):
            if re.search(pattern, line, flags=re.IGNORECASE):
                offenders.append(f"{path.relative_to(FRONTEND_DIR)}:{line_no}")
    assert not offenders, f"Found {description} in: {offenders}"


def test_every_page_has_favicon_and_legal_links():
    for page in FRONTEND_DIR.glob("*.html"):
        html = page.read_text()
        assert 'rel="icon"' in html, f"{page.name} is missing the favicon"
        assert 'href="/terms.html"' in html, f"{page.name} is missing the Terms link"
        assert 'href="/privacy.html"' in html, f"{page.name} is missing the Privacy link"


@pytest.mark.parametrize("path", ["/terms.html", "/privacy.html", "/favicon.svg"])
def test_legal_pages_and_favicon_are_served(client, path):
    assert client.get(path).status_code == 200


def test_scripts_and_styles_share_one_cache_version():
    """Every page links /js and /css with the same ?v=N, so bumping N forces browsers to
    download fresh copies even if they cached an old file before no-cache was added."""
    import re as _re

    versions = set()
    for page in FRONTEND_DIR.glob("*.html"):
        for ref in _re.findall(r'(?:src|href)="(/(?:js|css)/[^"]+)"', page.read_text()):
            match = _re.search(r"\?v=(\d+)$", ref)
            assert match, f"{page.name}: {ref} has no ?v= version"
            versions.add(match.group(1))
    assert len(versions) == 1, f"Pages use different versions: {versions}"


# ---------- Color contrast (WCAG AA) ----------

def _color_tokens():
    """The --name: #hex tokens from :root in style.css."""
    css = (FRONTEND_DIR / "css" / "style.css").read_text()
    root = css[css.index(":root {"):css.index("}", css.index(":root {"))]
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", root))


def _contrast(foreground, background):
    def luminance(hex_color):
        channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


# Every text-on-background pairing the pages use. Normal text needs 4.5:1.
TEXT_PAIRS = [
    ("text", "bg"), ("text", "surface"), ("text-muted", "bg"), ("text-muted", "surface"),
    ("accent", "bg"), ("accent", "surface"), ("accent-dark", "surface"), ("accent-dark", "accent-soft"),
    ("ok", "surface"), ("warn", "surface"), ("warn", "warn-bg"), ("warn", "bg"),
    ("error", "surface"), ("error", "error-bg"), ("text", "info-bg"),
]


@pytest.mark.parametrize("foreground,background", TEXT_PAIRS, ids=[f"{f} on {b}" for f, b in TEXT_PAIRS])
def test_text_colors_meet_wcag_aa(foreground, background):
    tokens = _color_tokens()
    ratio = _contrast(tokens[foreground], tokens[background])
    assert ratio >= 4.5, f"--{foreground} on --{background} is {ratio:.2f}:1"


@pytest.mark.parametrize("corner", ["have-all", "have-half", "have-few"])
def test_stamp_colors_are_visible(corner):
    # WCAG 1.4.11: shapes that carry meaning need 3:1 against what's next to them.
    tokens = _color_tokens()
    for background in ["surface"]:  # stamps sit on white ticket paper
        ratio = _contrast(tokens[corner], tokens[background])
        assert ratio >= 3, f"--{corner} on --{background} is {ratio:.2f}:1"


def test_white_button_text_meets_wcag_aa():
    tokens = _color_tokens()
    for background in ("accent", "accent-dark"):
        assert _contrast("#ffffff", tokens[background]) >= 4.5, background


def test_form_borders_are_visible():
    # WCAG 1.4.11: the edges of inputs need 3:1 against what's around them.
    tokens = _color_tokens()
    assert _contrast(tokens["input-border"], tokens["surface"]) >= 3
