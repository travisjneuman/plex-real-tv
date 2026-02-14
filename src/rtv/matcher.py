"""Fuzzy show name matching using rapidfuzz."""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz, process


MATCH_THRESHOLD = 65


@dataclass
class MatchResult:
    """A fuzzy match result with the matched title and confidence score."""

    title: str
    score: float
    index: int


def fuzzy_match(
    query: str, choices: list[str], limit: int = 5
) -> list[MatchResult]:
    """Match a query against a list of choices using fuzzy string matching.

    Returns matches sorted by score descending, filtered to those above the threshold.
    """
    if not choices:
        return []
    results = process.extract(
        query, choices, scorer=fuzz.WRatio, limit=limit
    )
    return [
        MatchResult(title=title, score=score, index=idx)
        for title, score, idx in results
        if score >= MATCH_THRESHOLD
    ]


def best_match(query: str, choices: list[str]) -> MatchResult | None:
    """Return the single best match above threshold, or None."""
    matches = fuzzy_match(query, choices, limit=1)
    return matches[0] if matches else None


def exact_match(query: str, choices: list[str]) -> str | None:
    """Return an exact case-insensitive match, or None."""
    query_lower = query.lower()
    for choice in choices:
        if choice.lower() == query_lower:
            return choice
    return None
