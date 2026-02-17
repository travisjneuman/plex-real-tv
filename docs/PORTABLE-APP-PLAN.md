# Portable Desktop Application Plan

> Add a standalone, offline-capable desktop application for Windows, macOS, and Linux alongside the existing Python package.

---

## Executive Summary

**Goal:** Create a portable `.exe` (Windows), `.app` (macOS), and binary (Linux) that runs the RealTV Web UI natively without requiring Python installation, network access for CDNs, or any external dependencies.

**Approach:** PyWebView + PyInstaller — the most direct path for this Python-based project.

**Key Principle:** Zero changes to existing codebase. The portable app is a separate build target that wraps the existing FastAPI backend and Jinja2 templates.

---

## Approach Comparison

| Criteria | PyWebView + PyInstaller | Tauri + Python Sidecar |
|----------|------------------------|------------------------|
| **Language** | Python only | Rust + Python |
| **Build complexity** | Low | High (requires Rust toolchain) |
| **Existing code reuse** | 100% | 100% (as sidecar) |
| **File size** | ~80-150 MB | ~15-30 MB (smaller) |
| **Maintenance burden** | Low | Medium (two ecosystems) |
| **Dev experience** | Same Python stack | Need Rust knowledge |
| **Native feel** | Good (webview) | Excellent (native webview) |
| **Learning curve** | Minimal | Steep |

### Recommendation: PyWebView + PyInstaller

**Why:**
1. **Single ecosystem** — Entire project stays Python-based
2. **Minimal changes** — PyWebView wraps FastAPI directly, no architecture rewrite
3. **Proven pattern** — Well-documented approach for FastAPI apps
4. **Easier maintenance** — No Rust build complexity for future contributors
5. **Faster implementation** — Estimated 2-3 days vs 1-2 weeks for Tauri

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

User runs: rtv-desktop.exe
   |
   +-> PyWebView launches native window
   +-> FastAPI server starts on random free port (localhost only)
   +-> PyWebView navigates to http://localhost:NNNN
   +-> User interacts with identical Web UI experience
```

### How It Works

1. **Startup**: `rtv-desktop.exe` starts
2. **Server spawn**: FastAPI launches on `localhost:NNNN` (random free port)
3. **Window open**: PyWebView creates native OS window pointing to localhost
4. **User interaction**: Identical to Web UI - htmx, SSE, all work the same
5. **Shutdown**: Window close -> server cleanup -> process exit

---

## Implementation Plan

### Phase 1: Offline Asset Bundling

Replace all CDN dependencies with local files.

#### 1.1 Download and Vendor Assets

Create `src/rtv/desktop/static/vendor/`:

| Asset | Source | Destination |
|-------|--------|-------------|
| Tailwind CSS | Pre-compiled from usage | `vendor/tailwind.min.css` (~20-50KB) |
| htmx 2.0.4 | `https://unpkg.com/htmx.org@2.0.4` | `vendor/htmx.min.js` (~15KB) |
| htmx-sse 2.2.2 | `https://unpkg.com/htmx-ext-sse@2.2.2/sse.js` | `vendor/htmx-sse.min.js` (~5KB) |
| Dela Gothic One | Google Fonts | `fonts/DelaGothicOne.woff2` (~25KB) |
| JetBrains Mono | Google Fonts | `fonts/JetBrainsMono-*.woff2` (~200KB all weights) |

#### 1.2 Create fonts.css

```css
/* src/rtv/desktop/static/fonts.css */
@font-face {
    font-family: 'Dela Gothic One';
    src: url('/static/fonts/DelaGothicOne.woff2') format('woff2');
    font-weight: 400;
    font-style: normal;
    font-display: swap;
}

@font-face {
    font-family: 'JetBrains Mono';
    src: url('/static/fonts/JetBrainsMono-Regular.woff2') format('woff2');
    font-weight: 400;
    font-style: normal;
    font-display: swap;
}
/* ... other weights ... */
```

---

### Phase 2: PyWebView Wrapper

Create the desktop application entry point.

#### 2.1 Directory Structure

