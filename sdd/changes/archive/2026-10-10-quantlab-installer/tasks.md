# Tasks: QuantLab Installer

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 1500–1800 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 → PR 4 → PR 5 |
| Delivery strategy | force-chained |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Scaffolding + Core Pipeline | PR 1 | `cd installer && go test ./internal/pipeline/... ./internal/journal/...` | `quantlab install --dry-run` on temp $HOME | Revert `installer/cmd/`, `internal/app/`, `pipeline/`, `journal/`, `model/` |
| 2 | OpenCode Integration | PR 2 | `cd installer && go test ./internal/opencode/... ./internal/filemerge/...` | Fake opencode.json merge, verify agents injected | Revert `internal/opencode/`, `filemerge/`, `skills/`, `prompts/` + assets |
| 3 | SDK Install + Config Wizard | PR 3 | `cd installer && go test ./internal/sdk/... ./internal/config/... ./internal/state/...` | `quantlab configure` in temp $HOME | Revert `internal/sdk/`, `config/`, `state/` + templates |
| 4 | Lifecycle Commands | PR 4 | `cd installer && go test ./internal/update/...` | `quantlab status`, `quantlab update --dry-run` | Revert `internal/update/` |
| 5 | Build & Release | PR 5 | CI workflow validates cross-compile | Manual: download release, verify `quantlab version` | Revert `.github/workflows/release-installer.yml` |

## PR 1: Scaffolding + Core Pipeline

- [x] 1.1 `installer/go.mod` — Bubbletea, Bubbles, Lipgloss, yaml.v3, x/sys deps
- [x] 1.2 `installer/internal/model/types.go` — Component, SkillID, Config, InstallState
- [x] 1.3 `installer/internal/journal/journal.go` — before-image capture, multi-dir restore
- [x] 1.4 `installer/internal/filemerge/writer.go` — WriteFileAtomic (temp+rename, compare-and-swap)
- [x] 1.5 `installer/internal/pipeline/stages.go` — Step/RollbackStep, StagePlan, ProgressFunc
- [x] 1.6 `installer/internal/pipeline/runner.go` — step exec with progress, auto-rollback on failure
- [x] 1.7 `installer/internal/app/app.go` — CLI dispatch: install/uninstall/sync/configure/update/status/dashboard
- [x] 1.8 `installer/cmd/quantlab/main.go` — entry point with version ldflags
- [x] 1.9 Tests: journal capture/restore table-driven, pipeline rollback on failure, WriteFileAtomic atomicity

## PR 2: OpenCode Integration

- [x] 2.1 `installer/internal/filemerge/json_merge.go` — deep merge, `__replace__` sentinel, recursive objects, JSONC normalization
- [x] 2.2 `installer/internal/opencode/config.go` — Config struct, Read/WriteSettings, DefaultSettingsPath, agent accessors
- [x] 2.3 `installer/internal/opencode/merge.go` — MergeAgents with embedded overlay.json, RemoveAgents
- [x] 2.4 `installer/internal/opencode/ownership.go` — InstallPlan/UninstallPlan, capture/restore default_agent
- [x] 2.5 `installer/internal/opencode/mcp.go` — MergeMCPServers (placeholder for future QuantLab MCPs)
- [x] 2.6 `installer/assets/skills/` — quantlab-run-campaign, quantlab-deploy-strategy, quantlab-monitor-status
- [x] 2.7 `installer/assets/prompts/` — orchestrator, campaign, deploy, monitor prompt files
- [x] 2.8 `installer/internal/opencode/skills.go` — InstallSkills, InstallPrompts, RemoveSkills, RemovePrompts
- [x] 2.9 `installer/internal/state/state.go` — LoadOrInit, Save, Add/Remove/HasComponent, AddAgent
- [x] 2.10 Tests: filemerge (deep merge, sentinel, empty, malformed, JSONC, idempotent), opencode (config read/write, merge agents, ownership lifecycle, MCP merge, skills/prompts install/remove), state (load/save cycle, add/remove, corrupt file detection)

## PR 3: SDK Install + Config Wizard ✅

- [x] 3.1 `installer/internal/state/state.go` — state.json Read/Write, config_hash SHA-256 (already implemented in PR 2)
- [x] 3.2 `installer/internal/config/config.go` — config.yaml Read/Write, 0600 perms
- [x] 3.3 `installer/internal/tui/wizard/wizard.go` — Bubbletea TUI: API Key, Model selection, SDK path, confirm screen (moved to tui/wizard per refined spec)
- [x] 3.4 `installer/internal/sdk/install.go` — detect Python 3.11+, create venv, pip install from source/PyPI
- [x] 3.5 `installer/assets/templates/config.yaml` — default config template
- [x] 3.6 Wire `install` pipeline + `uninstall` pipeline: validate prereqs → wizard → SDK install → opencode merge → skills → prompts → ownership → state (+ rollback via pipeline)
- [x] 3.7 Tests: config Read/Write, SDK mock exec, wizard model, qllm client, spinner/progress/confirm models, install/uninstall plan validation, state persistence

## PR 4: Lifecycle Commands ✅

- [x] 4.1 `installer/internal/update/update.go` — download release, SHA-256 verify, atomic swap, exec new binary
- [x] 4.2 `quantlab uninstall` — read state, remove agents via overlay, restore default_agent, rm skills/prompts/venv, delete `~/.quantlab/`
- [x] 4.3 `quantlab sync` — update skills/prompts, match agents by ID, no duplicate entries
- [x] 4.4 `quantlab status` — version, component list, service health, detect missing state/orphaned agents
- [x] 4.5 `quantlab dashboard` — open URL in browser (or print)
- [x] 4.6 `quantlab configure` — standalone wizard re-run
- [x] 4.7 Inconsistent-state detection on startup (journal residue) + interactive rollback prompt
- [x] 4.8 Tests: self-update unit, uninstall plan, sync plan, status detection, dashboard URL, configure --reset

## PR 5: Build & Release ✅

- [x] 5.1 `installer/.goreleaser.yaml` — GoReleaser cross-compile: linux/amd64, linux/arm64, darwin/amd64, darwin/arm64, NFM .deb/.rpm, GitHub release
- [x] 5.2 `installer/internal/app/version.go` — version, commit, date ldflags; VersionInfo(), UserAgent(), enhanced `cmdVersion`
- [x] 5.3 `installer/Makefile` — build/test/lint/clean/tidy targets with VERSION/COMMIT/DATE ldflags
- [x] 5.4 `installer/cmd/quantlab/main.go` — simplified (version now in app pkg), no-args shows help + install tip
