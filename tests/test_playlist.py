"""Tests for playlist generation algorithm — v2 per-playlist model."""

from __future__ import annotations

import random
from collections import deque
from unittest.mock import MagicMock, patch

import pytest

from rtv.config import (
    RTVConfig,
    PlexConfig,
    GlobalShow,
    PlaylistShow,
    PlaylistDefinition,
    BreakConfig,
    BlockDuration,
    CommercialConfig,
    CommercialCategory,
)
from rtv.playlist import (
    generate_playlist,
    build_commercial_block,
    build_commercial_block_for_playlist,
    pick_single_commercial,
    _get_next_episode,
    ShowState,
    _get_duration_secs,
)


# ---------------------------------------------------------------------------
# Mock factories
# ---------------------------------------------------------------------------


def _make_mock_episode(
    season: int, episode: int, title: str = "", duration_ms: int = 1800000
) -> MagicMock:
    """Create a mock Episode object."""
    ep = MagicMock()
    ep.index = episode
    ep.parentIndex = season
    ep.seasonNumber = season
    ep.episodeNumber = episode
    ep.title = title or f"S{season:02d}E{episode:02d}"
    ep.duration = duration_ms
    return ep


def _make_mock_season(season_num: int, episode_count: int) -> MagicMock:
    """Create a mock Season object."""
    season = MagicMock()
    season.index = season_num
    episodes = [_make_mock_episode(season_num, i + 1) for i in range(episode_count)]
    season.episodes.return_value = episodes
    return season


def _make_mock_show(
    title: str, seasons: dict[int, int]
) -> MagicMock:
    """Create a mock Show object.

    Args:
        title: Show title
        seasons: dict of {season_number: episode_count}
    """
    show = MagicMock()
    show.title = title

    mock_seasons = []
    for sn, ep_count in seasons.items():
        mock_seasons.append(_make_mock_season(sn, ep_count))

    show.seasons.return_value = mock_seasons

    def mock_season_fn(season: int | None = None, title: str | None = None) -> MagicMock:
        for ms in mock_seasons:
            if ms.index == season:
                return ms
        from plexapi.exceptions import NotFound
        raise NotFound(f"Season {season} not found")

    show.season = mock_season_fn

    all_episodes = []
    for ms in mock_seasons:
        all_episodes.extend(ms.episodes())
    show.episodes.return_value = all_episodes

    return show


def _make_mock_commercial(
    title: str = "Ad", duration_ms: int = 30000, category: str = "80s"
) -> MagicMock:
    """Create a mock commercial Video object."""
    clip = MagicMock()
    clip.title = title
    clip.duration = duration_ms
    clip.locations = [f"D:\\Media\\Commercials\\{category}\\{title}.mp4"]
    return clip


# ---------------------------------------------------------------------------
# v2 config + playlist builder helpers
# ---------------------------------------------------------------------------


def _make_config(
    global_shows: list[GlobalShow] | None = None,
    commercial_categories: list[CommercialCategory] | None = None,
    block_min: int = 60,
    block_max: int = 120,
) -> RTVConfig:
    """Build a v2 test config (global shows only, no playlists)."""
    return RTVConfig(
        config_version=2,
        plex=PlexConfig(token="test"),
        shows=global_shows or [],
        commercials=CommercialConfig(
            library_path="D:\\Media\\Commercials",
            block_duration=BlockDuration(min=block_min, max=block_max),
            categories=commercial_categories or [],
        ),
        playlists=[],
        default_playlist="Real TV",
    )


def _make_playlist(
    name: str = "Real TV",
    show_names: list[str] | None = None,
    break_style: str = "single",
    break_enabled: bool = True,
    frequency: int = 1,
    min_gap: int = 50,
    episodes_per_generation: int = 30,
    sort_by: str = "premiere_year",
    block_min: int = 30,
    block_max: int = 120,
) -> PlaylistDefinition:
    """Build a PlaylistDefinition for testing."""
    shows = [PlaylistShow(name=n) for n in (show_names or [])]
    return PlaylistDefinition(
        name=name,
        shows=shows,
        breaks=BreakConfig(
            enabled=break_enabled,
            style=break_style,
            frequency=frequency,
            min_gap=min_gap,
            block_duration=BlockDuration(min=block_min, max=block_max),
        ),
        episodes_per_generation=episodes_per_generation,
        sort_by=sort_by,
    )


