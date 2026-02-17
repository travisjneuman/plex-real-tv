"""FastAPI application factory and uvicorn launcher for plex-real-tv web UI."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from threading import Timer

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def _load_config_safe():
    """Load config without raising on missing file."""
    try:
        from rtv.config import load_config
        return load_config(), True
    except (FileNotFoundError, Exception):
        from rtv.config import RTVConfig
        return RTVConfig(), False


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="plex-real-tv",
        description="Web UI for plex-real-tv playlist management",
    )

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.templates = templates

    from rtv.web.routes.setup import router as setup_router
    from rtv.web.routes.shows import router as shows_router
    from rtv.web.routes.playlists import router as playlists_router
    from rtv.web.routes.generate import router as generate_router

    app.include_router(setup_router)
    app.include_router(shows_router)
    app.include_router(playlists_router)
    app.include_router(generate_router)

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        config, config_exists = _load_config_safe()
        show_count = len(config.shows)
        playlist_count = len(config.playlists)
        generation_count = len(config.history) if hasattr(config, "history") else 0

        # Plex status indicator
        if not config_exists or not config.plex.token:
            plex_status = "Not Set"
        else:
            plex_status = "Configured"

        # Last generation
        last_generation = None
        if hasattr(config, "history") and config.history:
            last = config.history[-1]
            last_generation = last

        return templates.TemplateResponse("home.html", {
            "request": request,
            "config_exists": config_exists,
            "show_count": show_count,
            "playlist_count": playlist_count,
            "generation_count": generation_count,
            "plex_status": plex_status,
            "last_generation": last_generation,
        })

    # Inject nav badge counts into every template context
    @app.middleware("http")
    async def inject_nav_counts(request: Request, call_next):
        config, _ = _load_config_safe()
        request.state.show_count = len(config.shows)
        request.state.playlist_count = len(config.playlists)
        return await call_next(request)

    return app


app = create_app()


def run_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    open_browser: bool = True,
) -> None:
    """Launch the web server with optional browser auto-open."""
    import uvicorn

    if open_browser:
        browse_url = f"http://127.0.0.1:{port}" if host == "0.0.0.0" else f"http://{host}:{port}"
        Timer(1.5, webbrowser.open, args=[browse_url]).start()

    uvicorn.run(app, host=host, port=port, log_level="info")
