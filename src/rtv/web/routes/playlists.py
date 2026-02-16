"""Playlist CRUD routes: create, edit, delete, configure breaks, select shows."""

from __future__ import annotations

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from rtv.config import (
    PlaylistDefinition,
    PlaylistShow,
    BreakConfig,
    BlockDuration,
    load_config,
    save_config,
    find_config_path,
)

router = APIRouter(prefix="/playlists", tags=["playlists"])


def _load_config():
    """Load config or return defaults."""
    try:
        return load_config(), find_config_path()
    except FileNotFoundError:
        from rtv.config import RTVConfig
        return RTVConfig(), None


@router.get("/", response_class=HTMLResponse)
async def playlists_page(request: Request):
    """Render the playlists overview page."""
    templates = request.app.state.templates
    config, _ = _load_config()
    return templates.TemplateResponse("playlists.html", {
        "request": request,
        "config": config,
        "playlists": config.playlists,
        "default_playlist": config.default_playlist,
        "message": None,
        "error": None,
    })


@router.post("/create", response_class=HTMLResponse)
async def create_playlist(
    request: Request,
    name: str = Form(...),
    episodes_per_generation: int = Form(0),
    break_style: str = Form("single"),
    frequency: int = Form(1),
    sort_by: str = Form("premiere_year"),
):
    """Create a new playlist definition."""
    templates = request.app.state.templates
    config, config_path = _load_config()

    name = name.strip()
    if not name:
        return templates.TemplateResponse("playlists.html", {
            "request": request,
            "config": config,
            "playlists": config.playlists,
            "default_playlist": config.default_playlist,
            "message": None,
            "error": "Playlist name is required.",
        })

    if config.get_playlist(name) is not None:
        return templates.TemplateResponse("playlists.html", {
            "request": request,
            "config": config,
            "playlists": config.playlists,
            "default_playlist": config.default_playlist,
            "message": None,
            "error": f"Playlist '{name}' already exists.",
        })

    breaks_enabled = break_style != "disabled"
    new_pl = PlaylistDefinition(
        name=name,
        breaks=BreakConfig(
            enabled=breaks_enabled,
            style=break_style if breaks_enabled else "single",
            frequency=max(1, frequency),
        ),
        episodes_per_generation=max(0, episodes_per_generation),
        sort_by=sort_by,
    )
    config.playlists.append(new_pl)

    if len(config.playlists) == 1:
        config.default_playlist = name

    try:
        save_config(config, config_path)
        message = f"Created playlist '{name}'."
        error = None
    except Exception as e:
        message = None
        error = str(e)

    return templates.TemplateResponse("playlists.html", {
        "request": request,
        "config": config,
        "playlists": config.playlists,
        "default_playlist": config.default_playlist,
        "message": message,
        "error": error,
    })


@router.get("/{playlist_name}", response_class=HTMLResponse)
async def playlist_detail(request: Request, playlist_name: str):
    """Render a single playlist's detail / edit page."""
    templates = request.app.state.templates
    config, _ = _load_config()

    pl = config.get_playlist(playlist_name)
    if pl is None:
        return templates.TemplateResponse("playlists.html", {
            "request": request,
            "config": config,
            "playlists": config.playlists,
            "default_playlist": config.default_playlist,
            "message": None,
            "error": f"Playlist '{playlist_name}' not found.",
        })

    # Shows in the playlist vs available global shows
    playlist_show_names = {ps.name.lower() for ps in pl.shows}
    available_shows = [
        s for s in config.shows
        if s.name.lower() not in playlist_show_names
    ]

    return templates.TemplateResponse("playlist_detail.html", {
        "request": request,
        "config": config,
        "playlist": pl,
        "available_shows": available_shows,
        "is_default": pl.name == config.default_playlist,
        "message": None,
        "error": None,
    })


@router.post("/{playlist_name}/update", response_class=HTMLResponse)
async def update_playlist(
    request: Request,
    playlist_name: str,
    episodes_per_generation: int = Form(0),
    break_style: str = Form("single"),
    frequency: int = Form(1),
    min_gap: int = Form(50),
    block_min: int = Form(30),
    block_max: int = Form(120),
    sort_by: str = Form("premiere_year"),
):
    """Update playlist settings (breaks, episodes, sort)."""
    templates = request.app.state.templates
    config, config_path = _load_config()

    pl = config.get_playlist(playlist_name)
    if pl is None:
        return RedirectResponse("/playlists", status_code=303)

    breaks_enabled = break_style != "disabled"
    pl.breaks = BreakConfig(
        enabled=breaks_enabled,
        style=break_style if breaks_enabled else "single",
        frequency=max(1, frequency),
        min_gap=max(1, min_gap),
        block_duration=BlockDuration(min=max(1, block_min), max=max(1, block_max)),
    )
    pl.episodes_per_generation = max(0, episodes_per_generation)
    pl.sort_by = sort_by

    try:
        save_config(config, config_path)
        message = "Playlist settings updated."
        error = None
    except Exception as e:
        message = None
        error = str(e)

    playlist_show_names = {ps.name.lower() for ps in pl.shows}
    available_shows = [
        s for s in config.shows
        if s.name.lower() not in playlist_show_names
    ]

    return templates.TemplateResponse("playlist_detail.html", {
        "request": request,
        "config": config,
        "playlist": pl,
        "available_shows": available_shows,
        "is_default": pl.name == config.default_playlist,
        "message": message,
        "error": error,
    })