def _mock_get_episode(show: object, season: int, episode: int) -> MagicMock | None:
    """Standard mock for plex_client.get_episode."""
    try:
        s = show.season(season=season)
        for ep in s.episodes():
            if ep.index == episode:
                return ep
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# TestBuildCommercialBlock (original function — still works)
# ---------------------------------------------------------------------------


class TestBuildCommercialBlock:
    def test_empty_commercials(self) -> None:
        config = CommercialConfig(library_path="C:\\test")
        block, duration = build_commercial_block([], config, {})
        assert block == []
        assert duration == 0.0

    def test_block_meets_target_duration(self) -> None:
        random.seed(42)
        clips = [_make_mock_commercial(f"Ad{i}", 30000) for i in range(10)]
        config = CommercialConfig(
            library_path="C:\\test",
            block_duration=BlockDuration(min=60, max=120),
        )
        block, duration = build_commercial_block(clips, config, {})
        assert len(block) >= 2  # At least 2x30s clips needed for 60s min
        assert duration >= 60.0

    def test_block_uses_weighted_selection(self) -> None:
        random.seed(42)
        clips_80s = [_make_mock_commercial(f"80s-{i}", 30000, "80s") for i in range(5)]
        clips_toys = [_make_mock_commercial(f"toys-{i}", 30000, "toys") for i in range(5)]
        all_clips = clips_80s + clips_toys

        config = CommercialConfig(
            library_path="C:\\test",
            block_duration=BlockDuration(min=30, max=60),
            categories=[
                CommercialCategory(name="80s", weight=10.0),
                CommercialCategory(name="toys", weight=0.1),
            ],
        )
        eighty_count = 0
        toy_count = 0
        for _ in range(100):
            block, _ = build_commercial_block(all_clips, config, {})
            for clip in block:
                if "80s" in clip.locations[0]:
                    eighty_count += 1
                elif "toys" in clip.locations[0]:
                    toy_count += 1
        assert eighty_count > toy_count * 2


# ---------------------------------------------------------------------------
# TestBuildCommercialBlockForPlaylist (new per-playlist block builder)
# ---------------------------------------------------------------------------


class TestBuildCommercialBlockForPlaylist:
    def test_empty_commercials(self) -> None:
        break_config = BreakConfig(style="block")
        commercial_config = CommercialConfig(library_path="C:\\test")
        block, duration = build_commercial_block_for_playlist([], break_config, commercial_config, {})
        assert block == []
        assert duration == 0.0

    def test_uses_break_config_duration(self) -> None:
        random.seed(42)
        clips = [_make_mock_commercial(f"Ad{i}", 15000) for i in range(20)]
        break_config = BreakConfig(
            style="block",
            block_duration=BlockDuration(min=45, max=90),
        )
        commercial_config = CommercialConfig(
            library_path="C:\\test",
            block_duration=BlockDuration(min=999, max=999),  # should be ignored
        )
        block, duration = build_commercial_block_for_playlist(clips, break_config, commercial_config, {})
        assert len(block) >= 3  # At least 3x15s = 45s to meet min
        assert duration >= 45.0


# ---------------------------------------------------------------------------
# TestGetNextEpisode
# ---------------------------------------------------------------------------


