"""Pydantic v2 configuration models and YAML load/save."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


CONFIG_FILENAME = "config.yaml"
CONFIG_SEARCH_PATHS = [
    Path.cwd() / CONFIG_FILENAME,
    Path.home() / ".config" / "rtv" / CONFIG_FILENAME,
]


class BlockDuration(BaseModel):
    """Min/max duration for commercial blocks in seconds."""

    min: int = Field(default=30, ge=1)
    max: int = Field(default=120, ge=1)

    @model_validator(mode="after")
    def min_le_max(self) -> BlockDuration:
        if self.min > self.max:
            raise ValueError(f"block_duration.min ({self.min}) must be <= max ({self.max})")
        return self


class PlexConfig(BaseModel):
    """Plex server connection settings."""

    url: str = "http://localhost:32400"
    token: str = ""
    tv_libraries: list[str] = Field(default_factory=lambda: ["TV Shows"])

    @model_validator(mode="after")
    def validate_url(self) -> PlexConfig:
        if self.url and not self.url.startswith(("http://", "https://")):
            raise ValueError(f"Plex URL must start with http:// or https://, got: {self.url}")
        return self


class ShowConfig(BaseModel):
    """A show in the rotation with its current playback position."""

    name: str
    library: str = "TV Shows"
    current_season: int = Field(default=1, ge=1)
    current_episode: int = Field(default=1, ge=1)
    year: int | None = None


class CommercialCategory(BaseModel):
    """A category of commercials with search terms and selection weight."""

    name: str
    search_terms: list[str] = Field(default_factory=list)
    weight: float = Field(default=1.0, gt=0)


class CommercialConfig(BaseModel):
    """Commercial library settings."""

    library_name: str = "RealTV Commercials"
    library_path: str = "F:\\Commercials"
    block_duration: BlockDuration = Field(default_factory=BlockDuration)
    categories: list[CommercialCategory] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_category_names(self) -> CommercialConfig:
        names = [c.name.lower() for c in self.categories]
        if len(names) != len(set(names)):
            seen: set[str] = set()
            for n in names:
                if n in seen:
                    raise ValueError(f"Duplicate category name: '{n}'")
                seen.add(n)
        return self


class PlaylistConfig(BaseModel):
    """Playlist generation settings."""

    default_name: str = "Real TV"
    episodes_per_generation: int = Field(default=30, ge=1)
    commercial_frequency: int = Field(default=1, ge=1)
    commercial_min_gap: int = Field(default=50, ge=1)
    sort_by: str = "premiere_year"

    @model_validator(mode="after")
    def validate_sort_by(self) -> PlaylistConfig:
        valid = ("premiere_year", "premiere_year_desc", "alphabetical", "config_order")
        if self.sort_by not in valid:
            raise ValueError(f"sort_by must be one of {valid}, got: '{self.sort_by}'")
        return self


class HistoryEntry(BaseModel):
    """A record of a generated playlist."""

    timestamp: str
    playlist_name: str
    episode_count: int
    shows: list[str]
    runtime_secs: float = 0.0


class RTVConfig(BaseModel):
    """Root configuration model for plex-real-tv."""

    plex: PlexConfig = Field(default_factory=PlexConfig)
    shows: list[ShowConfig] = Field(default_factory=list)
    commercials: CommercialConfig = Field(default_factory=CommercialConfig)
    playlist: PlaylistConfig = Field(default_factory=PlaylistConfig)
    history: list[HistoryEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_show_names(self) -> RTVConfig:
        names = [s.name.lower() for s in self.shows]
        if len(names) != len(set(names)):
            seen: set[str] = set()
            for n in names:
                if n in seen:
                    raise ValueError(f"Duplicate show name: '{n}'")
                seen.add(n)
        return self


DEFAULT_SHOWS: list[dict[str, str | int]] = [
    {"name": "Seinfeld", "year": 1989},
    {"name": "Beavis and Butt-Head", "year": 1993},
    {"name": "The X-Files", "year": 1993},
    {"name": "Friends", "year": 1994},
    {"name": "King of the Hill", "year": 1997},
    {"name": "South Park", "year": 1997},
    {"name": "The King of Queens", "year": 1998},
    {"name": "That '70s Show", "year": 1998},
    {"name": "Two Guys and a Girl", "year": 1998},
    {"name": "SpongeBob SquarePants", "year": 1999},
    {"name": "Malcolm in the Middle", "year": 2000},
    {"name": "24", "year": 2001},
    {"name": "Scrubs", "year": 2001},
    {"name": "Trailer Park Boys", "year": 2001},
    {"name": "Arrested Development", "year": 2003},
    {"name": "Chappelle's Show", "year": 2003},
    {"name": "Reno 911!", "year": 2003},
    {"name": "Two and a Half Men", "year": 2003},
    {"name": "American Dad!", "year": 2005},
    {"name": "How I Met Your Mother", "year": 2005},
    {"name": "It's Always Sunny in Philadelphia", "year": 2005},
    {"name": "The Office (US)", "year": 2005},
    {"name": "Psych", "year": 2006},
    {"name": "Burn Notice", "year": 2007},
    {"name": "Parks and Recreation", "year": 2009},
    {"name": "Last Man Standing (2011)", "year": 2011},
    {"name": "The Blacklist", "year": 2013},
    {"name": "Brooklyn Nine-Nine", "year": 2013},
    {"name": "Schitt's Creek", "year": 2015},
    {"name": "The Good Place", "year": 2016},
]


def find_config_path() -> Path | None:
    """Find the config file in search paths. Returns None if not found."""
    for path in CONFIG_SEARCH_PATHS:
        if path.exists():
            return path
    return None


def load_config(path: Path | None = None) -> RTVConfig:
    """Load config from YAML file. Raises FileNotFoundError if not found."""
    if path is None:
        path = find_config_path()
    if path is None or not path.exists():
        raise FileNotFoundError(
            f"Config file not found. Run 'rtv init' to create one, "
            f"or place config.yaml in {CONFIG_SEARCH_PATHS[0]}"
        )
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        data = {}
    return RTVConfig.model_validate(data)


def save_config(config: RTVConfig, path: Path | None = None) -> Path:
    """Save config to YAML file. Returns the path written to."""
    if path is None:
        path = find_config_path()
    if path is None:
        path = CONFIG_SEARCH_PATHS[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump()
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return path


def get_config_or_exit() -> tuple[RTVConfig, Path]:
    """Load config or print error and exit. Returns (config, path)."""
    import click

    path = find_config_path()
    try:
        config = load_config(path)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except Exception as e:
        raise click.ClickException(f"Invalid config: {e}") from e
    assert path is not None
    return config, path
