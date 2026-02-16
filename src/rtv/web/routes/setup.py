"""Setup routes: Plex connection, auto-discovery, SSH configuration."""

from __future__ import annotations

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse

from rtv.config import (
    RTVConfig,
    PlexConfig,
    SSHConfig,
    load_config,
    save_config,
    find_config_path,
)

router = APIRouter(prefix="/setup", tags=["setup"])


def _load_or_default() -> tuple[RTVConfig, bool]:
    """Load config or return a fresh default. Returns (config, exists)."""
    try:
        config = load_config()
        return config, True
    except FileNotFoundError:
        return RTVConfig(), False


@router.get("/", response_class=HTMLResponse)
async def setup_page(request: Request):
    """Render the setup / connection page."""
    templates = request.app.state.templates
    config, config_exists = _load_or_default()
    return templates.TemplateResponse("setup.html", {
        "request": request,
        "config": config,
        "config_exists": config_exists,
        "message": None,
        "error": None,
    })


@router.post("/plex", response_class=HTMLResponse)
async def save_plex_settings(
    request: Request,
    plex_url: str = Form(...),
    plex_token: str = Form(...),
    tv_libraries: str = Form("TV Shows"),
):
    """Save Plex connection settings."""
    templates = request.app.state.templates
    config, _ = _load_or_default()

    libs = [lib.strip() for lib in tv_libraries.split(",") if lib.strip()]

    config.plex = PlexConfig(
        url=plex_url.strip(),
        token=plex_token.strip(),
        tv_libraries=libs,
    )

    try:
        path = save_config(config)
        message = f"Plex settings saved to {path}"
        error = None
    except Exception as e:
        message = None
        error = f"Failed to save: {e}"

    return templates.TemplateResponse("setup.html", {
        "request": request,
        "config": config,
        "config_exists": True,
        "message": message,
        "error": error,
    })


@router.post("/ssh", response_class=HTMLResponse)
async def save_ssh_settings(
    request: Request,
    ssh_enabled: bool = Form(False),
    ssh_host: str = Form(""),
    ssh_port: int = Form(22),
    ssh_username: str = Form(""),
    ssh_key_path: str = Form(""),
    ssh_remote_path: str = Form(""),
):
    """Save SSH configuration."""
    templates = request.app.state.templates
    config, _ = _load_or_default()

    config.ssh = SSHConfig(
        enabled=ssh_enabled,
        host=ssh_host.strip(),
        port=ssh_port,
        username=ssh_username.strip(),
        key_path=ssh_key_path.strip(),
        remote_commercial_path=ssh_remote_path.strip(),
    )

    try:
        path = save_config(config)
        message = f"SSH settings saved to {path}"
        error = None
    except Exception as e:
        message = None
        error = f"Failed to save: {e}"

    return templates.TemplateResponse("setup.html", {
        "request": request,
        "config": config,
        "config_exists": True,
        "message": message,
        "error": error,
    })


@router.post("/test-connection", response_class=HTMLResponse)
async def test_connection(request: Request):
    """Test the current Plex connection and return a status fragment."""
    config, _ = _load_or_default()

    try:
        from rtv.plex_client import connect
        server = connect(config.plex)
        server_name = getattr(server, "friendlyName", "Unknown")
        version = getattr(server, "version", "Unknown")
        return HTMLResponse(
            f'<div class="toast toast-success" id="toast">'
            f'Connected to <strong>{server_name}</strong> (v{version})'
            f'</div>'
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="toast toast-error" id="toast">'
            f'Connection failed: {e}'
            f'</div>'
        )


@router.post("/discover", response_class=HTMLResponse)
async def discover_servers(request: Request):
    """Auto-discover Plex servers on the local network via GDM."""
    try:
        from rtv.plex_client import discover_servers as _discover
        servers = _discover()
    except Exception:
        servers = []

    if not servers:
        return HTMLResponse(
            '<div class="toast toast-warning" id="toast">'
            'No Plex servers found on the local network. '
            'Make sure GDM is enabled in Plex settings.'
            '</div>'
        )

    rows = ""
    for srv in servers:
        name = srv.get("name", "Unknown")
        host = srv.get("host", "")
        port = srv.get("port", 32400)
        url = f"https://{host}:{port}"
        rows += (
            f'<button type="button" class="discovered-server" '
            f'hx-on:click="document.getElementById(\'plex_url\').value=\'{url}\'">'
            f'<span class="server-name">{name}</span>'
            f'<span class="server-url">{url}</span>'
            f'</button>'
        )

    return HTMLResponse(
        f'<div class="discovered-list">'
        f'<p class="discovered-label">Found {len(servers)} server(s) &mdash; click to use:</p>'
        f'{rows}'
        f'</div>'
    )
