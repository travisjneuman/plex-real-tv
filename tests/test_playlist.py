"""Tests for playlist generation algorithm."""

from __future__ import annotations

import random
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from rtv.config import (
    RTVConfig,
    PlexConfig,
    ShowConfig,
    CommercialConfig,
    CommercialCategory,
    BlockDuration,
    PlaylistConfig,
)
from rtv.playlist import (
    generate_playlist,
    build_commercial_block,
    pick_single_commercial,
    _get_next_episode,
    ShowState,
    _get_duration_secs,
)


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


def _make_config(
    shows: list[ShowConfig] | None = None,
    commercial_categories: list[CommercialCategory] | None = None,
    block_min: int = 60,
    block_max: int = 120,
    episodes_per_gen: int = 30,
    commercial_frequency: int = 1,
) -> RTVConfig:
    """Build a test config."""
    return RTVConfig(
        plex=PlexConfig(token="test"),
        shows=shows or [],
        commercials=CommercialConfig(
            library_path="D:\\Media\\Commercials",
            block_duration=BlockDuration(min=block_min, max=block_max),
            categories=commercial_categories or [],
        ),
        playlist=PlaylistConfig(
            episodes_per_generation=episodes_per_gen,
            commercial_frequency=commercial_frequency,
        ),
    )


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
        assert duration >= 60.0  # Should meet minimum

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
        # Run many times to check weight bias
        eighty_count = 0
        toy_count = 0
        for _ in range(100):
            block, _ = build_commercial_block(all_clips, config, {})
            for clip in block:
                if "80s" in clip.locations[0]:
                    eighty_count += 1
                elif "toys" in clip.locations[0]:
                    toy_count += 1
        # 80s should appear much more often due to 100x weight
        assert eighty_count > toy_count * 2


