"""Tests for config module."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from rtv.config import (
    RTVConfig,
    PlexConfig,
    ShowConfig,
    CommercialConfig,
    CommercialCategory,
    BlockDuration,
    PlaylistConfig,
    HistoryEntry,
    DEFAULT_SHOWS,
    load_config,
    save_config,
)


def _make_config(**overrides: object) -> RTVConfig:
    """Create a config with sensible defaults, overriding as needed."""
    defaults: dict[str, object] = {
        "plex": PlexConfig(url="http://localhost:32400", token="test-token", tv_libraries=["TV Shows"]),
        "shows": [],
        "commercials": CommercialConfig(
            library_name="RealTV Commercials",
            library_path="D:\\Media\\Commercials",
            block_duration=BlockDuration(min=30, max=120),
        ),
        "playlist": PlaylistConfig(),
    }
    defaults.update(overrides)
    return RTVConfig(**defaults)  # type: ignore[arg-type]


class TestRTVConfig:
    def test_valid_config_creation(self) -> None:
        config = _make_config()
        assert config.plex.url == "http://localhost:32400"
        assert config.plex.token == "test-token"
        assert config.playlist.default_name == "Real TV"
        assert config.playlist.episodes_per_generation == 30
        assert config.playlist.commercial_frequency == 1

    def test_default_values(self) -> None:
        config = RTVConfig(
            plex=PlexConfig(token="tok"),
        )
        assert config.plex.url == "http://localhost:32400"
        assert config.plex.tv_libraries == ["TV Shows"]
        assert config.shows == []
        assert config.commercials.library_name == "RealTV Commercials"
        assert config.commercials.library_path == "F:\\Commercials"
        assert config.commercials.block_duration.min == 30
        assert config.commercials.block_duration.max == 120
        assert config.playlist.default_name == "Real TV"
        assert config.playlist.sort_by == "premiere_year"

    def test_show_config_defaults(self) -> None:
        show = ShowConfig(name="Test Show")
        assert show.library == "TV Shows"
        assert show.current_season == 1
        assert show.current_episode == 1

    def test_commercial_category_defaults(self) -> None:
        cat = CommercialCategory(name="80s")
        assert cat.search_terms == []
        assert cat.weight == 1.0

    def test_block_duration_validation(self) -> None:
        bd = BlockDuration(min=60, max=180)
        assert bd.min == 60
        assert bd.max == 180

    def test_block_duration_rejects_zero(self) -> None:
        with pytest.raises(Exception):
            BlockDuration(min=0, max=300)

    def test_block_duration_rejects_min_gt_max(self) -> None:
        with pytest.raises(ValueError, match="must be <= max"):
            BlockDuration(min=300, max=60)

    def test_playlist_config_rejects_zero_episodes(self) -> None:
        with pytest.raises(Exception):
            PlaylistConfig(episodes_per_generation=0)

    def test_playlist_config_rejects_zero_frequency(self) -> None:
        with pytest.raises(Exception):
            PlaylistConfig(commercial_frequency=0)

    def test_commercial_category_rejects_zero_weight(self) -> None:
        with pytest.raises(Exception):
            CommercialCategory(name="test", weight=0)

    def test_commercial_category_rejects_negative_weight(self) -> None:
        with pytest.raises(Exception):
            CommercialCategory(name="test", weight=-1.0)


class TestURLValidation:
    def test_valid_http_url(self) -> None:
        config = PlexConfig(url="http://192.168.1.100:32400", token="t")
        assert config.url == "http://192.168.1.100:32400"

    def test_valid_https_url(self) -> None:
        config = PlexConfig(url="https://plex.example.com", token="t")
        assert config.url == "https://plex.example.com"

    def test_invalid_url_rejected(self) -> None:
        with pytest.raises(ValueError, match="http://"):
            PlexConfig(url="ftp://plex.local", token="t")

    def test_empty_url_allowed(self) -> None:
        # Empty URL is allowed (will fail at connection time)
        config = PlexConfig(url="", token="t")
        assert config.url == ""


class TestDuplicateValidation:
    def test_duplicate_show_names_rejected(self) -> None:
        with pytest.raises(ValueError, match="Duplicate show name"):
            RTVConfig(
                shows=[
                    ShowConfig(name="Seinfeld"),
                    ShowConfig(name="seinfeld"),
                ],
            )

    def test_duplicate_category_names_rejected(self) -> None:
        with pytest.raises(ValueError, match="Duplicate category name"):
            CommercialConfig(
                library_path="C:\\test",
                categories=[
                    CommercialCategory(name="80s"),
                    CommercialCategory(name="80s"),
                ],
            )

    def test_unique_show_names_pass(self) -> None:
        config = RTVConfig(
            shows=[
                ShowConfig(name="Seinfeld"),
                ShowConfig(name="Friends"),
            ],
        )
        assert len(config.shows) == 2

    def test_unique_category_names_pass(self) -> None:
        config = CommercialConfig(
            library_path="C:\\test",
            categories=[
                CommercialCategory(name="80s"),
                CommercialCategory(name="90s"),
            ],
        )
        assert len(config.categories) == 2


class TestHistoryEntry:
    def test_history_entry_creation(self) -> None:
        entry = HistoryEntry(
            timestamp="2026-02-14 15:30",
            playlist_name="Real TV",
            episode_count=30,
            shows=["Seinfeld", "Friends"],
            runtime_secs=54000.0,
        )
        assert entry.timestamp == "2026-02-14 15:30"
        assert entry.episode_count == 30
        assert len(entry.shows) == 2

    def test_history_in_config(self) -> None:
        config = _make_config()
        assert config.history == []

        config.history.append(HistoryEntry(
            timestamp="2026-02-14 15:30",
            playlist_name="Test",
            episode_count=10,
            shows=["Show1"],
        ))
        assert len(config.history) == 1


class TestConfigLoadSave:
    def test_round_trip(self, tmp_path: Path) -> None:
        """Config survives save -> load cycle identically."""
        config = _make_config(
            shows=[
                ShowConfig(name="The Office", library="TV Shows", current_season=3, current_episode=7),
                ShowConfig(name="Seinfeld", library="TV Shows 2"),
            ],
        )
        config.commercials.categories = [
            CommercialCategory(name="80s", search_terms=["80s ads"], weight=1.0),
            CommercialCategory(name="toys", search_terms=["toy commercial"], weight=0.5),
        ]

        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        loaded = load_config(config_path)

        assert loaded.plex.url == config.plex.url
        assert loaded.plex.token == config.plex.token
        assert len(loaded.shows) == 2
        assert loaded.shows[0].name == "The Office"
        assert loaded.shows[0].current_season == 3
        assert loaded.shows[0].current_episode == 7
        assert loaded.shows[1].name == "Seinfeld"
        assert len(loaded.commercials.categories) == 2
        assert loaded.commercials.categories[1].weight == 0.5

    def test_round_trip_with_history(self, tmp_path: Path) -> None:
        """History survives save -> load cycle."""
        config = _make_config()
        config.history = [
            HistoryEntry(
                timestamp="2026-02-14 15:30",
                playlist_name="Test",
                episode_count=10,
                shows=["Seinfeld", "Friends"],
                runtime_secs=18000.0,
            )
        ]

        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        loaded = load_config(config_path)

        assert len(loaded.history) == 1
        assert loaded.history[0].playlist_name == "Test"
        assert loaded.history[0].episode_count == 10
        assert loaded.history[0].shows == ["Seinfeld", "Friends"]

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_load_empty_file_uses_defaults(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text("", encoding="utf-8")
        config = load_config(config_path)
        assert config.plex.url == "http://localhost:32400"
        assert config.plex.token == ""
        assert config.shows == []

    def test_load_minimal_yaml(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            yaml.dump({
                "plex": {"token": "abc"},
                "commercials": {"library_path": "C:\\test"},
            }),
            encoding="utf-8",
        )
        config = load_config(config_path)
        assert config.plex.token == "abc"
        assert config.plex.url == "http://localhost:32400"

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        config = _make_config()
        deep_path = tmp_path / "a" / "b" / "config.yaml"
        save_config(config, deep_path)
        assert deep_path.exists()

    def test_show_position_persistence(self, tmp_path: Path) -> None:
        """Show positions are saved and restored correctly."""
        config = _make_config(
            shows=[ShowConfig(name="TestShow", current_season=5, current_episode=12)]
        )
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)

        loaded = load_config(config_path)
        assert loaded.shows[0].current_season == 5
        assert loaded.shows[0].current_episode == 12

    def test_load_invalid_url_raises(self, tmp_path: Path) -> None:
        """Config with invalid URL format is rejected on load."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            yaml.dump({"plex": {"url": "ftp://bad.url", "token": "t"}}),
            encoding="utf-8",
        )
        with pytest.raises(Exception):
            load_config(config_path)

    def test_year_field_round_trip(self, tmp_path: Path) -> None:
        """ShowConfig.year survives save -> load cycle."""
        config = _make_config(
            shows=[
                ShowConfig(name="Seinfeld", year=1989),
                ShowConfig(name="Friends", year=1994),
                ShowConfig(name="Unknown Show"),  # year=None
            ],
        )
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        loaded = load_config(config_path)

        assert loaded.shows[0].year == 1989
        assert loaded.shows[1].year == 1994
        assert loaded.shows[2].year is None


