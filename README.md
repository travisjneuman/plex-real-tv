<p align="center">
  <img src="assets/logo.png" alt="plex-real-tv" width="200">
</p>

<h1 align="center">plex-real-tv</h1>

<p align="center">
  <strong>Generate Plex playlists that simulate real TV — round-robin episodes with vintage commercial breaks.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/plex-compatible-e5a00d?style=flat-square&logo=plex&logoColor=white" alt="Plex Compatible">
  <img src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square" alt="MIT License">
  <img src="https://img.shields.io/badge/version-0.2.0-6366f1?style=flat-square" alt="v0.2.0">
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &middot;
  <a href="#web-ui">Web UI</a> &middot;
  <a href="#cli">CLI</a> &middot;
  <a href="#terminal-tui">TUI</a> &middot;
  <a href="#how-it-works">How It Works</a> &middot;
  <a href="#command-reference">Commands</a>
</p>

---

Point it at your Plex server, tell it which shows to include, build up a library of commercials, and run `rtv generate`. You get a playlist that feels like flipping on a cable channel: an episode of Seinfeld, a commercial break, an episode of The Office, another commercial, repeat. Each commercial is randomly selected with a configurable no-repeat window so you don't see the same one twice.

<p align="center">
  <img src="screenshots/landing.png" alt="Landing Page" width="700">
</p>

## Architecture

Three interfaces — one engine. The CLI remains the canonical interface.

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
# Clone and install
git clone https://github.com/travisjneuman/plex-real-tv.git
cd plex-real-tv
pip install -e .

# Create config and add shows
rtv init
rtv add-show "Seinfeld"
rtv add-show "The Office"

# Build your commercial library
rtv find-commercials -c "80s"

# Generate and play
rtv generate
```

Open Plex, find the "Real TV" playlist, and hit play.

## Prerequisites

- **[Python 3.11+](https://www.python.org/)**
- **[Plex Media Server](https://www.plex.tv/)** running and accessible over the network
- **Plex Token** — your X-Plex-Token for authentication. [How to find it](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).

## Installation

```bash
git clone https://github.com/travisjneuman/plex-real-tv.git
cd plex-real-tv
pip install -e .

# Verify
rtv --version
rtv --help
```

### Dependencies

All installed automatically via `pip install -e .`:

| Category | Package | Purpose |
|----------|---------|---------|
| **Core** | [`click`](https://click.palletsprojects.com/) | CLI framework |
| | [`PlexAPI`](https://github.com/pkkid/python-plexapi) | Plex server communication |
| | [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) | Commercial search & download |
| | [`pyyaml`](https://github.com/yaml/pyyaml) | Config file parsing |
| | [`pydantic`](https://docs.pydantic.dev/) | Config validation |
| | [`rapidfuzz`](https://github.com/rapidfuzz/RapidFuzz) | Fuzzy show name matching |
| | [`rich`](https://github.com/Textualize/rich) | Terminal formatting |
| **Web UI** | [`fastapi`](https://fastapi.tiangolo.com/) | Web framework |
| | [`uvicorn`](https://www.uvicorn.org/) | ASGI server |
| | [`jinja2`](https://jinja.palletsprojects.com/) | HTML templates |
| | [`sse-starlette`](https://github.com/sysid/sse-starlette) | Server-sent events (live progress) |
| **TUI** | [`textual`](https://textual.textualize.io/) | Terminal UI framework |
| **Remote** | [`paramiko`](https://www.paramiko.org/) | SSH/SFTP for remote Plex servers |

---

## Web UI

```bash
rtv web                    # Launch on default port 8080
rtv web --port 3000        # Custom port
rtv web --no-open          # Don't auto-open browser
```

Accessible from any device on your network at `http://<your-ip>:8080`.