class TestGetNextEpisode:
    def test_normal_episode(self) -> None:
        show = _make_mock_show("Test", {1: 10})
        state = ShowState(
            config=ShowConfig(name="Test"),
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
        state = ShowState(
            config=ShowConfig(name="Test"),
            plex_show=show,
            current_season=1,
            current_episode=4,  # Beyond season 1's 3 episodes
        )
        with patch("rtv.plex_client.get_episode") as mock_get, \
             patch("rtv.plex_client.get_next_season_number") as mock_next:
            mock_get.side_effect = [None, _make_mock_episode(2, 1)]  # First call fails, second succeeds
            mock_next.return_value = 2
            ep = _get_next_episode(state)
            assert ep is not None
            assert state.current_season == 2
            assert state.current_episode == 1

    def test_show_exhausted(self) -> None:
        show = _make_mock_show("Test", {1: 3})
        state = ShowState(
            config=ShowConfig(name="Test"),
            plex_show=show,
            current_season=1,
            current_episode=4,  # Beyond all episodes
        )
        with patch("rtv.plex_client.get_episode") as mock_get, \
             patch("rtv.plex_client.get_next_season_number") as mock_next:
            mock_get.return_value = None
            mock_next.return_value = None
            ep = _get_next_episode(state)
            assert ep is None


class TestGeneratePlaylist:
    def _setup_mocks(
        self,
        shows_data: dict[str, dict[int, int]],
        commercial_count: int = 5,
    ) -> tuple[RTVConfig, MagicMock, dict[str, MagicMock]]:
        """Set up mocks for generate_playlist testing.

        Args:
            shows_data: {"ShowName": {season_num: ep_count, ...}, ...}
            commercial_count: Number of mock commercials

        Returns:
            (config, mock_server, {show_name: mock_show_obj})
        """
        show_configs = [
            ShowConfig(name=name, library="TV Shows")
            for name in shows_data
        ]
        config = _make_config(
            shows=show_configs,
            block_min=30,
            block_max=60,
        )

        mock_server = MagicMock()
        mock_shows = {}
        for name, seasons in shows_data.items():
            mock_shows[name] = _make_mock_show(name, seasons)

        return config, mock_server, mock_shows

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_single_show(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config, server, shows = self._setup_mocks({"ShowA": {1: 5}})

        mock_pc.get_show.return_value = shows["ShowA"]
        mock_pc.get_commercials.return_value = []

        def mock_get_episode(show: object, season: int, episode: int) -> MagicMock | None:
            try:
                s = show.season(season=season)
                for ep in s.episodes():
                    if ep.index == episode:
                        return ep
            except Exception:
                pass
            return None

        mock_pc.get_episode.side_effect = mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, server, episode_count=3, from_start=True)
        assert result.episodes_by_show["ShowA"] == 3
        assert len(result.playlist_items) == 3
        assert result.commercial_block_count == 0  # No commercials available

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_round_robin_two_shows(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config, server, shows = self._setup_mocks({
            "ShowA": {1: 10},
            "ShowB": {1: 10},
        })

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return shows[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []

        def mock_get_episode(show: object, season: int, episode: int) -> MagicMock | None:
            try:
                s = show.season(season=season)
                for ep in s.episodes():
                    if ep.index == episode:
                        return ep
            except Exception:
                pass
            return None

        mock_pc.get_episode.side_effect = mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, server, episode_count=6, from_start=True)
        assert result.episodes_by_show["ShowA"] == 3
        assert result.episodes_by_show["ShowB"] == 3

        # Verify alternating pattern: A, B, A, B, A, B
        items = result.playlist_items
        for i, item in enumerate(items):
            expected_show = "ShowA" if i % 2 == 0 else "ShowB"
            # The mock episodes have show title embedded via the parent show
            assert item.parentIndex == 1  # All season 1

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_round_robin_three_shows(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config, server, shows = self._setup_mocks({
            "ShowA": {1: 10},
            "ShowB": {1: 10},
            "ShowC": {1: 10},
        })

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return shows[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []

        def mock_get_episode(show: object, season: int, episode: int) -> MagicMock | None:
            try:
                s = show.season(season=season)
                for ep in s.episodes():
                    if ep.index == episode:
                        return ep
            except Exception:
                pass
            return None

        mock_pc.get_episode.side_effect = mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, server, episode_count=9, from_start=True)
        assert result.episodes_by_show["ShowA"] == 3
        assert result.episodes_by_show["ShowB"] == 3
        assert result.episodes_by_show["ShowC"] == 3

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_show_exhaustion(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """Show with fewer episodes drops out, others continue."""
        config, server, shows = self._setup_mocks({
            "ShowA": {1: 10},
            "ShowB": {1: 2},  # Only 2 episodes
        })

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return shows[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []

        def mock_get_episode(show: object, season: int, episode: int) -> MagicMock | None:
            try:
                s = show.season(season=season)
                for ep in s.episodes():
                    if ep.index == episode:
                        return ep
            except Exception:
                pass
            return None

        mock_pc.get_episode.side_effect = mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, server, episode_count=6, from_start=True)
        # ShowB has 2 eps, ShowA fills the rest
        assert result.episodes_by_show["ShowB"] == 2
        assert result.episodes_by_show["ShowA"] == 4
        assert "ShowB" in result.dropped_shows

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_from_start_resets_positions(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config, server, shows = self._setup_mocks({"ShowA": {1: 10}})
        config.shows[0].current_season = 3
        config.shows[0].current_episode = 7

        mock_pc.get_show.return_value = shows["ShowA"]
        mock_pc.get_commercials.return_value = []

        def mock_get_episode(show: object, season: int, episode: int) -> MagicMock | None:
            try:
                s = show.season(season=season)
                for ep in s.episodes():
                    if ep.index == episode:
                        return ep
            except Exception:
                pass
            return None

        mock_pc.get_episode.side_effect = mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, server, episode_count=1, from_start=True)
        # Position should have been reset to S01E01, then advanced to S01E02
        assert config.shows[0].current_season == 1
        assert config.shows[0].current_episode == 2

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_with_commercials(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        random.seed(42)
        config, server, shows = self._setup_mocks({"ShowA": {1: 10}})

        mock_pc.get_show.return_value = shows["ShowA"]

        commercials = [_make_mock_commercial(f"Ad{i}", 30000) for i in range(5)]
        mock_pc.get_commercials.return_value = commercials

        def mock_get_episode(show: object, season: int, episode: int) -> MagicMock | None:
            try:
                s = show.season(season=season)
                for ep in s.episodes():
                    if ep.index == episode:
                        return ep
            except Exception:
                pass
            return None

        mock_pc.get_episode.side_effect = mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, server, episode_count=3, from_start=True)
        # Should have 3 episodes + 2 single commercials (not after last episode)
        assert sum(result.episodes_by_show.values()) == 3
        assert result.commercial_block_count == 2
        assert len(result.playlist_items) == 5  # 3 episodes + 2 single commercials

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_no_shows_raises(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config = _make_config(shows=[])
        server = MagicMock()
        with pytest.raises(ValueError, match="No shows in rotation"):
            generate_playlist(config, server, episode_count=10, from_start=True)

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_commercial_frequency_2(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """Commercial blocks every 2 episodes instead of every 1."""
        random.seed(42)
        config, server, shows = self._setup_mocks({"ShowA": {1: 10}})
        config.playlist.commercial_frequency = 2

        mock_pc.get_show.return_value = shows["ShowA"]
        commercials = [_make_mock_commercial(f"Ad{i}", 30000) for i in range(5)]
        mock_pc.get_commercials.return_value = commercials

        def mock_get_episode(show: object, season: int, episode: int) -> MagicMock | None:
            try:
                s = show.season(season=season)
                for ep in s.episodes():
                    if ep.index == episode:
                        return ep
            except Exception:
                pass
            return None

        mock_pc.get_episode.side_effect = mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, server, episode_count=6, from_start=True)
        # 6 episodes with frequency 2 = 2 commercial blocks (after ep 2, 4; not after 6)
        assert result.commercial_block_count == 2


    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_commercial_frequency_3(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """Commercial blocks every 3 episodes."""
        random.seed(42)
        config, server, shows = self._setup_mocks({"ShowA": {1: 10}})
        config.playlist.commercial_frequency = 3

        mock_pc.get_show.return_value = shows["ShowA"]
        commercials = [_make_mock_commercial(f"Ad{i}", 30000) for i in range(5)]
        mock_pc.get_commercials.return_value = commercials

        def mock_get_episode(show: object, season: int, episode: int) -> MagicMock | None:
            try:
                s = show.season(season=season)
                for ep in s.episodes():
                    if ep.index == episode:
                        return ep
            except Exception:
                pass
            return None

        mock_pc.get_episode.side_effect = mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, server, episode_count=9, from_start=True)
        # 9 episodes with frequency 3 = 2 commercial blocks (after ep 3, 6; not after 9)
        assert result.commercial_block_count == 2

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_season_advancement_integration(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """Show advances from season 1 to season 2 during generation."""
        config, server, shows = self._setup_mocks({"ShowA": {1: 2, 2: 3}})

        mock_pc.get_show.return_value = shows["ShowA"]
        mock_pc.get_commercials.return_value = []

        def mock_get_episode(show: object, season: int, episode: int) -> MagicMock | None:
            try:
                s = show.season(season=season)
                for ep in s.episodes():
                    if ep.index == episode:
                        return ep
            except Exception:
                pass
            return None

        def mock_next_season(show: object, current: int) -> int | None:
            seasons = sorted(s.index for s in show.seasons())
            for sn in seasons:
                if sn > current:
                    return sn
            return None

        mock_pc.get_episode.side_effect = mock_get_episode
        mock_pc.get_next_season_number.side_effect = mock_next_season

        result = generate_playlist(config, server, episode_count=4, from_start=True)
        # S1E1, S1E2, then advances to S2E1, S2E2
        assert result.episodes_by_show["ShowA"] == 4
        assert config.shows[0].current_season == 2
        assert config.shows[0].current_episode == 3  # next would be S2E3

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_all_shows_exhaust(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        """All shows exhaust — generation stops early."""
        config, server, shows = self._setup_mocks({
            "ShowA": {1: 2},
            "ShowB": {1: 1},
        })

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return shows[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []

        def mock_get_episode(show: object, season: int, episode: int) -> MagicMock | None:
            try:
                s = show.season(season=season)
                for ep in s.episodes():
                    if ep.index == episode:
                        return ep
            except Exception:
                pass
            return None

        mock_pc.get_episode.side_effect = mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, server, episode_count=100, from_start=True)
        # Only 3 total episodes available (2 + 1)
        total = sum(result.episodes_by_show.values())
        assert total == 3
        assert "ShowA" in result.dropped_shows
        assert "ShowB" in result.dropped_shows


class TestSortByPremiereYear:
    """Test that sort_by controls round-robin order in generate_playlist."""

    def _setup_sorted_mocks(
        self,
        sort_by: str,
    ) -> tuple[RTVConfig, MagicMock, dict[str, MagicMock]]:
        show_configs = [
            ShowConfig(name="ShowC", library="TV Shows", year=2010),
            ShowConfig(name="ShowA", library="TV Shows", year=1990),
            ShowConfig(name="ShowB", library="TV Shows", year=2000),
        ]
        config = _make_config(
            shows=show_configs,
            block_min=30,
            block_max=60,
        )
        config.playlist.sort_by = sort_by

        mock_server = MagicMock()
        mock_shows: dict[str, MagicMock] = {}
        for sc in show_configs:
            mock_shows[sc.name] = _make_mock_show(sc.name, {1: 10})
            mock_shows[sc.name].year = sc.year

        return config, mock_server, mock_shows

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_premiere_year_oldest_first(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config, server, shows = self._setup_sorted_mocks("premiere_year")

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return shows[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []

        def mock_get_episode(show: object, season: int, episode: int) -> MagicMock | None:
            try:
                s = show.season(season=season)
                for ep in s.episodes():
                    if ep.index == episode:
                        return ep
            except Exception:
                pass
            return None

        mock_pc.get_episode.side_effect = mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, server, episode_count=3, from_start=True)
        # With premiere_year sort: ShowA(1990), ShowB(2000), ShowC(2010)
        items = result.playlist_items
        assert items[0].title == "S01E01"  # ShowA first (1990)
        # Verify all 3 shows got 1 episode each
        assert result.episodes_by_show["ShowA"] == 1
        assert result.episodes_by_show["ShowB"] == 1
        assert result.episodes_by_show["ShowC"] == 1

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_premiere_year_desc(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config, server, shows = self._setup_sorted_mocks("premiere_year_desc")

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return shows[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []

        def mock_get_episode(show: object, season: int, episode: int) -> MagicMock | None:
            try:
                s = show.season(season=season)
                for ep in s.episodes():
                    if ep.index == episode:
                        return ep
            except Exception:
                pass
            return None

        mock_pc.get_episode.side_effect = mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, server, episode_count=3, from_start=True)
        # With desc sort: ShowC(2010), ShowB(2000), ShowA(1990)
        assert result.episodes_by_show["ShowC"] == 1
        assert result.episodes_by_show["ShowB"] == 1
        assert result.episodes_by_show["ShowA"] == 1

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_alphabetical_sort(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        config, server, shows = self._setup_sorted_mocks("alphabetical")

        def mock_get_show(s: object, name: str, lib: str) -> MagicMock:
            return shows[name]

        mock_pc.get_show.side_effect = mock_get_show
        mock_pc.get_commercials.return_value = []

        def mock_get_episode(show: object, season: int, episode: int) -> MagicMock | None:
            try:
                s = show.season(season=season)
                for ep in s.episodes():
                    if ep.index == episode:
                        return ep
            except Exception:
                pass
            return None

        mock_pc.get_episode.side_effect = mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        result = generate_playlist(config, server, episode_count=3, from_start=True)
        # Alphabetical: ShowA, ShowB, ShowC
        assert result.episodes_by_show["ShowA"] == 1
        assert result.episodes_by_show["ShowB"] == 1
        assert result.episodes_by_show["ShowC"] == 1

    @patch("rtv.playlist.plex_client")
    @patch("rtv.playlist.display")
    def test_none_years_sorted_to_end(self, mock_display: MagicMock, mock_pc: MagicMock) -> None:
        show_configs = [
            ShowConfig(name="NoYear", library="TV Shows"),  # year=None
            ShowConfig(name="OldShow", library="TV Shows", year=1990),
        ]
        config = _make_config(shows=show_configs, block_min=30, block_max=60)
        config.playlist.sort_by = "premiere_year"

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

        def mock_get_episode(show: object, season: int, episode: int) -> MagicMock | None:
            try:
                s = show.season(season=season)
                for ep in s.episodes():
                    if ep.index == episode:
                        return ep
            except Exception:
                pass
            return None

        mock_pc.get_episode.side_effect = mock_get_episode
        mock_pc.get_next_season_number.return_value = None

        server = MagicMock()
        result = generate_playlist(config, server, episode_count=2, from_start=True)
        # OldShow (1990) should come first, NoYear sorted to end
        assert result.episodes_by_show["OldShow"] == 1
        assert result.episodes_by_show["NoYear"] == 1


class TestPickSingleCommercial:
    def test_returns_none_for_empty_list(self) -> None:
        from collections import deque
        history: deque[int] = deque(maxlen=50)
        clip, duration = pick_single_commercial([], history)
        assert clip is None
        assert duration == 0.0

    def test_returns_single_commercial(self) -> None:
        from collections import deque
        clips = [_make_mock_commercial(f"Ad{i}", 30000) for i in range(10)]
        history: deque[int] = deque(maxlen=50)
        clip, duration = pick_single_commercial(clips, history)
        assert clip is not None
        assert duration == 30.0
        assert len(history) == 1

    def test_no_repeat_within_gap(self) -> None:
        """No commercial should repeat within min_gap plays."""
        random.seed(42)
        from collections import deque
        clips = [_make_mock_commercial(f"Ad{i}", 30000) for i in range(60)]
        min_gap = 50
        history: deque[int] = deque(maxlen=min_gap)

        seen_indices: list[int] = []
        for _ in range(100):
            clip, _ = pick_single_commercial(clips, history, min_gap)
            assert clip is not None
            # Find which index was just added
            idx = history[-1]
            seen_indices.append(idx)

        # Check that no index repeats within a window of min_gap
        for i in range(len(seen_indices)):
            window_start = max(0, i - min_gap + 1)
            window = seen_indices[window_start:i]
            assert seen_indices[i] not in window, (
                f"Commercial {seen_indices[i]} repeated within {min_gap}-item window at position {i}"
            )

    def test_fallback_when_pool_smaller_than_gap(self) -> None:
        """When pool < min_gap, should still return a commercial (oldest used)."""
        from collections import deque
        clips = [_make_mock_commercial(f"Ad{i}", 30000) for i in range(3)]
        min_gap = 50
        history: deque[int] = deque(maxlen=min_gap)

        # Use all 3 commercials
        for _ in range(3):
            clip, _ = pick_single_commercial(clips, history, min_gap)
            assert clip is not None

        # 4th pick: all are in history, should fall back to oldest
        clip, _ = pick_single_commercial(clips, history, min_gap)
        assert clip is not None
        # The oldest entry (index 0 from first pick) should be reused
        assert history[-1] == history[0]

    def test_history_tracks_across_calls(self) -> None:
        from collections import deque
        clips = [_make_mock_commercial(f"Ad{i}", 30000) for i in range(5)]
        history: deque[int] = deque(maxlen=50)

        for _ in range(5):
            pick_single_commercial(clips, history)

        assert len(history) == 5

    def test_default_duration_for_zero(self) -> None:
        """Clips with 0 duration should get default 30s."""
        from collections import deque
        clip = _make_mock_commercial("Ad0", 0)
        history: deque[int] = deque(maxlen=50)
        result_clip, duration = pick_single_commercial([clip], history)
        assert duration == 30.0


class TestBuildCommercialBlockDuration:
    def test_block_duration_within_bounds(self) -> None:
        """Block duration should reach at least the minimum target."""
        random.seed(42)
        clips = [_make_mock_commercial(f"Ad{i}", 15000) for i in range(20)]  # 15s each
        config = CommercialConfig(
            library_path="C:\\test",
            block_duration=BlockDuration(min=60, max=120),
        )
        # Run multiple times to verify consistency
        for _ in range(10):
            block, duration = build_commercial_block(clips, config, {})
            # Duration should always reach at least the minimum
            assert duration >= 60.0
            assert len(block) >= 4  # At least 4x15s to reach 60s


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
