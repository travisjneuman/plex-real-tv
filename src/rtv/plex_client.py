"""Plex server interaction via python-plexapi."""

from __future__ import annotations

import time

import requests
import urllib3
from plexapi.server import PlexServer
from plexapi.playlist import Playlist
from plexapi.video import Show, Episode, Video
from plexapi.library import LibrarySection
from plexapi.exceptions import NotFound

from rtv.config import PlexConfig


CONNECT_TIMEOUT = 5
MAX_RETRIES = 2


def _make_session() -> requests.Session:
    """Create a requests session that accepts self-signed HTTPS certs."""
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = requests.Session()
    session.verify = False
    return session


def connect(config: PlexConfig) -> PlexServer:
    """Connect to the Plex server with retry logic.

    Retries once after a 5-second timeout, then raises with troubleshooting info.
    Uses a session with SSL verification disabled for self-signed certs.
    """
    session = _make_session() if config.url.startswith("https://") else None
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return PlexServer(config.url, config.token, session=session, timeout=CONNECT_TIMEOUT)
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)

    raise ConnectionError(
        f"Could not connect to Plex at {config.url}\n"
        f"  Error: {last_error}\n"
        f"  Troubleshooting:\n"
        f"    1. Is Plex Media Server running?\n"
        f"    2. Is the URL correct? (default: http://localhost:32400)\n"
        f"    3. Is the token valid? Find yours at:\n"
        f"       https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/\n"
        f"    4. Is a firewall blocking the connection?"
    ) from last_error


def get_library_section(server: PlexServer, library_name: str) -> LibrarySection:
    """Get a library section by name. Raises NotFound if missing."""
    return server.library.section(library_name)


def get_all_shows(server: PlexServer, library_name: str) -> list[Show]:
    """Get all shows from a library section."""
    section = get_library_section(server, library_name)
    return section.all()


def get_show(server: PlexServer, name: str, library_name: str) -> Show:
    """Get a show by exact name from a library. Raises NotFound if missing."""
    section = get_library_section(server, library_name)
    return section.get(name)


def get_episode(
    show: Show, season_num: int, episode_num: int
) -> Episode | None:
    """Get a specific episode by season and episode number.

    Returns None if the episode doesn't exist (end of season or show).
    """
    try:
        season = show.season(season=season_num)
    except NotFound:
        return None
    for ep in season.episodes():
        if ep.index == episode_num:
            return ep
    return None


def get_next_season_number(show: Show, current_season: int) -> int | None:
    """Get the next season number after current_season. Returns None if no more seasons."""
    season_numbers = sorted(s.index for s in show.seasons() if s.index is not None and s.index > 0)
    for sn in season_numbers:
        if sn > current_season:
            return sn
    return None


def get_commercials(server: PlexServer, library_name: str) -> list[Video]:
    """Get all items from the commercial library."""
    try:
        section = get_library_section(server, library_name)
    except NotFound:
        return []
    return section.all()


def rescan_library(server: PlexServer, library_name: str, timeout: int = 120) -> int:
    """Trigger a library scan and wait for it to complete.

    Returns the total number of items in the library after scanning.
    Raises TimeoutError if the scan doesn't finish within ``timeout`` seconds.
    """
    section = get_library_section(server, library_name)
    section.update()

    elapsed = 0
    while elapsed < timeout:
        time.sleep(2)
        elapsed += 2
        section.reload()
        if not section.refreshing:
            return section.totalSize

    raise TimeoutError(
        f"Library '{library_name}' scan did not complete within {timeout}s"
    )


def discover_servers() -> list[dict[str, str | int]]:
    """Find Plex servers on local network using GDM protocol.

    Returns list of dicts with: name, host, port.
    """
    try:
        from plexapi.gdm import GDM
        gdm = GDM()
        gdm.scan()
        results = []
        for entry in gdm.entries:
            results.append({
                "name": entry.get("Name", "Unknown"),
                "host": entry.get("Host", ""),
                "port": int(entry.get("Port", 32400)),
            })
        return results
    except Exception:
        return []


PLAYLIST_CHUNK_SIZE = 200


def create_or_update_playlist(
    server: PlexServer, name: str, items: list[Video | Episode]
) -> Playlist:
    """Create a new playlist or replace an existing one with the given items.

    For large playlists, items are added in chunks to avoid URI length limits.
    """
    try:
        existing = server.playlist(name)
        existing.delete()
    except NotFound:
        pass

    if len(items) <= PLAYLIST_CHUNK_SIZE:
        return Playlist.create(server, title=name, items=items)

    # Create with first chunk, then append remaining chunks
    playlist = Playlist.create(server, title=name, items=items[:PLAYLIST_CHUNK_SIZE])
    for i in range(PLAYLIST_CHUNK_SIZE, len(items), PLAYLIST_CHUNK_SIZE):
        chunk = items[i : i + PLAYLIST_CHUNK_SIZE]
        playlist.addItems(chunk)
    return playlist