> **Note:** The Web UI is served locally by FastAPI, but the **browser** needs internet access to load frontend assets from CDNs: [Tailwind CSS](https://tailwindcss.com/) (styling), [htmx](https://htmx.org/) (interactivity), [htmx SSE extension](https://htmx.org/extensions/server-sent-events/) (live progress), and [Google Fonts](https://fonts.google.com/) (Dela Gothic One + JetBrains Mono). The CLI and TUI work fully offline.

<details>
<summary><strong>Setup</strong> — Plex connection, server discovery, SSH config</summary>
<br>
<img src="screenshots/setup.png" alt="Setup Page" width="700">
</details>

<details>
<summary><strong>Shows</strong> — Global show pool, toggle enabled/disabled, scan Plex</summary>
<br>
<img src="screenshots/shows.png" alt="Shows Page" width="700">
</details>

<details>
<summary><strong>Playlists</strong> — Create/edit playlists, manage shows, configure breaks</summary>
<br>
<img src="screenshots/playlists.png" alt="Playlists Page" width="700">
</details>

<details>
<summary><strong>Generate</strong> — Generate playlists with live SSE progress & TV static animation</summary>
<br>
<img src="screenshots/generate.png" alt="Generate Page" width="700">
</details>

---

## CLI

### Show Management

```bash
rtv add-show "the office"                  # Fuzzy match against Plex library
rtv add-show "Dragon Ball Z" --library "Anime"
rtv list-shows                             # Show pool with status + membership
rtv remove-show "Seinfeld"
rtv enable-show "The Office (US)"
rtv disable-show "Friends"
```

### Playlist Management

```bash
rtv create-playlist "Late Night"
rtv playlist-add "Late Night" "Seinfeld"
rtv playlist-remove "Late Night" "Friends"
rtv list-playlists
rtv delete-playlist "Late Night"
rtv set-default "90s Night"
```

### Generation

```bash
rtv generate                    # Generate default playlist
rtv generate "90s Night"        # Specific playlist
rtv generate -e 50              # Custom episode count
rtv generate --from-start       # Reset all shows to S01E01
rtv generate --rescan           # Rescan Plex library first
rtv generate --from-start --export  # Generate + export CSV
```

### Commercials

RTV includes optional [yt-dlp](https://github.com/yt-dlp/yt-dlp) integration to search for and download commercials. You can also drop MP4 files directly into your commercial folder. You're responsible for ensuring your use complies with applicable terms of service and copyright law.

```bash
rtv find-commercials -c "80s"
rtv download-commercials "https://youtube.com/watch?v=..." -c "90s"
rtv download-commercials --from-search -c "80s"
rtv add-category "PSAs" -s "vintage PSA" -s "public service announcement" -w 0.5
rtv list-commercials
```

### Diagnostics & Export

```bash
rtv doctor                      # Full setup check
rtv preview -e 10               # Dry-run preview
rtv history                     # Last 5 generations
rtv status                      # Plex connection + inventory
rtv export                      # Export playlist to CSV
rtv export --format json        # Export as JSON
rtv export -o my_playlist.csv -n "90s Night"
```

---

## Terminal TUI

```bash
rtv tui
```

Full-screen terminal interface with keyboard navigation. Works over SSH for headless servers.

| Key | Screen |
|-----|--------|
| `d` | Dashboard — Plex status, stats, last generation |
| `s` | Shows — DataTable with search/filter, toggle enabled |
| `p` | Playlists — create, edit, generate, set default |
| `q` | Quit |

---

## How It Works

### The Round-Robin Algorithm

`rtv generate` builds a playlist by cycling through your shows in order:

```
Episode 1: Seinfeld S03E12
  [Commercial: Random 80s clip]
Episode 2: The Office S01E01
  [Commercial: Different clip (no repeats)]
Episode 3: Friends S05E08
  [Commercial: Yet another unique clip]
Episode 4: Seinfeld S03E13
  ...
```

Each show maintains its own position (season + episode) **per playlist**. Positions are saved after each generation so the next run picks up where you left off. Use `--from-start` to reset all positions to S01E01.

**Show exhaustion:** If a show runs out of episodes, it drops out and the remaining shows continue.

**Independent positions:** Two playlists can share the same show at different positions. "Real TV" might be at Seinfeld S05E03 while "90s Night" is still at S01E01.

### Break Styles

| Style | Behavior |
|-------|----------|
| `single` | One random commercial between episodes (default) |
| `block` | Multiple commercials filling a time window (like a real TV break) |
| `disabled` | No commercials |

---

## Configuration

### Interactive Setup

```bash
rtv init
```

Prompts for Plex URL, token, library names, and commercial path. Creates `config.yaml` in the current directory.

### Config Search Paths

1. `./config.yaml` (current directory)
2. `~/.config/rtv/config.yaml` (home config)

### Config Reference

<details>
<summary><code>config.yaml</code> — full example</summary>

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

# Global show pool
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
      frequency: 1         # break every N episodes
      min_gap: 50           # no-repeat window for commercials
      block_duration: { min: 30, max: 120 }
    episodes_per_generation: 30
    sort_by: premiere_year  # premiere_year | premiere_year_desc | alphabetical

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
</details>

### Config Migration (v1 → v2)

Existing v1 configs auto-migrate on first load — backs up to `config.yaml.v1.bak`, converts shows to global pool format, and creates a default playlist.

---

## Commercial Library Setup

Commercials need their own Plex library so they can be included in playlists alongside TV episodes.

### 1. Create the folder

```
D:\Media\Commercials\
├── 80s/
│   ├── Coca Cola 1985.mp4
│   └── Nintendo NES Commercial.mp4
├── 90s/
│   └── Got Milk 1993.mp4
├── PSAs/
│   └── This Is Your Brain On Drugs.mp4
└── toys/
    └── Easy Bake Oven.mp4
```

Each subfolder becomes a category for weighted selection during generation.

### 2. Add in Plex

1. Settings → Libraries → Add Library
2. Type: **Movies** (not TV Shows — commercials are single files)
3. Name: `RealTV Commercials` (must match config)
4. Point to your commercial folder

### 3. Hide from home (optional)

Settings → Libraries → RealTV Commercials → gear icon → uncheck "Include in dashboard"

---

## Multi-Drive Setup

```yaml
plex:
  tv_show_paths:
    - "D:\\TV Shows"
    - "E:\\TV Shows"
    - "F:\\TV Shows"
    - "K:\\TV Shows"
```

`rtv add-show` searches all configured libraries automatically.

## Remote Server (SSH)

For when plex-real-tv runs on a different machine than your Plex server:

```yaml
ssh:
  enabled: true
  host: "192.168.1.10"
  port: 22
  username: "admin"
  key_path: "~/.ssh/id_rsa"
  remote_commercial_path: "F:\\Commercials"
```

Or configure via the Web UI Setup page. SSH enables remote commercial directory scanning, SFTP uploads, and remote command execution.

---

## Command Reference

| Command | Description |
|---------|-------------|
| `rtv init` | Create config.yaml interactively |
| `rtv status` | Test Plex connection, show inventory |
| `rtv doctor` | Run diagnostic checks |
| **Shows** | |
| `rtv add-show NAME` | Add show to global pool |
| `rtv remove-show NAME` | Remove show |
| `rtv list-shows` | List pool with status |
| `rtv enable-show NAME` | Enable a show |
| `rtv disable-show NAME` | Disable a show |
| **Playlists** | |
| `rtv create-playlist NAME` | Create playlist |
| `rtv delete-playlist NAME` | Delete playlist |
| `rtv list-playlists` | List all playlists |
| `rtv playlist-add PLAYLIST SHOW` | Add show at S01E01 |
| `rtv playlist-remove PLAYLIST SHOW` | Remove show |
| `rtv set-default NAME` | Set default playlist |
| **Generation** | |
| `rtv generate [NAME]` | Generate Plex playlist |
| `rtv generate --from-start` | Reset to S01E01 |
| `rtv generate --rescan` | Rescan Plex first |
| `rtv generate --export` | Export after generating |
| `rtv preview [NAME]` | Dry-run preview |
| `rtv export` | Export to CSV/JSON |
| `rtv history` | Last 5 generations |
| **Commercials** | |
| `rtv find-commercials -c CAT` | Search for commercials |
| `rtv download-commercials URL` | Download by URL |
| `rtv add-category NAME` | Add category |
| `rtv list-commercials` | Show inventory |
| **GUI** | |
| `rtv web` | Launch Web UI |
| `rtv tui` | Launch Terminal TUI |

---

## Troubleshooting

<details>
<summary><strong>"Could not connect to Plex"</strong></summary>

1. Is Plex Media Server running?
2. Is the URL correct? Check with `rtv doctor`
3. Is the token valid? Tokens can expire — regenerate from Plex settings
4. Firewall blocking port 32400?
</details>

<details>
<summary><strong>"No match found" when adding a show</strong></summary>

- Try the exact name as it appears in Plex
- Check which libraries are configured: `rtv status`
- Use `--library` to search a specific library
</details>

<details>
<summary><strong>"No commercials found"</strong></summary>

1. Have you downloaded any? `rtv find-commercials -c "80s"`
2. Is the commercial path correct? `rtv doctor`
3. Did you create the Plex library and scan it?
4. Commercial files must be `.mp4` format
</details>

<details>
<summary><strong>"rtv: command not found"</strong></summary>

Make sure you ran `pip install -e .` and that your Python Scripts directory is in PATH:
```bash
pip show plex-real-tv
```
</details>

`rtv doctor` checks everything: Plex connection, libraries, shows, commercial path, yt-dlp availability.

---

## Disclaimer

This tool generates playlists from media you already own in your Plex library. It does not distribute, stream, or share any media content. Commercial clips are sourced and stored locally by the user — RTV does not include or distribute any media files. You are responsible for ensuring your use of yt-dlp and any downloaded content complies with applicable terms of service and copyright law.

## License

[MIT](LICENSE)
