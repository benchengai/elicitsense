"""Check that every cited quote actually appears in its cited segment."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

FUZZY_THRESHOLD = 0.9

_PUNCT_RE = re.compile(r"[^a-z0-9$%' ]+")


def normalise(text: str) -> str:
    text = text.lower().replace("’", "'").replace("‘", "'")
    text = _PUNCT_RE.sub(" ", text)
    return " ".join(text.split())


def quote_matches(quote: str, segment_text: str) -> bool:
    q, s = normalise(quote), normalise(segment_text)
    if not q:
        return False
    if q in s:
        return True
    # Tolerate tiny transcription-level differences (e.g. "twenty four" vs "twenty-four").
    qw, sw = q.split(), s.split()
    n = len(qw)
    if n == 0 or n > len(sw):
        return SequenceMatcher(None, q, s).ratio() >= FUZZY_THRESHOLD
    return any(
        SequenceMatcher(None, q, " ".join(sw[i:i + n])).ratio() >= FUZZY_THRESHOLD
        for i in range(len(sw) - n + 1)
    )