class TestGetNextEpisode:
    def test_normal_episode(self) -> None:
        show = _make_mock_show("Test", {1: 10})
        ps = PlaylistShow(name="Test")
        state = ShowState(
            name="Test",
            library="TV Shows",
            year=None,
            playlist_show=ps,
            plex_show=show,
            current_season=1,
            current_episode=1,
        )
        with patch("rtv.plex_client.get_episode") as mock_get:
            mock_get.return_value = _make_mock_episode(1, 1)
            ep = _get_next_episode(state)
            assert ep is not None
            assert ep.index == 1

    def test_season_advancement(self) -> None:
        show = _make_mock_show("Test", {1: 3, 2: 5})
        ps = PlaylistShow(name="Test", current_season=1, current_episode=4)
        state = ShowState(
            name="Test",
            library="TV Shows",
            year=None,
            playlist_show=ps,
            plex_show=show,
            current_season=1,
            current_episode=4,
        )
        with patch("rtv.plex_client.get_episode") as mock_get, \
             patch("rtv.plex_client.get_next_season_number") as mock_next:
            mock_get.side_effect = [None, _make_mock_episode(2, 1)]
            mock_next.return_value = 2
            ep = _get_next_episode(state)
            assert ep is not None
            assert state.current_season == 2
            assert state.current_episode == 1

    def test_show_exhausted(self) -> None:
        show = _make_mock_show("Test", {1: 3})
        ps = PlaylistShow(name="Test", current_season=1, current_episode=4)
        state = ShowState(
            name="Test",
            library="TV Shows",
            year=None,
            playlist_show=ps,
            plex_show=show,
            current_season=1,
            current_episode=4,
        )
        with patch("rtv.plex_client.get_episode") as mock_get, \
             patch("rtv.plex_client.get_next_season_number") as mock_next:
            mock_get.return_value = None
            mock_next.return_value = None
            ep = _get_next_episode(state)
            assert ep is None


# ---------------------------------------------------------------------------
# TestGeneratePlaylist — v2 signature
# ---------------------------------------------------------------------------


