"""Duplicate detection for lessons: tokens, coverage and match tests.

Pure functions. No database access. A candidate is a plain dict
``{"id": int, "full": str, "rule": str}``, where ``full`` is what_happened, general_rule and
proposal joined by spaces, and ``rule`` is general_rule. The new lesson uses the same shape with
``id`` set to None.
"""

from __future__ import annotations

import functools
import importlib.resources
import re

MIN_TOKEN_LEN = 4
SIMILAR_MIN_SHARED = 2
FULL_MIN_SHARED = 4
FULL_MIN_COVERAGE = 0.30
RULE_MIN_SHARED = 3
RULE_MIN_COVERAGE = 0.50

_WORD = re.compile(r"[^\W_]+")


@functools.cache
def load_stopwords() -> frozenset[str]:
    """Return the English stopwords shipped in ``chanchi/data/stopwords_en.txt`` (read once)."""
    text = (importlib.resources.files("chanchi") / "data" / "stopwords_en.txt").read_text(
        encoding="utf-8"
    )
    return frozenset(
        line.strip().lower()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def tokens(text: str) -> set[str]:
    """Lowercase, split on anything that is not a letter or digit, and keep tokens of
    ``MIN_TOKEN_LEN`` or more characters that are not stopwords."""
    stop = load_stopwords()
    return {
        word
        for word in _WORD.findall(text.lower())
        if len(word) >= MIN_TOKEN_LEN and word not in stop
    }


def coverage(a: set[str], b: set[str]) -> float:
    """``|a & b| / min(|a|, |b|)``; 0.0 when either set is empty."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def similar(text: str, candidates: list[dict], limit: int = 5) -> list[dict]:
    """Return up to ``limit`` candidates that look like ``text``, as ``{id, coverage, shared}``.

    For each candidate, the full-text test and the rule test are both computed and the one with
    the higher coverage is kept (ties: more shared tokens). ``shared`` is that test's count.
    Only candidates sharing at least ``SIMILAR_MIN_SHARED`` tokens are returned, ordered by
    coverage (highest first), then shared count (highest first), then id (lowest first).
    """
    wanted = tokens(text)
    found = []
    for candidate in candidates:
        full = _overlap(wanted, tokens(candidate["full"]))
        rule = _overlap(wanted, tokens(candidate["rule"]))
        shared, cov = max(full, rule, key=lambda pair: (pair[1], pair[0]))
        if shared >= SIMILAR_MIN_SHARED:
            found.append({"id": candidate["id"], "coverage": cov, "shared": shared})
    found.sort(key=lambda item: (-item["coverage"], -item["shared"], item["id"]))
    return found[:limit]


def _overlap(a: set[str], b: set[str]) -> tuple[int, float]:
    """Return ``(shared count, coverage)`` for two token sets."""
    return len(a & b), coverage(a, b)


def matches(new: dict, candidate: dict) -> dict | None:
    """Return the first test that matches ``new`` against ``candidate``, or None.

    The full-text test runs first: at least ``FULL_MIN_SHARED`` shared tokens and coverage of at
    least ``FULL_MIN_COVERAGE`` over ``full``. Then the rule test: at least ``RULE_MIN_SHARED``
    shared tokens and coverage of at least ``RULE_MIN_COVERAGE`` over ``rule``.

    On a match, returns a dict::

        {"id": candidate id, "test": "full" | "rule", "coverage": float,
         "shared": sorted list of the shared tokens for that test}

    The shared count is ``len(result["shared"])``.
    """
    new_full, new_rule = tokens(new["full"]), tokens(new["rule"])
    cand_full, cand_rule = tokens(candidate["full"]), tokens(candidate["rule"])

    full_shared = new_full & cand_full
    full_cov = coverage(new_full, cand_full)
    if len(full_shared) >= FULL_MIN_SHARED and full_cov >= FULL_MIN_COVERAGE:
        return _match_result(candidate, "full", full_cov, full_shared)

    rule_shared = new_rule & cand_rule
    rule_cov = coverage(new_rule, cand_rule)
    if len(rule_shared) >= RULE_MIN_SHARED and rule_cov >= RULE_MIN_COVERAGE:
        return _match_result(candidate, "rule", rule_cov, rule_shared)

    return None


def _match_result(candidate: dict, test: str, cov: float, shared: set[str]) -> dict:
    return {"id": candidate["id"], "test": test, "coverage": cov, "shared": sorted(shared)}


def blocking_match(new: dict, candidates: list[dict]) -> dict | None:
    """Of the candidates that match ``new`` (see ``matches``), return the one with the highest
    coverage; ties go to the lowest id. Returns None when nothing matches."""
    best = None
    for candidate in candidates:
        found = matches(new, candidate)
        if found is None:
            continue
        if best is None or (-found["coverage"], found["id"]) < (-best["coverage"], best["id"]):
            best = found
    return best
