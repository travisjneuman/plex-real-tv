"""Dashboard screen — Plex connection status, quick stats, recent history."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Static,
)
from textual import work

from rtv.config import RTVConfig, load_config, find_config_path


class StatBox(Static):
    """A single statistic display with value and label."""

    def __init__(self, value: str, label: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._value = value
        self._label = label

    def compose(self) -> ComposeResult:
        yield Static(self._value, classes="stat-value")
        yield Static(self._label, classes="stat-label")

    def update_stat(self, value: str) -> None:
        self._value = value
        try:
            val_widget = self.query_one(".stat-value", Static)
            val_widget.update(value)
        except Exception:
            pass


class DashboardScreen(Screen):
    """Main dashboard showing Plex status, stats, and quick actions."""

    BINDINGS = [
        ("g", "quick_generate", "Quick Generate"),
        ("r", "refresh_status", "Refresh"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._config: RTVConfig | None = None
        self._plex_connected = False
        self._plex_version = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="dashboard-container"):
            yield Static(
                "[bold]Plex Connection[/bold]  [ ... checking ... ]",
                id="status-panel",
            )
            with Horizontal(id="stats-row"):
                yield StatBox("--", "Shows", classes="stat-box", id="stat-shows")
                yield StatBox("--", "Playlists", classes="stat-box", id="stat-playlists")
                yield StatBox("--", "Enabled", classes="stat-box", id="stat-enabled")
                yield StatBox("--", "History", classes="stat-box", id="stat-history")
            yield Static("", id="history-panel")
            with Horizontal(id="quick-actions"):
                yield Button("Generate Default", id="btn-generate", variant="primary")
                yield Button("Refresh", id="btn-refresh")
        yield Footer()

    def on_mount(self) -> None:
        self._load_and_display()

    def _load_and_display(self) -> None:
        """Load config and update stats, then kick off async Plex check."""
        try:
            self._config = load_config(find_config_path())
        except Exception:
            self._config = None

        self._update_stats()
        self._check_plex_connection()

    def _update_stats(self) -> None:
        """Update stat boxes from loaded config."""
        cfg = self._config
        if cfg is None:
            for box_id in ("stat-shows", "stat-playlists", "stat-enabled", "stat-history"):
                try:
                    self.query_one(f"#{box_id}", StatBox).update_stat("?")
                except Exception:
                    pass
            return

        total_shows = len(cfg.shows)
        enabled_shows = sum(1 for s in cfg.shows if s.enabled)
        total_playlists = len(cfg.playlists)
        history_count = len(cfg.history)

        self.query_one("#stat-shows", StatBox).update_stat(str(total_shows))
        self.query_one("#stat-playlists", StatBox).update_stat(str(total_playlists))
        self.query_one("#stat-enabled", StatBox).update_stat(str(enabled_shows))
        self.query_one("#stat-history", StatBox).update_stat(str(history_count))

        # Render recent history
        history_panel = self.query_one("#history-panel", Static)
        if cfg.history:
            last = cfg.history[-1]
            runtime_mins = int(last.runtime_secs) // 60
            hours, mins = divmod(runtime_mins, 60)
            rt_str = f"{hours}h {mins}m" if hours else f"{mins}m"
            history_panel.update(
                f"[bold]Last Generation[/bold]\n"
                f"  Playlist: {last.playlist_name}  |  "
                f"Episodes: {last.episode_count}  |  "
                f"Runtime: {rt_str}  |  "
                f"{last.timestamp}"
            )
        else:
            history_panel.update("[dim]No generation history yet.[/dim]")

    @work(thread=True)
    def _check_plex_connection(self) -> None:
        """Check Plex connectivity in a worker thread."""
        if self._config is None:
            return
        try:
            from rtv.plex_client import connect

            server = connect(self._config.plex)
            self._plex_connected = True
            self._plex_version = getattr(server, "version", "unknown")
        except Exception:
            self._plex_connected = False
            self._plex_version = ""

        self.call_from_thread(self._render_plex_status)

    def _render_plex_status(self) -> None:
        """Update the status panel with Plex connection result."""
        panel = self.query_one("#status-panel", Static)
        if self._config is None:
            panel.update(
                "[bold]Plex Connection[/bold]  "
                "[red]No config file found. Run `rtv init`.[/red]"
            )
            return

        url = self._config.plex.url
        if self._plex_connected:
            panel.update(
                f"[bold]Plex Connection[/bold]  "
                f"[green]Connected[/green] to {url}  "
                f"(v{self._plex_version})"
            )
        else:
            panel.update(
                f"[bold]Plex Connection[/bold]  "
                f"[red]Disconnected[/red] from {url}  "
                f"[dim](check server and token)[/dim]"
            )

    # -- Actions ----------------------------------------------------------

    def action_refresh_status(self) -> None:
        self._load_and_display()

    def action_quick_generate(self) -> None:
        if self._config is None:
            self.notify("No config loaded", severity="error")
            return
        from rtv.tui.screens.generate import GenerateScreen

        default_pl = self._config.get_playlist()
        if default_pl is None:
            self.notify("No default playlist configured", severity="error")
            return
        self.app.push_screen(GenerateScreen(default_pl.name))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-generate":
            self.action_quick_generate()
        elif event.button.id == "btn-refresh":
            self.action_refresh_status()
