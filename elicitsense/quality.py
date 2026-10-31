"""Rule-based requirement quality checks (deterministic, so they are auditable)."""

from __future__ import annotations

import re

# Terms that make a requirement unverifiable unless a measurable target is given.
AMBIGUOUS_TERMS = [
    "fast", "quick", "quickly", "easy", "easy to use", "user-friendly", "user friendly",
    "intuitive", "simple", "seamless", "efficient", "flexible", "robust", "modern",
    "responsive", "as soon as possible", "etc",
]


def check(statement: str, req_type: str, acceptance: list[str]) -> list[dict]:
    issues = []
    lower = statement.lower()
    has_number = bool(re.search(r"\d", statement))
    for term in AMBIGUOUS_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", lower) and not has_number:
            issues.append({"kind": "ambiguous_term", "detail": f'"{term}" has no measurable target'})
    if req_type in ("functional", "non_functional") and not acceptance:
        issues.append({"kind": "missing_acceptance", "detail": "no acceptance criteria were discussed"})
    if re.search(r"\b(and|or)\b.*\b(and|or)\b", lower) and len(statement.split()) > 30:
        issues.append({"kind": "compound", "detail": "long statement with several clauses; consider splitting"})
    return issues
