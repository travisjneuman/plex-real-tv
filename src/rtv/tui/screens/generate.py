"""Generate screen — playlist generation with progress tracking."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    ProgressBar,
    RichLog,
    Static,
)
from textual.containers import Horizontal, Vertical
from textual import work

from rtv.config import (
    RTVConfig,
    HistoryEntry,
    load_config,
    save_config,
    find_config_path,
)


class GenerateScreen(Screen):
    """Playlist generation with live progress bar and log output."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def __init__(self, playlist_name: str) -> None:
        super().__init__()
        self._playlist_name = playlist_name
        self._config: RTVConfig | None = None
        self._config_path = find_config_path()
        self._running = False
        self._completed = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="generate-container"):
            yield Static(
                f"[bold]Generate Playlist:[/bold] {self._playlist_name}",
                id="gen-header",
            )
            yield ProgressBar(total=100, show_eta=True, id="gen-progress-bar")
            yield Static("", id="gen-current-show")
            yield RichLog(highlight=True, markup=True, id="gen-log")
            yield Static("", id="gen-summary")
            with Horizontal(id="gen-actions"):
                yield Button(
                    "Start Generation",
                    id="btn-start",
                    variant="primary",
                )
                yield Button("Back", id="btn-back")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#gen-log", RichLog)
        log.write("[dim]Press 'Start Generation' to begin.[/dim]")

        try:
            self._config = load_config(self._config_path)
        except Exception as exc:
            log.write(f"[red]Failed to load config: {exc}[/red]")
            return

        playlist = self._config.get_playlist(self._playlist_name)
        if playlist is None:
            log.write(f"[red]Playlist '{self._playlist_name}' not found in config.[/red]")
            return

        # Show pre-generation info
        log.write(f"Playlist: [bold]{playlist.name}[/bold]")
        log.write(f"Shows: {len(playlist.shows)}")
        log.write(f"Episodes to generate: {playlist.episodes_per_generation}")
        brk = playlist.breaks
        if brk.enabled:
            log.write(f"Breaks: {brk.style} every {brk.frequency} ep(s)")
        else:
            log.write("Breaks: disabled")
        log.write(f"Sort: {playlist.sort_by}")
        log.write("")

    # -- Generation worker ------------------------------------------------

    @work(thread=True, exclusive=True)
    def _run_generation(self) -> None:
        """Execute playlist generation in a background thread."""
        if self._config is None:
            return

        playlist = self._config.get_playlist(self._playlist_name)
        if playlist is None:
            self.call_from_thread(self._log, "[red]Playlist not found.[/red]")
            return

        # Connect to Plex
        self.call_from_thread(self._log, "Connecting to Plex...")
        self.call_from_thread(self._update_current_show, "Connecting to Plex...")

        try:
            from rtv.plex_client import connect

            server = connect(self._config.plex)
        except Exception as exc:
            self.call_from_thread(
                self._log, f"[red]Plex connection failed: {exc}[/red]"
            )
            self.call_from_thread(self._update_current_show, "Connection failed")
            self.call_from_thread(self._mark_done, False)
            return

        self.call_from_thread(self._log, "[green]Connected to Plex.[/green]")

        # Set progress bar total
        ep_count = playlist.episodes_per_generation
        self.call_from_thread(self._set_progress_total, ep_count)

        # Progress callback bridges the generator to the UI
        def on_progress(current: int, total: int) -> None:
            self.call_from_thread(self._set_progress, current)
            self.call_from_thread(
                self._update_current_show,
                f"Episode {current}/{total}",
            )

        # Generate
        self.call_from_thread(self._log, "Generating playlist...")
        start_time = datetime.now()

        try:
            from rtv.playlist import generate_playlist

            result = generate_playlist(
                config=self._config,
                playlist=playlist,
                server=server,
                episode_count=ep_count,
                from_start=False,
                progress_callback=on_progress,
            )
        except Exception as exc:
            self.call_from_thread(self._log, f"[red]Generation failed: {exc}[/red]")
            self.call_from_thread(self._update_current_show, "Generation failed")
            self.call_from_thread(self._mark_done, False)
            return

        elapsed = (datetime.now() - start_time).total_seconds()

        # Push to Plex
        self.call_from_thread(self._log, "Creating Plex playlist...")
        self.call_from_thread(self._update_current_show, "Creating Plex playlist...")

        try:
            from rtv.plex_client import create_or_update_playlist

            create_or_update_playlist(
                server, playlist.name, result.playlist_items
            )
        except Exception as exc:
            self.call_from_thread(
                self._log,
                f"[red]Failed to create Plex playlist: {exc}[/red]",
            )
            self.call_from_thread(self._mark_done, False)
            return

        # Record history
        entry = HistoryEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            playlist_name=playlist.name,
            episode_count=sum(result.episodes_by_show.values()),
            shows=list(result.episodes_by_show.keys()),
            runtime_secs=result.total_runtime_secs,
        )
        self._config.history.append(entry)

        # Save updated positions and history
        save_config(self._config, self._config_path)

        # Log summary
        self.call_from_thread(self._log, "")
        self.call_from_thread(self._log, "[green bold]Generation complete![/green bold]")
        for show_name, count in result.episodes_by_show.items():
            pos = result.show_positions.get(show_name, "?")
            self.call_from_thread(
                self._log, f"  {show_name}: {count} ep(s) -> next {pos}"
            )

        total_items = len(result.playlist_items)
        runtime_mins = int(result.total_runtime_secs) // 60
        hours, mins = divmod(runtime_mins, 60)
        comm_mins = int(result.commercial_total_secs) // 60

        self.call_from_thread(self._render_summary, {
            "total_items": total_items,
            "runtime": f"{hours}h {mins}m",
            "commercial_blocks": result.commercial_block_count,
            "commercial_mins": comm_mins,
            "elapsed": f"{elapsed:.1f}s",
            "dropped": result.dropped_shows,
        })
        self.call_from_thread(self._update_current_show, "Complete!")
        self.call_from_thread(self._mark_done, True)

    # -- UI update helpers (called from worker via call_from_thread) -------

    def _log(self, message: str) -> None:
        self.query_one("#gen-log", RichLog).write(message)

    def _set_progress_total(self, total: int) -> None:
        bar = self.query_one("#gen-progress-bar", ProgressBar)
        bar.update(total=total, progress=0)

    def _set_progress(self, current: int) -> None:
        bar = self.query_one("#gen-progress-bar", ProgressBar)
        bar.update(progress=current)

    def _update_current_show(self, text: str) -> None:
        self.query_one("#gen-current-show", Static).update(text)

    def _render_summary(self, stats: dict[str, object]) -> None:
        lines = [
            "[bold]Summary[/bold]",
            f"  Total items: {stats['total_items']}",
            f"  Runtime: {stats['runtime']}",
            f"  Commercial blocks: {stats['commercial_blocks']} ({stats['commercial_mins']} min)",
            f"  Generation time: {stats['elapsed']}",
        ]
        dropped = stats.get("dropped")
        if dropped:
            lines.append(f"  Dropped shows: {', '.join(dropped)}")  # type: ignore[arg-type]
        self.query_one("#gen-summary", Static).update("\n".join(lines))

    def _mark_done(self, success: bool) -> None:
        self._running = False
        self._completed = True
        btn = self.query_one("#btn-start", Button)
        if success:
            btn.label = "Done"
        else:
            btn.label = "Retry"
        btn.disabled = False

    # -- Button handlers --------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-start":
            if self._running:
                return
            if self._completed:
                # Reset for retry
                self._completed = False
                self.query_one("#gen-log", RichLog).clear()
                self.query_one("#gen-summary", Static).update("")
                bar = self.query_one("#gen-progress-bar", ProgressBar)
                bar.update(total=100, progress=0)

            self._running = True
            event.button.label = "Running..."
            event.button.disabled = True
            self._run_generation()

        elif event.button.id == "btn-back":
            self.action_go_back()

    def action_go_back(self) -> None:
        if self._running:
            self.notify("Generation in progress -- please wait", severity="warning")
            return
        self.app.pop_screen()
