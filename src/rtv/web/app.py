"""FastAPI application factory and uvicorn launcher for plex-real-tv web UI."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from threading import Timer

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


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
