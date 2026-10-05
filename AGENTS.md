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

## Public Copy Style (owner rule, 2026-10-05)

Canonical copy: `tjn.portfolio/AGENTS.md`. Everything a visitor can read (site copy, README, docs pages, meta tags, titles, alt text, UI strings) must sound like Travis wrote it.

- **No em dashes (—)** anywhere public, and no spaced en dashes used as em dashes. Use a colon, a comma, parentheses, or a new sentence. Titles use ` | ` (for example `About | Site Name`).
- First person where a person is speaking, plain words, short sentences. Say what it does and what happened.
- Avoid AI tells: "not X but Y" / "rather than" setups, "built as a … surface", "demonstrates", "showcases", "leverage", "seamless", "robust", "passionate", "journey", slogans, and stacked triplets used for rhythm.
- No meta talk about the project's public positioning. If something is private, say so once, plainly.
- Only verified facts and numbers. Employers stay anonymized; named clients need Travis's OK.

## Validation

- Run the focused tests for the area changed.
- For shared behavior, run `pytest`.
- For packaging or CLI entrypoint changes, also run the affected `rtv` command
  in a way that does not require real Plex credentials.
- Update docs when user-visible commands, config keys, workflows, screenshots,
  or packaging behavior change.

## Showcase facts contract

This repo is showcased on travisjneuman.com and github.com/travisjneuman.
`showcase.json` is the only source for public facts about this project
(schema: travisjneuman/travisjneuman `showcase/schema/showcase-v1.json`).

- If a change affects anything in it (counts, version, status, stack, links,
  summary), update `showcase.json` in the same commit. Re-run each metric's
  `source` command; never guess. `floor-2sig` metrics round down to two
  significant digits plus "+" (398 -> "390+").
- Set `updated` (and the touched metric's `asOf`) to today's date.
- Never put private URLs, hostnames, user data, or private names in it.
- The profile repo's `scripts/showcase/sync-showcase.mjs` regenerates the GitHub
  cards, README table, and portfolio data from these files.
