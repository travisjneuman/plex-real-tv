"""Round-robin playlist generation algorithm with commercial breaks."""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from plexapi.server import PlexServer
from plexapi.video import Video, Episode

from rtv.config import (
    RTVConfig,
    GlobalShow,
    PlaylistShow,
    PlaylistDefinition,
    BreakConfig,
    CommercialConfig,
)
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

    name: str
    library: str
    year: int | None
    playlist_show: PlaylistShow
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
            clip_duration = 30.0

        block.append(chosen)
        block_duration += clip_duration

    return block, block_duration


def build_commercial_block_for_playlist(
    commercials: list[Video],
    break_config: BreakConfig,
    commercial_config: CommercialConfig,
    categories_by_path: dict[str, str],
) -> tuple[list[Video], float]:
    """Build a commercial block using playlist-specific break settings.

    Uses break_config.block_duration for the target range.
    Returns (list of commercial items, total duration in seconds).
    """
    if not commercials:
        return [], 0.0

    target_duration = random.uniform(
        break_config.block_duration.min,
        break_config.block_duration.max,
    )

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
            clip_duration = 30.0
        block.append(chosen)
        block_duration += clip_duration

    return block, block_duration


def _get_clip_category(clip: Video, categories_by_path: dict[str, str]) -> str:
    """Determine the category of a commercial clip from its file path."""
    if hasattr(clip, "locations") and clip.locations:
        from pathlib import PurePosixPath, PureWindowsPath

        location = clip.locations[0]
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
    playlist: PlaylistDefinition,
    server: PlexServer,
    episode_count: int | None = None,
    from_start: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> GenerationResult:
    """Generate round-robin playlist with commercial breaks.

    Args:
        config: The full RTV configuration (for global shows and commercial settings).
        playlist: The specific playlist definition to generate.
        server: Connected PlexServer instance.
        episode_count: Maximum number of episodes. None = use playlist default.
        from_start: If True, reset all show positions to S01E01.
        progress_callback: Optional callback(current, total) for progress updates.

    Returns:
        GenerationResult with all playlist items and statistics.
    """
    if not playlist.shows:
        raise ValueError(
            f"Playlist '{playlist.name}' has no shows. "
            "Use 'rtv playlist-add' to add shows."
        )

    ep_count = episode_count or playlist.episodes_per_generation

    # Reset positions if requested
    if from_start:
        for ps in playlist.shows:
            ps.current_season = 1
            ps.current_episode = 1

    # Initialize show states from playlist shows + global show metadata
    show_states: list[ShowState] = []
    for ps in playlist.shows:
        global_show = config.get_global_show(ps.name)
        if global_show is None:
            display.warning(f"'{ps.name}' not found in global shows, skipping.")
            continue
        if not global_show.enabled:
            continue

        try:
            plex_show = plex_client.get_show(
                server, ps.name, global_show.library
            )
            show_states.append(ShowState(
                name=ps.name,
                library=global_show.library,
                year=global_show.year,
                playlist_show=ps,
                plex_show=plex_show,
                current_season=ps.current_season,
                current_episode=ps.current_episode,
            ))
        except Exception as e:
            display.warning(f"Could not find '{ps.name}' in Plex: {e}")

    if not show_states:
        raise ValueError("None of the playlist's shows could be found in Plex.")

    # Backfill missing years from Plex metadata
    for state in show_states:
        if state.year is None:
            plex_year = getattr(state.plex_show, "year", None)
            if plex_year is not None:
                state.year = int(plex_year)
                # Also update global show
                gs = config.get_global_show(state.name)
                if gs is not None:
                    gs.year = state.year

    # Sort show states
    sort_by = playlist.sort_by
    if sort_by == "premiere_year":
        show_states.sort(key=lambda s: (s.year is None, s.year or 0))
    elif sort_by == "premiere_year_desc":
        show_states.sort(key=lambda s: (s.year is None, -(s.year or 0)))
    elif sort_by == "alphabetical":
        show_states.sort(key=lambda s: s.name.lower())
    # "config_order" — no sorting needed

    # Load commercials
    breaks = playlist.breaks
    commercials: list[Video] = []
    if breaks.enabled:
        commercials = plex_client.get_commercials(server, config.commercials.library_name)
        if not commercials:
            display.warning("No commercials found. Generating playlist without commercial breaks.")

    # No-repeat tracking for single-style commercials
    commercial_history: deque[int] = deque(maxlen=breaks.min_gap)

    # Build the playlist
    playlist_items: list[Video | Episode] = []
    episodes_added = 0
    commercial_block_count = 0
    commercial_total_secs = 0.0
    total_runtime_secs = 0.0
    dropped_shows: list[str] = []
    episodes_since_last_commercial = 0

    rotation_idx = 0

    while episodes_added < ep_count:
        active_states = [s for s in show_states if not s.exhausted]
        if not active_states:
            display.warning("All shows exhausted.")
            break

        state = active_states[rotation_idx % len(active_states)]
        rotation_idx += 1

        episode = _get_next_episode(state)
        if episode is None:
            state.exhausted = True
            dropped_shows.append(state.name)
            display.warning(f"'{state.name}' has no more episodes.")
            rotation_idx -= 1
            continue

        playlist_items.append(episode)
        episodes_added += 1
        state.episodes_added += 1

        if progress_callback is not None:
            progress_callback(episodes_added, ep_count)

        ep_duration = _get_duration_secs(episode)
        total_runtime_secs += ep_duration
        episodes_since_last_commercial += 1

        # Advance position
        state.current_episode += 1

        # Insert commercial(s) if frequency met and breaks enabled
        if (
            commercials
            and breaks.enabled
            and episodes_since_last_commercial >= breaks.frequency
            and episodes_added < ep_count
        ):
            if breaks.style == "single":
                clip, clip_duration = pick_single_commercial(
                    commercials, commercial_history, breaks.min_gap
                )
                if clip is not None:
                    playlist_items.append(clip)
                    commercial_block_count += 1
                    commercial_total_secs += clip_duration
                    total_runtime_secs += clip_duration
            elif breaks.style == "block":
                block_items, block_duration = build_commercial_block_for_playlist(
                    commercials, breaks, config.commercials, {}
                )
                if block_items:
                    playlist_items.extend(block_items)
                    commercial_block_count += 1
                    commercial_total_secs += block_duration
                    total_runtime_secs += block_duration
            episodes_since_last_commercial = 0

    # Save updated positions back to playlist shows
    for state in show_states:
        state.playlist_show.current_season = state.current_season
        state.playlist_show.current_episode = state.current_episode

    # Build result
    episodes_by_show: dict[str, int] = {}
    show_positions: dict[str, str] = {}
    for state in show_states:
        episodes_by_show[state.name] = state.episodes_added
        show_positions[state.name] = (
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
        return None

    state.current_season = next_season
    state.current_episode = 1

    episode = plex_client.get_episode(
        state.plex_show, state.current_season, state.current_episode  # type: ignore[arg-type]
    )
    return episode
