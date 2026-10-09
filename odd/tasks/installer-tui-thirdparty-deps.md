# ODD Task Document: installer-tui-thirdparty-deps

## Objective

Extend the installer TUI wizard to guide installation/verification of third-party dependencies (StrategyQuant X, gentle-ai) and present a functional verification checklist before applying installation. The installer must leave QuantLab ready to use in OpenCode with `quantlab-orchestrator` selected.

## Problem

The current Go installer wizard (Bubbletea) only covers API key, model, and SDK path. It does not:
- Detect/validate StrategyQuant X (`sqx_path`) and persist it
- Detect/verify `gentle-ai` presence (coexistence, never overwrite)
- Show a functional verification checklist with ✓/✗/⚠ and block Continue until all OK
- End with a clear "ready to open OpenCode → select `quantlab-orchestrator`" message

## Why

To make QuantLab installable by non-developer traders with an interactive TUI that validates third-party components before setup, per the requested flow: prerequisites + gentle-ai check + SQX path + functional verification → ready to use.

## Scope

### In Scope
- Wizard: add `StepGentleAI`, `StepSQX`, `StepVerify`
- SQX: `autoDetectSQX()` with common paths (Linux/macOS/Windows), `validateSQXPath()` (exists, dir, accessible, minimal structure), realtime validation
- Gentle AI: detect presence in `~/.config/opencode/agents/gentle-*` and `~/.config/opencode/skills/gentle-*`; never modify/delete `gentle-*`; show explanation + allow Continue (with warning) if missing but user confirms awareness
- Verify: functional checklist with ✓/✗/⚠, disable Continue until all OK
- State/Config: persist `SQXPath string`, `GentleAIPresent bool`, `DepsVerified bool` in `~/.quantlab/state.json`
- Install pipeline: pass validated `sqxPath` through (prioritize validated path)
- Summary/Confirm: reflect SQX path and deps status

### Out of Scope
- Download/installing SQX or gentle-ai binaries (external deps). Only detect/validate/guide.
- Modifying `gentle-*` agents/skills (explicitly forbidden).
- Changing OpenCode JSON for third-party deps (SQX path not written to `opencode.json`).

## Authorized Scope
- `installer/internal/tui/wizard/wizard.go` (steps, views, update/init, detect/validate)
- `installer/internal/tui/wizard/styles.go` (checklist styles if needed)
- `installer/internal/state/state.go` (add fields + persistence)
- `installer/internal/app/install.go` (prereqs, pass sqxPath, wizardEnabled unchanged)
- `installer/internal/config/*` (optional: store sqx.path in config.yaml if present; safe perms)

## Acceptance Criteria
- [ ] Wizard includes new steps in correct order and progress bar reflects total steps
- [ ] SQX auto-detect finds common paths; manual input validates in real-time with clear error messages
- [ ] Gentle AI detection is read-only; coexistence rule respected (never overwrite)
- [ ] Verify step shows checklist with all items OK before enabling Continue
- [ ] State persists `SQXPath`, `GentleAIPresent`, `DepsVerified`
- [ ] Validated SQX path is used by install pipeline (not lost)
- [ ] End message clearly states: “Ready to open OpenCode → select agent `quantlab-orchestrator`”
- [ ] Existing behavior unchanged when skipping wizard (--no-wizard)

## Applicable Checks
- Go build: `cd installer && go build ./...`
- Go vet: `cd installer && go vet ./...`
- Installer unit tests (if any): `cd installer && go test ./...`
- Manual smoke test: run `quantlab install` in isolated temp HOME (non-interactive skipped, interactive TUI flow)

## Tasks

- [x] T1: Extend Step enum + titles + total steps in wizard (add StepGentleAI, StepSQX, StepVerify)
- [x] T2: Implement SQX auto-detect and validation (autoDetectSQX, validateSQXPath). Add SQX path state to Model
- [x] T3: Implement gentle-ai detection (read-only). Add GentleAI state to Model
- [x] T4: Implement Verify step with functional checklist, validation gate (disable Continue until all OK)
- [x] T5: Update state.State with SQXPath, GentleAIPresent, DepsVerified; persist/load
- [x] T6: Wire validated sqxPath through install flow (cmdInstallHome/cmdInstall, buildInstallPlan)
- [x] T7: Update Summary/Confirm views + final success message; test build/vet + basic flow

## Progress
- Created: 2025-10-06
- Status: completed
- Active Task: none

## Rationale For Accepted Changes
- T2-T6: Implemented SQX auto-detect/validate, gentle-ai detection, Verify checklist with gate, state persistence, and wiring validated sqxPath through install flow; success message includes readiness. All related tests/build/vet pass.- T1: Extended wizard steps (GentleAI, SQX, Verify), added state fields, auto-detect/validate helpers, verify checklist views. Build and existing wizard tests updated.

## Next Step
Ready to close.
