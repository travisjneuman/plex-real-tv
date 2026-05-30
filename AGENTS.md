# AGENTS.md - plex-real-tv

## Project Scope

This repo builds `plex-real-tv`, a Python 3.11+ application that creates Plex
playlists with round-robin TV episodes and commercial breaks. It includes a CLI,
FastAPI/Jinja web UI, Textual TUI, and optional desktop packaging.

## Working Rules

- Read `README.md`, `pyproject.toml`, relevant `src/rtv/**` modules, and nearby
  tests before changing behavior.
- Keep compatibility with existing CLI commands, config file shape, playlist
  generation behavior, and Plex API assumptions unless the task explicitly
  changes them.
- Do not commit real Plex tokens, server URLs, local library paths, SSH details,
  media filenames used as private evidence, or generated local config.
- Treat `config.example.yaml` as the documented public example. Keep
  `config.yaml` and backup config files local unless the user explicitly asks
  to change them.
- Avoid changing packaged static assets or vendored browser files unless the
  task is specifically about the web or desktop UI.
- Preserve cross-platform behavior for Windows, macOS, Linux, and headless SSH
  use when touching paths, subprocesses, packaging, or terminal/UI code.

## Validation

- Run the focused tests for the area changed.
- For shared behavior, run `pytest`.
- For packaging or CLI entrypoint changes, also run the affected `rtv` command
  in a way that does not require real Plex credentials.
- Update docs when user-visible commands, config keys, workflows, screenshots,
  or packaging behavior change.
