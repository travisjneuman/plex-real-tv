"""Round-robin playlist generation algorithm with commercial breaks."""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field

from plexapi.server import PlexServer
from plexapi.video import Video, Episode

from rtv.config import RTVConfig, ShowConfig, CommercialConfig
from rtv import plex_client, display


@dataclass
class GenerationResult:
    """Results from playlist generation."""

    playlist_items: list[Video | Episode]
    episodes_by_show: dict[str, int]
    show_positions: dict[str, str]
    total_runtime_secs: float
    commercial_block_count: int
    commercial_total_secs: float
    dropped_shows: list[str]


@dataclass
class ShowState:
    """Mutable state tracking for a show during generation."""

    config: ShowConfig
    plex_show: object  # plexapi.video.Show
    current_season: int
    current_episode: int
    exhausted: bool = False
    episodes_added: int = 0


def pick_single_commercial(
    commercials: list[Video],
    recent_history: deque[int],
    min_gap: int = 50,
) -> tuple[Video | None, float]:
    """Pick a single random commercial, avoiding recent repeats.

    Maintains a deque of recently-used commercial indices. A commercial won't
    repeat until at least ``min_gap`` others have played. If the pool is smaller
    than min_gap, falls back to the oldest-used commercial.

    Returns (commercial, duration_secs) or (None, 0.0) if no commercials.
    """
    if not commercials:
        return None, 0.0

    # Build eligible indices (not in recent history)
    recent_set = set(recent_history)
    eligible = [i for i in range(len(commercials)) if i not in recent_set]

    if not eligible:
        # All commercials used recently — pick the oldest one (first in deque)
        idx = recent_history[0]
    else:
        idx = random.choice(eligible)

    recent_history.append(idx)

    clip = commercials[idx]
    duration = _get_duration_secs(clip)
    if duration <= 0:
        duration = 30.0

    return clip, duration


def build_commercial_block(
    commercials: list[Video],
    commercial_config: CommercialConfig,
    categories_by_path: dict[str, str],
) -> tuple[list[Video], float]:
    """Build a commercial block of random clips meeting the target duration.

    Returns (list of commercial items, total duration in seconds).
    Kept for backwards compatibility but no longer used by generate_playlist.
    """
    if not commercials:
        return [], 0.0

    target_duration = random.uniform(
        commercial_config.block_duration.min,
        commercial_config.block_duration.max,
    )

    # Build weighted pool based on category weights
    category_weights: dict[str, float] = {}
    for cat in commercial_config.categories:
        category_weights[cat.name.lower()] = cat.weight

    weighted_pool: list[tuple[Video, float]] = []
    for clip in commercials:
        clip_category = _get_clip_category(clip, categories_by_path)
        weight = category_weights.get(clip_category.lower(), 1.0)
        weighted_pool.append((clip, weight))

    if not weighted_pool:
        return [], 0.0

    clips = [item[0] for item in weighted_pool]
    weights = [item[1] for item in weighted_pool]

    block: list[Video] = []
    block_duration = 0.0

    while block_duration < target_duration and clips:
        chosen = random.choices(clips, weights=weights, k=1)[0]
        clip_duration = _get_duration_secs(chosen)
        if clip_duration <= 0:
            clip_duration = 30.0  # Default 30s for unknown duration clips

        block.append(chosen)
        block_duration += clip_duration

    return block, block_duration


def _get_clip_category(clip: Video, categories_by_path: dict[str, str]) -> str:
    """Determine the category of a commercial clip from its file path."""
    if hasattr(clip, "locations") and clip.locations:
        from pathlib import PurePosixPath, PureWindowsPath

        location = clip.locations[0]
        # Try to extract parent folder name as category
        for path_class in (PureWindowsPath, PurePosixPath):
            try:
                p = path_class(location)
                return p.parent.name
            except Exception:
                continue
    return "uncategorized"


def _get_duration_secs(item: Video | Episode) -> float:
    """Get duration of a Plex item in seconds. Returns 0 if unavailable."""
    if hasattr(item, "duration") and item.duration:
        return item.duration / 1000.0
    return 0.0


