"""FastAPI server launcher for desktop app with offline assets."""

from __future__ import annotations

import socket
import threading
from pathlib import Path

DESKTOP_DIR = Path(__file__).parent
TEMPLATES_DIR = DESKTOP_DIR / "templates"
STATIC_DIR = DESKTOP_DIR / "static"
WEB_STATIC_DIR = DESKTOP_DIR.parent / "web" / "static"


def find_free_port() -> int:
    """Find an available port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        return s.getsockname()[1]


def create_desktop_app():
    """Create FastAPI app with offline templates and static files."""
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates

    app = FastAPI(
        title="RealTV Desktop",
        description="Desktop application for plex-real-tv",
    )

    # Mount static directories
    # Desktop static (fonts, vendor JS)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.templates = templates

    # Import and include routers from web UI
    from rtv.web.routes.setup import router as setup_router
    from rtv.web.routes.shows import router as shows_router
    from rtv.web.routes.playlists import router as playlists_router
    from rtv.web.routes.generate import router as generate_router

    app.include_router(setup_router)
    app.include_router(shows_router)
    app.include_router(playlists_router)
    app.include_router(generate_router)

    def _load_config_safe():
        """Load config without raising on missing file."""
        try:
            from rtv.config import load_config
            return load_config(), True
        except (FileNotFoundError, Exception):
            from rtv.config import RTVConfig
            return RTVConfig(), False

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        config, config_exists = _load_config_safe()
        show_count = len(config.shows)
        playlist_count = len(config.playlists)
        generation_count = len(config.history) if hasattr(config, "history") else 0

        if not config_exists or not config.plex.token:
            plex_status = "Not Set"
        else:
            plex_status = "Configured"

        last_generation = None
        if hasattr(config, "history") and config.history:
            last_generation = config.history[-1]

        return templates.TemplateResponse("home.html", {
            "request": request,
            "config_exists": config_exists,
            "show_count": show_count,
            "playlist_count": playlist_count,
            "generation_count": generation_count,
            "plex_status": plex_status,
            "last_generation": last_generation,
        })

    @app.middleware("http")
    async def inject_nav_counts(request: Request, call_next):
        config, _ = _load_config_safe()
        request.state.show_count = len(config.shows)
        request.state.playlist_count = len(config.playlists)
        return await call_next(request)

    return app


def run_server(port: int, ready_event: threading.Event = None):
    """Run the FastAPI server on the given port."""
    import uvicorn

    app = create_desktop_app()
    
    if ready_event:
        ready_event.set()

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="error",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()