```
src/rtv/desktop/
+-- __init__.py
+-- app.py              # PyWebView entry point
+-- server.py           # FastAPI launcher with port discovery
+-- templates/
|   +-- base_offline.html
+-- static/
    +-- fonts.css
    +-- vendor/
    |   +-- tailwind.min.css
    |   +-- htmx.min.js
    |   +-- htmx-sse.min.js
    +-- fonts/
        +-- DelaGothicOne.woff2
        +-- JetBrainsMono-*.woff2
```

---

### Phase 3: PyInstaller Configuration

Create build configuration for cross-platform executables.

#### 3.1 File Size Estimates

| Platform | Expected Size | Notes |
|----------|--------------|-------|
| Windows (.exe) | 80-120 MB | Includes Python runtime, Qt WebEngine |
| macOS (.app) | 90-130 MB | Includes Python runtime, Cocoa WebKit |
| Linux (binary) | 70-110 MB | Includes Python runtime, GTK WebKit |

**Optimization opportunities:**
- Use `--exclude-module` to remove unused packages
- Enable UPX compression (`upx=True`)
- Pre-compile Tailwind CSS (saves ~2.5MB vs CDN runtime)
- Strip debug symbols in release builds

---

## Required New Files Summary

```
plex-real-tv/
+-- src/rtv/desktop/
|   +-- __init__.py
|   +-- app.py                    # PyWebView entry point
|   +-- server.py                 # FastAPI launcher
|   +-- templates/
|   |   +-- base_offline.html     # CDN-free base template
|   +-- static/
|       +-- fonts.css
|       +-- vendor/
|       |   +-- tailwind.min.css
|       |   +-- htmx.min.js
|       |   +-- htmx-sse.min.js
|       +-- fonts/
|           +-- DelaGothicOne.woff2
|           +-- JetBrainsMono-*.woff2
+-- scripts/portable/
|   +-- build.py                  # Build script
|   +-- rtv-desktop.spec          # PyInstaller spec
|   +-- create_ico.py             # Windows icon generator
+-- assets/
    +-- logo.ico                  # Windows icon (create from logo.png)
```

---

## Distribution Strategy

### GitHub Releases (Recommended)

- Attach built binaries to each GitHub release
- Users download `RealTV-Windows.zip`, `RealTV-macOS.dmg`, or `RealTV-Linux.tar.gz`
- No installer needed - portable executables

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Large file size | Use Tailwind CLI for CSS, exclude unused modules |
| PyWebView webview engine varies by OS | Test on all platforms; use Qt WebEngine on Linux for consistency |
| PyInstaller misses hidden imports | Comprehensive `hiddenimports` list; test built executables |
| yt-dlp requires internet for YouTube | Document that commercial search/download needs internet |

---

## Build Requirements

### Python Version
**Important:** PyWebView requires `pythonnet` on Windows, which currently only supports Python 3.7-3.13.
You must use **Python 3.11, 3.12, or 3.13** to build the desktop app. Python 3.14+ is not yet supported.

### Windows
```bash
# Install dependencies
pip install -e ".[desktop]"

# Build the executable
python scripts/build/portable/build.py
```

### macOS
```bash
# Install dependencies
pip install -e ".[desktop]"

# Build the app bundle
python scripts/build/portable/build.py
```

### Linux
```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get install libgtk-3-dev libwebkit2gtk-4.0-dev

# Install Python dependencies
pip install -e ".[desktop]"

# Build the binary
python scripts/build/portable/build.py
```

---

## Development Testing

To run the desktop app in development mode (without building):

```bash
# From project root
python -c "import sys; sys.path.insert(0, 'src'); from rtv.desktop.app import main; main()"
```

Or install the package and use the CLI:

```bash
pip install -e ".[desktop]"
rtv-desktop
```

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 1. Asset bundling | 4-6 hours | Local fonts, Tailwind, htmx |
| 2. PyWebView wrapper | 4-8 hours | Working desktop window with FastAPI |
| 3. PyInstaller config | 4-6 hours | Working .exe on Windows |
| 4. Cross-platform build | 2-4 hours | GitHub Actions workflow |
| 5. Testing & polish | 4-8 hours | Verified builds on all platforms |

**Total: 2-3 days of focused work**