def generate_playlist(
    config: RTVConfig,
    server: PlexServer,
    episode_count: int,
    from_start: bool,
    progress_task: tuple[object, object] | None = None,
) -> GenerationResult:
    """Generate round-robin playlist with commercial blocks.

    Args:
        config: The full RTV configuration.
        server: Connected PlexServer instance.
        episode_count: Maximum number of episodes to include.
        from_start: If True, reset all show positions to S01E01.
        progress_task: Optional (Progress, task_id) tuple for progress bar updates.

    Returns:
        GenerationResult with all playlist items and statistics.
    """
    if not config.shows:
        raise ValueError("No shows in rotation. Use 'rtv add-show' first.")

    # Reset positions if requested
    if from_start:
        for show in config.shows:
            show.current_season = 1
            show.current_episode = 1

    # Initialize show states
    show_states: list[ShowState] = []
    for show_config in config.shows:
        try:
            plex_show = plex_client.get_show(
                server, show_config.name, show_config.library
            )
            show_states.append(ShowState(
                config=show_config,
                plex_show=plex_show,
                current_season=show_config.current_season,
                current_episode=show_config.current_episode,
            ))
        except Exception as e:
            display.warning(f"Could not find '{show_config.name}' in Plex: {e}")

    if not show_states:
        raise ValueError("None of the configured shows could be found in Plex.")

    # Backfill missing years from Plex metadata
    for state in show_states:
        if state.config.year is None:
            plex_year = getattr(state.plex_show, "year", None)
            if plex_year is not None:
                state.config.year = int(plex_year)

    # Sort show states according to playlist.sort_by
    sort_by = config.playlist.sort_by
    if sort_by == "premiere_year":
        show_states.sort(key=lambda s: (s.config.year is None, s.config.year or 0))
    elif sort_by == "premiere_year_desc":
        show_states.sort(key=lambda s: (s.config.year is None, -(s.config.year or 0)))
    elif sort_by == "alphabetical":
        show_states.sort(key=lambda s: s.config.name.lower())
    # "config_order" — no sorting needed

    # Load commercials
    commercials = plex_client.get_commercials(server, config.commercials.library_name)
    if not commercials:
        display.warning("No commercials found. Generating playlist without commercial breaks.")

    # No-repeat tracking: deque with maxlen = commercial_min_gap
    commercial_history: deque[int] = deque(maxlen=config.playlist.commercial_min_gap)

    # Build the playlist
    playlist_items: list[Video | Episode] = []
    episodes_added = 0
    commercial_block_count = 0
    commercial_total_secs = 0.0
    total_runtime_secs = 0.0
    dropped_shows: list[str] = []
    episodes_since_last_commercial = 0

    rotation_idx = 0

    while episodes_added < episode_count:
        # Filter out exhausted shows
        active_states = [s for s in show_states if not s.exhausted]
        if not active_states:
            display.warning("All shows exhausted.")
            break

        # Pick next show in round-robin
        state = active_states[rotation_idx % len(active_states)]
        rotation_idx += 1

        # Get the next episode
        episode = _get_next_episode(state)
        if episode is None:
            # Show is exhausted
            state.exhausted = True
            dropped_shows.append(state.config.name)
            display.warning(f"'{state.config.name}' has no more episodes.")
            # Don't increment rotation_idx extra — the exhausted show
            # is filtered out next iteration
            rotation_idx -= 1  # Adjust so we don't skip the next show
            continue

        # Add the episode
        playlist_items.append(episode)
        episodes_added += 1
        state.episodes_added += 1

        # Update progress bar if provided
        if progress_task is not None:
            progress, task_id = progress_task
            progress.update(task_id, completed=episodes_added)  # type: ignore[union-attr]
        ep_duration = _get_duration_secs(episode)
        total_runtime_secs += ep_duration
        episodes_since_last_commercial += 1

        # Advance position
        state.current_episode += 1

        # Insert single commercial if frequency met
        if (
            commercials
            and episodes_since_last_commercial >= config.playlist.commercial_frequency
            and episodes_added < episode_count  # Don't add commercials after last episode
        ):
            clip, clip_duration = pick_single_commercial(
                commercials, commercial_history, config.playlist.commercial_min_gap
            )
            if clip is not None:
                playlist_items.append(clip)
                commercial_block_count += 1
                commercial_total_secs += clip_duration
                total_runtime_secs += clip_duration
            episodes_since_last_commercial = 0

    # Save updated positions back to config
    for state in show_states:
        state.config.current_season = state.current_season
        state.config.current_episode = state.current_episode

    # Build result
    episodes_by_show: dict[str, int] = {}
    show_positions: dict[str, str] = {}
    for state in show_states:
        episodes_by_show[state.config.name] = state.episodes_added
        show_positions[state.config.name] = (
            f"S{state.current_season:02d}E{state.current_episode:02d}"
        )

    return GenerationResult(
        playlist_items=playlist_items,
        episodes_by_show=episodes_by_show,
        show_positions=show_positions,
        total_runtime_secs=total_runtime_secs,
        commercial_block_count=commercial_block_count,
        commercial_total_secs=commercial_total_secs,
        dropped_shows=dropped_shows,
    )


def _get_next_episode(state: ShowState) -> Episode | None:
    """Get the next episode for a show, advancing through seasons as needed.

    Returns None if the show is completely exhausted.
    """
    # Try current position
    episode = plex_client.get_episode(
        state.plex_show, state.current_season, state.current_episode  # type: ignore[arg-type]
    )
    if episode is not None:
        return episode

    # Current episode doesn't exist — try advancing to next season
    next_season = plex_client.get_next_season_number(
        state.plex_show, state.current_season  # type: ignore[arg-type]
    )
    if next_season is None:
        # No more seasons
        return None

    state.current_season = next_season
    state.current_episode = 1

    # Try first episode of next season
    episode = plex_client.get_episode(
        state.plex_show, state.current_season, state.current_episode  # type: ignore[arg-type]
    )
    return episode
