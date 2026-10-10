# Apply Progress: QuantLab Installer

## Status

**IMPLEMENTED — 38/38 tasks checked, pending verify + archive.**

## PR 1: Scaffolding + Core Pipeline (1.1–1.9) ✅

- `installer/go.mod` (Bubbletea, Bubbles, Lipgloss, yaml.v3, x/sys)
- `installer/internal/model/types.go` (Component, SkillID, Config, InstallState)
- `installer/internal/journal/journal.go` (before-image capture, multi-dir restore)
- `installer/internal/filemerge/writer.go` (WriteFileAtomic: temp+rename)
- `installer/internal/pipeline/stages.go` + `runner.go` (step exec, auto-rollback)
- `installer/internal/app/app.go` (install/uninstall/sync/configure/update/status/dashboard)
- `installer/cmd/quantlab/main.go` (entry point, version ldflags)
- Tests: journal, pipeline rollback, WriteFileAtomic — green.

## PR 2: OpenCode Integration (2.1–2.10) ✅

- `installer/internal/filemerge/json_merge.go` (deep merge, `__replace__`, JSONC)
- `installer/internal/opencode/config.go`, `merge.go` (MergeAgents), `ownership.go`, `mcp.go`, `skills.go`
- `installer/internal/assets/` (skills, prompts, templates) + `installer/internal/state/state.go`
- Tests: filemerge, opencode, state — green.

## PR 3: SDK Install + Config Wizard (3.1–3.7) ✅

- `installer/internal/config/config.go` (0600 perms), `installer/internal/tui/wizard/wizard.go`
- `installer/internal/sdk/install.go` (Python 3.11+ detect, venv, pip)
- Install/uninstall pipelines wired with rollback.
- Landed visibly: `install.sh` (15.5K, commit `f2e73f0`), TUI single command (`b7fadea`).

## PR 4: Lifecycle Commands (4.1–4.8) ✅

- `installer/internal/update/update.go` (SHA-256 verify, atomic swap)
- uninstall / sync / status / dashboard / configure + journal-residue detection.
- Tests: self-update, uninstall/sync/status plans — green.

## PR 5: Build & Release (5.1–5.4) ✅

- `installer/.goreleaser.yaml`, `installer/internal/app/version.go`, `installer/Makefile`.
- Tests: version, help — green.
