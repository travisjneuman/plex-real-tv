"""Main Textual application for plex-real-tv TUI."""

from __future__ import annotations

from textual.app import App

from rtv.tui.screens.dashboard import DashboardScreen
from rtv.tui.screens.shows import ShowsScreen
from rtv.tui.screens.playlists import PlaylistsScreen


class PlexRealTVApp(App):
    """Full-screen terminal UI for plex-real-tv."""

    TITLE = "plex-real-tv"
    SUB_TITLE = "Simulate real TV on Plex"

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        ("d", "switch_mode('dashboard')", "Dashboard"),
        ("s", "switch_mode('shows')", "Shows"),
        ("p", "switch_mode('playlists')", "Playlists"),
        ("q", "quit", "Quit"),
    ]

    MODES = {
        "dashboard": DashboardScreen,
        "shows": ShowsScreen,
        "playlists": PlaylistsScreen,
    }

    def on_mount(self) -> None:
        self.switch_mode("dashboard")


def run_tui() -> None:
    """Entry point to launch the TUI application."""
    app = PlexRealTVApp()
    app.run()


if __name__ == "__main__":
    run_tui()
