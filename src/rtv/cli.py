"""Click CLI entry point for plex-real-tv v2."""

from __future__ import annotations

import copy
import shutil
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from rtv import __version__
from rtv.config import (
    RTVConfig,
    PlexConfig,
    CommercialConfig,
    BlockDuration,
    SSHConfig,
    GlobalShow,
    PlaylistShow,
    PlaylistDefinition,
    BreakConfig,
    CommercialCategory,
    HistoryEntry,
    DEFAULT_SHOWS,
    load_config,
    save_config,
    find_config_path,
    get_config_or_exit,
    # Legacy (kept for reference)
    ShowConfig,
    PlaylistConfig,
)
from rtv import display

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="plex-real-tv")
def cli() -> None:
    """plex-real-tv: Simulate real TV on Plex with round-robin episodes and commercial breaks."""


# ---------------------------------------------------------------------------
# init + status
# ---------------------------------------------------------------------------


@cli.command()
def init() -> None:
    """Create config.yaml interactively."""
    existing = find_config_path()
    if existing is not None:
        if not click.confirm(f"Config already exists at {existing}. Overwrite?"):
            display.info("Cancelled.")
            return

    display.info("Setting up plex-real-tv configuration...\n")

    plex_url = click.prompt("Plex server URL", default="http://localhost:32400")
    plex_token = click.prompt("Plex token")
    libs_raw = click.prompt(
        "TV library names (comma-separated)", default="TV Shows"
    )
    tv_libraries = [lib.strip() for lib in libs_raw.split(",") if lib.strip()]

    commercial_lib_name = click.prompt(
        "Commercial library name in Plex", default="RealTV Commercials"
    )
    commercial_path = click.prompt(
        "Commercial files path", default=r"D:\Media\Commercials"
    )

    config = RTVConfig(
        plex=PlexConfig(
            url=plex_url,
            token=plex_token,
            tv_libraries=tv_libraries,
        ),
        commercials=CommercialConfig(
            library_name=commercial_lib_name,
            library_path=commercial_path,
            block_duration=BlockDuration(),
        ),
    )

    # Offer to seed with default shows
    if click.confirm("Seed config with 30 default shows?", default=True):
        for entry in DEFAULT_SHOWS:
            config.shows.append(GlobalShow(
                name=str(entry["name"]),
                year=int(entry["year"]),  # type: ignore[arg-type]
            ))
        display.success(f"Added {len(DEFAULT_SHOWS)} shows to pool.")

    # Create default playlist with all shows
    default_pl = PlaylistDefinition(
        name="Real TV",
        shows=[PlaylistShow(name=s.name) for s in config.shows],
    )
    config.playlists.append(default_pl)
    config.default_playlist = "Real TV"

    path = save_config(config)
    display.success(f"\nConfig saved to {path}")
    display.info("Next: run 'rtv status' to test your connection.")


