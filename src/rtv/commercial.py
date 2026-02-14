"""YouTube search, download, and commercial inventory management via yt-dlp."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

import yt_dlp

from rtv.config import CommercialConfig, CommercialCategory


LAST_SEARCH_FILE = Path(tempfile.gettempdir()) / "rtv_last_search.json"


def _sanitize_filename(title: str) -> str:
    """Sanitize a string for use as a filename."""
    sanitized = re.sub(r'[<>:"/\\|?*]', "", title)
    sanitized = sanitized.strip(". ")
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    return sanitized or "untitled"


def search_youtube(query: str, max_results: int = 10) -> list[dict[str, str | int | float]]:
    """Search YouTube for videos matching the query.

    Returns a list of dicts with keys: title, duration, channel, url, id.
    """
    ydl_opts: dict[str, object] = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
    }
    search_url = f"ytsearch{max_results}:{query}"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search_url, download=False)

    if info is None:
        return []

    entries = info.get("entries", [])
    results: list[dict[str, str | int | float]] = []
    for entry in entries:
        if entry is None:
            continue
        results.append({
            "title": entry.get("title", "Unknown"),
            "duration": entry.get("duration", 0) or 0,
            "channel": entry.get("channel", entry.get("uploader", "Unknown")),
            "url": entry.get("url", entry.get("webpage_url", "")),
            "id": entry.get("id", ""),
        })

    return results


def save_search_results(results: list[dict[str, str | int | float]]) -> None:
    """Save search results to temp file for --from-search usage."""
    with open(LAST_SEARCH_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def load_search_results() -> list[dict[str, str | int | float]]:
    """Load last search results from temp file."""
    if not LAST_SEARCH_FILE.exists():
        return []
    with open(LAST_SEARCH_FILE, encoding="utf-8") as f:
        return json.load(f)


class DownloadError(Exception):
    """Raised when a video download fails with a specific reason."""

    def __init__(self, url: str, reason: str) -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"Failed to download {url}: {reason}")


def download_video(url: str, output_dir: Path) -> Path:
    """Download a YouTube video as MP4 to the given directory.

    Returns the path to the downloaded file.
    Raises DownloadError with specific reason on failure.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(output_dir / "%(title).150s - %(channel).30s (%(upload_date>%Y)s).%(ext)s")

    ydl_opts: dict[str, object] = {
        "format": "best[height<=720][ext=mp4]/best[height<=720]/best",
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "quiet": False,
        "no_warnings": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()
        if "sign in" in error_msg or "age" in error_msg:
            raise DownloadError(url, "Age-restricted video — requires sign-in") from e
        if "geo" in error_msg or "not available in your country" in error_msg:
            raise DownloadError(url, "Geo-blocked — not available in your region") from e
        if "private" in error_msg or "removed" in error_msg or "unavailable" in error_msg:
            raise DownloadError(url, "Video is private, removed, or unavailable") from e
        if "copyright" in error_msg:
            raise DownloadError(url, "Blocked due to copyright claim") from e
        raise DownloadError(url, str(e)) from e
    except Exception as e:
        raise DownloadError(url, str(e)) from e

    if info is None:
        raise DownloadError(url, "No video info returned")

    filename = ydl.prepare_filename(info)
    downloaded = Path(filename)
    if not downloaded.suffix == ".mp4":
        downloaded = downloaded.with_suffix(".mp4")
    return downloaded


def parse_selection(selection: str, max_index: int) -> list[int]:
    """Parse a user selection string like '1,3,5-7' or 'all' into a list of 0-based indices.

    Accepts 1-based input from the user and returns 0-based indices.
    """
    selection = selection.strip().lower()
    if selection in ("all", "a"):
        return list(range(max_index))
    if selection in ("none", "n", ""):
        return []

    indices: list[int] = []
    for part in selection.split(","):
        part = part.strip()
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start = int(start_str.strip())
            end = int(end_str.strip())
            for i in range(start, end + 1):
                if 1 <= i <= max_index:
                    indices.append(i - 1)
        else:
            val = int(part)
            if 1 <= val <= max_index:
                indices.append(val - 1)

    return sorted(set(indices))


def get_category_search_query(
    category_name: str, config: CommercialConfig
) -> str:
    """Get the search query for a category. Uses search_terms if category exists, otherwise the name."""
    for cat in config.categories:
        if cat.name.lower() == category_name.lower():
            if cat.search_terms:
                return " ".join(cat.search_terms[:1])
            return cat.name
    return category_name


def scan_commercial_inventory(
    library_path: str, categories: list[CommercialCategory]
) -> list[dict[str, str | int | float]]:
    """Scan the commercial library path and return inventory by category.

    Returns list of dicts with: name, count, duration (total seconds).
    Duration is estimated from file metadata if available, otherwise 0.
    """
    base = Path(library_path)
    if not base.exists():
        return []

    inventory: list[dict[str, str | int | float]] = []

    subdirs = [d for d in base.iterdir() if d.is_dir()]

    for subdir in sorted(subdirs):
        mp4_files = list(subdir.glob("*.mp4"))
        if not mp4_files:
            continue

        total_duration = 0.0
        for f in mp4_files:
            dur = _get_video_duration(f)
            total_duration += dur

        inventory.append({
            "name": subdir.name,
            "count": len(mp4_files),
            "duration": total_duration,
        })

    # Also check for mp4 files directly in the base directory (uncategorized)
    root_mp4s = list(base.glob("*.mp4"))
    if root_mp4s:
        total_duration = sum(_get_video_duration(f) for f in root_mp4s)
        inventory.insert(0, {
            "name": "(uncategorized)",
            "count": len(root_mp4s),
            "duration": total_duration,
        })

    return inventory


def _get_video_duration(filepath: Path) -> float:
    """Get video duration in seconds using yt-dlp's probe. Returns 0 on failure."""
    try:
        ydl_opts: dict[str, object] = {
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(str(filepath), download=False)
            if info and info.get("duration"):
                return float(info["duration"])
    except Exception:
        pass
    return 0.0
