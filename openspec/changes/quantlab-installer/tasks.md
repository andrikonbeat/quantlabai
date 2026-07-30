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

## PR 3: SDK Install + Config Wizard

- [ ] 3.1 `installer/internal/state/state.go` — state.json Read/Write, config_hash SHA-256
- [ ] 3.2 `installer/internal/config/config.go` — config.yaml Read/Write, 0600 perms
- [ ] 3.3 `installer/internal/config/wizard.go` — Bubbletea TUI: SQX path, JForex host:port+creds, API keys, confirm screen
- [ ] 3.4 `installer/internal/sdk/install.go` — detect Python 3.11+, create venv, pip install from wheel asset
- [ ] 3.5 `installer/assets/templates/config.yaml` — default config template
- [ ] 3.6 Wire `install` pipeline: PREPARE (validate prereqs, capture before-images) → WIZARD → APPLY (state→config→venv/SDK→opencode merge→skills→prompts→ownership→state) → VERIFY → COMPLETE/rollback
- [ ] 3.7 Tests: config validators (SQX path, JForex TCP, API key format), SDK mock exec, state persistence, full install cycle in temp $HOME

## PR 4: Lifecycle Commands

- [ ] 4.1 `installer/internal/update/update.go` — download release, SHA-256 verify, atomic swap, exec new binary
- [ ] 4.2 `quantlab uninstall` — read state, remove agents via overlay, restore default_agent, rm skills/prompts/venv, delete `~/.quantlab/`
- [ ] 4.3 `quantlab sync` — update skills/prompts, match agents by ID, no duplicate entries
- [ ] 4.4 `quantlab status` — version, component list, service health, detect missing state/orphaned agents
- [ ] 4.5 `quantlab dashboard` — open URL in browser (or print)
- [ ] 4.6 `quantlab configure` — standalone wizard re-run
- [ ] 4.7 Inconsistent-state detection on startup (journal residue) + interactive rollback prompt
- [ ] 4.8 Tests: self-update E2E (local binary, fake release), uninstall clears all state, sync idempotent

## PR 5: Build & Release

- [ ] 5.1 `.github/workflows/release-installer.yml` — GoReleaser cross-compile: linux/amd64, linux/arm64, darwin/amd64, darwin/arm64
- [ ] 5.2 Version ldflags — inject commit, tag, date into `main.go` at build time
- [ ] 5.3 `installer/Makefile` — build/test/lint/clean targets
- [ ] 5.4 CI verification — all targets compile, SHA-256 checksums generated, release artifact valid
