# plex-real-tv

Generate [Plex](https://www.plex.tv/) playlists that simulate real TV — round-robin episodes from multiple shows with commercial breaks between them.

Point it at your Plex server, tell it which shows to include, build up a library of commercials over time, and run `rtv generate`. You get a playlist that feels like flipping on a cable channel: an episode of Seinfeld, a commercial, an episode of The Office, another commercial, repeat. One random commercial per break with a configurable no-repeat window so you don't see the same one twice.

## v2 — Multi-Playlist + GUI

v2 adds **multiple named playlists**, a **browser-based Web UI**, and a **terminal TUI** — all sharing the same core engine. The CLI remains the canonical interface.

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Web UI    │  │ Terminal TUI│  │     CLI     │
│ FastAPI +   │  │  Textual    │  │   Click     │
│ htmx/Jinja2 │  │             │  │             │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
              ┌─────────┴─────────┐
              │    Core Layer     │
              │  config.py        │
              │  playlist.py      │
              │  plex_client.py   │
              │  commercial.py    │
              │  matcher.py       │
              └───────────────────┘
```

## Quick Start

```bash
# 1. Install
pip install -e .

# 2. Create config
rtv init

# 3. Add shows to the rotation
rtv add-show "Seinfeld"
rtv add-show "The Office"

# 4. Search for and download some commercials (you build your own library)
rtv find-commercials -c "80s"

# 5. Generate your playlist
rtv generate
```

Open Plex, find the "Real TV" playlist, and hit play.

### Launch the Web UI

```bash
rtv web
# Opens http://localhost:8080 in your browser
```

### Launch the Terminal TUI

```bash
rtv tui
# Full-screen terminal dashboard (works over SSH)
```

## Prerequisites

- **[Python 3.11+](https://www.python.org/)**
- **[Plex Media Server](https://www.plex.tv/)** running and accessible over the network
- **Plex Token** — you need your X-Plex-Token to authenticate. Find it by following [Plex's guide](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).

## Installation

```bash
# Clone or copy the project
git clone https://github.com/travisjneuman/plex-real-tv.git
cd plex-real-tv

# Install (editable mode recommended for development)
pip install -e .

# Verify
rtv --version
rtv --help
```

### Dependencies

Installed automatically:

**Core:**
- [`click`](https://click.palletsprojects.com/) — CLI framework
- [`PlexAPI`](https://github.com/pkkid/python-plexapi) — Plex server communication
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) — Video search and download (used for finding commercials)
- [`pyyaml`](https://github.com/yaml/pyyaml) — Config file parsing
- [`pydantic`](https://docs.pydantic.dev/) — Config validation
- [`rapidfuzz`](https://github.com/rapidfuzz/RapidFuzz) — Fuzzy show name matching
- [`rich`](https://github.com/Textualize/rich) — Terminal output formatting

**Web UI:**
- [`fastapi`](https://fastapi.tiangolo.com/) — Web framework
- [`uvicorn`](https://www.uvicorn.org/) — ASGI server
- [`jinja2`](https://jinja.palletsprojects.com/) — HTML templates
- [`sse-starlette`](https://github.com/sysid/sse-starlette) — Server-sent events for live progress

**Terminal TUI:**
- [`textual`](https://textual.textualize.io/) — Terminal UI framework

**Remote server:**
- [`paramiko`](https://www.paramiko.org/) — SSH/SFTP for remote Plex servers

## Configuration

### Interactive Setup

```bash
rtv init
```

Prompts you for Plex URL, token, library names, and commercial storage path. Creates `config.yaml` in the current directory.

### Config File Reference (v2)

`config.yaml` (or `~/.config/rtv/config.yaml`):

```yaml
config_version: 2

plex:
  url: "http://192.168.1.100:32400"
  token: "your-plex-token-here"
  tv_libraries:
    - "TV Shows"
  tv_show_paths:
    - "D:\\TV Shows"
    - "E:\\TV Shows"
    - "F:\\TV Shows"
    - "K:\\TV Shows"

# Global show pool — add shows here, assign them to playlists
shows:
  - name: "Seinfeld"
    library: "TV Shows"
    year: 1989
    enabled: true
  - name: "The Office (US)"
    library: "TV Shows"
    year: 2005
    enabled: true

# Named playlists with independent settings and positions
playlists:
  - name: "Real TV"
    shows:
      - { name: "Seinfeld", current_season: 3, current_episode: 7 }
      - { name: "The Office (US)", current_season: 1, current_episode: 1 }
    breaks:
      enabled: true
      style: single       # single | block | disabled
      frequency: 1         # insert break every N episodes
      min_gap: 50           # no-repeat window for commercials
      block_duration: { min: 30, max: 120 }
    episodes_per_generation: 30
    sort_by: premiere_year  # premiere_year | premiere_year_desc | alphabetical | config_order

default_playlist: "Real TV"

# Optional SSH for remote Plex servers
ssh:
  enabled: false
  host: ""
  port: 22
  username: ""
  key_path: ""
  remote_commercial_path: ""

commercials:
  library_name: "RealTV Commercials"
  library_path: "D:\\Media\\Commercials"
  block_duration: { min: 120, max: 300 }
  categories: []

history: []
```

### Config Search Paths

RTV looks for `config.yaml` in this order:
1. Current working directory (`./config.yaml`)
2. Home config directory (`~/.config/rtv/config.yaml`)

### Config Migration (v1 → v2)

If you have an existing v1 config, RTV auto-migrates on first load:
- Backs up your config to `config.yaml.v1.bak`
- Converts shows to the new global pool format
- Creates a single "Real TV" playlist with your existing positions
- Sets `config_version: 2`

## Usage

### Web UI

```bash
rtv web                    # Launch on default port 8080
rtv web --port 3000        # Custom port
rtv web --no-browser       # Don't auto-open browser
```

The Web UI provides:
- **Setup** — Configure Plex connection, auto-discover servers on your network, SSH settings for remote servers
- **Shows** — Browse your global show pool, toggle enabled/disabled, scan Plex for new shows
- **Playlists** — Create/edit/delete playlists, add/remove shows, configure break settings
- **Generate** — Generate playlists with a live SSE progress bar and TV static animation

Accessible from any device on your network at `http://<your-ip>:8080`.

### Terminal TUI

```bash
rtv tui
```

Full-screen terminal interface with keyboard navigation:
- **`d`** — Dashboard (Plex status, stats, last generation)
- **`s`** — Shows (DataTable with search/filter, toggle enabled)
- **`p`** — Playlists (create, edit, generate, set default)
- **`q`** — Quit

Works over SSH for headless servers.

### Show Management

```bash
# Add a show — fuzzy matches against your Plex library
rtv add-show "the office"

# Add from a specific library
rtv add-show "Dragon Ball Z" --library "Anime"

# See your show pool with enabled/disabled status and playlist membership
rtv list-shows

# Remove a show from the pool
rtv remove-show "Seinfeld"

# Toggle enabled/disabled without removing
rtv enable-show "The Office (US)"
rtv disable-show "Friends"
```

### Playlist Management

```bash
# Create a new playlist
rtv create-playlist "Late Night"

# Add shows to a playlist (starts at S01E01)
rtv playlist-add "Late Night" "Seinfeld"
rtv playlist-add "Late Night" "Friends"

# Remove a show from a playlist
rtv playlist-remove "Late Night" "Friends"

# List all playlists
rtv list-playlists

# Delete a playlist
rtv delete-playlist "Late Night"

# Change the default playlist
rtv set-default "90s Night"
```

### Playlist Generation

```bash
# Generate default playlist
rtv generate

# Generate a specific playlist
rtv generate "90s Night"

# Custom episode count
rtv generate -e 50

# Start all shows from S01E01
rtv generate --from-start

# Rescan Plex commercial library before generating
rtv generate --from-start --rescan

# Auto-export playlist to CSV after generating
rtv generate --from-start --export
```

### Commercial Management

RTV includes optional [yt-dlp](https://github.com/yt-dlp/yt-dlp) integration to help you search for and download commercials to build your own library. You're responsible for ensuring your use complies with applicable terms of service and copyright law. You can also add commercial clips from any source — just drop MP4 files into your commercial folder.

```bash
# Search for commercials (uses yt-dlp)
rtv find-commercials -c "80s"

# Download a specific video by URL
rtv download-commercials "https://youtube.com/watch?v=..." -c "90s"

# Download from your last search results
rtv download-commercials --from-search -c "80s"

# Add a named category with custom search terms
rtv add-category "PSAs" -s "vintage PSA" -s "public service announcement" -w 0.5

# See what commercials you have
rtv list-commercials
```

### Diagnostics

```bash
# Check your entire setup
rtv doctor

# Preview what a playlist would look like (no changes made)
rtv preview -e 10

# See your last 5 generated playlists
rtv history

# Test Plex connection and see inventory
rtv status
```

### Playlist Export

```bash
# Export current Plex playlist to CSV (default)
rtv export

# Export as JSON
rtv export --format json

# Custom output file and playlist name
rtv export -o my_playlist.csv -n "90s Night"
```

## Commercial Library Setup in Plex

Commercials need their own Plex library so they can be included in playlists alongside TV episodes.

### Step 1: Create the Commercial Folder

Create a folder on your server to store commercial MP4s:

```
D:\Media\Commercials\
├── 80s\
│   ├── Coca Cola 1985.mp4
│   ├── Nintendo NES Commercial.mp4
│   └── ...
├── 90s\
│   ├── Got Milk 1993.mp4
│   └── ...
├── PSAs\
│   └── This Is Your Brain On Drugs.mp4
└── toys\
    └── Easy Bake Oven.mp4
```

Each subfolder becomes a "category" that RTV uses for weighted selection during playlist generation.

### Step 2: Add the Library in Plex

1. Open Plex → Settings → Libraries → Add Library
2. Choose type: **Movies** (not TV Shows — commercials are single files, not series)
3. Name it exactly what your config says (default: `RealTV Commercials`)
4. Point it to your commercial folder (e.g., `D:\Media\Commercials`)
5. Click Add Library

### Step 3: Hide from Home Screen (Optional)

You probably don't want commercials showing up on your Plex home screen:

1. Go to Settings → Libraries
2. Find "RealTV Commercials"
3. Click the gear icon
4. Uncheck "Include in dashboard"

### Step 4: Let Plex Scan

Plex needs to scan and index the commercial files. This happens automatically, but you can force it:

1. Go to the RealTV Commercials library
2. Click the "..." menu → Scan Library Files

After scanning, `rtv status` should show the commercial count.

## Break Styles

Each playlist can use a different commercial break style:

| Style | Behavior |
|-------|----------|
| `single` | One random commercial between episodes (default) |
| `block` | Multiple commercials filling a time window (like a real TV break) |
| `disabled` | No commercials at all |

Configure via CLI (`rtv create-playlist`), Web UI, or directly in `config.yaml`.

## Multi-Drive Setup

If your TV shows are spread across multiple drives (common for large collections), configure multiple TV show paths:

**In config.yaml:**
```yaml
plex:
  tv_show_paths:
    - "D:\\TV Shows"
    - "E:\\TV Shows"
    - "F:\\TV Shows"
    - "K:\\TV Shows"
```

When you run `rtv add-show`, it searches all configured libraries automatically.

## Remote Server (SSH)

When plex-real-tv runs on a different machine than your Plex server, enable SSH for remote file management:

```bash
rtv web  # Use the Setup page to configure SSH
```

Or in `config.yaml`:
```yaml
ssh:
  enabled: true
  host: "192.168.1.10"
  port: 22
  username: "admin"
  key_path: "~/.ssh/id_rsa"
  remote_commercial_path: "F:\\Commercials"
```

SSH enables remote commercial directory scanning, file uploads via SFTP, and remote command execution.

## How It Works

### The Round-Robin Algorithm

When you run `rtv generate`, RTV builds a playlist by cycling through your shows in order:

```
Episode 1: Seinfeld S03E12
  [Commercial: Random 70s/80s/90s/2000s/2010s clip]
Episode 2: The Office S01E01
  [Commercial: Different random clip (no repeats)]
Episode 3: Friends S05E08
  [Commercial: Yet another unique clip]
Episode 4: Seinfeld S03E13
  ...
```

Each show maintains its own position (season + episode) **per playlist**. After generating, positions are saved so the next generation picks up where you left off.

### Show Exhaustion

If a show runs out of episodes (reached the last episode of the last season), it drops out of the rotation and the remaining shows continue.

### Independent Positions

Two playlists can share the same show with different positions. "Real TV" might be at Seinfeld S05E03 while "90s Night" is still at S01E01.

### Position Tracking

Show positions are stored per playlist in `config.yaml`:

```yaml
playlists:
  - name: "Real TV"
    shows:
      - { name: "Seinfeld", current_season: 5, current_episode: 3 }
```

Use `--from-start` to reset all positions to S01E01.

## Command Reference

| Command | Description |
|---------|-------------|
| `rtv init` | Create config.yaml interactively |
| `rtv status` | Test Plex connection, show inventory summary |
| `rtv doctor` | Run diagnostic checks on your setup |
| **Show Management** | |
| `rtv add-show NAME` | Add a show to the global pool |
| `rtv remove-show NAME` | Remove a show from the pool |
| `rtv list-shows` | Show pool with enabled/disabled status |
| `rtv enable-show NAME` | Enable a show |
| `rtv disable-show NAME` | Disable a show (skipped in generation) |
| **Playlist Management** | |
| `rtv create-playlist NAME` | Create a new playlist |
| `rtv delete-playlist NAME` | Delete a playlist |
| `rtv list-playlists` | Summary of all playlists |
| `rtv playlist-add PLAYLIST SHOW` | Add show to playlist at S01E01 |
| `rtv playlist-remove PLAYLIST SHOW` | Remove show from playlist |
| `rtv set-default NAME` | Set the default playlist |
| **Generation** | |
| `rtv generate [NAME]` | Generate a Plex playlist |
| `rtv generate --from-start` | Reset all shows to S01E01 |
| `rtv generate --rescan` | Rescan Plex library before generating |
| `rtv generate --export` | Export playlist to CSV after generating |
| `rtv preview [NAME]` | Dry-run preview of playlist |
| `rtv export` | Export playlist to CSV or JSON |
| `rtv history` | Show last 5 generated playlists |
| **Commercials** | |
| `rtv find-commercials -c CATEGORY` | Search YouTube for commercials |
| `rtv download-commercials URL` | Download a commercial by URL |
| `rtv add-category NAME` | Add a commercial category |
| `rtv list-commercials` | Show commercial inventory |
| **GUI** | |
| `rtv web` | Launch browser-based Web UI |
| `rtv tui` | Launch terminal TUI |

## Troubleshooting

### "Could not connect to Plex"

1. Is Plex Media Server running?
2. Is the URL correct? Check with `rtv doctor`
3. Is the token valid? Tokens can expire — regenerate from Plex settings
4. Firewall blocking port 32400?

### "No match found" when adding a show

- Try the exact name as it appears in Plex
- Check which libraries are configured: `rtv status`
- Use `--library` to search a specific library

### "No commercials found"

1. Have you downloaded any? `rtv find-commercials -c "80s"`
2. Is the commercial path correct in config? `rtv doctor`
3. Did you create the Plex library and scan it?
4. Commercial files must be `.mp4` format

### "rtv: command not found"

Make sure you ran `pip install -e .` and that your Python Scripts directory is in PATH:
```bash
pip show plex-real-tv
```

### Run the diagnostic

`rtv doctor` checks everything: Plex connection, libraries, shows, commercial path, yt-dlp availability.

## Disclaimer

This tool generates playlists from media you already own in your Plex library. It does not distribute, stream, or share any media content. Commercial clips are sourced and stored locally by the user — RTV does not include or distribute any media files. You are responsible for ensuring your use of yt-dlp and any downloaded content complies with applicable terms of service and copyright law.

## License

MIT
