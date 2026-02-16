# plex-real-tv

Generate [Plex](https://www.plex.tv/) playlists that simulate real TV — round-robin episodes from multiple shows with commercial breaks between them.

Point it at your Plex server, tell it which shows to include, build up a library of commercials over time, and run `rtv generate`. You get a playlist that feels like flipping on a cable channel: an episode of Seinfeld, a commercial, an episode of The Office, another commercial, repeat. One random commercial per break with a configurable no-repeat window so you don't see the same one twice.

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
- [`click`](https://click.palletsprojects.com/) — CLI framework
- [`PlexAPI`](https://github.com/pkkid/python-plexapi) — Plex server communication
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) — Video search and download (used for finding commercials)
- [`pyyaml`](https://github.com/yaml/pyyaml) — Config file parsing
- [`pydantic`](https://docs.pydantic.dev/) — Config validation
- [`rapidfuzz`](https://github.com/rapidfuzz/RapidFuzz) — Fuzzy show name matching
- [`rich`](https://github.com/Textualize/rich) — Terminal output formatting

## Configuration

### Interactive Setup

```bash
rtv init
```

Prompts you for Plex URL, token, library names, and commercial storage path. Creates `config.yaml` in the current directory.

### Config File Reference

`config.yaml` (or `~/.config/rtv/config.yaml`):

```yaml
plex:
  # Your Plex server URL (include port)
  url: "http://192.168.1.100:32400"

  # Your X-Plex-Token (see Prerequisites)
  token: "your-plex-token-here"

  # Plex library section names containing your TV shows
  # Supports multiple libraries for multi-drive setups
  tv_libraries:
    - "TV Shows"
    - "TV Shows 2"
    - "Anime"

# Shows in the rotation — managed via CLI commands
shows:
  - name: "Seinfeld"
    library: "TV Shows"
    current_season: 3
    current_episode: 12
  - name: "The Office (US)"
    library: "TV Shows"
    current_season: 1
    current_episode: 1
  - name: "Friends"
    library: "TV Shows 2"
    current_season: 5
    current_episode: 8

commercials:
  # Name of the Plex library for commercials (must match exactly)
  library_name: "RealTV Commercials"

  # Local filesystem path where commercial MP4s are stored
  # This path is scanned by yt-dlp for downloads
  library_path: "D:\\Media\\Commercials"

  # How long each commercial break should be (in seconds)
  block_duration:
    min: 120   # 2 minutes minimum
    max: 300   # 5 minutes maximum

  # Commercial categories with YouTube search terms and weights
  categories:
    - name: "80s"
      search_terms: ["80s commercials", "1980s TV ads"]
      weight: 1.0
    - name: "90s"
      search_terms: ["90s commercials", "1990s TV ads"]
      weight: 1.0
    - name: "toys"
      search_terms: ["vintage toy commercials"]
      weight: 0.5   # appears less often

playlist:
  # Default playlist name in Plex
  default_name: "Real TV"

  # How many episodes per generation (across all shows)
  episodes_per_generation: 30

  # Insert a commercial every N episodes
  commercial_frequency: 1   # 1 = after every episode, 2 = every other, etc.

  # No-repeat guarantee: don't replay a commercial until this many others have played
  commercial_min_gap: 50
```

### Config Search Paths

RTV looks for `config.yaml` in this order:
1. Current working directory (`./config.yaml`)
2. Home config directory (`~/.config/rtv/config.yaml`)

## Usage

### Show Management

```bash
# Add a show — fuzzy matches against your Plex library
rtv add-show "the office"
# → Matched: 'The Office (US)' (72% confidence)

# Add from a specific library
rtv add-show "Dragon Ball Z" --library "Anime"

# See your rotation with current positions
rtv list-shows

# Remove a show
rtv remove-show "Seinfeld"
```

### Commercial Management

RTV includes optional [yt-dlp](https://github.com/yt-dlp/yt-dlp) integration to help you search for and download commercials to build your own library. You're responsible for ensuring your use complies with applicable terms of service and copyright law. You can also add commercial clips from any source — just drop MP4 files into your commercial folder.

```bash
# Search for commercials (uses yt-dlp)
rtv find-commercials -c "80s"
# Displays results, prompts you to download

# Download a specific video by URL
rtv download-commercials "https://youtube.com/watch?v=..." -c "90s"

# Download from your last search results
rtv download-commercials --from-search -c "80s"

# Add a named category with custom search terms
rtv add-category "PSAs" -s "vintage PSA" -s "public service announcement" -w 0.5

# See what commercials you have
rtv list-commercials
```

### Playlist Generation

```bash
# Generate with defaults (30 episodes, playlist named "Real TV")
rtv generate

# Custom episode count
rtv generate -e 50

# Custom playlist name
rtv generate "Saturday Night TV"

# Start all shows from S01E01
rtv generate --from-start

# Rescan Plex commercial library before generating (picks up new/deleted files)
rtv generate --from-start --rescan

# Auto-export playlist to CSV after generating
rtv generate --from-start --export

# Export to a specific path
rtv generate --from-start --export --export-path "C:\Users\YourUser\Desktop\playlist.csv"

# Combine everything: rescan, regenerate from scratch, export
rtv generate --from-start --rescan --export
```

### Playlist Export

```bash
# Export current Plex playlist to CSV (default)
rtv export

# Export as JSON
rtv export --format json

# Custom output file and playlist name
rtv export -o my_playlist.csv -n "Saturday Night TV"
```

The export includes item number, type (episode/commercial), title, duration, and show/category for each item. Useful for reviewing large playlists without scrolling through thousands of items in Plex.

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

## Multi-Drive Setup

If your TV shows are spread across multiple drives (common for large collections), configure multiple Plex libraries:

**On your server:**
```
C:\Media\TV Shows\        → Plex library "TV Shows"
D:\Media\TV Shows 2\      → Plex library "TV Shows 2"
E:\Media\Anime\           → Plex library "Anime"
```

**In config.yaml:**
```yaml
plex:
  tv_libraries:
    - "TV Shows"
    - "TV Shows 2"
    - "Anime"
```

When you run `rtv add-show`, it searches all configured libraries automatically. Each show remembers which library it belongs to:

```bash
rtv add-show "Seinfeld"          # found in "TV Shows"
rtv add-show "Dragon Ball Z"      # found in "Anime"
```

## Windows Server 2022 Deployment

RTV is designed to run on the same machine as your Plex server.

### 1. Install Python

Download Python 3.11+ from [python.org](https://www.python.org/downloads/) and install. Check "Add to PATH" during installation.

Verify:
```cmd
python --version
```

### 2. Copy the Project

Copy the `plex-real-tv` folder to your server. A good location:

```
C:\Tools\plex-real-tv\
```

### 3. Install Dependencies

```cmd
cd C:\Tools\plex-real-tv
pip install -e .
```

### 4. Configure

```cmd
rtv init
```

When prompted:
- **Plex URL**: Use `http://localhost:32400` (server is local)
- **Token**: Your X-Plex-Token
- **TV libraries**: Enter all your library names, comma-separated
- **Commercial path**: Where you'll store commercial MP4s (e.g., `D:\Media\Commercials`)

### 5. Set Up Commercials

```cmd
# Create some categories and download commercials
rtv add-category "80s" -s "80s commercials" -s "1980s TV ads"
rtv find-commercials -c "80s"

# Create the Plex library (see Commercial Library Setup above)
```

### 6. Add Shows and Generate

```cmd
rtv add-show "Seinfeld"
rtv add-show "The Office"
rtv generate
```

### 7. Scheduled Generation (Optional)

To regenerate the playlist automatically, use Windows Task Scheduler:

1. Open Task Scheduler
2. Create Basic Task → name it "RTV Playlist"
3. Set trigger (e.g., daily at 3 AM)
4. Action: Start a program
   - Program: `C:\Tools\plex-real-tv\.venv\Scripts\rtv.exe` (or wherever your Python scripts are)
   - Arguments: `generate`
   - Start in: `C:\Tools\plex-real-tv`
5. Click Finish

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
  [Commercial: Still no repeats within 50-clip window]
Episode 5: The Office S01E02
  ...
```

Each show maintains its own position (season + episode). After generating, positions are saved to `config.yaml` so the next generation picks up where you left off.

### Show Exhaustion

If a show runs out of episodes (reached the last episode of the last season), it drops out of the rotation and the remaining shows continue:

```
Episode 1: Short Show S01E01  (only 3 episodes total)
Episode 2: Long Show S01E01
Episode 3: Short Show S01E02
Episode 4: Long Show S01E02
Episode 5: Short Show S01E03  ← last episode!
Episode 6: Long Show S01E03   ← Short Show dropped, only Long Show continues
Episode 7: Long Show S01E04
...
```

### Commercial Breaks

Each commercial break inserts exactly one random commercial between episodes. Commercials are baked into the Plex playlist at generation time (Plex has no dynamic ad insertion).

**No-repeat guarantee:** A commercial won't replay until at least `commercial_min_gap` (default 50) other commercials have played. The larger your library, the more variety you get. If your library is smaller than the gap setting, the oldest-played commercial is reused first.

### Position Tracking

Show positions are stored in `config.yaml` and persist between runs:

```yaml
shows:
  - name: "Seinfeld"
    current_season: 3
    current_episode: 15   # next run starts here
```

Use `--from-start` to reset all positions to S01E01.

## Playlist Maintenance

The `rtv generate` command is your single tool for any playlist changes. There are no separate refresh or rebalance commands — any change to your shows or commercials means regenerating the full playlist.

### Deleted Commercials

If you remove commercial files from the drive:

```bash
# Rescan Plex so it drops the deleted files, regenerate from scratch, export
rtv generate --from-start --rescan --export
```

### Added Commercials

Same workflow — download new files to the commercial folder, then:

```bash
rtv generate --from-start --rescan --export
```

### Added or Removed Shows

```bash
# Add a show
rtv add-show "Breaking Bad"

# Remove a show
rtv remove-show "Two and a Half Men"

# Regenerate
rtv generate --from-start --export
```

No `--rescan` needed for show changes since the TV libraries haven't changed — only use `--rescan` when commercial files on disk have changed.

### Routine Regeneration

If nothing changed and you just want a fresh shuffle of commercial placement:

```bash
rtv generate --from-start --export
```

## Mid-Episode Commercial Breaks

**Current behavior (v1):** Commercial breaks are inserted _between_ episodes, not in the middle of an episode. This is simpler and doesn't require modifying your media files.

**Future option:** True mid-episode commercial insertion would require FFmpeg to split episodes at specific timestamps and concatenate with commercial clips. This could be implemented as `rtv preprocess-episode` in a future version, but is not currently supported due to complexity (accurate split points, re-encoding, storage requirements).

For a natural viewing experience, the between-episode approach works well — real TV channels have commercial breaks at episode boundaries too.

## Server Operations (Remote via SSH)

The Plex server runs Windows Server 2022. All operations are run remotely over SSH from the development machine — nothing is uploaded manually. Set up an SSH config alias (e.g., `plex`) in `~/.ssh/config` pointing to your server.

### SSH Connection

```bash
# Test connection
ssh plex "hostname && python --version"

# Replace 'plex' with your SSH host alias
```

### Batch Commercial Downloads

The download script (`scripts/server_download_commercials.py`) can run directly on your server so downloads land on the correct drive without transferring files between machines. Copy it via `scp` and execute remotely.

**Step 1: Copy the script to the server**

```bash
scp scripts/server_download_commercials.py plex:C:/server_download_commercials.py
```

**Step 2: Run via Windows Scheduled Task (survives SSH disconnect)**

Direct SSH execution (`ssh plex "python script.py"`) dies when the SSH session closes. Windows `start /b` also doesn't work over SSH. The reliable approach is a one-time scheduled task:

```bash
# Create and immediately run a scheduled task
ssh plex 'schtasks /create /tn "DownloadCommercials" /tr "cmd /c python C:\server_download_commercials.py > C:\commercial_download.log 2>&1" /sc once /st 00:00 /f /ru YourUsername && schtasks /run /tn "DownloadCommercials"'
```

The `/st 00:00` warning is harmless — `schtasks /run` starts it immediately regardless.

**Step 3: Monitor progress**

```bash
# Check if still running
ssh plex "schtasks /query /tn \"DownloadCommercials\" /fo list"
# Look for: Status: Running

# Check Python process
ssh plex "tasklist /fi \"imagename eq python.exe\""

# See recent log output
ssh plex "powershell -c \"Get-Content C:\commercial_download.log -Tail 10\""

# Find latest clip number
ssh plex "powershell -c \"(Select-String -Path C:\commercial_download.log -Pattern '^\s+\[(\d+)\]' | Select-Object -Last 1).Line.Trim()\""

# Count files per decade
ssh plex "for /d %d in (D:\Media\Commercials\*) do @echo %d & dir /b /a-d \"%d\\*.mp4\" 2>nul | find /c /v \"\""
```

**Step 4: Clean up after completion**

```bash
ssh plex "schtasks /delete /tn \"DownloadCommercials\" /f"
```

### After Downloads: Rescan and Regenerate

```bash
# 1. Trigger Plex library scan (or do it from the Plex web UI)
# 2. Verify commercial count
ssh plex "for /d %d in (D:\Media\Commercials\*) do @echo %d & dir /b /a-d \"%d\\*.mp4\" 2>nul | find /c /v \"\""

# 3. Regenerate playlist with new commercials
rtv generate --from-start
```

### Key Gotchas

| Problem | Cause | Solution |
|---------|-------|----------|
| Script dies when SSH closes | SSH child processes are killed on disconnect | Use `schtasks` (scheduled task), not direct `ssh plex "python ..."` |
| `start /b` fails over SSH | Windows `start` doesn't work without a console session | Use `schtasks /create ... && schtasks /run ...` |
| `&` backgrounding fails | Not supported in Windows cmd over SSH | Use `schtasks` |
| Script shows old targets | Old version still on server at `C:\server_download_commercials.py` | `scp` the updated script first |
| Downloads go to wrong machine | Script must run on the server, not locally | Always `scp` + `schtasks`, never run locally |

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

### Downloads fail

- **Age-restricted**: Some videos require YouTube sign-in. Try a different video.
- **Geo-blocked**: Video not available in your region. Skip it.
- **Copyright claim**: Video was taken down. Find an alternative.

### "rtv: command not found"

Make sure you ran `pip install -e .` and that your Python Scripts directory is in PATH:
```bash
# Check where pip installed the script
pip show plex-real-tv
```

### Run the diagnostic

`rtv doctor` checks everything: Plex connection, libraries, shows, commercial path, yt-dlp availability.

## Command Reference

| Command | Description |
|---------|-------------|
| `rtv init` | Create config.yaml interactively |
| `rtv status` | Test Plex connection, show inventory summary |
| `rtv doctor` | Run diagnostic checks on your setup |
| `rtv add-show NAME` | Add a show to the rotation |
| `rtv remove-show NAME` | Remove a show from the rotation |
| `rtv list-shows` | Show rotation with episode positions |
| `rtv find-commercials -c CATEGORY` | Search YouTube for commercials |
| `rtv download-commercials URL` | Download a commercial by URL |
| `rtv add-category NAME` | Add a commercial category |
| `rtv list-commercials` | Show commercial inventory |
| `rtv generate [NAME]` | Generate a Plex playlist |
| `rtv generate --rescan` | Rescan Plex commercial library before generating |
| `rtv generate --export` | Export playlist to CSV after generating |
| `rtv generate --from-start` | Reset all shows to S01E01 |
| `rtv preview [NAME]` | Dry-run preview of playlist |
| `rtv export` | Export playlist to CSV or JSON |
| `rtv history` | Show last 5 generated playlists |

## Disclaimer

This tool generates playlists from media you already own in your Plex library. It does not distribute, stream, or share any media content. Commercial clips are sourced and stored locally by the user — RTV does not include or distribute any media files. You are responsible for ensuring your use of yt-dlp and any downloaded content complies with applicable terms of service and copyright law.

## License

MIT
