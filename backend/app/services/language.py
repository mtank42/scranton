"""Answer-language pinning: a tiny French/English detector.

Why a heuristic and not a library: the POC needs to tell French from
English (the owner's two working languages), nothing more. A stopword
count is deterministic, dependency-free and fully testable offline.
The detected value is only a PIN injected into prompts, so a wrong
guess degrades gracefully to the previous behavior (the model decides).
"""

import re

# Disjoint marker sets on purpose: a word appearing in both languages
# ("on", "a", "or" as a noun...) is a vote for neither.
FRENCH_MARKERS = frozenset(
    """le la les un une des du de et est sont avec pour dans que qui pas
    sur au aux ce cette son sa ses il elle nous vous je tu ne se etre
    ete fait faire plus mais ou donc quand comme tres aussi en""".split()
) | frozenset(("à", "où", "été", "être", "très"))

ENGLISH_MARKERS = frozenset(
    """the an of and is are was were with for in that which not at this
    his her its he she we you i been be did done but so when as very
    also to what have has had from by will would about""".split()
)

_WORDS = re.compile(r"[a-zàâäçéèêëîïôöùûüÿœ']+")
_FRENCH_ACCENTS = re.compile(r"[àâäçéèêëîïôöùûüÿœ]")


def dominant_language(text: str) -> str:
    """Return 'French' or 'English' for the given text.

    Ties (including marker-free text such as bare names and dates) fall
    back to the accent test: any French accented letter tips the scale.
    """
    lowered = text.lower()
    words = _WORDS.findall(lowered)
    french = sum(1 for word in words if word in FRENCH_MARKERS)
    english = sum(1 for word in words if word in ENGLISH_MARKERS)
    if french == english:
        return "French" if _FRENCH_ACCENTS.search(lowered) else "English"
    return "French" if french > english else "English"
