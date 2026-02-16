"""Tests for the plex-real-tv TUI (Textual screens)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from rtv.config import (
    RTVConfig,
    GlobalShow,
    PlaylistDefinition,
    PlaylistShow,
    BreakConfig,
    PlexConfig,
    save_config,
)
from rtv.tui.app import PlexRealTVApp


@pytest.fixture
def tmp_config(tmp_path: Path):
    """Create a temp config file and patch config search paths."""
    config = RTVConfig(
        plex=PlexConfig(url="http://localhost:32400", token="test-token"),
        shows=[
            GlobalShow(name="Seinfeld", library="TV Shows", year=1989, enabled=True),
            GlobalShow(name="Friends", library="TV Shows", year=1994, enabled=True),
            GlobalShow(name="The Office (US)", library="TV Shows", year=2005, enabled=False),
        ],
        playlists=[
            PlaylistDefinition(
                name="Real TV",
                shows=[
                    PlaylistShow(name="Seinfeld"),
                    PlaylistShow(name="Friends"),
                ],
                breaks=BreakConfig(enabled=True, style="single", frequency=1),
                episodes_per_generation=30,
            ),
        ],
        default_playlist="Real TV",
    )
    config_path = tmp_path / "config.yaml"
    save_config(config, config_path)

    with patch("rtv.config.CONFIG_SEARCH_PATHS", [config_path]):
        yield config_path


class TestPlexRealTVApp:
    """Test the main TUI app structure."""

    def test_app_has_modes(self):
        app = PlexRealTVApp()
        assert "dashboard" in app.MODES
        assert "shows" in app.MODES
        assert "playlists" in app.MODES

    def test_app_bindings(self):
        app = PlexRealTVApp()
        # BINDINGS are tuples (key, action, description)
        keys = [b[0] for b in app.BINDINGS]
        assert "d" in keys
        assert "s" in keys
        assert "p" in keys
        assert "q" in keys

    def test_app_title(self):
        app = PlexRealTVApp()
        assert app.TITLE == "plex-real-tv"

    @pytest.mark.asyncio
    async def test_app_mounts_dashboard(self, tmp_config):
        """App should start in dashboard mode on mount."""
        async with PlexRealTVApp().run_test(size=(120, 40)) as pilot:
            # Dashboard is the initial mode
            app = pilot.app
            assert app.current_mode == "dashboard"


class TestDashboardScreen:
    """Test dashboard screen rendering."""

    @pytest.mark.asyncio
    async def test_dashboard_renders(self, tmp_config):
        async with PlexRealTVApp().run_test(size=(120, 40)) as pilot:
            # Should show dashboard content
            app = pilot.app
            assert app.current_mode == "dashboard"


class TestShowsScreen:
    """Test shows screen."""

    @pytest.mark.asyncio
    async def test_shows_screen_switch(self, tmp_config):
        """Pressing 's' switches to shows screen."""
        async with PlexRealTVApp().run_test(size=(120, 40)) as pilot:
            await pilot.press("s")
            assert pilot.app.current_mode == "shows"


class TestPlaylistsScreen:
    """Test playlists screen."""

    @pytest.mark.asyncio
    async def test_playlists_screen_switch(self, tmp_config):
        """Pressing 'p' switches to playlists screen."""
        async with PlexRealTVApp().run_test(size=(120, 40)) as pilot:
            await pilot.press("p")
            assert pilot.app.current_mode == "playlists"