@cli.command()
def status() -> None:
    """Test Plex connection and show inventory summary."""
    config, _ = get_config_or_exit()

    connected = False
    libraries: list[str] = []
    commercial_count = 0
    commercial_duration = 0.0

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Connecting to Plex...[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("connect", total=None)
        try:
            from rtv import plex_client

            server = plex_client.connect(config.plex)
            connected = True

            for lib_name in config.plex.tv_libraries:
                try:
                    section = plex_client.get_library_section(server, lib_name)
                    libraries.append(f"{lib_name} ({section.totalSize} items)")
                except Exception:
                    libraries.append(f"{lib_name} (not found)")

            commercials = plex_client.get_commercials(server, config.commercials.library_name)
            commercial_count = len(commercials)
            for item in commercials:
                if hasattr(item, "duration") and item.duration:
                    commercial_duration += item.duration / 1000.0

        except Exception as e:
            display.error(f"Could not connect to Plex: {e}")
            display.info("Check your URL and token in config.yaml.")

    display.show_status(
        plex_url=config.plex.url,
        connected=connected,
        libraries=libraries,
        show_count=len(config.shows),
        commercial_count=commercial_count,
        commercial_duration_total=commercial_duration,
        playlist_count=len(config.playlists),
    )


# ---------------------------------------------------------------------------
# Show management
# ---------------------------------------------------------------------------


@cli.command("add-show")
@click.argument("name")
@click.option("--library", default=None, help="Plex library name (searches all if not specified)")
def add_show(name: str, library: str | None) -> None:
    """Add a show to the global pool (fuzzy matches against Plex library)."""
    config, config_path = get_config_or_exit()

    # Check for duplicate
    for show in config.shows:
        if show.name.lower() == name.lower():
            raise click.ClickException(f"'{name}' is already in the pool.")

    from rtv import plex_client, matcher

    try:
        server = plex_client.connect(config.plex)
    except Exception as e:
        raise click.ClickException(f"Could not connect to Plex: {e}") from e

    search_libs = [library] if library else config.plex.tv_libraries

    all_shows: list[tuple[str, str]] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Scanning Plex libraries...[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("scan", total=None)
        for lib_name in search_libs:
            try:
                shows = plex_client.get_all_shows(server, lib_name)
                for s in shows:
                    all_shows.append((s.title, lib_name))
            except Exception:
                display.warning(f"Could not access library '{lib_name}'")

    if not all_shows:
        raise click.ClickException("No shows found in configured libraries.")

    show_titles = [s[0] for s in all_shows]

    exact = matcher.exact_match(name, show_titles)
    if exact:
        matched_title = exact
    else:
        matches = matcher.fuzzy_match(name, show_titles, limit=5)
        if not matches:
            raise click.ClickException(
                f"No match found for '{name}'. Check the show name or library."
            )

        if len(matches) == 1 and matches[0].score >= 95:
            matched_title = matches[0].title
            display.info(f"Matched: '{matched_title}' ({matches[0].score:.0f}% confidence)")
        else:
            display.info(f"Multiple matches for '{name}':")
            for i, m in enumerate(matches, 1):
                click.echo(f"  {i}. {m.title} ({m.score:.0f}%)")
            choice = click.prompt("Pick a number (or 0 to cancel)", type=int, default=1)
            if choice < 1 or choice > len(matches):
                display.info("Cancelled.")
                return
            matched_title = matches[choice - 1].title

    matched_lib = next(lib for title, lib in all_shows if title == matched_title)

    try:
        show_obj = plex_client.get_show(server, matched_title, matched_lib)
        episodes = show_obj.episodes()
        if not episodes:
            raise click.ClickException(f"'{matched_title}' has no episodes.")
        total_eps = len(episodes)
    except Exception as e:
        raise click.ClickException(f"Could not access '{matched_title}': {e}") from e

    show_year: int | None = getattr(show_obj, "year", None)

    new_show = GlobalShow(
        name=matched_title,
        library=matched_lib,
        year=show_year,
    )
    config.shows.append(new_show)
    save_config(config, config_path)
    year_str = f", {show_year}" if show_year else ""
    display.success(f"Added '{matched_title}' from '{matched_lib}' ({total_eps} episodes{year_str})")


@cli.command("remove-show")
@click.argument("name")
def remove_show(name: str) -> None:
    """Remove a show from the global pool."""
    config, config_path = get_config_or_exit()

    name_lower = name.lower()
    found_idx: int | None = None
    for i, show in enumerate(config.shows):
        if show.name.lower() == name_lower:
            found_idx = i
            break

    if found_idx is None:
        from rtv import matcher
        show_names = [s.name for s in config.shows]
        match = matcher.best_match(name, show_names)
        if match:
            if click.confirm(f"Did you mean '{match.title}'?"):
                found_idx = next(
                    i for i, s in enumerate(config.shows) if s.name == match.title
                )
            else:
                display.info("Cancelled.")
                return
        else:
            raise click.ClickException(
                f"'{name}' is not in the pool. Use 'rtv list-shows' to see current shows."
            )

    removed = config.shows[found_idx]
    # Warn if in playlists
    membership = config.get_playlist_membership(removed.name)
    if membership:
        display.warning(f"'{removed.name}' is in playlists: {', '.join(membership)}")
        if not click.confirm("Remove anyway?"):
            display.info("Cancelled.")
            return

    config.shows.pop(found_idx)
    save_config(config, config_path)
    display.success(f"Removed '{removed.name}' from pool.")


@cli.command("list-shows")
def list_shows() -> None:
    """Show all shows in the global pool."""
    config, _ = get_config_or_exit()

    episode_counts: dict[str, int] | None = None
    try:
        from rtv import plex_client
        server = plex_client.connect(config.plex)
        episode_counts = {}
        for show in config.shows:
            try:
                show_obj = plex_client.get_show(server, show.name, show.library)
                episode_counts[show.name] = len(show_obj.episodes())
            except Exception:
                episode_counts[show.name] = 0
    except Exception:
        pass

    # Build playlist membership
    membership: dict[str, list[str]] = {}
    for show in config.shows:
        membership[show.name] = config.get_playlist_membership(show.name)

    display.show_shows_table(config.shows, episode_counts, membership)


@cli.command("enable-show")
@click.argument("name")
def enable_show(name: str) -> None:
    """Enable a show in the global pool."""
    config, config_path = get_config_or_exit()
    gs = config.get_global_show(name)
    if gs is None:
        raise click.ClickException(f"Show '{name}' not found in pool.")
    gs.enabled = True
    save_config(config, config_path)
    display.success(f"Enabled '{gs.name}'.")


@cli.command("disable-show")
@click.argument("name")
def disable_show(name: str) -> None:
    """Disable a show in the global pool (skipped during generation)."""
    config, config_path = get_config_or_exit()
    gs = config.get_global_show(name)
    if gs is None:
        raise click.ClickException(f"Show '{name}' not found in pool.")
    gs.enabled = False
    save_config(config, config_path)
    display.success(f"Disabled '{gs.name}'. It will be skipped during generation.")


# ---------------------------------------------------------------------------
# Playlist management
# ---------------------------------------------------------------------------


@cli.command("create-playlist")
@click.argument("name")
@click.option("--episodes", "-e", default=30, help="Episodes per generation (default 30)")
@click.option("--break-style", type=click.Choice(["single", "block", "disabled"]), default="single")
@click.option("--frequency", default=1, help="Commercial break frequency (every N episodes)")
def create_playlist(name: str, episodes: int, break_style: str, frequency: int) -> None:
    """Create a new playlist."""
    config, config_path = get_config_or_exit()

    if config.get_playlist(name) is not None:
        raise click.ClickException(f"Playlist '{name}' already exists.")

    breaks_enabled = break_style != "disabled"
    new_pl = PlaylistDefinition(
        name=name,
        breaks=BreakConfig(
            enabled=breaks_enabled,
            style=break_style if breaks_enabled else "single",
            frequency=frequency,
        ),
        episodes_per_generation=episodes,
    )
    config.playlists.append(new_pl)
    save_config(config, config_path)
    display.success(f"Created playlist '{name}'. Use 'rtv playlist-add {name} <show>' to add shows.")


@cli.command("delete-playlist")
@click.argument("name")
def delete_playlist(name: str) -> None:
    """Delete a playlist."""
    config, config_path = get_config_or_exit()

    pl = config.get_playlist(name)
    if pl is None:
        raise click.ClickException(f"Playlist '{name}' not found.")

    if not click.confirm(f"Delete playlist '{pl.name}' ({len(pl.shows)} shows)?"):
        display.info("Cancelled.")
        return

    config.playlists = [p for p in config.playlists if p.name.lower() != name.lower()]
    if config.default_playlist.lower() == name.lower() and config.playlists:
        config.default_playlist = config.playlists[0].name
        display.info(f"Default playlist changed to '{config.default_playlist}'.")

    save_config(config, config_path)
    display.success(f"Deleted playlist '{pl.name}'.")


@cli.command("list-playlists")
def list_playlists() -> None:
    """Show all playlists."""
    config, _ = get_config_or_exit()
    display.show_playlists_table(config.playlists, config.default_playlist)


@cli.command("playlist-add")
@click.argument("playlist_name")
@click.argument("show_name")
def playlist_add(playlist_name: str, show_name: str) -> None:
    """Add a show to a playlist at S01E01."""
    config, config_path = get_config_or_exit()

    pl = config.get_playlist(playlist_name)
    if pl is None:
        raise click.ClickException(f"Playlist '{playlist_name}' not found.")

    gs = config.get_global_show(show_name)
    if gs is None:
        raise click.ClickException(f"Show '{show_name}' not found in global pool. Use 'rtv add-show' first.")

    # Check if already in playlist
    for ps in pl.shows:
        if ps.name.lower() == show_name.lower():
            raise click.ClickException(f"'{show_name}' is already in playlist '{pl.name}'.")

    pl.shows.append(PlaylistShow(name=gs.name))
    save_config(config, config_path)
    display.success(f"Added '{gs.name}' to playlist '{pl.name}' at S01E01.")


@cli.command("playlist-remove")
@click.argument("playlist_name")
@click.argument("show_name")
def playlist_remove(playlist_name: str, show_name: str) -> None:
    """Remove a show from a playlist."""
    config, config_path = get_config_or_exit()

    pl = config.get_playlist(playlist_name)
    if pl is None:
        raise click.ClickException(f"Playlist '{playlist_name}' not found.")

    name_lower = show_name.lower()
    new_shows = []
    removed = False
    for ps in pl.shows:
        if ps.name.lower() == name_lower and not removed:
            removed = True
        else:
            new_shows.append(ps)
    pl.shows = new_shows

    if not removed:
        raise click.ClickException(f"'{show_name}' is not in playlist '{pl.name}'.")

    save_config(config, config_path)
    display.success(f"Removed '{show_name}' from playlist '{pl.name}'.")


@cli.command("set-default")
@click.argument("name")
def set_default(name: str) -> None:
    """Set the default playlist."""
    config, config_path = get_config_or_exit()

    pl = config.get_playlist(name)
    if pl is None:
        raise click.ClickException(f"Playlist '{name}' not found.")

    config.default_playlist = pl.name
    save_config(config, config_path)
    display.success(f"Default playlist set to '{pl.name}'.")


# ---------------------------------------------------------------------------
# Commercial management
# ---------------------------------------------------------------------------


@cli.command("find-commercials")
@click.option("--category", "-c", required=True, help="Category name or search query")
@click.option("-n", "max_results", default=10, help="Number of results to show")
def find_commercials(category: str, max_results: int) -> None:
    """Search YouTube for commercials by category."""
    config, _ = get_config_or_exit()

    from rtv import commercial

    query = commercial.get_category_search_query(category, config.commercials)

    with Progress(
        SpinnerColumn(),
        TextColumn(f"[cyan]Searching YouTube for: '{query}'...[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("search", total=None)
        try:
            results = commercial.search_youtube(query, max_results)
        except Exception as e:
            raise click.ClickException(f"Search failed: {e}") from e

    if not results:
        display.warning("No results found.")
        return

    commercial.save_search_results(results)
    display.show_search_results(results)

    selection = click.prompt(
        "\nDownload which? (e.g. 1,3,5-7 or 'all' or 'none')",
        default="none",
    )
    indices = commercial.parse_selection(selection, len(results))
    if not indices:
        display.info("No downloads selected.")
        return

    output_dir = Path(config.commercials.library_path) / category
    failed: list[str] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description}[/cyan]"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Downloading...", total=len(indices))
        for idx in indices:
            r = results[idx]
            url = str(r.get("url", ""))
            title = str(r.get("title", "Unknown"))
            if not url:
                display.warning(f"  Skipping '{title}': no URL")
                progress.advance(task)
                continue
            progress.update(task, description=f"Downloading: {title[:40]}...")
            try:
                downloaded = commercial.download_video(url, output_dir)
                display.success(f"  Saved: {downloaded.name}")
            except Exception as e:
                display.error(f"  Failed: '{title}': {e}")
                failed.append(title)
            progress.advance(task)

    if failed:
        display.warning(f"\n{len(failed)} download(s) failed: {', '.join(failed)}")


@cli.command("download-commercials")
@click.argument("url", required=False)
@click.option("--category", "-c", default="uncategorized", help="Category subfolder")
@click.option("--from-search", "from_search", is_flag=True, help="Download from last search results")
def download_commercials(
    url: str | None, category: str, from_search: bool
) -> None:
    """Download a commercial from URL or from last search results."""
    config, _ = get_config_or_exit()

    from rtv import commercial

    if from_search:
        results = commercial.load_search_results()
        if not results:
            raise click.ClickException(
                "No previous search results. Run 'rtv find-commercials' first."
            )
        display.show_search_results(results)
        selection = click.prompt(
            "\nDownload which? (e.g. 1,3,5-7 or 'all' or 'none')",
            default="none",
        )
        indices = commercial.parse_selection(selection, len(results))
        if not indices:
            display.info("No downloads selected.")
            return

        output_dir = Path(config.commercials.library_path) / category
        failed: list[str] = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]{task.description}[/cyan]"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Downloading...", total=len(indices))
            for idx in indices:
                r = results[idx]
                vid_url = str(r.get("url", ""))
                title = str(r.get("title", "Unknown"))
                if not vid_url:
                    display.warning(f"  Skipping '{title}': no URL")
                    progress.advance(task)
                    continue
                progress.update(task, description=f"Downloading: {title[:40]}...")
                try:
                    downloaded = commercial.download_video(vid_url, output_dir)
                    display.success(f"  Saved: {downloaded.name}")
                except Exception as e:
                    display.error(f"  Failed: '{title}': {e}")
                    failed.append(title)
                progress.advance(task)

        if failed:
            display.warning(f"\n{len(failed)} download(s) failed: {', '.join(failed)}")

    elif url:
        output_dir = Path(config.commercials.library_path) / category
        display.info(f"Downloading to {output_dir}...")
        try:
            downloaded = commercial.download_video(url, output_dir)
            display.success(f"Saved: {downloaded.name}")
        except Exception as e:
            raise click.ClickException(f"Download failed: {e}") from e
    else:
        raise click.ClickException(
            "Provide a URL or use --from-search. See 'rtv download-commercials --help'."
        )