class TestGeneratePlaylist:
    def _setup_mocks(
        self,
        shows_data: dict[str, dict[int, int]],
        break_style: str = "single",
        break_enabled: bool = True,
        frequency: int = 1,
        sort_by: str = "premiere_year",
    ) -> tuple[RTVConfig, PlaylistDefinition, MagicMock, dict[str, MagicMock]]:
        """Set up config, playlist, and mocks for generate_playlist.

        Args:
            shows_data: {"ShowName": {season_num: ep_count, ...}, ...}

        Returns:
            (config, playlist, mock_server, {show_name: mock_show_obj})
        """
        global_shows = [
            GlobalShow(name=name, library="TV Shows")
            for name in shows_data
        ]
        config = _make_config(
            global_shows=global_shows,
            block_min=30,
            block_max=60,
        )

        playlist = _make_playlist(
            show_names=list(shows_data.keys()),
            break_style=break_style,
            break_enabled=break_enabled,
            frequency=frequency,
            sort_by=sort_by,
        )

        mock_server = MagicMock()
        mock_shows = {}
        for name, seasons in shows_data.items():
            mock_shows[name] = _make_mock_show(name, seasons)

        return config, playlist, mock_server, mock_shows

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_single_show(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config, playlist, server, shows = self._setup_mocks({"ShowA": {1: 5}})

        mock_pc.get_show.return_value = shows["ShowA"]
        mock_pc.get_commercials.return_value = []
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, playlist, server, episode_count=3, from_start=True)
        assert result.episodes_by_show["ShowA"] == 3
        assert len(result.playlist_items) == 3
        assert result.commercial_block_count == 0

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_round_robin_two_shows(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config, playlist, server, shows = self._setup_mocks({
            "ShowA": {1: 10},
            "ShowB": {1: 10},
        })

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return shows[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, playlist, server, episode_count=6, from_start=True)
        assert result.episodes_by_show["ShowA"] == 3
        assert result.episodes_by_show["ShowB"] == 3

        # Verify alternating pattern
        items = result.playlist_items
        for i, item in enumerate(items):
            assert item.parentIndex == 1  # All season 1

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_round_robin_three_shows(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config, playlist, server, shows = self._setup_mocks({
            "ShowA": {1: 10},
            "ShowB": {1: 10},
            "ShowC": {1: 10},
        })

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return shows[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, playlist, server, episode_count=9, from_start=True)
        assert result.episodes_by_show["ShowA"] == 3
        assert result.episodes_by_show["ShowB"] == 3
        assert result.episodes_by_show["ShowC"] == 3

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_show_exhaustion(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """Show with fewer episodes drops out, others continue."""
        config, playlist, server, shows = self._setup_mocks({
            "ShowA": {1: 10},
            "ShowB": {1: 2},
        })

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return shows[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, playlist, server, episode_count=6, from_start=True)
        assert result.episodes_by_show["ShowB"] == 2
        assert result.episodes_by_show["ShowA"] == 4
        assert "ShowB" in result.dropped_shows

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_from_start_resets_positions(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config, _, server, shows = self._setup_mocks({"ShowA": {1: 10}})

        # Playlist with non-default position
        playlist = PlaylistDefinition(
            name="Real TV",
            shows=[PlaylistShow(name="ShowA", current_season=3, current_episode=7)],
            breaks=BreakConfig(enabled=False),
        )

        mock_pc.get_show.return_value = shows["ShowA"]
        mock_pc.get_commercials.return_value = []
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, playlist, server, episode_count=1, from_start=True)
        # Position should have been reset to S01E01, then advanced to S01E02
        assert playlist.shows[0].current_season == 1
        assert playlist.shows[0].current_episode == 2

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_with_single_commercials(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        random.seed(42)
        config, playlist, server, shows = self._setup_mocks(
            {"ShowA": {1: 10}},
            break_style="single",
        )

        mock_pc.get_show.return_value = shows["ShowA"]
        commercials = [_make_mock_commercial(f"Ad{i}", 30000) for i in range(5)]
        mock_pc.get_commercials.return_value = commercials
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, playlist, server, episode_count=3, from_start=True)
        assert sum(result.episodes_by_show.values()) == 3
        assert result.commercial_block_count == 2  # after ep 1 and ep 2 (not after last)
        assert len(result.playlist_items) == 5  # 3 episodes + 2 single commercials

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_no_shows_raises(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config = _make_config(global_shows=[])
        playlist = PlaylistDefinition(name="Empty", shows=[])
        server = MagicMock()
        with pytest.raises(ValueError, match="has no shows"):
            generate_playlist(config, playlist, server, episode_count=10, from_start=True)

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_commercial_frequency_2(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """Commercial blocks every 2 episodes instead of every 1."""
        random.seed(42)
        config, playlist, server, shows = self._setup_mocks(
            {"ShowA": {1: 10}},
            frequency=2,
        )

        mock_pc.get_show.return_value = shows["ShowA"]
        commercials = [_make_mock_commercial(f"Ad{i}", 30000) for i in range(5)]
        mock_pc.get_commercials.return_value = commercials
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, playlist, server, episode_count=6, from_start=True)
        # 6 episodes with frequency 2 = 2 commercial blocks (after ep 2, 4; not after 6)
        assert result.commercial_block_count == 2

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_commercial_frequency_3(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """Commercial blocks every 3 episodes."""
        random.seed(42)
        config, playlist, server, shows = self._setup_mocks(
            {"ShowA": {1: 10}},
            frequency=3,
        )

        mock_pc.get_show.return_value = shows["ShowA"]
        commercials = [_make_mock_commercial(f"Ad{i}", 30000) for i in range(5)]
        mock_pc.get_commercials.return_value = commercials
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, playlist, server, episode_count=9, from_start=True)
        # 9 episodes with frequency 3 = 2 commercial blocks (after ep 3, 6; not after 9)
        assert result.commercial_block_count == 2

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_season_advancement_integration(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """Show advances from season 1 to season 2 during generation."""
        config, playlist, server, shows = self._setup_mocks({"ShowA": {1: 2, 2: 3}})

        mock_pc.get_show.return_value = shows["ShowA"]
        mock_pc.get_commercials.return_value = []
        mock_pc.get_episode.side_effect = _mock_get_episode

        def mock_next_season(show: object, current: int) -> int | None:
            seasons = sorted(s.index for s in show.seasons())
            for sn in seasons:
                if sn > current:
                    return sn
            return None

        mock_pc.get_next_season_number.side_effect = mock_next_season

        result = generate_playlist(config, playlist, server, episode_count=4, from_start=True)
        assert result.episodes_by_show["ShowA"] == 4
        # Positions saved back to playlist show
        assert playlist.shows[0].current_season == 2
        assert playlist.shows[0].current_episode == 3

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_all_shows_exhaust(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """All shows exhaust — generation stops early."""
        config, playlist, server, shows = self._setup_mocks({
            "ShowA": {1: 2},
            "ShowB": {1: 1},
        })

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return shows[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, playlist, server, episode_count=100, from_start=True)
        total = sum(result.episodes_by_show.values())
        assert total == 3
        assert "ShowA" in result.dropped_shows
        assert "ShowB" in result.dropped_shows


# ---------------------------------------------------------------------------
# Disabled shows (GlobalShow.enabled=False)
# ---------------------------------------------------------------------------


class TestDisabledShows:
    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_disabled_show_skipped(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """GlobalShow with enabled=False is excluded from generation."""
        config = _make_config(global_shows=[
            GlobalShow(name="Active", library="TV Shows"),
            GlobalShow(name="Disabled", library="TV Shows", enabled=False),
        ])
        playlist = _make_playlist(show_names=["Active", "Disabled"])

        mock_show = _make_mock_show("Active", {1: 10})
        mock_disabled = _make_mock_show("Disabled", {1: 10})

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return {"Active": mock_show, "Disabled": mock_disabled}[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        server = MagicMock()
        result = generate_playlist(config, playlist, server, episode_count=3, from_start=True)

        # Only Active should have episodes
        assert result.episodes_by_show.get("Active") == 3
        assert "Disabled" not in result.episodes_by_show


# ---------------------------------------------------------------------------
# Break styles: disabled, single, block
# ---------------------------------------------------------------------------


class TestBreakStyles:
    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_breaks_disabled(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """When breaks.enabled=False, no commercials are inserted."""
        config, playlist, server, shows = TestGeneratePlaylist()._setup_mocks(
            {"ShowA": {1: 10}},
            break_enabled=False,
        )

        mock_pc.get_show.return_value = shows["ShowA"]
        mock_pc.get_commercials.return_value = [_make_mock_commercial(f"Ad{i}") for i in range(5)]
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, playlist, server, episode_count=5, from_start=True)
        assert result.commercial_block_count == 0
        assert result.commercial_total_secs == 0.0
        assert len(result.playlist_items) == 5  # episodes only

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_block_style_commercials(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """Block-style breaks insert multi-clip blocks."""
        random.seed(42)
        config, _, server, shows = TestGeneratePlaylist()._setup_mocks(
            {"ShowA": {1: 10}},
        )
        playlist = _make_playlist(
            show_names=["ShowA"],
            break_style="block",
            frequency=1,
            block_min=30,
            block_max=60,
        )

        mock_pc.get_show.return_value = shows["ShowA"]
        commercials = [_make_mock_commercial(f"Ad{i}", 15000) for i in range(20)]
        mock_pc.get_commercials.return_value = commercials
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, playlist, server, episode_count=3, from_start=True)
        assert result.commercial_block_count >= 1
        assert result.commercial_total_secs > 0.0
        # More items than just episodes (blocks add multiple clips)
        assert len(result.playlist_items) > 3


# ---------------------------------------------------------------------------
# Progress callback
# ---------------------------------------------------------------------------


class TestProgressCallback:
    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_callback_invoked(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """progress_callback is called for each episode added."""
        config, playlist, server, shows = TestGeneratePlaylist()._setup_mocks(
            {"ShowA": {1: 10}},
            break_enabled=False,
        )

        mock_pc.get_show.return_value = shows["ShowA"]
        mock_pc.get_commercials.return_value = []
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        progress_calls: list[tuple[int, int]] = []

        def callback(current: int, total: int) -> None:
            progress_calls.append((current, total))

        result = generate_playlist(
            config, playlist, server, episode_count=5, from_start=True,
            progress_callback=callback,
        )
        assert len(progress_calls) == 5
        assert progress_calls[0] == (1, 5)
        assert progress_calls[-1] == (5, 5)

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_callback_none_is_fine(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """progress_callback=None doesn't crash."""
        config, playlist, server, shows = TestGeneratePlaylist()._setup_mocks(
            {"ShowA": {1: 10}},
            break_enabled=False,
        )

        mock_pc.get_show.return_value = shows["ShowA"]
        mock_pc.get_commercials.return_value = []
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(
            config, playlist, server, episode_count=2, from_start=True,
            progress_callback=None,
        )
        assert result.episodes_by_show["ShowA"] == 2


# ---------------------------------------------------------------------------
# Per-playlist episodes_per_generation default
# ---------------------------------------------------------------------------


class TestEpisodesPerGeneration:
    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_uses_playlist_default_when_none(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """When episode_count=None, uses playlist.episodes_per_generation."""
        config = _make_config(global_shows=[GlobalShow(name="ShowA")])
        playlist = _make_playlist(
            show_names=["ShowA"],
            episodes_per_generation=5,
            break_enabled=False,
        )
        mock_show = _make_mock_show("ShowA", {1: 10})
        mock_pc.get_show.return_value = mock_show
        mock_pc.get_commercials.return_value = []
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        server = MagicMock()
        result = generate_playlist(config, playlist, server, episode_count=None, from_start=True)
        assert result.episodes_by_show["ShowA"] == 5


# ---------------------------------------------------------------------------
# Sort order tests
# ---------------------------------------------------------------------------


class TestSortByPremiereYear:
    """Test that sort_by on the playlist controls round-robin order."""

    def _setup_sorted_mocks(
        self,
        sort_by: str,
    ) -> tuple[RTVConfig, PlaylistDefinition, MagicMock, dict[str, MagicMock]]:
        global_shows = [
            GlobalShow(name="ShowC", library="TV Shows", year=2010),
            GlobalShow(name="ShowA", library="TV Shows", year=1990),
            GlobalShow(name="ShowB", library="TV Shows", year=2000),
        ]
        config = _make_config(global_shows=global_shows, block_min=30, block_max=60)
        playlist = _make_playlist(
            show_names=["ShowC", "ShowA", "ShowB"],
            sort_by=sort_by,
            break_enabled=False,
        )

        mock_server = MagicMock()
        mock_shows: dict[str, MagicMock] = {}
        for gs in global_shows:
            mock_shows[gs.name] = _make_mock_show(gs.name, {1: 10})
            mock_shows[gs.name].year = gs.year

        return config, playlist, mock_server, mock_shows

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_premiere_year_oldest_first(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config, playlist, server, shows = self._setup_sorted_mocks("premiere_year")

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return shows[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, playlist, server, episode_count=3, from_start=True)
        items = result.playlist_items
        assert items[0].title == "S01E01"  # ShowA first (1990)
        assert result.episodes_by_show["ShowA"] == 1
        assert result.episodes_by_show["ShowB"] == 1
        assert result.episodes_by_show["ShowC"] == 1

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_premiere_year_desc(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config, playlist, server, shows = self._setup_sorted_mocks("premiere_year_desc")

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return shows[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, playlist, server, episode_count=3, from_start=True)
        assert result.episodes_by_show["ShowC"] == 1
        assert result.episodes_by_show["ShowB"] == 1
        assert result.episodes_by_show["ShowA"] == 1

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_alphabetical_sort(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config, playlist, server, shows = self._setup_sorted_mocks("alphabetical")

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return shows[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, playlist, server, episode_count=3, from_start=True)
        assert result.episodes_by_show["ShowA"] == 1
        assert result.episodes_by_show["ShowB"] == 1
        assert result.episodes_by_show["ShowC"] == 1

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_none_years_sorted_to_end(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config = _make_config(global_shows=[
            GlobalShow(name="NoYear", library="TV Shows"),
            GlobalShow(name="OldShow", library="TV Shows", year=1990),
        ])
        playlist = _make_playlist(
            show_names=["NoYear", "OldShow"],
            sort_by="premiere_year",
            break_enabled=False,
        )

        mock_shows = {
            "NoYear": _make_mock_show("NoYear", {1: 10}),
            "OldShow": _make_mock_show("OldShow", {1: 10}),
        }
        mock_shows["NoYear"].year = None
        mock_shows["OldShow"].year = 1990

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return mock_shows[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []
        mock_pc.get_episode.side_effect = _mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        server = MagicMock()
        result = generate_playlist(config, playlist, server, episode_count=2, from_start=True)
        # OldShow (1990) should come first, NoYear sorted to end
        assert result.episodes_by_show["OldShow"] == 1
        assert result.episodes_by_show["NoYear"] == 1


# ---------------------------------------------------------------------------
# TestPickSingleCommercial
# ---------------------------------------------------------------------------


class TestPickSingleCommercial:
    def test_returns_none_for_empty_list(self) -> None:
        history: deque[int] = deque(maxlen=50)
        clip, duration = pick_single_commercial([], history)
        assert clip is None
        assert duration == 0.0

    def test_returns_single_commercial(self) -> None:
        clips = [_make_mock_commercial(f"Ad{i}", 30000) for i in range(10)]
        history: deque[int] = deque(maxlen=50)
        clip, duration = pick_single_commercial(clips, history)
        assert clip is not None
        assert duration == 30.0
        assert len(history) == 1

    def test_no_repeat_within_gap(self) -> None:
        """No commercial should repeat within min_gap plays."""
        random.seed(42)
        clips = [_make_mock_commercial(f"Ad{i}", 30000) for i in range(60)]
        min_gap = 50
        history: deque[int] = deque(maxlen=min_gap)

        seen_indices: list[int] = []
        for _ in range(100):
            clip, _ = pick_single_commercial(clips, history, min_gap)
            assert clip is not None
            idx = history[-1]
            seen_indices.append(idx)

        for i in range(len(seen_indices)):
            window_start = max(0, i - min_gap + 1)
            window = seen_indices[window_start:i]
            assert seen_indices[i] not in window, (
                f"Commercial {seen_indices[i]} repeated within {min_gap}-item window at position {i}"
            )

    def test_fallback_when_pool_smaller_than_gap(self) -> None:
        """When pool < min_gap, should still return a commercial (oldest used)."""
        clips = [_make_mock_commercial(f"Ad{i}", 30000) for i in range(3)]
        min_gap = 50
        history: deque[int] = deque(maxlen=min_gap)

        for _ in range(3):
            clip, _ = pick_single_commercial(clips, history, min_gap)
            assert clip is not None

        clip, _ = pick_single_commercial(clips, history, min_gap)
        assert clip is not None
        assert history[-1] == history[0]

    def test_history_tracks_across_calls(self) -> None:
        clips = [_make_mock_commercial(f"Ad{i}", 30000) for i in range(5)]
        history: deque[int] = deque(maxlen=50)

        for _ in range(5):
            pick_single_commercial(clips, history)

        assert len(history) == 5

    def test_default_duration_for_zero(self) -> None:
        """Clips with 0 duration should get default 30s."""
        clip = _make_mock_commercial("Ad0", 0)
        history: deque[int] = deque(maxlen=50)
        result_clip, duration = pick_single_commercial([clip], history)
        assert duration == 30.0


# ---------------------------------------------------------------------------
# TestBuildCommercialBlockDuration
# ---------------------------------------------------------------------------


class TestBuildCommercialBlockDuration:
    def test_block_duration_within_bounds(self) -> None:
        """Block duration should reach at least the minimum target."""
        random.seed(42)
        clips = [_make_mock_commercial(f"Ad{i}", 15000) for i in range(20)]
        config = CommercialConfig(
            library_path="C:\\test",
            block_duration=BlockDuration(min=60, max=120),
        )
        for _ in range(10):
            block, duration = build_commercial_block(clips, config, {})
            assert duration >= 60.0
            assert len(block) >= 4


# ---------------------------------------------------------------------------
# TestGetDurationSecs
# ---------------------------------------------------------------------------


class TestGetDurationSecs:
    def test_normal_duration(self) -> None:
        item = MagicMock()
        item.duration = 1800000  # 30 minutes
        assert _get_duration_secs(item) == 1800.0

    def test_no_duration(self) -> None:
        item = MagicMock()
        item.duration = None
        assert _get_duration_secs(item) == 0.0

    def test_zero_duration(self) -> None:
        item = MagicMock()
        item.duration = 0
        assert _get_duration_secs(item) == 0.0
