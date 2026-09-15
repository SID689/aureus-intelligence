"""
app/core/copy.py
------------------
Punctuation house style for text a reader sees.

The product's copy uses no em dashes. Deterministic text follows the rule
where it is written; this applies the same rule to text a language model
returns, since a model cannot be relied on to follow an instruction every
time. The rules match the one-off rewrite of the codebase's own copy:

  * two dashes around a short aside become commas, or parentheses when
    the aside is itself a list;
  * a dash before a continuation word (but, and, which...) becomes a comma;
  * any other dash becomes a colon, or a comma when the sentence already
    has a colon;
  * a dash between two digits is a range and becomes an en dash.
"""

import re

_CONT = {
    "but", "and", "or", "nor", "which", "who", "whose", "that", "not", "using", "including", "so", "because",
    "yet", "while", "rather", "then", "only", "even", "especially", "typically", "often", "usually", "plus",
    "instead", "though", "although", "unless", "until", "whereas", "where", "when", "with", "without", "as",
}

_PAIR = re.compile(r"([\w)\]*%'\"’])[ \t]*—[ \t]*([^—.!?\n\"`]{2,140}?)[ \t]*—[ \t]*([\w(\[*'\"‘$])")
_SINGLE = re.compile(r"([^\s—])[ \t]*—([ \t\n]*)(?=[^\s—])")


def plain_punctuation(text: str) -> str:
    if not text or "—" not in text:
        return text

    def pair(m: re.Match) -> str:
        aside = m.group(2).strip()
        if len(aside.split()) > 14 or re.search(r"[.!?:;]", aside):
            return m.group(0)
        if "," in aside:
            return f"{m.group(1)} ({aside}) {m.group(3)}"
        return f"{m.group(1)}, {aside}, {m.group(3)}"

    def single(m: re.Match) -> str:
        before, ws = m.group(1), m.group(2)
        rest = m.string[m.end():]
        if before.isdigit() and rest[:1].isdigit():
            return f"{before}–"
        word = re.match(r"[A-Za-z']+", rest)
        start = max(m.string.rfind(c, 0, m.start()) for c in ".!?\n")
        ends = [i for i in (m.string.find(c, m.end()) for c in ".!?\n") if i != -1]
        sentence = m.string[start + 1:(min(ends) if ends else len(m.string))]
        continuing = bool(word) and word.group(0).lower() in _CONT
        punct = "," if (continuing or ":" in sentence) else ":"
        return f"{before}{punct}{ws[ws.index(chr(10)):] if chr(10) in ws else ' '}"

    text = _PAIR.sub(pair, text)
    text = _SINGLE.sub(single, text)
    # A dash left at either end of the text has nothing to join.
    return re.sub(r"^\s*—\s*|\s*—\s*$", "", text).replace("—", ",")