@router.post("/{playlist_name}/add-show", response_class=HTMLResponse)
async def add_show_to_playlist(
    request: Request,
    playlist_name: str,
    show_name: str = Form(...),
):
    """Add a global show to a playlist at S01E01."""
    templates = request.app.state.templates
    config, config_path = _load_config()

    pl = config.get_playlist(playlist_name)
    if pl is None:
        return RedirectResponse("/playlists", status_code=303)

    gs = config.get_global_show(show_name)
    if gs is None:
        error = f"Show '{show_name}' not found in global pool."
        message = None
    elif any(ps.name.lower() == show_name.lower() for ps in pl.shows):
        error = f"'{show_name}' is already in this playlist."
        message = None
    else:
        pl.shows.append(PlaylistShow(name=gs.name))
        try:
            save_config(config, config_path)
            message = f"Added '{gs.name}' to playlist."
            error = None
        except Exception as e:
            message = None
            error = str(e)

    playlist_show_names = {ps.name.lower() for ps in pl.shows}
    available_shows = [
        s for s in config.shows
        if s.name.lower() not in playlist_show_names
    ]

    return templates.TemplateResponse("playlist_detail.html", {
        "request": request,
        "config": config,
        "playlist": pl,
        "available_shows": available_shows,
        "is_default": pl.name == config.default_playlist,
        "message": message,
        "error": error,
    })


@router.post("/{playlist_name}/add-all-shows", response_class=HTMLResponse)
async def add_all_shows_to_playlist(request: Request, playlist_name: str):
    """Add all available global pool shows to this playlist at S01E01."""
    templates = request.app.state.templates
    config, config_path = _load_config()

    pl = config.get_playlist(playlist_name)
    if pl is None:
        return RedirectResponse("/playlists", status_code=303)

    playlist_show_names = {ps.name.lower() for ps in pl.shows}
    added_count = 0

    for gs in config.shows:
        if gs.name.lower() not in playlist_show_names:
            pl.shows.append(PlaylistShow(name=gs.name))
            playlist_show_names.add(gs.name.lower())
            added_count += 1

    if added_count > 0:
        try:
            save_config(config, config_path)
            message = f"Added {added_count} show(s) to playlist."
            error = None
        except Exception as e:
            message = None
            error = str(e)
    else:
        message = None
        error = "All pool shows are already in this playlist."

    available_shows = [
        s for s in config.shows
        if s.name.lower() not in playlist_show_names
    ]

    return templates.TemplateResponse("playlist_detail.html", {
        "request": request,
        "config": config,
        "playlist": pl,
        "available_shows": available_shows,
        "is_default": pl.name == config.default_playlist,
        "message": message,
        "error": error,
    })


@router.post("/{playlist_name}/remove-show/{show_name}", response_class=HTMLResponse)
async def remove_show_from_playlist(
    request: Request,
    playlist_name: str,
    show_name: str,
):
    """Remove a show from a playlist."""
    templates = request.app.state.templates
    config, config_path = _load_config()

    pl = config.get_playlist(playlist_name)
    if pl is None:
        return RedirectResponse("/playlists", status_code=303)

    original_count = len(pl.shows)
    pl.shows = [ps for ps in pl.shows if ps.name != show_name]

    if len(pl.shows) < original_count:
        try:
            save_config(config, config_path)
            message = f"Removed '{show_name}' from playlist."
            error = None
        except Exception as e:
            message = None
            error = str(e)
    else:
        message = None
        error = f"'{show_name}' was not in this playlist."

    playlist_show_names = {ps.name.lower() for ps in pl.shows}
    available_shows = [
        s for s in config.shows
        if s.name.lower() not in playlist_show_names
    ]

    return templates.TemplateResponse("playlist_detail.html", {
        "request": request,
        "config": config,
        "playlist": pl,
        "available_shows": available_shows,
        "is_default": pl.name == config.default_playlist,
        "message": message,
        "error": error,
    })


@router.post("/{playlist_name}/delete", response_class=HTMLResponse)
async def delete_playlist(request: Request, playlist_name: str):
    """Delete a playlist entirely."""
    config, config_path = _load_config()

    config.playlists = [
        p for p in config.playlists
        if p.name.lower() != playlist_name.lower()
    ]

    if config.default_playlist.lower() == playlist_name.lower() and config.playlists:
        config.default_playlist = config.playlists[0].name

    try:
        save_config(config, config_path)
    except Exception:
        pass

    return RedirectResponse("/playlists", status_code=303)


@router.post("/{playlist_name}/set-default")
async def set_default_playlist(request: Request, playlist_name: str):
    """Set this playlist as the default."""
    config, config_path = _load_config()

    pl = config.get_playlist(playlist_name)
    if pl is not None:
        config.default_playlist = pl.name
        try:
            save_config(config, config_path)
        except Exception:
            pass

    return RedirectResponse(f"/playlists/{playlist_name}", status_code=303)
