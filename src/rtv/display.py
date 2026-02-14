"""Rich output formatting for terminal display."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from rtv.config import ShowConfig, CommercialCategory, HistoryEntry

console = Console()


def success(message: str) -> None:
    """Print a success message in green."""
    console.print(f"[green]{message}[/green]")


def warning(message: str) -> None:
    """Print a warning message in yellow."""
    console.print(f"[yellow]{message}[/yellow]")


def error(message: str) -> None:
    """Print an error message in red."""
    console.print(f"[red]{message}[/red]")


def info(message: str) -> None:
    """Print an informational message in cyan."""
    console.print(f"[cyan]{message}[/cyan]")


def show_status(
    plex_url: str,
    connected: bool,
    libraries: list[str],
    show_count: int,
    commercial_count: int,
    commercial_duration_total: float,
) -> None:
    """Display the connection status and inventory summary."""
    table = Table(title="RTV Status", show_header=False, border_style="cyan")
    table.add_column("Key", style="bold")
    table.add_column("Value")

    status_text = "[green]Connected[/green]" if connected else "[red]Disconnected[/red]"
    table.add_row("Plex Server", f"{plex_url} ({status_text})")
    table.add_row("Libraries", ", ".join(libraries) if libraries else "[dim]None configured[/dim]")
    table.add_row("Shows in Rotation", str(show_count))
    table.add_row("Commercials", f"{commercial_count} clips ({commercial_duration_total:.0f}s total)")

    console.print(table)


def show_shows_table(shows: list[ShowConfig], episode_counts: dict[str, int] | None = None) -> None:
    """Display a table of shows in the rotation."""
    if not shows:
        warning("No shows in rotation. Use 'rtv add-show' to add one.")
        return

    table = Table(title="Show Rotation", border_style="cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Show", style="bold")
    table.add_column("Year", justify="center", width=6)
    table.add_column("Library")
    table.add_column("Position", justify="center")
    table.add_column("Total Episodes", justify="center")

    for i, show in enumerate(shows, 1):
        pos = f"S{show.current_season:02d}E{show.current_episode:02d}"
        total = str(episode_counts.get(show.name, "?")) if episode_counts else "?"
        year_str = str(show.year) if show.year else "-"
        table.add_row(str(i), show.name, year_str, show.library, pos, total)

    console.print(table)


def show_search_results(
    results: list[dict[str, str | int | float]],
) -> None:
    """Display YouTube search results in a table."""
    if not results:
        warning("No results found.")
        return

    table = Table(title="Search Results", border_style="cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Title", max_width=60)
    table.add_column("Duration", justify="right")
    table.add_column("Channel")
    table.add_column("URL", style="dim")

    for i, r in enumerate(results, 1):
        duration_secs = r.get("duration", 0)
        if isinstance(duration_secs, (int, float)) and duration_secs > 0:
            mins, secs = divmod(int(duration_secs), 60)
            dur_str = f"{mins}:{secs:02d}"
        else:
            dur_str = "?"
        table.add_row(
            str(i),
            str(r.get("title", "Unknown")),
            dur_str,
            str(r.get("channel", "Unknown")),
            str(r.get("url", "")),
        )

    console.print(table)


def show_commercial_inventory(
    categories: list[dict[str, str | int | float]],
) -> None:
    """Display commercial inventory by category."""
    if not categories:
        warning("No commercials found. Use 'rtv find-commercials' to search and download.")
        return

    table = Table(title="Commercial Inventory", border_style="cyan")
    table.add_column("Category", style="bold")
    table.add_column("Files", justify="right")
    table.add_column("Total Duration", justify="right")
    table.add_column("Avg Length", justify="right")

    total_files = 0
    total_duration = 0.0

    for cat in categories:
        count = int(cat.get("count", 0))
        duration = float(cat.get("duration", 0))
        avg = duration / count if count > 0 else 0
        total_files += count
        total_duration += duration

        dur_mins, dur_secs = divmod(int(duration), 60)
        avg_secs = int(avg)

        table.add_row(
            str(cat.get("name", "")),
            str(count),
            f"{dur_mins}:{dur_secs:02d}",
            f"{avg_secs}s",
        )

    table.add_section()
    total_mins, total_secs = divmod(int(total_duration), 60)
    table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{total_files}[/bold]",
        f"[bold]{total_mins}:{total_secs:02d}[/bold]",
        "",
    )

    console.print(table)


def show_generation_summary(
    playlist_name: str,
    total_items: int,
    episodes_by_show: dict[str, int],
    show_positions: dict[str, str],
    total_runtime_secs: float,
    commercial_block_count: int,
    commercial_total_secs: float,
) -> None:
    """Display the playlist generation summary."""
    table = Table(title=f"Playlist: {playlist_name}", border_style="green")
    table.add_column("Show", style="bold")
    table.add_column("Episodes", justify="right")
    table.add_column("Next Position", justify="center")

    for show_name, ep_count in episodes_by_show.items():
        pos = show_positions.get(show_name, "?")
        table.add_row(show_name, str(ep_count), pos)

    console.print(table)

    total_mins = int(total_runtime_secs) // 60
    total_hours = total_mins // 60
    remaining_mins = total_mins % 60
    comm_mins = int(commercial_total_secs) // 60

    info(f"Total items: {total_items}")
    info(f"Estimated runtime: {total_hours}h {remaining_mins}m")
    info(f"Commercial blocks: {commercial_block_count} ({comm_mins} min)")
    success(f"\nPlaylist ready! Open Plex and play '{playlist_name}'")


def show_preview(
    playlist_name: str,
    items: list[dict[str, str]],
    episodes_by_show: dict[str, int],
    show_positions: dict[str, str],
    total_runtime_secs: float,
    commercial_block_count: int,
    commercial_total_secs: float,
    show_years: dict[str, int | None] | None = None,
) -> None:
    """Display a preview of what a playlist would look like (dry-run)."""
    table = Table(title=f"Preview: {playlist_name}", border_style="yellow")
    table.add_column("#", style="dim", width=4)
    table.add_column("Type", width=12)
    table.add_column("Item", max_width=50)
    table.add_column("Duration", justify="right")

    for i, item in enumerate(items, 1):
        item_type = item.get("type", "")
        style = "green" if item_type == "episode" else "yellow"
        type_label = f"[{style}]{item_type}[/{style}]"
        table.add_row(str(i), type_label, item["title"], item.get("duration", "?"))

    console.print(table)

    # Summary
    summary = Table(title="Preview Summary", border_style="yellow", show_header=False)
    summary.add_column("Key", style="bold")
    summary.add_column("Value")

    for show_name, ep_count in episodes_by_show.items():
        pos = show_positions.get(show_name, "?")
        year_info = show_years.get(show_name) if show_years else None
        year_prefix = f"({year_info}) " if year_info else ""
        summary.add_row(f"  {show_name}", f"{year_prefix}{ep_count} episodes -> next: {pos}")

    total_mins = int(total_runtime_secs) // 60
    total_hours = total_mins // 60
    remaining_mins = total_mins % 60
    comm_mins = int(commercial_total_secs) // 60

    summary.add_section()
    summary.add_row("Total items", str(len(items)))
    summary.add_row("Estimated runtime", f"{total_hours}h {remaining_mins}m")
    summary.add_row("Commercial blocks", f"{commercial_block_count} ({comm_mins} min)")

    console.print(summary)
    warning("\nThis is a preview -- no playlist was created.")


def show_doctor_results(checks: list[tuple[str, bool, str]]) -> None:
    """Display diagnostic check results.

    Each check is (name, passed, detail_message).
    """
    table = Table(title="RTV Doctor", border_style="cyan")
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center", width=8)
    table.add_column("Details")

    all_passed = True
    for name, passed, detail in checks:
        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        if not passed:
            all_passed = False
        table.add_row(name, status, detail)

    console.print(table)

    if all_passed:
        success("\nAll checks passed! Your setup looks good.")
    else:
        warning("\nSome checks failed. Fix the issues above before generating playlists.")


def show_history(entries: list[HistoryEntry]) -> None:
    """Display playlist generation history."""
    if not entries:
        info("No playlist history yet. Run 'rtv generate' to create your first playlist.")
        return

    table = Table(title="Playlist History", border_style="cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Timestamp")
    table.add_column("Playlist")
    table.add_column("Episodes", justify="right")
    table.add_column("Shows")
    table.add_column("Runtime", justify="right")

    for i, entry in enumerate(entries, 1):
        runtime_mins = int(entry.runtime_secs) // 60
        hours = runtime_mins // 60
        mins = runtime_mins % 60
        runtime_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

        table.add_row(
            str(i),
            entry.timestamp,
            entry.playlist_name,
            str(entry.episode_count),
            ", ".join(entry.shows),
            runtime_str,
        )

    console.print(table)
