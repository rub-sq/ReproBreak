import re
import sqlite3
from collections import Counter

from config import LB_PATH

# Attributes / data-* attributes that signal test-data selectors
TEST_DATA_ATTRS = re.compile(
    r"""data-(?:test(?:id)?|cy|qa|automation|e2e)""",
    re.IGNORECASE,
)

# Matches plain quoted strings that look like human-readable text
#   e.g.  "Submit",  'Click here',  `Hello world`
TEXT_LITERAL = re.compile(
    r"""^["'`]\s*[A-Za-z][A-Za-z0-9 ,.'!?–\-]{1,120}\s*["'`]$"""
)

# CSS class selectors: start with a dot or contain compound classes
CSS_CLASS = re.compile(r"""(?:^|["'`])\.[a-zA-Z_\-][a-zA-Z0-9_\-]*""")

# CSS attribute selectors  [attr=…]  or pseudo-classes  :nth-child(…)
CSS_ATTR_OR_PSEUDO = re.compile(r"""\[.+?\]|::?[a-zA-Z\-]+""")

# HTML ID selectors: #id
HTML_ID = re.compile(r"""["'`]#[a-zA-Z_\-][a-zA-Z0-9_\-]*["'`]?""")

# Tag-only selectors  e.g.  'div',  'button',  'input'
TAG_ONLY = re.compile(r"""^["'`][a-zA-Z][a-zA-Z0-9]*["'`]$""")


def _strip_outer_quotes(value: str) -> str:
    """Remove one layer of surrounding quotes/backticks if present."""
    value = value.strip()
    if len(value) >= 2 and value[0] in ('"', "'", "`") and value[-1] == value[0]:
        return value[1:-1]
    return value


def categorize(raw_locator: str) -> str:
    """
    Categorize a raw locator string into one of:
        CSS | HTML_ID | TEST_DATA | TEXT | ELSE
    """
    v = raw_locator.strip()
    inner = _strip_outer_quotes(v)
    parameter = v[v.find('(') + 1:].strip()

    # ── TEST_DATA ──────────────────────────────────────────────────────────────
    # getByTestId calls are always test-data
    if "getByTestId" in raw_locator:
        return "TEST_DATA"
    # data-test*, data-cy, data-qa, data-automation, data-e2e attributes
    if TEST_DATA_ATTRS.search(inner):
        return "TEST_DATA"

    # ── TEXT ──────────────────────────────────────────────────────────────────
    # getByText calls are always text
    if "getByText" in raw_locator:
        return "TEXT"
    # cy.contains() with a plain string argument is text-based
    if "cy.contains" in raw_locator:
        return "TEXT"
    # Plain human-readable string literal (no CSS/HTML special chars)
    if TEXT_LITERAL.match(v) and not re.search(r"[.#\[\]:>+~]", inner):
        return "TEXT"
    if parameter.startswith("'text=") or parameter.startswith("\"text=") or parameter.startswith("`text="):
        return "TEXT"

    # ── HTML_ID ───────────────────────────────────────────────────────────────
    if HTML_ID.search(v):
        return "HTML_ID"
    # bare  #id  without surrounding quotes (e.g. variable passed as string)
    if re.match(r"^#[a-zA-Z_\-][a-zA-Z0-9_\-]*$", inner):
        return "HTML_ID"

    # ── HTML_Attributes ───────────────────────────────────────────────────────
    if "getByRole" in raw_locator:
        return "HTML_ATT"


    # ── CSS ───────────────────────────────────────────────────────────────────
    if CSS_CLASS.search(v):
        return "CSS"
    if CSS_ATTR_OR_PSEUDO.search(inner):
        return "CSS"
    # Tag-only selector counts as CSS
    if TAG_ONLY.match(v):
        return "CSS"
    # XPath-style or complex selectors that contain CSS combinators
    if re.search(r"""[>+~]\s*[a-zA-Z.*#\[]""", inner):
        return "CSS"
    if parameter.startswith("'") or parameter.startswith("\"") and not parameter[1] == "@":
        return "CSS"

    # ── ELSE ──────────────────────────────────────────────────────────────────
    return "ELSE"

con = sqlite3.connect(LB_PATH)
cur = con.cursor()

cur.execute("SELECT old_locator, new_locator FROM locator_change")
locator_breaks = cur.fetchall()

locator_break_classification = []
for locator_break in locator_breaks:
    locator_break_types = {
        "old_locator": locator_break[0],
        "old_locator_type": categorize(locator_break[0]),
        "new_locator": locator_break[1],
        "new_locator_type": categorize(locator_break[1])}
    locator_break_classification.append(locator_break_types)
old_locator_type_counts = Counter([locator_break["old_locator_type"] for locator_break in locator_break_classification])
new_locator_type_counts = Counter([locator_break["new_locator_type"] for locator_break in locator_break_classification])

text_aria = [(locator_break['old_locator'], locator_break['new_locator']) for locator_break in locator_break_classification if locator_break['old_locator_type'] == "TEXT" and locator_break['new_locator_type'] == "TEST_DATA"]

type_changes = [f"{locator_break['old_locator_type']}-{locator_break['new_locator_type']}" for locator_break in locator_break_classification]
locator_break_type_change_counts = Counter(type_changes)

print(old_locator_type_counts)
print(new_locator_type_counts)
for x, y in locator_break_type_change_counts.items():
    print(x, y)