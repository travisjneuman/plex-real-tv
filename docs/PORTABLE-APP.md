# Portable Desktop Application

> Standalone, offline-capable desktop application for Windows, macOS, and Linux.

---

## Overview

RealTV is available as a portable desktop application — a standalone executable that runs the Web UI natively without requiring Python installation, network access for CDNs, or any external dependencies.

**Features:**
- **Fully offline** — all fonts, styling, and JavaScript bundled locally
- **No installation** — just download and run
- **Same UI as Web** — identical interface and functionality
- **Auto-discovery** — finds Plex servers on your network automatically
- **Cross-platform** — Windows, macOS, and Linux supported

---

## Download

Get the latest release from [GitHub Releases](https://github.com/travisjneuman/plex-real-tv/releases):

| Platform | File | Size |
|----------|------|------|
| Windows | `RealTV-Windows.zip` | ~30 MB |
| macOS | `RealTV-macOS.zip` | ~60 MB |
| Linux | `RealTV-Linux.tar.gz` | ~50 MB |

---

## Installation & Usage

### Windows

1. Download `RealTV-Windows.zip`
2. Extract anywhere
3. Double-click `RealTV.exe`

### macOS

1. Download `RealTV-macOS.zip`
2. Extract and move `RealTV.app` to Applications (or anywhere)
3. Open the app (may need to right-click → Open on first run due to code signing)

### Linux

1. Download `RealTV-Linux.tar.gz`
2. Extract: `tar -xzf RealTV-Linux.tar.gz`
3. Run: `./RealTV`

---

## Configuration

The portable app stores configuration in your system's AppData folder:

| Platform | Config Location |
|----------|-----------------|
| Windows | `%APPDATA%\RealTV\config.yaml` |
| macOS | `~/Library/Application Support/RealTV/config.yaml` |
| Linux | `~/.config/rtv/config.yaml` |

### Transferring Settings

To move your configuration to another computer, copy the `config.yaml` file to the corresponding location on the new machine.

---

## Architecture

```
+---------------------------------------------------------------------+
|                    PORTABLE APP (rtv-desktop)                       |
+---------------------------------------------------------------------+
|                                                                      |
|  +---------------------------------------------------------------+  |
|  |                     PyWebView Window                          |  |
|  |                   (Native OS Webview)                         |  |
|  |                                                               |  |
|  |    +-----------------------------------------------------+    |  |
|  |    |         http://localhost:NNNN (FastAPI)              |    |  |
|  |    |                                                      |    |  |
|  |    |   +---------+  +---------+  +---------------------+  |    |  |
|  |    |   | htmx.js |  | Jinja2  |  |  Tailwind (local)   |  |    |  |
|  |    |   | (local) |  | Templs  |  |  Fonts (local)      |  |    |  |
|  |    |   +---------+  +---------+  +---------------------+  |    |  |
|  |    |                                                      |    |  |
|  |    |   Routes: /setup, /shows, /playlists, /generate      |    |  |
|  |    +-----------------------------------------------------+    |  |
|  +---------------------------------------------------------------+  |
|                              |                                       |
|                              v                                       |
|  +---------------------------------------------------------------+  |
|  |              Core Engine (Unchanged)                           |  |
|  |                                                               |  |
|  |   config.py  |  playlist.py  |  plex_client.py  |  etc.      |  |
|  +---------------------------------------------------------------+  |
|                                                                      |
+---------------------------------------------------------------------+
```

### How It Works

1. **Startup**: User launches `RealTV.exe` (or `.app` / binary)
2. **Server spawn**: FastAPI launches on `localhost:NNNN` (random free port)
3. **Window open**: PyWebView creates native OS window pointing to localhost
4. **User interaction**: Identical to Web UI - htmx, SSE, all work the same
5. **Shutdown**: Window close → server cleanup → process exit

---

## Building from Source

### Requirements

**Important:** PyWebView requires `pythonnet` on Windows, which only supports Python 3.11-3.13. You must use one of these versions to build.

### Setup

```bash
# Clone the repository
git clone https://github.com/travisjneuman/plex-real-tv.git
cd plex-real-tv

# Install with desktop dependencies
pip install -e ".[desktop]"
```

### Build Commands

**Windows:**
```bash
pip install Pillow  # For icon generation
python scripts/portable/create_ico.py  # Create Windows icon
python scripts/portable/build.py
```

**macOS:**
```bash
python scripts/portable/build.py
```

**Linux:**
```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get install libgtk-3-dev libwebkit2gtk-4.1-dev

python scripts/portable/build.py
```

Output will be in the `dist/` directory.

---

## Development Testing

Run the desktop app without building:

```bash
pip install -e ".[desktop]"
rtv-desktop
```

Or directly:
```bash
python -m rtv.desktop.app
```

---

## File Structure

```
plex-real-tv/
├── src/rtv/desktop/
│   ├── __init__.py
│   ├── app.py                 # PyWebView entry point
│   ├── server.py              # FastAPI launcher with port discovery
│   ├── templates/             # Offline-ready base template
│   │   └── base.html
│   └── static/
│       ├── fonts.css          # Local font declarations
│       ├── app.css            # Application styles
│       ├── favicon.svg
│       ├── vendor/
│       │   ├── htmx.min.js
│       │   ├── htmx-sse.min.js
│       │   └── tailwind.min.js
│       └── fonts/
│           ├── DelaGothicOne-Regular.ttf
│           └── JetBrainsMono-*.woff2
├── scripts/portable/
│   ├── build.py               # Cross-platform build script
│   ├── rtv-desktop.spec       # PyInstaller spec file
│   ├── create_ico.py          # Windows icon generator
│   └── hook-fastapi.py        # PyInstaller runtime hook
└── .github/workflows/
    └── build-desktop.yml      # CI/CD for releases
```

---

## Limitations

- **Commercial search/download** requires internet access (yt-dlp)
- **First run on macOS** may require: System Settings → Privacy & Security → "Open Anyway" (unsigned app)
- **File size** is larger than native apps due to bundled Python runtime

---

## Troubleshooting

<details>
<summary><strong>macOS: "App is damaged and can't be opened"</strong></summary>

This is due to code signing. Run:
```bash
xattr -cr RealTV.app
```
Then open the app again.
</details>

<details>
<summary><strong>Windows: SmartScreen warning</strong></summary>

Click "More info" → "Run anyway". This appears because the app is not code-signed.
</details>

<details>
<summary><strong>Linux: Missing webkit dependencies</strong></summary>

Install system dependencies:
```bash
# Ubuntu/Debian
sudo apt-get install libgtk-3-dev libwebkit2gtk-4.1-dev

# Fedora
sudo dnf install gtk3-devel webkit2gtk4.1-devel
```
</details>

---

## Release Process

Releases are built automatically via GitHub Actions when a new release is published. The workflow:

1. Builds on Windows, macOS, and Linux in parallel
2. Creates archives for each platform
3. Uploads to the GitHub release

To trigger a build:
1. Create a new tag: `git tag v0.x.x && git push origin v0.x.x`
2. Create a release on GitHub from that tag
3. Wait for the workflow to complete
4. Download the artifacts from the release page
