"""Playlists screen — list, inspect, and manage playlists."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Static,
)
from textual.containers import Horizontal, Vertical

from rtv.config import (
    RTVConfig,
    PlaylistDefinition,
    PlaylistShow,
    BreakConfig,
    load_config,
    save_config,
    find_config_path,
)


class PlaylistsScreen(Screen):
    """Browse playlists and drill into details."""

    BINDINGS = [
        ("enter", "select_playlist", "View Details"),
        ("n", "new_playlist", "New Playlist"),
        ("g", "generate_selected", "Generate"),
        ("delete", "delete_playlist", "Delete"),
        ("r", "reload", "Reload"),
        ("escape", "go_back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._config: RTVConfig | None = None
        self._config_path = find_config_path()
        self._selected_playlist: PlaylistDefinition | None = None
        self._showing_new_input = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="playlists-container"):
            with Horizontal(id="playlists-top"):
                yield Button("New Playlist", id="btn-new-playlist")
                yield Input(
                    placeholder="Enter playlist name...",
                    id="new-playlist-input",
                    display=False,
                )
            yield DataTable(id="playlists-table")
            yield Static("", id="playlist-detail")
            with Horizontal(id="playlist-actions"):
                yield Button("Generate", id="btn-generate", variant="primary")
                yield Button("Set Default", id="btn-set-default")
                yield Button("Delete", id="btn-delete")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#playlists-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("#", "Name", "Shows", "Break Style", "Eps/Gen", "Sort By", "Default")
        self._load_playlists()

    def _load_playlists(self) -> None:
        try:
            self._config = load_config(self._config_path)
        except Exception:
            self._config = None
            self.notify("Could not load config", severity="error")
            return
        self._refresh_table()

    def _refresh_table(self) -> None:
        if self._config is None:
            return

        table = self.query_one("#playlists-table", DataTable)
        table.clear()

        for i, pl in enumerate(self._config.playlists, 1):
            is_default = "Yes" if pl.name == self._config.default_playlist else ""
            break_style = pl.breaks.style if pl.breaks.enabled else "disabled"
            table.add_row(
                str(i),
                pl.name,
                str(len(pl.shows)),
                break_style,
                str(pl.episodes_per_generation),
                pl.sort_by,
                is_default,
                key=pl.name,
            )

        # Clear detail when refreshing
        if self._selected_playlist is not None:
            self._render_detail(self._selected_playlist)
        else:
            self.query_one("#playlist-detail", Static).update("")

    def _render_detail(self, playlist: PlaylistDefinition) -> None:
        """Show detailed info for a selected playlist."""
        if self._config is None:
            return

        lines: list[str] = [
            f"[bold]{playlist.name}[/bold]",
            "",
        ]

        # Show list with positions
        if playlist.shows:
            lines.append("[bold]Shows:[/bold]")
            enabled_map = {s.name.lower(): s.enabled for s in self._config.shows}
            for ps in playlist.shows:
                pos = f"S{ps.current_season:02d}E{ps.current_episode:02d}"
                enabled = enabled_map.get(ps.name.lower(), True)
                marker = "[green]+[/green]" if enabled else "[dim]-[/dim]"
                lines.append(f"  {marker} {ps.name}  ({pos})")
        else:
            lines.append("[dim]No shows in this playlist.[/dim]")

        # Break config
        brk = playlist.breaks
        lines.append("")
        if brk.enabled:
            lines.append(
                f"[bold]Breaks:[/bold] {brk.style}  "
                f"every {brk.frequency} ep(s)  "
                f"min_gap={brk.min_gap}"
            )
            if brk.style == "block":
                lines.append(
                    f"  Block duration: {brk.block_duration.min}-{brk.block_duration.max}s"
                )
        else:
            lines.append("[bold]Breaks:[/bold] disabled")

        lines.append(f"[bold]Episodes/gen:[/bold] {playlist.episodes_per_generation}")
        lines.append(f"[bold]Sort:[/bold] {playlist.sort_by}")

        self.query_one("#playlist-detail", Static).update("\n".join(lines))

    # -- Table selection --------------------------------------------------

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._select_row(event.row_key)

    def _select_row(self, row_key: object) -> None:
        if self._config is None:
            return
        name = str(row_key.value) if hasattr(row_key, "value") else str(row_key)
        pl = self._config.get_playlist(name)
        if pl is not None:
            self._selected_playlist = pl
            self._render_detail(pl)

    # -- Actions ----------------------------------------------------------

    def action_select_playlist(self) -> None:
        table = self.query_one("#playlists-table", DataTable)
        if table.row_count == 0:
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        self._select_row(row_key)

    def action_new_playlist(self) -> None:
        name_input = self.query_one("#new-playlist-input", Input)
        if name_input.display:
            # Already showing — hide it
            name_input.display = False
            self._showing_new_input = False
        else:
            name_input.display = True
            name_input.value = ""
            name_input.focus()
            self._showing_new_input = True

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "new-playlist-input":
            name = event.value.strip()
            if not name:
                self.notify("Playlist name cannot be empty", severity="warning")
                return
            self._create_playlist(name)
            event.input.display = False
            self._showing_new_input = False

    def _create_playlist(self, name: str) -> None:
        if self._config is None:
            return

        existing = self._config.get_playlist(name)
        if existing is not None:
            self.notify(f"Playlist '{name}' already exists", severity="warning")
            return

        new_pl = PlaylistDefinition(
            name=name,
            shows=[],
            breaks=BreakConfig(),
            episodes_per_generation=30,
            sort_by="premiere_year",
        )
        self._config.playlists.append(new_pl)
        save_config(self._config, self._config_path)
        self._selected_playlist = new_pl
        self._refresh_table()
        self.notify(f"Created playlist '{name}'")

    def action_generate_selected(self) -> None:
        if self._selected_playlist is None:
            self.notify("Select a playlist first", severity="warning")
            return
        from rtv.tui.screens.generate import GenerateScreen

        self.app.push_screen(GenerateScreen(self._selected_playlist.name))

    def action_delete_playlist(self) -> None:
        if self._config is None or self._selected_playlist is None:
            self.notify("Select a playlist first", severity="warning")
            return

        name = self._selected_playlist.name
        self._config.playlists = [
            p for p in self._config.playlists if p.name != name
        ]
        save_config(self._config, self._config_path)
        self._selected_playlist = None
        self._refresh_table()
        self.query_one("#playlist-detail", Static).update("")
        self.notify(f"Deleted playlist '{name}'")

    def action_reload(self) -> None:
        self._selected_playlist = None
        self._load_playlists()
        self.notify("Reloaded config")

    def action_go_back(self) -> None:
        if self._showing_new_input:
            self.query_one("#new-playlist-input", Input).display = False
            self._showing_new_input = False
        else:
            self.app.switch_mode("dashboard")

    # -- Button handlers --------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-new-playlist":
            self.action_new_playlist()
        elif event.button.id == "btn-generate":
            self.action_generate_selected()
        elif event.button.id == "btn-set-default":
            self._set_default()
        elif event.button.id == "btn-delete":
            self.action_delete_playlist()

    def _set_default(self) -> None:
        if self._config is None or self._selected_playlist is None:
            self.notify("Select a playlist first", severity="warning")
            return
        self._config.default_playlist = self._selected_playlist.name
        save_config(self._config, self._config_path)
        self._refresh_table()
        self.notify(f"Default playlist set to '{self._selected_playlist.name}'")
