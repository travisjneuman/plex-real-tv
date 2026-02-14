"""Tests for fuzzy matching."""

from __future__ import annotations

import pytest

from rtv.matcher import fuzzy_match, best_match, exact_match, MatchResult


SHOW_LIST = [
    "The Office (US)",
    "The Office (UK)",
    "Seinfeld",
    "The X-Files",
    "Breaking Bad",
    "Friends",
    "Game of Thrones",
]


class TestExactMatch:
    def test_exact_case_sensitive(self) -> None:
        assert exact_match("Seinfeld", SHOW_LIST) == "Seinfeld"

    def test_exact_case_insensitive(self) -> None:
        assert exact_match("seinfeld", SHOW_LIST) == "Seinfeld"

    def test_exact_no_match(self) -> None:
        assert exact_match("Lost", SHOW_LIST) is None

    def test_exact_empty_choices(self) -> None:
        assert exact_match("anything", []) is None


class TestFuzzyMatch:
    def test_close_match(self) -> None:
        matches = fuzzy_match("the office", SHOW_LIST)
        assert len(matches) >= 1
        # Should find at least one "The Office" variant
        titles = [m.title for m in matches]
        assert any("Office" in t for t in titles)

    def test_fuzzy_office_us(self) -> None:
        matches = fuzzy_match("office us", SHOW_LIST)
        if matches:
            assert matches[0].title == "The Office (US)"

    def test_no_match_below_threshold(self) -> None:
        matches = fuzzy_match("zzzznotashow", SHOW_LIST)
        assert matches == []

    def test_multiple_candidates_ranked(self) -> None:
        matches = fuzzy_match("the office", SHOW_LIST, limit=5)
        # Both Office variants should be in results
        titles = [m.title for m in matches]
        office_matches = [t for t in titles if "Office" in t]
        assert len(office_matches) >= 1

    def test_empty_choices(self) -> None:
        assert fuzzy_match("anything", []) == []

    def test_score_is_positive(self) -> None:
        matches = fuzzy_match("Breaking Bad", SHOW_LIST)
        assert all(m.score > 0 for m in matches)

    def test_index_is_correct(self) -> None:
        matches = fuzzy_match("Seinfeld", SHOW_LIST)
        assert matches[0].index == SHOW_LIST.index("Seinfeld")


class TestBestMatch:
    def test_returns_best(self) -> None:
        result = best_match("seinfeld", SHOW_LIST)
        assert result is not None
        assert result.title == "Seinfeld"

    def test_returns_none_no_match(self) -> None:
        result = best_match("zzzznotashow", SHOW_LIST)
        assert result is None
