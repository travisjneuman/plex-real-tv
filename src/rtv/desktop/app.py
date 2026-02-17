"""PyWebView entry point for plex-real-tv desktop application."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import webview


def get_asset_path(relative_path: str) -> str:
    """Get absolute path to asset, works for dev and PyInstaller."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent
    return str(base_path / relative_path)


def main():
    """Launch the desktop application."""
    from rtv.desktop.server import find_free_port, run_server

    port = find_free_port()
    ready = threading.Event()

    server_thread = threading.Thread(
        target=run_server,
        args=(port, ready),
        daemon=True,
    )
    server_thread.start()
    ready.wait()

    window = webview.create_window(
        title="RealTV - Plex TV Simulator",
        url=f"http://127.0.0.1:{port}",
        width=1280,
        height=800,
        resizable=True,
        text_select=True,
        min_size=(800, 600),
    )

    def on_closing():
        pass

    window.events.closing += on_closing

    webview.start(
        debug=False,
        http_server=False,
    )


if __name__ == "__main__":
    main()