"""Tests for config module — v2 models and v1->v2 migration."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from rtv.config import (
    RTVConfig,
    PlexConfig,
    GlobalShow,
    PlaylistShow,
    PlaylistDefinition,
    BreakConfig,
    BlockDuration,
    SSHConfig,
    CommercialConfig,
    CommercialCategory,
    HistoryEntry,
    ShowConfig,
    PlaylistConfig,
    DEFAULT_SHOWS,
    VALID_SORT_VALUES,
    load_config,
    save_config,
    _is_v1_config,
    _migrate_v1_to_v2,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides: object) -> RTVConfig:
    """Create a v2 config with sensible defaults, overriding as needed."""
    defaults: dict[str, object] = {
        "config_version": 2,
        "plex": PlexConfig(url="http://localhost:32400", token="test-token", tv_libraries=["TV Shows"]),
        "shows": [],
        "commercials": CommercialConfig(
            library_name="RealTV Commercials",
            library_path="D:\\Media\\Commercials",
            block_duration=BlockDuration(min=30, max=120),
        ),
        "playlists": [
            PlaylistDefinition(name="Real TV"),
        ],
        "default_playlist": "Real TV",
        "ssh": SSHConfig(),
    }
    defaults.update(overrides)
    return RTVConfig(**defaults)  # type: ignore[arg-type]


def _make_v1_yaml_data(
    shows: list[dict] | None = None,
    playlist: dict | None = None,
) -> dict:
    """Build a v1-format config dict (no config_version)."""
    data: dict = {
        "plex": {"url": "http://192.168.1.10:32400", "token": "v1-token"},
        "shows": shows or [
            {"name": "Seinfeld", "library": "TV Shows", "current_season": 3, "current_episode": 5, "year": 1989},
            {"name": "Friends", "library": "TV Shows", "current_season": 1, "current_episode": 1, "year": 1994},
        ],
        "commercials": {"library_path": "F:\\Commercials"},
    }
    if playlist is not None:
        data["playlist"] = playlist
    else:
        data["playlist"] = {
            "default_name": "Real TV",
            "episodes_per_generation": 25,
            "commercial_frequency": 2,
            "commercial_min_gap": 40,
            "sort_by": "alphabetical",
        }
    return data


# ---------------------------------------------------------------------------
# v2 model tests: GlobalShow
# ---------------------------------------------------------------------------


class TestGlobalShow:
    def test_defaults(self) -> None:
        show = GlobalShow(name="Seinfeld")
        assert show.library == "TV Shows"
        assert show.year is None
        assert show.enabled is True

    def test_all_fields(self) -> None:
        show = GlobalShow(name="Friends", library="Sitcoms", year=1994, enabled=False)
        assert show.name == "Friends"
        assert show.library == "Sitcoms"
        assert show.year == 1994
        assert show.enabled is False

    def test_enabled_toggle(self) -> None:
        show = GlobalShow(name="Test", enabled=True)
        show.enabled = False
        assert show.enabled is False


# ---------------------------------------------------------------------------
# v2 model tests: PlaylistShow
# ---------------------------------------------------------------------------


class TestPlaylistShow:
    def test_defaults(self) -> None:
        ps = PlaylistShow(name="Test Show")
        assert ps.current_season == 1
        assert ps.current_episode == 1

    def test_custom_position(self) -> None:
        ps = PlaylistShow(name="Test", current_season=5, current_episode=12)
        assert ps.current_season == 5
        assert ps.current_episode == 12

    def test_rejects_zero_season(self) -> None:
        with pytest.raises(Exception):
            PlaylistShow(name="X", current_season=0)

    def test_rejects_zero_episode(self) -> None:
        with pytest.raises(Exception):
            PlaylistShow(name="X", current_episode=0)


# ---------------------------------------------------------------------------
# v2 model tests: BreakConfig
# ---------------------------------------------------------------------------


class TestBreakConfig:
    def test_defaults(self) -> None:
        bc = BreakConfig()
        assert bc.enabled is True
        assert bc.style == "single"
        assert bc.frequency == 1
        assert bc.min_gap == 50
        assert bc.block_duration.min == 30
        assert bc.block_duration.max == 120

    def test_single_style(self) -> None:
        bc = BreakConfig(style="single")
        assert bc.style == "single"

    def test_block_style(self) -> None:
        bc = BreakConfig(style="block", block_duration=BlockDuration(min=60, max=180))
        assert bc.style == "block"
        assert bc.block_duration.min == 60

    def test_disabled_style(self) -> None:
        bc = BreakConfig(style="disabled")
        assert bc.style == "disabled"

    def test_disabled_enabled_false(self) -> None:
        bc = BreakConfig(enabled=False)
        assert bc.enabled is False

    def test_invalid_style_rejected(self) -> None:
        with pytest.raises(ValueError, match="break style must be one of"):
            BreakConfig(style="random")

    def test_rejects_zero_frequency(self) -> None:
        with pytest.raises(Exception):
            BreakConfig(frequency=0)

    def test_rejects_zero_min_gap(self) -> None:
        with pytest.raises(Exception):
            BreakConfig(min_gap=0)

    def test_custom_block_duration(self) -> None:
        bc = BreakConfig(block_duration=BlockDuration(min=45, max=90))
        assert bc.block_duration.min == 45
        assert bc.block_duration.max == 90


# ---------------------------------------------------------------------------
# v2 model tests: PlaylistDefinition
# ---------------------------------------------------------------------------


class TestPlaylistDefinition:
    def test_defaults(self) -> None:
        pd = PlaylistDefinition(name="My Playlist")
        assert pd.name == "My Playlist"
        assert pd.shows == []
        assert pd.breaks.enabled is True
        assert pd.episodes_per_generation == 0
        assert pd.sort_by == "premiere_year"

    def test_with_shows_and_breaks(self) -> None:
        pd = PlaylistDefinition(
            name="Test",
            shows=[
                PlaylistShow(name="ShowA", current_season=2, current_episode=3),
                PlaylistShow(name="ShowB"),
            ],
            breaks=BreakConfig(style="block", frequency=2),
            episodes_per_generation=50,
            sort_by="alphabetical",
        )
        assert len(pd.shows) == 2
        assert pd.shows[0].current_season == 2
        assert pd.breaks.style == "block"
        assert pd.breaks.frequency == 2
        assert pd.episodes_per_generation == 50
        assert pd.sort_by == "alphabetical"

    def test_valid_sort_values(self) -> None:
        for val in VALID_SORT_VALUES:
            pd = PlaylistDefinition(name="T", sort_by=val)
            assert pd.sort_by == val

    def test_invalid_sort_by_rejected(self) -> None:
        with pytest.raises(ValueError, match="sort_by must be one of"):
            PlaylistDefinition(name="T", sort_by="random")

    def test_accepts_zero_episodes_per_gen(self) -> None:
        """0 means unlimited — generate all available episodes."""
        pd = PlaylistDefinition(name="T", episodes_per_generation=0)
        assert pd.episodes_per_generation == 0

    def test_rejects_negative_episodes_per_gen(self) -> None:
        with pytest.raises(Exception):
            PlaylistDefinition(name="T", episodes_per_generation=-1)


# ---------------------------------------------------------------------------
# v2 model tests: SSHConfig
# ---------------------------------------------------------------------------


class TestSSHConfig:
    def test_defaults(self) -> None:
        ssh = SSHConfig()
        assert ssh.enabled is False
        assert ssh.host == ""
        assert ssh.port == 22
        assert ssh.username == ""
        assert ssh.key_path == ""
        assert ssh.remote_commercial_path == ""

    def test_full_config(self) -> None:
        ssh = SSHConfig(
            enabled=True,
            host="192.168.1.10",
            port=2222,
            username="admin",
            key_path="~/.ssh/plex_key",
            remote_commercial_path="F:\\Commercials",
        )
        assert ssh.enabled is True
        assert ssh.host == "192.168.1.10"
        assert ssh.port == 2222
        assert ssh.username == "admin"


# ---------------------------------------------------------------------------
# v2 model tests: RTVConfig
# ---------------------------------------------------------------------------


class TestRTVConfig:
    def test_valid_config_creation(self) -> None:
        config = _make_config()
        assert config.config_version == 2
        assert config.plex.url == "http://localhost:32400"
        assert config.plex.token == "test-token"
        assert config.default_playlist == "Real TV"
        assert len(config.playlists) == 1
        assert config.playlists[0].name == "Real TV"

    def test_default_values(self) -> None:
        config = RTVConfig(plex=PlexConfig(token="tok"))
        assert config.config_version == 2
        assert config.plex.url == "http://localhost:32400"
        assert config.plex.tv_libraries == ["TV Shows"]
        assert config.shows == []
        assert config.playlists == []
        assert config.default_playlist == "Real TV"
        assert config.ssh.enabled is False
        assert config.commercials.library_name == "RealTV Commercials"
        assert config.commercials.block_duration.min == 30
        assert config.commercials.block_duration.max == 120
        assert config.history == []

    def test_get_playlist_by_name(self) -> None:
        config = _make_config(playlists=[
            PlaylistDefinition(name="Real TV"),
            PlaylistDefinition(name="Late Night"),
        ])
        pl = config.get_playlist("Late Night")
        assert pl is not None
        assert pl.name == "Late Night"

    def test_get_playlist_case_insensitive(self) -> None:
        config = _make_config(playlists=[PlaylistDefinition(name="Real TV")])
        pl = config.get_playlist("real tv")
        assert pl is not None
        assert pl.name == "Real TV"

    def test_get_playlist_default(self) -> None:
        config = _make_config(
            playlists=[PlaylistDefinition(name="Real TV")],
            default_playlist="Real TV",
        )
        pl = config.get_playlist()
        assert pl is not None
        assert pl.name == "Real TV"

    def test_get_playlist_not_found(self) -> None:
        config = _make_config(playlists=[PlaylistDefinition(name="Real TV")])
        pl = config.get_playlist("Nonexistent")
        assert pl is None

    def test_get_playlist_or_raise(self) -> None:
        config = _make_config(playlists=[PlaylistDefinition(name="Real TV")])
        with pytest.raises(ValueError, match="not found"):
            config.get_playlist_or_raise("Nonexistent")

    def test_get_global_show(self) -> None:
        config = _make_config(shows=[
            GlobalShow(name="Seinfeld", year=1989),
            GlobalShow(name="Friends", year=1994),
        ])
        gs = config.get_global_show("seinfeld")
        assert gs is not None
        assert gs.name == "Seinfeld"
        assert gs.year == 1989

    def test_get_global_show_not_found(self) -> None:
        config = _make_config(shows=[GlobalShow(name="Seinfeld")])
        assert config.get_global_show("Unknown") is None

    def test_get_playlist_membership(self) -> None:
        config = _make_config(
            shows=[GlobalShow(name="Seinfeld"), GlobalShow(name="Friends")],
            playlists=[
                PlaylistDefinition(name="PL1", shows=[PlaylistShow(name="Seinfeld")]),
                PlaylistDefinition(name="PL2", shows=[PlaylistShow(name="Seinfeld"), PlaylistShow(name="Friends")]),
            ],
        )
        memberships = config.get_playlist_membership("Seinfeld")
        assert memberships == ["PL1", "PL2"]

        memberships_f = config.get_playlist_membership("Friends")
        assert memberships_f == ["PL2"]

    def test_duplicate_show_names_rejected(self) -> None:
        with pytest.raises(ValueError, match="Duplicate show name"):
            RTVConfig(shows=[
                GlobalShow(name="Seinfeld"),
                GlobalShow(name="seinfeld"),
            ])

    def test_unique_show_names_pass(self) -> None:
        config = RTVConfig(shows=[
            GlobalShow(name="Seinfeld"),
            GlobalShow(name="Friends"),
        ])
        assert len(config.shows) == 2


# ---------------------------------------------------------------------------
# BlockDuration
# ---------------------------------------------------------------------------


class TestBlockDuration:
    def test_valid(self) -> None:
        bd = BlockDuration(min=60, max=180)
        assert bd.min == 60
        assert bd.max == 180

    def test_rejects_zero(self) -> None:
        with pytest.raises(Exception):
            BlockDuration(min=0, max=300)

    def test_rejects_min_gt_max(self) -> None:
        with pytest.raises(ValueError, match="must be <= max"):
            BlockDuration(min=300, max=60)


# ---------------------------------------------------------------------------
# PlexConfig / URL validation
# ---------------------------------------------------------------------------


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
        config = PlexConfig(url="", token="t")
        assert config.url == ""


# ---------------------------------------------------------------------------
# CommercialConfig / categories
# ---------------------------------------------------------------------------


class TestCommercialConfig:
    def test_commercial_category_defaults(self) -> None:
        cat = CommercialCategory(name="80s")
        assert cat.search_terms == []
        assert cat.weight == 1.0

    def test_duplicate_category_names_rejected(self) -> None:
        with pytest.raises(ValueError, match="Duplicate category name"):
            CommercialConfig(
                library_path="C:\\test",
                categories=[
                    CommercialCategory(name="80s"),
                    CommercialCategory(name="80s"),
                ],
            )

    def test_unique_category_names_pass(self) -> None:
        config = CommercialConfig(
            library_path="C:\\test",
            categories=[
                CommercialCategory(name="80s"),
                CommercialCategory(name="90s"),
            ],
        )
        assert len(config.categories) == 2

    def test_commercial_category_rejects_zero_weight(self) -> None:
        with pytest.raises(Exception):
            CommercialCategory(name="test", weight=0)

    def test_commercial_category_rejects_negative_weight(self) -> None:
        with pytest.raises(Exception):
            CommercialCategory(name="test", weight=-1.0)


# ---------------------------------------------------------------------------
# HistoryEntry
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Config load/save round-trips (v2)
# ---------------------------------------------------------------------------


class TestConfigLoadSave:
    def test_round_trip(self, tmp_path: Path) -> None:
        """Config survives save -> load cycle identically."""
        config = _make_config(
            shows=[
                GlobalShow(name="The Office", library="TV Shows", year=2005),
                GlobalShow(name="Seinfeld", library="TV Shows 2", year=1989),
            ],
            playlists=[
                PlaylistDefinition(
                    name="Real TV",
                    shows=[
                        PlaylistShow(name="The Office", current_season=3, current_episode=7),
                        PlaylistShow(name="Seinfeld"),
                    ],
                    breaks=BreakConfig(style="single", frequency=2, min_gap=40),
                    episodes_per_generation=25,
                    sort_by="alphabetical",
                ),
            ],
        )
        config.commercials.categories = [
            CommercialCategory(name="80s", search_terms=["80s ads"], weight=1.0),
            CommercialCategory(name="toys", search_terms=["toy commercial"], weight=0.5),
        ]

        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        loaded = load_config(config_path)

        assert loaded.config_version == 2
        assert loaded.plex.url == config.plex.url
        assert loaded.plex.token == config.plex.token
        assert len(loaded.shows) == 2
        assert loaded.shows[0].name == "The Office"
        assert loaded.shows[0].year == 2005
        assert loaded.shows[1].name == "Seinfeld"

        # Playlist round-trip
        assert len(loaded.playlists) == 1
        pl = loaded.playlists[0]
        assert pl.name == "Real TV"
        assert len(pl.shows) == 2
        assert pl.shows[0].current_season == 3
        assert pl.shows[0].current_episode == 7
        assert pl.breaks.style == "single"
        assert pl.breaks.frequency == 2
        assert pl.breaks.min_gap == 40
        assert pl.episodes_per_generation == 25
        assert pl.sort_by == "alphabetical"

        # Commercials
        assert len(loaded.commercials.categories) == 2
        assert loaded.commercials.categories[1].weight == 0.5

    def test_round_trip_with_history(self, tmp_path: Path) -> None:
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

    def test_round_trip_ssh_config(self, tmp_path: Path) -> None:
        config = _make_config(
            ssh=SSHConfig(
                enabled=True,
                host="192.168.1.10",
                port=2222,
                username="admin",
                key_path="~/.ssh/plex",
                remote_commercial_path="F:\\Commercials",
            ),
        )
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        loaded = load_config(config_path)

        assert loaded.ssh.enabled is True
        assert loaded.ssh.host == "192.168.1.10"
        assert loaded.ssh.port == 2222
        assert loaded.ssh.username == "admin"
        assert loaded.ssh.key_path == "~/.ssh/plex"

    def test_round_trip_break_config_block_style(self, tmp_path: Path) -> None:
        config = _make_config(
            playlists=[
                PlaylistDefinition(
                    name="Block Test",
                    breaks=BreakConfig(
                        style="block",
                        frequency=3,
                        min_gap=30,
                        block_duration=BlockDuration(min=60, max=180),
                    ),
                ),
            ],
        )
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        loaded = load_config(config_path)

        pl = loaded.playlists[0]
        assert pl.breaks.style == "block"
        assert pl.breaks.frequency == 3
        assert pl.breaks.block_duration.min == 60
        assert pl.breaks.block_duration.max == 180

    def test_round_trip_disabled_breaks(self, tmp_path: Path) -> None:
        config = _make_config(
            playlists=[
                PlaylistDefinition(
                    name="No Breaks",
                    breaks=BreakConfig(enabled=False),
                ),
            ],
        )
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        loaded = load_config(config_path)

        assert loaded.playlists[0].breaks.enabled is False

    def test_round_trip_multiple_playlists(self, tmp_path: Path) -> None:
        config = _make_config(
            shows=[
                GlobalShow(name="ShowA"),
                GlobalShow(name="ShowB"),
            ],
            playlists=[
                PlaylistDefinition(
                    name="Playlist 1",
                    shows=[PlaylistShow(name="ShowA")],
                    sort_by="alphabetical",
                ),
                PlaylistDefinition(
                    name="Playlist 2",
                    shows=[PlaylistShow(name="ShowA"), PlaylistShow(name="ShowB")],
                    sort_by="premiere_year_desc",
                    episodes_per_generation=50,
                ),
            ],
        )
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        loaded = load_config(config_path)

        assert len(loaded.playlists) == 2
        assert loaded.playlists[0].name == "Playlist 1"
        assert len(loaded.playlists[0].shows) == 1
        assert loaded.playlists[1].name == "Playlist 2"
        assert len(loaded.playlists[1].shows) == 2
        assert loaded.playlists[1].episodes_per_generation == 50

    def test_round_trip_global_show_enabled_field(self, tmp_path: Path) -> None:
        config = _make_config(shows=[
            GlobalShow(name="Active", enabled=True),
            GlobalShow(name="Inactive", enabled=False),
        ])
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        loaded = load_config(config_path)

        assert loaded.shows[0].enabled is True
        assert loaded.shows[1].enabled is False

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_load_empty_file_uses_defaults(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text("", encoding="utf-8")
        config = load_config(config_path)
        assert config.config_version == 2
        assert config.plex.url == "http://localhost:32400"
        assert config.plex.token == ""
        assert config.shows == []

    def test_load_minimal_yaml(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            yaml.dump({
                "config_version": 2,
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

    def test_load_invalid_url_raises(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            yaml.dump({"config_version": 2, "plex": {"url": "ftp://bad.url", "token": "t"}}),
            encoding="utf-8",
        )
        with pytest.raises(Exception):
            load_config(config_path)

    def test_year_field_round_trip(self, tmp_path: Path) -> None:
        config = _make_config(shows=[
            GlobalShow(name="Seinfeld", year=1989),
            GlobalShow(name="Friends", year=1994),
            GlobalShow(name="Unknown Show"),
        ])
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        loaded = load_config(config_path)

        assert loaded.shows[0].year == 1989
        assert loaded.shows[1].year == 1994
        assert loaded.shows[2].year is None


# ---------------------------------------------------------------------------
# DEFAULT_SHOWS
# ---------------------------------------------------------------------------


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

    def test_creates_valid_global_shows(self) -> None:
        shows = [GlobalShow(name=str(e["name"]), year=int(e["year"])) for e in DEFAULT_SHOWS]  # type: ignore[arg-type]
        config = RTVConfig(shows=shows)
        assert len(config.shows) == 30


# ---------------------------------------------------------------------------
# Legacy v1 models (basic tests — kept for migration)
# ---------------------------------------------------------------------------


class TestLegacyModels:
    def test_show_config_defaults(self) -> None:
        show = ShowConfig(name="Test Show")
        assert show.library == "TV Shows"
        assert show.current_season == 1
        assert show.current_episode == 1
        assert show.year is None

    def test_show_config_full(self) -> None:
        show = ShowConfig(name="Seinfeld", library="Sitcoms", current_season=5, current_episode=3, year=1989)
        assert show.name == "Seinfeld"
        assert show.current_season == 5
        assert show.year == 1989

    def test_playlist_config_defaults(self) -> None:
        pc = PlaylistConfig()
        assert pc.default_name == "Real TV"
        assert pc.episodes_per_generation == 30
        assert pc.commercial_frequency == 1
        assert pc.commercial_min_gap == 50
        assert pc.sort_by == "premiere_year"

    def test_playlist_config_rejects_zero_episodes(self) -> None:
        with pytest.raises(Exception):
            PlaylistConfig(episodes_per_generation=0)

    def test_playlist_config_rejects_zero_frequency(self) -> None:
        with pytest.raises(Exception):
            PlaylistConfig(commercial_frequency=0)

    def test_playlist_config_invalid_sort(self) -> None:
        with pytest.raises(ValueError, match="sort_by must be one of"):
            PlaylistConfig(sort_by="random")

    def test_playlist_config_valid_sort_values(self) -> None:
        for val in VALID_SORT_VALUES:
            pc = PlaylistConfig(sort_by=val)
            assert pc.sort_by == val


# ---------------------------------------------------------------------------
# v1 -> v2 migration
# ---------------------------------------------------------------------------


class TestV1Detection:
    def test_v1_config_detected(self) -> None:
        data = {"plex": {"token": "t"}, "shows": []}
        assert _is_v1_config(data) is True

    def test_v2_config_not_detected_as_v1(self) -> None:
        data = {"config_version": 2, "plex": {"token": "t"}}
        assert _is_v1_config(data) is False

    def test_empty_dict_is_v1(self) -> None:
        assert _is_v1_config({}) is True


class TestV1ToV2Migration:
    def test_basic_migration(self) -> None:
        v1_data = _make_v1_yaml_data()
        v2_data = _migrate_v1_to_v2(v1_data)

        assert v2_data["config_version"] == 2
        assert "plex" in v2_data
        assert v2_data["plex"]["url"] == "http://192.168.1.10:32400"

    def test_shows_split_into_global_and_playlist(self) -> None:
        v1_data = _make_v1_yaml_data(shows=[
            {"name": "Seinfeld", "library": "TV Shows", "current_season": 3, "current_episode": 5, "year": 1989},
            {"name": "Friends", "library": "Sitcoms", "current_season": 1, "current_episode": 1, "year": 1994},
        ])
        v2_data = _migrate_v1_to_v2(v1_data)

        # Global shows: name, library, year, enabled (no positions)
        global_shows = v2_data["shows"]
        assert len(global_shows) == 2
        assert global_shows[0]["name"] == "Seinfeld"
        assert global_shows[0]["library"] == "TV Shows"
        assert global_shows[0]["year"] == 1989
        assert global_shows[0]["enabled"] is True
        assert "current_season" not in global_shows[0]

        assert global_shows[1]["name"] == "Friends"
        assert global_shows[1]["library"] == "Sitcoms"

        # Playlist shows: name, current_season, current_episode (positions preserved)
        playlist_shows = v2_data["playlists"][0]["shows"]
        assert len(playlist_shows) == 2
        assert playlist_shows[0]["name"] == "Seinfeld"
        assert playlist_shows[0]["current_season"] == 3
        assert playlist_shows[0]["current_episode"] == 5
        assert playlist_shows[1]["name"] == "Friends"
        assert playlist_shows[1]["current_season"] == 1

    def test_playlist_settings_migrated(self) -> None:
        v1_data = _make_v1_yaml_data(playlist={
            "default_name": "My Playlist",
            "episodes_per_generation": 50,
            "commercial_frequency": 3,
            "commercial_min_gap": 75,
            "sort_by": "alphabetical",
        })
        v2_data = _migrate_v1_to_v2(v1_data)

        assert v2_data["default_playlist"] == "My Playlist"
        pl = v2_data["playlists"][0]
        assert pl["name"] == "My Playlist"
        assert pl["episodes_per_generation"] == 50
        assert pl["sort_by"] == "alphabetical"
        assert pl["breaks"]["frequency"] == 3
        assert pl["breaks"]["min_gap"] == 75
        assert pl["breaks"]["style"] == "single"
        assert pl["breaks"]["enabled"] is True

    def test_ssh_defaults_in_migration(self) -> None:
        v1_data = _make_v1_yaml_data()
        v2_data = _migrate_v1_to_v2(v1_data)
        assert v2_data["ssh"]["enabled"] is False

    def test_history_preserved(self) -> None:
        v1_data = _make_v1_yaml_data()
        v1_data["history"] = [
            {"timestamp": "2026-01-01", "playlist_name": "TV", "episode_count": 10, "shows": ["S"]},
        ]
        v2_data = _migrate_v1_to_v2(v1_data)
        assert len(v2_data["history"]) == 1
        assert v2_data["history"][0]["playlist_name"] == "TV"

    def test_commercials_preserved(self) -> None:
        v1_data = _make_v1_yaml_data()
        v1_data["commercials"] = {"library_path": "Z:\\Ads", "library_name": "My Ads"}
        v2_data = _migrate_v1_to_v2(v1_data)
        assert v2_data["commercials"]["library_path"] == "Z:\\Ads"
        assert v2_data["commercials"]["library_name"] == "My Ads"

    def test_migrated_data_validates_as_rtv_config(self) -> None:
        v1_data = _make_v1_yaml_data()
        v2_data = _migrate_v1_to_v2(v1_data)
        config = RTVConfig.model_validate(v2_data)
        assert config.config_version == 2
        assert len(config.shows) == 2
        assert len(config.playlists) == 1
        assert config.playlists[0].shows[0].current_season == 3

    def test_migration_creates_backup(self, tmp_path: Path) -> None:
        v1_data = _make_v1_yaml_data()
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(v1_data), encoding="utf-8")

        _migrate_v1_to_v2(v1_data, config_path)

        backup_path = config_path.with_suffix(".yaml.v1.bak")
        assert backup_path.exists()

    def test_auto_migration_on_load(self, tmp_path: Path) -> None:
        """load_config auto-migrates v1 and saves v2."""
        v1_data = _make_v1_yaml_data()
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(v1_data), encoding="utf-8")

        config = load_config(config_path)
        assert config.config_version == 2
        assert len(config.playlists) == 1
        assert config.playlists[0].name == "Real TV"
        assert config.playlists[0].shows[0].current_season == 3

        # Verify backup was created
        backup_path = config_path.with_suffix(".yaml.v1.bak")
        assert backup_path.exists()

        # Verify the saved file is now v2
        with open(config_path, encoding="utf-8") as f:
            saved_data = yaml.safe_load(f)
        assert saved_data["config_version"] == 2

    def test_v1_migration_missing_playlist_uses_defaults(self) -> None:
        """v1 config with no playlist section still migrates cleanly."""
        v1_data = {
            "plex": {"token": "t"},
            "shows": [{"name": "Test"}],
        }
        v2_data = _migrate_v1_to_v2(v1_data)
        assert v2_data["default_playlist"] == "Real TV"
        pl = v2_data["playlists"][0]
        assert pl["episodes_per_generation"] == 30
        assert pl["breaks"]["frequency"] == 1
        assert pl["breaks"]["min_gap"] == 50

    def test_v1_migration_show_defaults(self) -> None:
        """v1 shows without optional fields get defaults."""
        v1_data = {
            "plex": {"token": "t"},
            "shows": [{"name": "Bare Show"}],
        }
        v2_data = _migrate_v1_to_v2(v1_data)

        gs = v2_data["shows"][0]
        assert gs["name"] == "Bare Show"
        assert gs["library"] == "TV Shows"
        assert gs["year"] is None
        assert gs["enabled"] is True

        ps = v2_data["playlists"][0]["shows"][0]
        assert ps["name"] == "Bare Show"
        assert ps["current_season"] == 1
        assert ps["current_episode"] == 1
