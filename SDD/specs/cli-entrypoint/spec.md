# CLI Entrypoint Specification

## Purpose

Installed console command `quantlab` plus a module entry point, an `api` subcommand that boots the dashboard server, and build-system/lockfile packaging so the package installs cleanly with a working script.

## Requirements

### Requirement: CLI-01 Console script `quantlab`

The system MUST expose an installed console command `quantlab` via `[project.scripts]` mapping to `quantlab.cli.main:cli_entry` (main.py:1157).

#### Scenario: Help exits zero
- GIVEN the package is installed
- WHEN `quantlab --help` runs
- THEN it prints usage and exits 0

#### Scenario: No args exits non-zero
- GIVEN no subcommand
- WHEN `quantlab` runs bare
- THEN usage prints to stderr and exit code is non-zero

**Acceptance**: `quantlab --help` exits 0 in a fresh uv venv.

### Requirement: CLI-02 Module entry `python -m quantlab.cli`

The system MUST ship `sdk/quantlab/cli/__main__.py` invoking `main()` so module invocation matches the console script.

#### Scenario: Module invocation works
- GIVEN repo checkout without install
- WHEN `python -m quantlab.cli --help` runs
- THEN usage prints and exit code is 0

**Acceptance**: module invocation works from repo root and from `sdk/`.

### Requirement: CLI-03 `api` subcommand

The system MUST add an `api` subcommand that boots the dashboard server (`DashboardServer`) on host 0.0.0.0, port configurable (default 8080), and blocks until interrupted.

#### Scenario: API server boots
- GIVEN `quantlab api` invoked
- WHEN the server starts
- THEN `GET /api/health` returns 200 on 0.0.0.0:8080

#### Scenario: Clean shutdown
- GIVEN the server running
- WHEN Ctrl+C is sent
- THEN the server shuts down cleanly with exit 0

**Acceptance**: `quantlab api` boots (proposal success criterion).

### Requirement: CLI-04 Packaging + lockfile

`sdk/pyproject.toml` MUST declare `[build-system]`; the project SHOULD ship a `uv.lock`; a fresh `uv sync` in a clean venv MUST install the package with the console script.

#### Scenario: Fresh uv sync works
- GIVEN a clean venv
- WHEN `uv sync` runs from `sdk/`
- THEN `quantlab` is on PATH and imports resolve

#### Scenario: pip editable install still works
- GIVEN `[build-system]` added
- WHEN `pip install -e "sdk[dev]"` runs
- THEN install succeeds (no regression on hand-built venv)

**Acceptance**: fresh uv sync + console script works (proposal success criterion).
