"""Tests for the plex-real-tv Web UI (FastAPI routes)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient

from rtv.config import (
    RTVConfig,
    GlobalShow,
    PlaylistDefinition,
    PlaylistShow,
    BreakConfig,
    PlexConfig,
    save_config,
)
from rtv.web.app import create_app


@pytest.fixture
def tmp_config(tmp_path: Path):
    """Create a temp config file and patch config search paths to find it."""
    config = RTVConfig(
        plex=PlexConfig(url="http://localhost:32400", token="test-token"),
        shows=[
            GlobalShow(name="Seinfeld", library="TV Shows", year=1989, enabled=True),
            GlobalShow(name="Friends", library="TV Shows", year=1994, enabled=True),
            GlobalShow(name="The Office (US)", library="TV Shows", year=2005, enabled=False),
        ],
        playlists=[
            PlaylistDefinition(
                name="Real TV",
                shows=[
                    PlaylistShow(name="Seinfeld", current_season=1, current_episode=1),
                    PlaylistShow(name="Friends", current_season=1, current_episode=1),
                ],
                breaks=BreakConfig(enabled=True, style="single", frequency=1),
                episodes_per_generation=30,
                sort_by="premiere_year",
            ),
        ],
        default_playlist="Real TV",
    )
    config_path = tmp_path / "config.yaml"
    save_config(config, config_path)

    with patch("rtv.config.CONFIG_SEARCH_PATHS", [config_path]):
        yield config_path


@pytest.fixture
def client(tmp_config):
    """FastAPI test client with temp config."""
    app = create_app()
    return TestClient(app)


# ──────────────────────────────────────────────
# Setup routes
# ──────────────────────────────────────────────


class TestSetupRoutes:
    def test_setup_page_loads(self, client):
        resp = client.get("/setup/")
        assert resp.status_code == 200
        assert "Connection Setup" in resp.text

    def test_setup_page_shows_current_url(self, client):
        resp = client.get("/setup/")
        assert "http://localhost:32400" in resp.text

    def test_save_plex_settings(self, client, tmp_config):
        resp = client.post(
            "/setup/plex",
            data={
                "plex_url": "http://192.168.1.10:32400",
                "plex_token": "new-token-123",
                "tv_libraries": "TV Shows, Anime",
            },
        )
        assert resp.status_code == 200
        assert "Plex settings saved" in resp.text

        # Verify persisted
        with open(tmp_config) as f:
            saved = yaml.safe_load(f)
        assert saved["plex"]["url"] == "http://192.168.1.10:32400"
        assert saved["plex"]["token"] == "new-token-123"
        assert saved["plex"]["tv_libraries"] == ["TV Shows", "Anime"]

    def test_save_ssh_settings(self, client, tmp_config):
        resp = client.post(
            "/setup/ssh",
            data={
                "ssh_enabled": "true",
                "ssh_host": "192.168.1.10",
                "ssh_port": "22",
                "ssh_username": "admin",
                "ssh_key_path": "~/.ssh/id_rsa",
                "ssh_remote_path": "F:\\Commercials",
            },
        )
        assert resp.status_code == 200
        assert "SSH settings saved" in resp.text

        with open(tmp_config) as f:
            saved = yaml.safe_load(f)
        assert saved["ssh"]["enabled"] is True
        assert saved["ssh"]["host"] == "192.168.1.10"

    def test_discover_no_servers(self, client):
        with patch("rtv.plex_client.discover_servers", side_effect=ImportError):
            resp = client.post("/setup/discover")
            assert resp.status_code == 200
            assert "No Plex servers found" in resp.text


# ──────────────────────────────────────────────
# Shows routes
# ──────────────────────────────────────────────


class TestShowsRoutes:
    def test_shows_page_loads(self, client):
        resp = client.get("/shows/")
        assert resp.status_code == 200
        assert "Show Pool" in resp.text
        assert "Seinfeld" in resp.text
        assert "Friends" in resp.text

    def test_shows_page_count(self, client):
        resp = client.get("/shows/")
        assert "3 shows" in resp.text

    def test_add_show(self, client, tmp_config):
        resp = client.post(
            "/shows/add",
            data={"show_name": "Breaking Bad", "library": "TV Shows", "year": "2008"},
        )
        assert resp.status_code == 200
        assert "Added" in resp.text
        assert "Breaking Bad" in resp.text

        with open(tmp_config) as f:
            saved = yaml.safe_load(f)
        show_names = [s["name"] for s in saved["shows"]]
        assert "Breaking Bad" in show_names

    def test_add_duplicate_show(self, client):
        resp = client.post(
            "/shows/add",
            data={"show_name": "Seinfeld", "library": "TV Shows", "year": ""},
        )
        assert resp.status_code == 200
        assert "already in the pool" in resp.text

    def test_add_empty_show_name(self, client):
        resp = client.post(
            "/shows/add",
            data={"show_name": "  ", "library": "TV Shows", "year": ""},
        )
        assert resp.status_code == 200
        assert "required" in resp.text

    def test_remove_show(self, client, tmp_config):
        resp = client.post("/shows/remove/Seinfeld")
        assert resp.status_code == 200
        assert "Removed" in resp.text

        with open(tmp_config) as f:
            saved = yaml.safe_load(f)
        show_names = [s["name"] for s in saved["shows"]]
        assert "Seinfeld" not in show_names

    def test_remove_nonexistent_show(self, client):
        resp = client.post("/shows/remove/NobodyKnows")
        assert resp.status_code == 200
        assert "not found" in resp.text

    def test_toggle_show_on_to_off(self, client, tmp_config):
        resp = client.post("/shows/toggle/Seinfeld")
        assert resp.status_code == 200
        assert "OFF" in resp.text

    def test_toggle_show_off_to_on(self, client, tmp_config):
        # The Office is disabled by default in our fixture
        resp = client.post("/shows/toggle/The Office (US)")
        assert resp.status_code == 200
        assert "ON" in resp.text

    def test_toggle_nonexistent_show(self, client):
        resp = client.post("/shows/toggle/Nope")
        assert resp.status_code == 404


# ──────────────────────────────────────────────
# Playlists routes
# ──────────────────────────────────────────────


class TestPlaylistsRoutes:
    def test_playlists_page_loads(self, client):
        resp = client.get("/playlists/")
        assert resp.status_code == 200
        assert "Playlists" in resp.text
        assert "Real TV" in resp.text

    def test_create_playlist(self, client, tmp_config):
        resp = client.post(
            "/playlists/create",
            data={
                "name": "90s Night",
                "episodes_per_generation": "20",
                "break_style": "block",
                "frequency": "2",
                "sort_by": "premiere_year",
            },
        )
        assert resp.status_code == 200
        assert "Created playlist" in resp.text
        assert "90s Night" in resp.text

        with open(tmp_config) as f:
            saved = yaml.safe_load(f)
        pl_names = [p["name"] for p in saved["playlists"]]
        assert "90s Night" in pl_names

    def test_create_duplicate_playlist(self, client):
        resp = client.post(
            "/playlists/create",
            data={
                "name": "Real TV",
                "episodes_per_generation": "30",
                "break_style": "single",
                "frequency": "1",
                "sort_by": "premiere_year",
            },
        )
        assert resp.status_code == 200
        assert "already exists" in resp.text

    def test_create_playlist_empty_name(self, client):
        resp = client.post(
            "/playlists/create",
            data={
                "name": "  ",
                "episodes_per_generation": "30",
                "break_style": "single",
                "frequency": "1",
                "sort_by": "premiere_year",
            },
        )
        assert resp.status_code == 200
        assert "required" in resp.text

    def test_playlist_detail(self, client):
        resp = client.get("/playlists/Real TV")
        assert resp.status_code == 200
        assert "Real TV" in resp.text
        assert "Seinfeld" in resp.text

    def test_playlist_detail_not_found(self, client):
        resp = client.get("/playlists/NothingHere")
        assert resp.status_code == 200
        assert "not found" in resp.text

    def test_update_playlist_settings(self, client, tmp_config):
        resp = client.post(
            "/playlists/Real TV/update",
            data={
                "episodes_per_generation": "50",
                "break_style": "block",
                "frequency": "3",
                "min_gap": "25",
                "block_min": "60",
                "block_max": "180",
                "sort_by": "alphabetical",
            },
        )
        assert resp.status_code == 200
        assert "settings updated" in resp.text

        with open(tmp_config) as f:
            saved = yaml.safe_load(f)
        pl = saved["playlists"][0]
        assert pl["episodes_per_generation"] == 50
        assert pl["breaks"]["style"] == "block"
        assert pl["sort_by"] == "alphabetical"

    def test_add_show_to_playlist(self, client, tmp_config):
        resp = client.post(
            "/playlists/Real TV/add-show",
            data={"show_name": "The Office (US)"},
        )
        assert resp.status_code == 200
        assert "Added" in resp.text

        with open(tmp_config) as f:
            saved = yaml.safe_load(f)
        pl_shows = [s["name"] for s in saved["playlists"][0]["shows"]]
        assert "The Office (US)" in pl_shows

    def test_add_nonexistent_show_to_playlist(self, client):
        resp = client.post(
            "/playlists/Real TV/add-show",
            data={"show_name": "Nobody"},
        )
        assert resp.status_code == 200
        assert "not found" in resp.text

    def test_add_duplicate_show_to_playlist(self, client):
        resp = client.post(
            "/playlists/Real TV/add-show",
            data={"show_name": "Seinfeld"},
        )
        assert resp.status_code == 200
        assert "already in this playlist" in resp.text

    def test_remove_show_from_playlist(self, client, tmp_config):
        resp = client.post("/playlists/Real TV/remove-show/Seinfeld")
        assert resp.status_code == 200
        assert "Removed" in resp.text

        with open(tmp_config) as f:
            saved = yaml.safe_load(f)
        pl_shows = [s["name"] for s in saved["playlists"][0]["shows"]]
        assert "Seinfeld" not in pl_shows

    def test_remove_nonexistent_show_from_playlist(self, client):
        resp = client.post("/playlists/Real TV/remove-show/Nobody")
        assert resp.status_code == 200
        assert "was not in this playlist" in resp.text

    def test_delete_playlist(self, client, tmp_config):
        resp = client.post(
            "/playlists/Real TV/delete", follow_redirects=False,
        )
        assert resp.status_code == 303

        with open(tmp_config) as f:
            saved = yaml.safe_load(f)
        assert len(saved["playlists"]) == 0

    def test_set_default_playlist(self, client, tmp_config):
        # Create a second playlist first
        client.post(
            "/playlists/create",
            data={
                "name": "Late Night",
                "episodes_per_generation": "20",
                "break_style": "single",
                "frequency": "1",
                "sort_by": "premiere_year",
            },
        )
        resp = client.post(
            "/playlists/Late Night/set-default", follow_redirects=False,
        )
        assert resp.status_code == 303

        with open(tmp_config) as f:
            saved = yaml.safe_load(f)
        assert saved["default_playlist"] == "Late Night"


# ──────────────────────────────────────────────
# Generate routes
# ──────────────────────────────────────────────


class TestGenerateRoutes:
    def test_generate_page_loads(self, client):
        resp = client.get("/generate/")
        assert resp.status_code == 200
        assert "Generate" in resp.text
        assert "Real TV" in resp.text

    def test_generate_stream_missing_playlist(self, client):
        """SSE stream emits error for unknown playlist."""
        resp = client.get("/generate/stream?playlist_name=Ghost")
        assert resp.status_code == 200
        assert "not found" in resp.text

    def test_generate_stream_empty_playlist(self, client, tmp_config):
        """SSE stream emits error for playlist with no shows."""
        # Create a playlist with no shows
        from rtv.config import load_config
        with patch("rtv.config.CONFIG_SEARCH_PATHS", [tmp_config]):
            config = load_config()
            config.playlists.append(
                PlaylistDefinition(name="Empty", shows=[], episodes_per_generation=10)
            )
            save_config(config, tmp_config)

        resp = client.get("/generate/stream?playlist_name=Empty")
        assert resp.status_code == 200
        assert "no shows" in resp.text


# ──────────────────────────────────────────────
# No config edge case
# ──────────────────────────────────────────────


class TestNoConfig:
    def test_pages_load_without_config(self):
        """All pages should load gracefully even with no config file."""
        with patch("rtv.config.CONFIG_SEARCH_PATHS", [Path("/nonexistent/config.yaml")]):
            app = create_app()
            cl = TestClient(app)

            for path in ["/setup/", "/shows/", "/playlists/", "/generate/"]:
                resp = cl.get(path)
                assert resp.status_code == 200, f"{path} failed with no config"