@cli.command("add-category")
@click.argument("name")
@click.option("--search", "-s", "search_terms", multiple=True, help="Search terms for this category")
@click.option("--weight", "-w", default=1.0, help="Selection weight (default 1.0)")
def add_category(name: str, search_terms: tuple[str, ...], weight: float) -> None:
    """Add a new commercial category."""
    config, config_path = get_config_or_exit()

    for cat in config.commercials.categories:
        if cat.name.lower() == name.lower():
            raise click.ClickException(f"Category '{name}' already exists.")

    terms = list(search_terms) if search_terms else [name]
    new_cat = CommercialCategory(name=name, search_terms=terms, weight=weight)
    config.commercials.categories.append(new_cat)
    save_config(config, config_path)
    display.success(f"Added category '{name}' with search terms: {terms}")


@cli.command("list-commercials")
def list_commercials() -> None:
    """Show commercial inventory by category."""
    config, _ = get_config_or_exit()

    from rtv import commercial

    inventory = commercial.scan_commercial_inventory(
        config.commercials.library_path, config.commercials.categories
    )
    display.show_commercial_inventory(inventory)


# ---------------------------------------------------------------------------
# Playlist generation
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("name", required=False)
@click.option("--episodes", "-e", default=None, type=int, help="Number of episodes to generate")
@click.option("--from-start", "from_start", is_flag=True, help="Reset all show positions to S01E01")
@click.option("--rescan", is_flag=True, help="Trigger Plex library scan before generating")
@click.option("--export", "do_export", is_flag=True, help="Export playlist to CSV after generating")
@click.option("--export-path", default=None, help="CSV export path (default: playlist_export.csv)")
def generate(
    name: str | None,
    episodes: int | None,
    from_start: bool,
    rescan: bool,
    do_export: bool,
    export_path: str | None,
) -> None:
    """Generate a Plex playlist with round-robin episodes and commercial breaks."""
    config, config_path = get_config_or_exit()

    try:
        playlist = config.get_playlist_or_raise(name)
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    if not playlist.shows:
        raise click.ClickException(
            f"Playlist '{playlist.name}' has no shows. "
            "Use 'rtv playlist-add' to add shows."
        )

    episode_count = episodes or playlist.episodes_per_generation

    from rtv import plex_client as pc
    from rtv.playlist import generate_playlist

    try:
        server = pc.connect(config.plex)
    except Exception as e:
        raise click.ClickException(f"Could not connect to Plex: {e}") from e

    if rescan:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Scanning Plex commercial library...[/cyan]"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("scan", total=None)
            try:
                total = pc.rescan_library(server, config.commercials.library_name)
                display.success(f"Library scan complete — {total} commercials indexed.")
            except TimeoutError as e:
                display.warning(str(e))
            except Exception as e:
                raise click.ClickException(f"Library scan failed: {e}") from e

    display.info(f"Generating playlist '{playlist.name}' with up to {episode_count} episodes...")
    if from_start:
        display.info("Resetting all show positions to S01E01.")

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Building playlist...[/cyan]"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Generating", total=episode_count)

        def on_progress(current: int, total: int) -> None:
            progress.update(task, completed=current)

        try:
            result = generate_playlist(
                config, playlist, server, episode_count, from_start,
                progress_callback=on_progress,
            )
        except ValueError as e:
            raise click.ClickException(str(e)) from e

    if not result.playlist_items:
        raise click.ClickException("No items generated. Check your show configuration.")

    if len(result.playlist_items) > 500:
        display.warning(f"Large playlist ({len(result.playlist_items)} items). This may take a moment...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Creating Plex playlist...[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("create", total=None)
        try:
            pc.create_or_update_playlist(server, playlist.name, result.playlist_items)
        except Exception as e:
            raise click.ClickException(f"Failed to create playlist: {e}") from e

    entry = HistoryEntry(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        playlist_name=playlist.name,
        episode_count=sum(result.episodes_by_show.values()),
        shows=list(result.episodes_by_show.keys()),
        runtime_secs=result.total_runtime_secs,
    )
    config.history.append(entry)
    config.history = config.history[-5:]

    save_config(config, config_path)

    display.show_generation_summary(
        playlist_name=playlist.name,
        total_items=len(result.playlist_items),
        episodes_by_show=result.episodes_by_show,
        show_positions=result.show_positions,
        total_runtime_secs=result.total_runtime_secs,
        commercial_block_count=result.commercial_block_count,
        commercial_total_secs=result.commercial_total_secs,
        break_style=playlist.breaks.style if playlist.breaks.enabled else "disabled",
    )

    if result.dropped_shows:
        display.warning(f"Shows exhausted: {', '.join(result.dropped_shows)}")

    if do_export:
        out = Path(export_path) if export_path else Path("playlist_export.csv")
        _export_playlist(server, playlist.name, out)


# ---------------------------------------------------------------------------
# Playlist export
# ---------------------------------------------------------------------------


def _export_playlist(
    server: object,
    playlist_name: str,
    output_path: Path,
    fmt: str = "csv",
) -> None:
    """Export a Plex playlist to CSV or JSON."""
    from pathlib import PurePosixPath, PureWindowsPath

    with Progress(
        SpinnerColumn(),
        TextColumn(f"[cyan]Reading playlist '{playlist_name}'...[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("read", total=None)
        try:
            plex_playlist = server.playlist(playlist_name)  # type: ignore[union-attr]
            items = plex_playlist.items()
        except Exception as e:
            raise click.ClickException(f"Could not read playlist '{playlist_name}': {e}") from e

    if not items:
        raise click.ClickException(f"Playlist '{playlist_name}' is empty.")

    rows: list[dict[str, str | int | float]] = []
    for i, item in enumerate(items, 1):
        duration_secs = 0.0
        if hasattr(item, "duration") and item.duration:
            duration_secs = item.duration / 1000.0
        mins, secs = divmod(int(duration_secs), 60)
        dur_str = f"{mins}:{secs:02d}"

        grandparent = getattr(item, "grandparentTitle", None)
        title = getattr(item, "title", "Unknown")
        if grandparent:
            season_idx = getattr(item, "parentIndex", 0)
            ep_idx = getattr(item, "index", 0)
            item_type = "episode"
            display_title = f"{grandparent} S{season_idx:02d}E{ep_idx:02d}: {title}"
            show_category = grandparent
        else:
            item_type = "commercial"
            display_title = title
            location = ""
            if hasattr(item, "locations") and item.locations:
                location = item.locations[0]
            show_category = "uncategorized"
            for path_class in (PureWindowsPath, PurePosixPath):
                try:
                    show_category = path_class(location).parent.name
                    break
                except Exception:
                    continue

        rows.append({
            "#": i,
            "Type": item_type,
            "Title": display_title,
            "Duration": dur_str,
            "Show/Category": show_category,
        })

    if fmt == "csv":
        import csv
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["#", "Type", "Title", "Duration", "Show/Category"])
            writer.writeheader()
            writer.writerows(rows)
    else:
        import json
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)

    episode_count = sum(1 for r in rows if r["Type"] == "episode")
    commercial_count = sum(1 for r in rows if r["Type"] == "commercial")
    display.success(
        f"Exported {len(rows)} items ({episode_count} episodes, {commercial_count} commercials) "
        f"to {output_path}"
    )


@cli.command()
@click.option("--format", "fmt", type=click.Choice(["csv", "json"]), default="csv", help="Export format")
@click.option("--output", "-o", "output_file", default=None, help="Output file path")
@click.option("--name", "-n", default=None, help="Playlist name (default: default playlist)")
def export(fmt: str, output_file: str | None, name: str | None) -> None:
    """Export the current Plex playlist to CSV or JSON for review."""
    config, _ = get_config_or_exit()

    playlist_name = name or config.default_playlist

    from rtv import plex_client as pc

    try:
        server = pc.connect(config.plex)
    except Exception as e:
        raise click.ClickException(f"Could not connect to Plex: {e}") from e

    default_ext = "csv" if fmt == "csv" else "json"
    if output_file is None:
        output_file = f"playlist_export.{default_ext}"

    _export_playlist(server, playlist_name, Path(output_file), fmt)


# ---------------------------------------------------------------------------
# Quality of life commands
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("name", required=False)
@click.option("--episodes", "-e", default=None, type=int, help="Number of episodes to preview")
@click.option("--from-start", "from_start", is_flag=True, help="Preview from S01E01")
def preview(name: str | None, episodes: int | None, from_start: bool) -> None:
    """Dry-run: show what a playlist would look like without creating it."""
    config, _ = get_config_or_exit()

    try:
        playlist = config.get_playlist_or_raise(name)
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    if not playlist.shows:
        raise click.ClickException(
            f"Playlist '{playlist.name}' has no shows. Use 'rtv playlist-add' first."
        )

    episode_count = episodes or playlist.episodes_per_generation

    from rtv import plex_client as pc
    from rtv.playlist import generate_playlist

    try:
        server = pc.connect(config.plex)
    except Exception as e:
        raise click.ClickException(f"Could not connect to Plex: {e}") from e

    # Work on a deep copy so positions aren't modified
    preview_config = copy.deepcopy(config)
    preview_playlist = preview_config.get_playlist_or_raise(name)

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Generating preview...[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("preview", total=None)
        try:
            result = generate_playlist(
                preview_config, preview_playlist, server, episode_count, from_start
            )
        except ValueError as e:
            raise click.ClickException(str(e)) from e

    if not result.playlist_items:
        raise click.ClickException("No items would be generated.")

    preview_items: list[dict[str, str]] = []
    for item in result.playlist_items:
        duration_secs = 0.0
        if hasattr(item, "duration") and item.duration:
            duration_secs = item.duration / 1000.0
        mins, secs = divmod(int(duration_secs), 60)
        dur_str = f"{mins}:{secs:02d}" if duration_secs > 0 else "?"

        title = getattr(item, "title", "Unknown")
        grandparent = getattr(item, "grandparentTitle", None)
        if grandparent:
            season_idx = getattr(item, "parentIndex", 0)
            ep_idx = getattr(item, "index", 0)
            item_type = "episode"
            display_title = f"{grandparent} S{season_idx:02d}E{ep_idx:02d}: {title}"
        else:
            item_type = "commercial"
            display_title = title

        preview_items.append({
            "type": item_type,
            "title": display_title,
            "duration": dur_str,
        })

    show_years = {s.name: s.year for s in preview_config.shows}
    display.show_preview(
        playlist_name=preview_playlist.name,
        items=preview_items,
        episodes_by_show=result.episodes_by_show,
        show_positions=result.show_positions,
        total_runtime_secs=result.total_runtime_secs,
        commercial_block_count=result.commercial_block_count,
        commercial_total_secs=result.commercial_total_secs,
        show_years=show_years,
    )


@cli.command()
def doctor() -> None:
    """Run diagnostic checks on your RTV setup."""
    config, config_path = get_config_or_exit()

    checks: list[tuple[str, bool, str]] = []

    checks.append(("Config file", True, str(config_path)))
    checks.append(("Config version", True, f"v{config.config_version}"))

    url_ok = config.plex.url.startswith(("http://", "https://"))
    checks.append(("Plex URL format", url_ok, config.plex.url))

    token_ok = bool(config.plex.token)
    checks.append(("Plex token", token_ok, "Set" if token_ok else "Empty — run 'rtv init'"))

    server = None
    try:
        from rtv import plex_client
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Testing Plex connection...[/cyan]"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("connect", total=None)
            server = plex_client.connect(config.plex)
        checks.append(("Plex connection", True, f"Connected to {config.plex.url}"))
    except Exception as e:
        checks.append(("Plex connection", False, str(e)))

    if server:
        for lib_name in config.plex.tv_libraries:
            try:
                section = plex_client.get_library_section(server, lib_name)
                checks.append((f"Library: {lib_name}", True, f"{section.totalSize} items"))
            except Exception:
                checks.append((f"Library: {lib_name}", False, "Not found in Plex"))

    # Playlists
    checks.append(("Playlists", len(config.playlists) > 0, f"{len(config.playlists)} defined"))

    # Shows in pool
    enabled_count = sum(1 for s in config.shows if s.enabled)
    checks.append(("Global shows", len(config.shows) > 0, f"{len(config.shows)} total, {enabled_count} enabled"))

    # Commercial library path
    comm_path = Path(config.commercials.library_path)
    if config.commercials.library_path:
        if comm_path.exists():
            mp4_count = len(list(comm_path.rglob("*.mp4")))
            checks.append(("Commercial path", True, f"{comm_path} ({mp4_count} MP4 files)"))
        else:
            checks.append(("Commercial path", False, f"{comm_path} does not exist"))
    else:
        checks.append(("Commercial path", False, "Not configured"))

    if server:
        commercials = plex_client.get_commercials(server, config.commercials.library_name)
        if commercials:
            checks.append(("Plex commercial library", True, f"'{config.commercials.library_name}' has {len(commercials)} items"))
        else:
            checks.append(("Plex commercial library", False, f"'{config.commercials.library_name}' not found or empty"))

    ytdlp_path = shutil.which("yt-dlp")
    if ytdlp_path:
        checks.append(("yt-dlp", True, ytdlp_path))
    else:
        try:
            import yt_dlp
            checks.append(("yt-dlp", True, f"Python module v{yt_dlp.version.__version__}"))
        except ImportError:
            checks.append(("yt-dlp", False, "Not installed — pip install yt-dlp"))

    display.show_doctor_results(checks)


@cli.command()
def history() -> None:
    """Show last 5 generated playlists."""
    config, _ = get_config_or_exit()
    display.show_history(config.history)


# ---------------------------------------------------------------------------
# GUI launchers
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", "-p", default=8080, help="Port to bind to")
@click.option("--no-open", is_flag=True, help="Don't auto-open browser")
def web(host: str, port: int, no_open: bool) -> None:
    """Launch the web UI (FastAPI + htmx)."""
    from rtv.web.app import run_server
    run_server(host=host, port=port, open_browser=not no_open)


@cli.command()
def tui() -> None:
    """Launch the terminal UI (Textual)."""
    from rtv.tui.app import PlexRealTVApp
    app = PlexRealTVApp()
    app.run()


if __name__ == "__main__":
    cli()
