"""Playlist generation routes with SSE progress streaming."""

from __future__ import annotations

import asyncio
import copy
import json
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse

from rtv.config import (
    HistoryEntry,
    load_config,
    save_config,
    find_config_path,
)

router = APIRouter(prefix="/generate", tags=["generate"])


def _load_config():
    """Load config or return defaults."""
    try:
        return load_config(), find_config_path()
    except FileNotFoundError:
        from rtv.config import RTVConfig
        return RTVConfig(), None


@router.get("/", response_class=HTMLResponse)
async def generate_page(request: Request):
    """Render the generation page with playlist selector."""
    templates = request.app.state.templates
    config, _ = _load_config()
    return templates.TemplateResponse("generate.html", {
        "request": request,
        "config": config,
        "playlists": config.playlists,
        "default_playlist": config.default_playlist,
    })


@router.get("/stream")
async def generate_stream(
    request: Request,
    playlist_name: str = "",
    episode_count: int = 0,
    from_start: bool = False,
):
    """SSE endpoint that streams generation progress events.

    Events emitted:
      - progress: {current, total, percent, message}
      - complete: {summary dict}
      - error: {message}
    """
    from sse_starlette.sse import EventSourceResponse

    async def event_generator() -> AsyncGenerator[dict, None]:
        config, config_path = _load_config()

        target_name = playlist_name or config.default_playlist
        pl = config.get_playlist(target_name)
        if pl is None:
            yield {
                "event": "error",
                "data": json.dumps({"message": f"Playlist '{target_name}' not found."}),
            }
            return

        if not pl.shows:
            yield {
                "event": "error",
                "data": json.dumps({"message": f"Playlist '{pl.name}' has no shows."}),
            }
            return

        ep_count = episode_count if episode_count > 0 else pl.episodes_per_generation

        yield {
            "event": "progress",
            "data": json.dumps({
                "current": 0,
                "total": ep_count,
                "percent": 0,
                "message": "Connecting to Plex...",
            }),
        }
        await asyncio.sleep(0.1)

        try:
            from rtv.plex_client import connect, create_or_update_playlist
            server = connect(config.plex)
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"message": f"Could not connect to Plex: {e}"}),
            }
            return

        yield {
            "event": "progress",
            "data": json.dumps({
                "current": 0,
                "total": ep_count,
                "percent": 0,
                "message": "Building playlist...",
            }),
        }
        await asyncio.sleep(0.1)

        # Run generation in a thread to avoid blocking the event loop
        progress_queue: asyncio.Queue[tuple[int, int]] = asyncio.Queue()

        def progress_callback(current: int, total: int) -> None:
            try:
                progress_queue.put_nowait((current, total))
            except asyncio.QueueFull:
                pass

        loop = asyncio.get_event_loop()

        from rtv.playlist import generate_playlist

        gen_future = loop.run_in_executor(
            None,
            lambda: generate_playlist(
                config, pl, server, ep_count, from_start,
                progress_callback=progress_callback,
            ),
        )

        # Stream progress while generation runs
        while not gen_future.done():
            try:
                current, total = await asyncio.wait_for(
                    progress_queue.get(), timeout=0.3,
                )
                percent = int((current / total) * 100) if total > 0 else 0
                yield {
                    "event": "progress",
                    "data": json.dumps({
                        "current": current,
                        "total": total,
                        "percent": percent,
                        "message": f"Episode {current} of {total}...",
                    }),
                }
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

        # Drain remaining progress
        while not progress_queue.empty():
            try:
                current, total = progress_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        try:
            result = await gen_future
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"message": f"Generation failed: {e}"}),
            }
            return

        if not result.playlist_items:
            yield {
                "event": "error",
                "data": json.dumps({"message": "No items generated."}),
            }
            return

        # Push to Plex
        yield {
            "event": "progress",
            "data": json.dumps({
                "current": ep_count,
                "total": ep_count,
                "percent": 95,
                "message": "Creating Plex playlist...",
            }),
        }
        await asyncio.sleep(0.1)

        try:
            await loop.run_in_executor(
                None,
                lambda: create_or_update_playlist(server, pl.name, result.playlist_items),
            )
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"message": f"Failed to create playlist: {e}"}),
            }
            return

        # Save updated positions + history
        entry = HistoryEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            playlist_name=pl.name,
            episode_count=sum(result.episodes_by_show.values()),
            shows=list(result.episodes_by_show.keys()),
            runtime_secs=result.total_runtime_secs,
        )
        config.history.append(entry)
        config.history = config.history[-5:]

        try:
            save_config(config, config_path)
        except Exception:
            pass

        # Format runtime
        total_mins = int(result.total_runtime_secs) // 60
        hours = total_mins // 60
        mins = total_mins % 60
        runtime_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

        comm_mins = int(result.commercial_total_secs) // 60

        yield {
            "event": "complete",
            "data": json.dumps({
                "playlist_name": pl.name,
                "total_items": len(result.playlist_items),
                "episodes_by_show": result.episodes_by_show,
                "show_positions": result.show_positions,
                "runtime": runtime_str,
                "commercial_blocks": result.commercial_block_count,
                "commercial_minutes": comm_mins,
                "dropped_shows": result.dropped_shows,
            }),
        }

    return EventSourceResponse(event_generator())
