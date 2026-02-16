"""Shows screen — browse, search, and toggle global shows."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Static,
)
from textual.containers import Vertical

from rtv.config import RTVConfig, load_config, save_config, find_config_path


class ShowsScreen(Screen):
    """Full show pool browser with search filtering and enable/disable toggle."""

    BINDINGS = [
        ("enter", "toggle_show", "Toggle Enabled"),
        ("e", "enable_all", "Enable All"),
        ("x", "disable_all", "Disable All"),
        ("r", "reload", "Reload"),
        ("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._config: RTVConfig | None = None
        self._config_path = find_config_path()
        self._filter_text = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="shows-container"):
            yield Input(placeholder="Filter shows...", id="show-filter")
            yield DataTable(id="shows-table")
            yield Static("", id="show-status-bar")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#shows-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("#", "Name", "Year", "Library", "Enabled", "Playlists")
        self._load_shows()

    def _load_shows(self) -> None:
        """Load config and populate the table."""
        try:
            self._config = load_config(self._config_path)
        except Exception:
            self._config = None
            self.notify("Could not load config", severity="error")
            return
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Re-render the DataTable from current config and filter."""
        if self._config is None:
            return

        table = self.query_one("#shows-table", DataTable)
        table.clear()

        shows = self._config.shows
        filter_lower = self._filter_text.lower()

        visible_count = 0
        enabled_count = 0
        for i, show in enumerate(shows, 1):
            if filter_lower and filter_lower not in show.name.lower():
                continue
            visible_count += 1
            if show.enabled:
                enabled_count += 1

            year_str = str(show.year) if show.year else "-"
            enabled_str = "Yes" if show.enabled else "No"
            playlists = self._config.get_playlist_membership(show.name)
            playlists_str = ", ".join(playlists) if playlists else "-"

            table.add_row(
                str(i),
                show.name,
                year_str,
                show.library,
                enabled_str,
                playlists_str,
                key=show.name,
            )

        # Update status bar
        total = len(shows)
        status = self.query_one("#show-status-bar", Static)
        status.update(
            f" {visible_count}/{total} shows shown  |  "
            f"{enabled_count} enabled  |  "
            f"Enter=toggle  E=enable all  X=disable all"
        )

    # -- Input events -----------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "show-filter":
            self._filter_text = event.value
            self._refresh_table()

    # -- Actions ----------------------------------------------------------

    def action_toggle_show(self) -> None:
        """Toggle the enabled state of the currently selected show."""
        if self._config is None:
            return

        table = self.query_one("#shows-table", DataTable)
        if table.row_count == 0:
            return

        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        show_name = str(row_key.value)

        show = self._config.get_global_show(show_name)
        if show is None:
            return

        show.enabled = not show.enabled
        self._save_and_refresh()
        state = "enabled" if show.enabled else "disabled"
        self.notify(f"{show.name} {state}")

    def action_enable_all(self) -> None:
        """Enable all shows (respecting current filter)."""
        if self._config is None:
            return
        filter_lower = self._filter_text.lower()
        count = 0
        for show in self._config.shows:
            if filter_lower and filter_lower not in show.name.lower():
                continue
            if not show.enabled:
                show.enabled = True
                count += 1
        self._save_and_refresh()
        self.notify(f"Enabled {count} show(s)")

    def action_disable_all(self) -> None:
        """Disable all shows (respecting current filter)."""
        if self._config is None:
            return
        filter_lower = self._filter_text.lower()
        count = 0
        for show in self._config.shows:
            if filter_lower and filter_lower not in show.name.lower():
                continue
            if show.enabled:
                show.enabled = False
                count += 1
        self._save_and_refresh()
        self.notify(f"Disabled {count} show(s)")

    def action_reload(self) -> None:
        self._load_shows()
        self.notify("Reloaded config")

    def _save_and_refresh(self) -> None:
        """Persist config changes and refresh the table."""
        if self._config is not None:
            save_config(self._config, self._config_path)
        self._refresh_table()