class TestDefaultShows:
    def test_has_30_entries(self) -> None:
        assert len(DEFAULT_SHOWS) == 30

    def test_all_have_name_and_year(self) -> None:
        for entry in DEFAULT_SHOWS:
            assert "name" in entry, f"Missing name: {entry}"
            assert "year" in entry, f"Missing year: {entry}"
            assert isinstance(entry["name"], str)
            assert isinstance(entry["year"], int)

    def test_sorted_by_year(self) -> None:
        years = [int(entry["year"]) for entry in DEFAULT_SHOWS]  # type: ignore[arg-type]
        assert years == sorted(years)

    def test_creates_valid_show_configs(self) -> None:
        shows = [ShowConfig(name=str(e["name"]), year=int(e["year"])) for e in DEFAULT_SHOWS]  # type: ignore[arg-type]
        config = RTVConfig(shows=shows)
        assert len(config.shows) == 30


class TestCommercialMinGap:
    def test_default_min_gap(self) -> None:
        config = PlaylistConfig()
        assert config.commercial_min_gap == 50

    def test_custom_min_gap(self) -> None:
        config = PlaylistConfig(commercial_min_gap=100)
        assert config.commercial_min_gap == 100

    def test_min_gap_rejects_zero(self) -> None:
        with pytest.raises(Exception):
            PlaylistConfig(commercial_min_gap=0)

    def test_min_gap_round_trip(self, tmp_path: Path) -> None:
        config = _make_config()
        config.playlist.commercial_min_gap = 75
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        loaded = load_config(config_path)
        assert loaded.playlist.commercial_min_gap == 75


class TestPlaylistConfigSortBy:
    def test_default_sort_by(self) -> None:
        config = PlaylistConfig()
        assert config.sort_by == "premiere_year"

    def test_valid_sort_values(self) -> None:
        for val in ("premiere_year", "premiere_year_desc", "alphabetical", "config_order"):
            config = PlaylistConfig(sort_by=val)
            assert config.sort_by == val

    def test_invalid_sort_by_rejected(self) -> None:
        with pytest.raises(ValueError, match="sort_by must be one of"):
            PlaylistConfig(sort_by="random")
