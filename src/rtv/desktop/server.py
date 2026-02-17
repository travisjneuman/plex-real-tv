"""FastAPI server launcher for desktop app with offline assets."""

from __future__ import annotations

import sys
import socket
import threading
from pathlib import Path


def get_base_path() -> Path:
    """Get base path for bundled resources (works in dev and PyInstaller).
    
    In PyInstaller bundle: returns sys._MEIPASS (extraction root)
    In dev mode: returns project src directory
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    # Dev mode: this file is at src/rtv/desktop/server.py
    # Go up 3 levels to get to src/
    return Path(__file__).parent.parent.parent


BASE_PATH = get_base_path()
DESKTOP_DIR = BASE_PATH / "rtv" / "desktop"
TEMPLATES_DIR = DESKTOP_DIR / "templates"
STATIC_DIR = DESKTOP_DIR / "static"
WEB_TEMPLATES_DIR = BASE_PATH / "rtv" / "web" / "templates"
WEB_STATIC_DIR = BASE_PATH / "rtv" / "web" / "static"


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
    from jinja2 import FileSystemLoader, ChoiceLoader

    app = FastAPI(
        title="RealTV Desktop",
        description="Desktop application for plex-real-tv",
    )

    print(f"[DEBUG] BASE_PATH: {BASE_PATH}")
    print(f"[DEBUG] STATIC_DIR: {STATIC_DIR} (exists: {STATIC_DIR.exists()})")
    print(f"[DEBUG] TEMPLATES_DIR: {TEMPLATES_DIR} (exists: {TEMPLATES_DIR.exists()})")
    print(f"[DEBUG] WEB_TEMPLATES_DIR: {WEB_TEMPLATES_DIR} (exists: {WEB_TEMPLATES_DIR.exists()})")

    # Mount static directories
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static-desktop")
    
    # Use both desktop and web templates - desktop overrides web
    template_dirs = []
    if TEMPLATES_DIR.exists():
        template_dirs.append(str(TEMPLATES_DIR))
    if WEB_TEMPLATES_DIR.exists():
        template_dirs.append(str(WEB_TEMPLATES_DIR))
    
    print(f"[DEBUG] Template dirs: {template_dirs}")
    
    loader = ChoiceLoader([FileSystemLoader(d) for d in template_dirs]) if template_dirs else None
    templates = Jinja2Templates(directory=template_dirs[0] if template_dirs else ".", loader=loader)
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


def run_server(port: int, ready_event: threading.Event | None = None):
    """Run the FastAPI server on the given port."""
    import uvicorn

    app = create_desktop_app()

    class ServerWithReady(uvicorn.Server):
        def __init__(self, config, ready_evt):
            super().__init__(config)
            self._ready_evt = ready_evt

        async def startup(self, sockets=None):
            await super().startup(sockets)
            if self._ready_evt:
                self._ready_evt.set()

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="error",
        access_log=False,
    )
    server = ServerWithReady(config, ready_event)
    server.run()
