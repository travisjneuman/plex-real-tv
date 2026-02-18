#!/usr/bin/env python3
"""Generate a demo config.yaml for taking screenshots.

Creates a realistic-looking config with sample TV shows (no real Plex
connection needed). The Web UI renders all pages from config data, so
you can browse Setup, Shows, Playlists, and Generate pages freely.

Usage:
    python scripts/demo_config.py
    rtv web --port 9090
    # Take screenshots, then delete the demo config:
    rm config.yaml
"""

import yaml
from pathlib import Path

DEMO_CONFIG = {
    "config_version": 2,
    "plex": {
        "url": "http://192.168.1.100:32400",
        "token": "demo-token-not-real",
        "tv_libraries": ["TV Shows", "Anime"],
        "tv_show_paths": [
            "D:\\TV Shows",
            "E:\\TV Shows",
        ],
    },
    "shows": [
        {"name": "Seinfeld", "library": "TV Shows", "year": 1989, "enabled": True},
        {"name": "The Office (US)", "library": "TV Shows", "year": 2005, "enabled": True},
        {"name": "Friends", "library": "TV Shows", "year": 1994, "enabled": True},
        {"name": "Breaking Bad", "library": "TV Shows", "year": 2008, "enabled": True},
        {"name": "The Simpsons", "library": "TV Shows", "year": 1989, "enabled": True},
        {"name": "Cheers", "library": "TV Shows", "year": 1982, "enabled": True},
        {"name": "Frasier", "library": "TV Shows", "year": 1993, "enabled": False},
        {"name": "Dragon Ball Z", "library": "Anime", "year": 1989, "enabled": True},
        {"name": "Cowboy Bebop", "library": "Anime", "year": 1998, "enabled": True},
        {"name": "The X-Files", "library": "TV Shows", "year": 1993, "enabled": True},
        {"name": "Twin Peaks", "library": "TV Shows", "year": 1990, "enabled": True},
        {"name": "Star Trek: TNG", "library": "TV Shows", "year": 1987, "enabled": True},
    ],
    "playlists": [
        {
            "name": "Real TV",
            "shows": [
                {"name": "Seinfeld", "current_season": 4, "current_episode": 11},
                {"name": "The Office (US)", "current_season": 2, "current_episode": 6},
                {"name": "Friends", "current_season": 3, "current_episode": 14},
                {"name": "The Simpsons", "current_season": 7, "current_episode": 1},
                {"name": "Cheers", "current_season": 5, "current_episode": 22},
                {"name": "The X-Files", "current_season": 1, "current_episode": 8},
            ],
            "breaks": {
                "enabled": True,
                "style": "single",
                "frequency": 1,
                "min_gap": 50,
                "block_duration": {"min": 30, "max": 120},
            },
            "episodes_per_generation": 30,
            "sort_by": "premiere_year",
        },
        {
            "name": "90s Night",
            "shows": [
                {"name": "Seinfeld", "current_season": 1, "current_episode": 1},
                {"name": "Friends", "current_season": 1, "current_episode": 1},
                {"name": "Frasier", "current_season": 1, "current_episode": 1},
                {"name": "The X-Files", "current_season": 1, "current_episode": 1},
            ],
            "breaks": {
                "enabled": True,
                "style": "block",
                "frequency": 1,
                "min_gap": 30,
                "block_duration": {"min": 60, "max": 180},
            },
            "episodes_per_generation": 20,
            "sort_by": "premiere_year",
        },
        {
            "name": "Anime Block",
            "shows": [
                {"name": "Dragon Ball Z", "current_season": 1, "current_episode": 1},
                {"name": "Cowboy Bebop", "current_season": 1, "current_episode": 1},
            ],
            "breaks": {
                "enabled": False,
                "style": "disabled",
                "frequency": 1,
                "min_gap": 50,
                "block_duration": {"min": 30, "max": 120},
            },
            "episodes_per_generation": 10,
            "sort_by": "alphabetical",
        },
    ],
    "default_playlist": "Real TV",
    "ssh": {
        "enabled": False,
        "host": "",
        "port": 22,
        "username": "",
        "key_path": "",
        "remote_commercial_path": "",
    },
    "commercials": {
        "library_name": "RealTV Commercials",
        "library_path": "D:\\Media\\Commercials",
        "block_duration": {"min": 120, "max": 300},
        "categories": [
            {"name": "80s", "search_terms": ["80s commercial", "1980s ad"], "weight": 1.0},
            {"name": "90s", "search_terms": ["90s commercial", "1990s ad"], "weight": 1.0},
            {"name": "PSAs", "search_terms": ["vintage PSA"], "weight": 0.5},
        ],
    },
    "history": [
        {
            "playlist_name": "Real TV",
            "episode_count": 30,
            "shows": ["Seinfeld", "The Office (US)", "Friends", "The Simpsons", "Cheers", "The X-Files"],
            "runtime_secs": 45720.0,
            "timestamp": "2026-02-15T20:30:00",
        },
        {
            "playlist_name": "Real TV",
            "episode_count": 30,
            "shows": ["Seinfeld", "The Office (US)", "Friends", "The Simpsons", "Cheers", "The X-Files"],
            "runtime_secs": 44850.0,
            "timestamp": "2026-02-10T19:15:00",
        },
    ],
}


def main() -> None:
    config_path = Path("config.yaml")
    if config_path.exists():
        print(f"config.yaml already exists! Back it up or delete it first.")
        return

    with open(config_path, "w") as f:
        yaml.dump(DEMO_CONFIG, f, default_flow_style=False, sort_keys=False)

    print(f"Demo config written to {config_path}")
    print()
    print("Now launch the Web UI:")
    print("  rtv web --port 9090")
    print()
    print("Screenshots to capture:")
    print("  1. http://localhost:9090/           — Landing page")
    print("  2. http://localhost:9090/shows      — Show pool table")
    print("  3. http://localhost:9090/playlists/Real%20TV — Playlist detail")
    print("  4. http://localhost:9090/generate   — Generate form")
    print()
    print("Save screenshots to: assets/screenshots/")
    print("When done, delete the demo config: rm config.yaml")


if __name__ == "__main__":
    main()
