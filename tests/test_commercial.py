"""Tests for commercial management."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from rtv.commercial import (
    parse_selection,
    get_category_search_query,
    save_search_results,
    load_search_results,
    scan_commercial_inventory,
    _sanitize_filename,
    DownloadError,
    LAST_SEARCH_FILE,
)
from rtv.config import CommercialConfig, CommercialCategory, BlockDuration


class TestParseSelection:
    def test_all(self) -> None:
        assert parse_selection("all", 5) == [0, 1, 2, 3, 4]

    def test_all_shorthand(self) -> None:
        assert parse_selection("a", 5) == [0, 1, 2, 3, 4]

    def test_none(self) -> None:
        assert parse_selection("none", 5) == []

    def test_empty_string(self) -> None:
        assert parse_selection("", 5) == []

    def test_single_number(self) -> None:
        assert parse_selection("3", 5) == [2]  # 1-based to 0-based

    def test_comma_separated(self) -> None:
        assert parse_selection("1,3,5", 5) == [0, 2, 4]

    def test_range(self) -> None:
        assert parse_selection("2-4", 5) == [1, 2, 3]

    def test_mixed(self) -> None:
        assert parse_selection("1,3-5,7", 10) == [0, 2, 3, 4, 6]

    def test_out_of_bounds_ignored(self) -> None:
        assert parse_selection("1,10,20", 5) == [0]

    def test_duplicates_removed(self) -> None:
        assert parse_selection("1,1,2,2", 5) == [0, 1]

    def test_whitespace_handled(self) -> None:
        assert parse_selection(" 1 , 3 ", 5) == [0, 2]


class TestCategorySearchQuery:
    def test_known_category(self) -> None:
        config = CommercialConfig(
            library_path="C:\\test",
            categories=[
                CommercialCategory(name="80s", search_terms=["80s commercials", "1980s TV ads"]),
            ],
        )
        assert get_category_search_query("80s", config) == "80s commercials"

    def test_known_category_case_insensitive(self) -> None:
        config = CommercialConfig(
            library_path="C:\\test",
            categories=[
                CommercialCategory(name="PSAs", search_terms=["vintage PSA"]),
            ],
        )
        assert get_category_search_query("psas", config) == "vintage PSA"

    def test_unknown_category_uses_name(self) -> None:
        config = CommercialConfig(library_path="C:\\test")
        assert get_category_search_query("90s toys", config) == "90s toys"

    def test_category_no_search_terms(self) -> None:
        config = CommercialConfig(
            library_path="C:\\test",
            categories=[
                CommercialCategory(name="misc"),
            ],
        )
        assert get_category_search_query("misc", config) == "misc"


class TestSearchResultsPersistence:
    def test_save_and_load(self, tmp_path: Path) -> None:
        results = [
            {"title": "Test Video", "duration": 30, "channel": "TestCh", "url": "https://example.com", "id": "abc"},
        ]
        with patch("rtv.commercial.LAST_SEARCH_FILE", tmp_path / "search.json"):
            save_search_results(results)
        with patch("rtv.commercial.LAST_SEARCH_FILE", tmp_path / "search.json"):
            loaded = load_search_results()
        assert loaded == results

    def test_load_missing_file(self, tmp_path: Path) -> None:
        with patch("rtv.commercial.LAST_SEARCH_FILE", tmp_path / "nonexistent.json"):
            assert load_search_results() == []


class TestSanitizeFilename:
    def test_removes_special_chars(self) -> None:
        assert _sanitize_filename('Test: "Video" <file>') == "Test Video file"

    def test_strips_dots_and_spaces(self) -> None:
        assert _sanitize_filename("  ...test... ") == "test"

    def test_truncates_long_names(self) -> None:
        long_name = "x" * 300
        assert len(_sanitize_filename(long_name)) == 200

    def test_empty_becomes_untitled(self) -> None:
        assert _sanitize_filename("") == "untitled"
        assert _sanitize_filename("...") == "untitled"


class TestDownloadError:
    def test_download_error_attributes(self) -> None:
        err = DownloadError("https://example.com/video", "Age-restricted")
        assert err.url == "https://example.com/video"
        assert err.reason == "Age-restricted"
        assert "Age-restricted" in str(err)

    def test_download_error_is_exception(self) -> None:
        with pytest.raises(DownloadError):
            raise DownloadError("url", "reason")


class TestScanCommercialInventory:
    def test_empty_path(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent"
        result = scan_commercial_inventory(str(nonexistent), [])
        assert result == []

    def test_empty_directory(self, tmp_path: Path) -> None:
        result = scan_commercial_inventory(str(tmp_path), [])
        assert result == []

    def test_finds_categories(self, tmp_path: Path) -> None:
        # Create fake category subdirs with mp4 files
        cat_dir = tmp_path / "80s"
        cat_dir.mkdir()
        (cat_dir / "ad1.mp4").write_bytes(b"\x00" * 100)
        (cat_dir / "ad2.mp4").write_bytes(b"\x00" * 100)

        cat_dir2 = tmp_path / "90s"
        cat_dir2.mkdir()
        (cat_dir2 / "ad3.mp4").write_bytes(b"\x00" * 100)

        with patch("rtv.commercial._get_video_duration", return_value=30.0):
            result = scan_commercial_inventory(str(tmp_path), [])

        assert len(result) == 2
        names = [r["name"] for r in result]
        assert "80s" in names
        assert "90s" in names
        cat_80s = next(r for r in result if r["name"] == "80s")
        assert cat_80s["count"] == 2
        assert cat_80s["duration"] == 60.0
