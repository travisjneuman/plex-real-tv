"""Batch download retro commercials from YouTube across decades.

Downloads individual short commercial clips (30s-120s) organized by decade.
Target: ~50 total clips across 80s, 90s, 2000s, 2010s.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yt_dlp

# Search queries per decade — targeting individual classic commercials, not compilations
DECADE_QUERIES: dict[str, list[str]] = {
    "80s": [
        "1980s classic TV commercial",
        "80s retro commercial ad",
        "1985 TV advertisement original",
        "80s cereal commercial",
        "1980s fast food commercial",
    ],
    "90s": [
        "1990s classic TV commercial",
        "90s retro commercial ad",
        "1995 TV advertisement original",
        "90s toy commercial",
        "1990s snack commercial",
    ],
    "2000s": [
        "2000s classic TV commercial",
        "early 2000s commercial ad",
        "2005 TV advertisement",
        "2000s funny commercial",
    ],
    "2010s": [
        "2010s classic TV commercial",
        "2015 TV advertisement",
        "2010s Super Bowl commercial",
    ],
}

# Target per decade
TARGETS = {"80s": 13, "90s": 13, "2000s": 12, "2010s": 12}

# Duration filter: 15s-120s (actual commercials, not compilations)
MIN_DURATION = 15
MAX_DURATION = 120


def search_and_download(decade: str, queries: list[str], target: int, output_base: Path) -> int:
    """Search YouTube and download individual commercial clips for a decade."""
    output_dir = output_base / decade
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    seen_ids: set[str] = set()

    for query in queries:
        if downloaded >= target:
            break

        print(f"\n[{decade}] Searching: {query}")

        # Search phase
        search_opts: dict[str, object] = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
        }
        search_url = f"ytsearch20:{query}"

        try:
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                info = ydl.extract_info(search_url, download=False)
        except Exception as e:
            print(f"  Search failed: {e}")
            continue

        if not info or not info.get("entries"):
            print("  No results")
            continue

        # Filter by duration and download
        for entry in info["entries"]:
            if downloaded >= target:
                break
            if entry is None:
                continue

            vid_id = entry.get("id", "")
            if vid_id in seen_ids:
                continue
            seen_ids.add(vid_id)

            duration = entry.get("duration") or 0
            if duration < MIN_DURATION or duration > MAX_DURATION:
                continue

            title = entry.get("title", "Unknown")
            url = entry.get("url") or entry.get("webpage_url") or f"https://www.youtube.com/watch?v={vid_id}"

            print(f"  [{downloaded + 1}/{target}] Downloading: {title} ({duration}s)")

            outtmpl = str(output_dir / "%(title).150s - %(channel).30s (%(upload_date>%Y)s).%(ext)s")
            dl_opts: dict[str, object] = {
                "format": "best[height<=720][ext=mp4]/best[height<=720]/best",
                "outtmpl": outtmpl,
                "merge_output_format": "mp4",
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 30,
            }

            try:
                with yt_dlp.YoutubeDL(dl_opts) as ydl:
                    ydl.download([url])
                downloaded += 1
                print(f"    OK")
            except Exception as e:
                print(f"    FAILED: {e}")

    print(f"\n[{decade}] Downloaded {downloaded}/{target} clips")
    return downloaded


def main() -> None:
    output_base = Path("/tmp/rtv-commercials")
    output_base.mkdir(parents=True, exist_ok=True)

    total = 0
    for decade, queries in DECADE_QUERIES.items():
        target = TARGETS[decade]
        count = search_and_download(decade, queries, target, output_base)
        total += count

    print(f"\n{'='*60}")
    print(f"Total downloaded: {total}/50")

    # Show file counts per decade
    for decade in DECADE_QUERIES:
        d = output_base / decade
        mp4s = list(d.glob("*.mp4")) if d.exists() else []
        print(f"  {decade}: {len(mp4s)} files")


if __name__ == "__main__":
    main()
