"""Show management routes: browse, add, remove, toggle shows."""

from __future__ import annotations

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse

from rtv.config import (
    GlobalShow,
    load_config,
    save_config,
    find_config_path,
)

router = APIRouter(prefix="/shows", tags=["shows"])


def _load_config():
    """Load config, raising a clear error if missing."""
    try:
        return load_config(), find_config_path()
    except FileNotFoundError:
        from rtv.config import RTVConfig
        return RTVConfig(), None


@router.get("/", response_class=HTMLResponse)
async def shows_page(request: Request):
    """Render the global show pool page."""
    templates = request.app.state.templates
    config, _ = _load_config()

    membership: dict[str, list[str]] = {}
    for show in config.shows:
        membership[show.name] = config.get_playlist_membership(show.name)

    return templates.TemplateResponse("shows.html", {
        "request": request,
        "config": config,
        "shows": config.shows,
        "membership": membership,
        "message": None,
        "error": None,
    })


@router.post("/add", response_class=HTMLResponse)
async def add_show(
    request: Request,
    show_name: str = Form(...),
    library: str = Form("TV Shows"),
    year: str = Form(""),
):
    """Add a show to the global pool."""
    templates = request.app.state.templates
    config, config_path = _load_config()

    name = show_name.strip()
    if not name:
        return templates.TemplateResponse("shows.html", {
            "request": request,
            "config": config,
            "shows": config.shows,
            "membership": {},
            "message": None,
            "error": "Show name is required.",
        })

    # Check duplicate
    for s in config.shows:
        if s.name.lower() == name.lower():
            return templates.TemplateResponse("shows.html", {
                "request": request,
                "config": config,
                "shows": config.shows,
                "membership": {},
                "message": None,
                "error": f"'{name}' is already in the pool.",
            })

    year_val = int(year) if year.strip().isdigit() else None
    new_show = GlobalShow(
        name=name,
        library=library.strip(),
        year=year_val,
        enabled=True,
    )
    config.shows.append(new_show)

    try:
        save_config(config, config_path)
        message = f"Added '{name}' to the show pool."
        error = None
    except Exception as e:
        message = None
        error = f"Failed to save: {e}"

    membership: dict[str, list[str]] = {}
    for s in config.shows:
        membership[s.name] = config.get_playlist_membership(s.name)

    return templates.TemplateResponse("shows.html", {
        "request": request,
        "config": config,
        "shows": config.shows,
        "membership": membership,
        "message": message,
        "error": error,
    })


@router.post("/remove/{show_name}", response_class=HTMLResponse)
async def remove_show(request: Request, show_name: str):
    """Remove a show from the global pool."""
    templates = request.app.state.templates
    config, config_path = _load_config()

    original_count = len(config.shows)
    config.shows = [s for s in config.shows if s.name != show_name]

    if len(config.shows) == original_count:
        error = f"Show '{show_name}' not found."
        message = None
    else:
        try:
            save_config(config, config_path)
            message = f"Removed '{show_name}' from the pool."
            error = None
        except Exception as e:
            message = None
            error = str(e)

    membership: dict[str, list[str]] = {}
    for s in config.shows:
        membership[s.name] = config.get_playlist_membership(s.name)

    return templates.TemplateResponse("shows.html", {
        "request": request,
        "config": config,
        "shows": config.shows,
        "membership": membership,
        "message": message,
        "error": error,
    })


@router.post("/toggle/{show_name}", response_class=HTMLResponse)
async def toggle_show(request: Request, show_name: str):
    """Toggle a show's enabled state. Returns an htmx fragment for the row."""
    config, config_path = _load_config()

    gs = config.get_global_show(show_name)
    if gs is None:
        return HTMLResponse(
            f'<span class="badge badge-error">Not found</span>',
            status_code=404,
        )

    gs.enabled = not gs.enabled
    try:
        save_config(config, config_path)
    except Exception:
        pass

    if gs.enabled:
        return HTMLResponse(
            f'<button class="toggle-btn toggle-on" '
            f'hx-post="/shows/toggle/{show_name}" hx-swap="outerHTML" '
            f'title="Click to disable">'
            f'ON</button>'
        )
    else:
        return HTMLResponse(
            f'<button class="toggle-btn toggle-off" '
            f'hx-post="/shows/toggle/{show_name}" hx-swap="outerHTML" '
            f'title="Click to enable">'
            f'OFF</button>'
        )


@router.post("/scan", response_class=HTMLResponse)
async def scan_plex_shows(request: Request):
    """Scan Plex libraries and return available shows as a fragment."""
    config, _ = _load_config()

    try:
        from rtv.plex_client import connect, get_all_shows
        server = connect(config.plex)
    except Exception as e:
        return HTMLResponse(
            f'<div class="toast toast-error">Could not connect to Plex: {e}</div>'
        )

    existing_names = {s.name.lower() for s in config.shows}
    discovered: list[dict[str, str | int | None]] = []

    for lib_name in config.plex.tv_libraries:
        try:
            shows = get_all_shows(server, lib_name)
            for show in shows:
                title = show.title
                if title.lower() not in existing_names:
                    year = getattr(show, "year", None)
                    discovered.append({
                        "name": title,
                        "library": lib_name,
                        "year": year,
                    })
        except Exception:
            continue

    if not discovered:
        return HTMLResponse(
            '<div class="toast toast-warning">'
            'No new shows found (all Plex shows are already in the pool).'
            '</div>'
        )

    rows = ""
    for d in discovered[:50]:
        name = d["name"]
        lib = d["library"]
        year = d["year"] or ""
        rows += (
            f'<div class="scan-row">'
            f'<span class="scan-title">{name}</span>'
            f'<span class="scan-meta">{year} &middot; {lib}</span>'
            f'<button class="btn btn-sm btn-accent" '
            f'hx-post="/shows/add" '
            f'hx-vals=\'{{"show_name":"{name}","library":"{lib}","year":"{year}"}}\' '
            f'hx-target="#shows-container" hx-swap="innerHTML">'
            f'Add</button>'
            f'</div>'
        )

    count_note = f" (showing first 50)" if len(discovered) > 50 else ""
    return HTMLResponse(
        f'<div class="scan-results">'
        f'<p class="scan-header">Found {len(discovered)} new show(s){count_note}:</p>'
        f'{rows}'
        f'</div>'
    )
