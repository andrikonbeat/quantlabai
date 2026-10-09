# ODD Task Document: installer-onboarding-consent-flow

## Objective

Make the `quantlab onboarding` Bubbletea TUI's tool-consent and install flow
functional and aligned with the installation spec: interactive Sí/No consent for
OpenCode and gentle-ai, install execution with bounded retry and manual-URL
fallback, a functional verification checklist, and a closing "ready to open
OpenCode → `quantlab-orchestrator`" message with an example prompt.

## Problem

`viewConsent` is display-only. `consentOpenCode`/`consentGentleAI` are never
toggled (`installer/internal/tui/onboarding/onboarding.go:117-129`, `281-299`),
so `cmdOnboarding` never installs OpenCode or gentle-ai
(`installer/internal/app/onboarding.go:65-89`). There is no Sí/No prompt, no
retry, no manual fallback, no verification step, and no example prompt.

## Why

User-provided installation spec (installation flow, points 1-7): detect tools,
offer automatic install with an interactive Yes/No, retry on failure, fall back
to the official URL after repeated failures, verify functionally, and close by
telling the user how to start a campaign.

## Scope

### In Scope
- Interactive consent steps for OpenCode and gentle-ai (Sí/No when not detected;
  informational branch + delegate instruction when already detected).
- Install execution inside the TUI via injectable runners + `tea.Cmd`.
- Bounded retry (max 3 attempts) then automatic manual mode; manual mode shows
  the official URL and continues.
- Functional verification checklist (✓/✗/⚠) that recommends delegating to the
  OpenCode agent when something is missing (non-blocking).
- Closing message: how to open OpenCode, select `quantlab-orchestrator`, and an
  example prompt (`Comienza una campaña para un portafolio de 100USD`).
- `app/onboarding.go` consumes TUI results instead of re-installing.
- Update/extend Go tests (TDD).

### Out of Scope
- Rewriting `install.sh` (separate issue; it currently double-runs `main`/`main2`).
- The config wizard used by `quantlab install` (`internal/tui/wizard`).
- Actually downloading SQX/JForex; only guide + path collection.
- SQX/JForex auto-detect prefill in onboarding (follow-up task T5).
- Campaign pipeline + phase-1 artifact (separate front).

## Authorized Scope (allowed edit surfaces)

- installer/internal/tui/onboarding/onboarding.go
- installer/internal/tui/onboarding/onboarding_test.go
- installer/internal/app/onboarding.go
- installer/internal/app/onboarding_test.go

Read-only (import, do not edit): installer/internal/tools/*,
installer/internal/config/*, installer/internal/assets/*,
installer/internal/state/*.

## Design

### Step enum
```
StepIntro
StepConsentOpenCode
StepConsentGentleAI
StepInstalling
StepInstallFailed
StepInstallManual
StepSQX
StepJForex
StepVerify
StepPostInstall
stepCount
```

### Consent
- `StepConsentOpenCode`: if `openCodeInstalled` → informational text (already
  installed; how to delegate to the OpenCode agent: install command + a sample
  instruction + docs link) and Enter advances. Else prompt
  `¿Instalar OpenCode automáticamente? [S/N]`: `s`/`y` sets consent and queues
  install; `n` records skip and advances.
- `StepConsentGentleAI`: same shape adapted to gentle-ai.
- Consent is collected for both tools first; installs run afterwards in
  `StepInstalling`.

### Install execution
- `StepInstalling` runs a queue (`["opencode","gentle-ai"]` filtered by consent)
  one job at a time via `tea.Cmd`; each returns an `installDoneMsg{tool,display,err}`.
- Success → mark ready, run next job; when the queue is empty → `StepSQX`.
- Failure → `StepInstallFailed` recording the tool and error.
- `StepInstallFailed`: `[R]` retry (only while attempts < 3), `[M]` manual mode,
  `[O]` skip. At the 3rd consecutive failure, force manual mode.
- `StepInstallManual`: shows the official URL + install instruction; Enter marks
  the tool as "manual/pending", advances to the next job (or `StepSQX`).

### Injectable runners (for tests)
```go
installOpenCodeFn func(home string) (string, error) // default tools.InstallOpenCode
installGentleAIFn func(home string) (string, error) // default tools.InstallGentleAI
homeFn            func() (string, error)            // default os.UserHomeDir
```

### Verify
- `StepVerify`: checklist over OpenCode, gentle-ai, SQX path, JForex path, SDK
  readiness using ✓/✗/⚠. Non-blocking: if any item is ✗, show a note recommending
  running the install from the OpenCode agent. Enter → `StepPostInstall`.

### PostInstall / closing
- Final message: `1) cd "<campañas>/" && opencode`, `2) elegí el agente
  quantlab-orchestrator`, `3) prompt de ejemplo: "Comienza una campaña para un
  portafolio de 100USD"`. Keep loading guide steps from
  `assets/onboarding/steps.json`.

### Result
- Remove `Consent.SDK` (unused by `app/onboarding.go`).
- Add `OpenCodeReady bool` and `GentleAIReady bool` (detected at start or
  installed successfully during the flow).

### app/onboarding.go
- Stop calling `tools.InstallOpenCode`/`tools.InstallGentleAI` (the TUI now owns
  install execution). Print the readiness from `Result()` and keep the existing
  config write, primary-agent handling, and state save.

## Acceptance Criteria
- [ ] `viewConsent` is interactive: Sí/No install prompt when a tool is missing.
- [ ] Detected-tool branch shows the delegation instruction instead of a prompt.
- [ ] Consented installs execute via injectable runners; failures offer retry
      (max 3) then manual mode with the official URL.
- [ ] Verify step shows ✓/✗/⚠ and recommends delegating to the OpenCode agent
      when something is missing (does not hard-block).
- [ ] Closing message names `quantlab-orchestrator` and shows the example prompt.
- [ ] `app/onboarding.go` no longer double-installs.
- [ ] Existing and new tests pass; `go build ./...` and `go vet ./...` clean.

## Applicable Checks
- `cd installer && go test ./internal/tui/onboarding/... ./internal/app/...`
- `cd installer && go build ./...`
- `cd installer && go vet ./...`

## Tasks

- [x] T1: Restructure step enum + interactive consent steps (OpenCode, gentle-ai)
      with detected/not-detected branches. Update existing flow tests.
- [x] T2: Install execution via injectable runners + `tea.Cmd` queue;
      `StepInstalling`/`StepInstallFailed`/`StepInstallManual` with bounded retry
      and manual-URL fallback.
- [x] T3: `StepVerify` checklist (non-blocking + delegation recommendation) and
      `StepPostInstall` closing message alignment.
- [x] T4: `app/onboarding.go` consumes TUI results; remove double-install; tests.
- [ ] T5 (follow-up): SQX/JForex auto-detect prefill in onboarding.

## Progress
- Created: 2026-10-09
- Status: implemented, pending delivery decision (commit/review).
- Active Task: none (T1-T4 done; T5 follow-up).
- Evidence: `cd installer && go test ./internal/tui/onboarding/... ./internal/app/... ./internal/tools/...` → 119 passed (baseline 101). `go build ./...` and `go vet ./...` clean. Diff: 4 files, 966 insertions / 135 deletions (~1101 authored lines).

## Delivery Strategy
- Forecast authored changed lines: ~350-450. Actual: ~1101. **Budget risk: high** (exceeds the ~400 review slice).
- Strategy: ask-on-risk (default) → ask once for the chain strategy before the next commit.
- Commits held: repo is on branch `rescue/pre-recovery-20261005-200314` with unrelated uncommitted changes (`sdk/quantlab/knowledge/sqx_doc_provider.py`, `sdk/tests/agents/test_hypothesis_builder.py`, `tests/knowledge/test_sqx_doc_provider.py`, `.atl/skill-registry.md`). No commit/branch change made; the user decides branch + slicing.
- Native review (RDD is ON) is deferred until a work-unit commit exists, per the candidate = commit/PR-slice rule.

## Rationale For Accepted Changes
- T1-T4 implemented by a delegated bounded writer (`gentle-ai-worker`) with RED→GREEN; onboarding TUI now owns interactive Sí/No consent, install execution, bounded retry (max 3 → manual), non-blocking verification with delegation recommendation, and the closing message; `app/onboarding.go` no longer double-installs.
- Two scoped corrections applied by the orchestrator after a structural readback:
  1. Manual fallback was misclassified as success: a runner returning `(display, nil)` with a non-empty display now goes to `StepInstallManual` (not `OpenReady`), matching the spec's manual fallback. Added `manualDisplay` + surfaced it in the manual view.
  2. `loadPostInstallSteps` unmarshalled a bare array but `assets/onboarding/steps.json` is `{"steps":[...]}`, so the embedded guide was dead code and always fell back. Added a `postInstallGuide` wrapper. Added a test asserting the asset loads (fallback lacks the `gentle-ai` step).

## Known Follow-ups
- T5: SQX/JForex auto-detect prefill in onboarding (spec point 5).
- `install.sh` runs both `main` and `main2` (functions defined after `main "$@"`, then `main2 "$@"` at EOF) → the guided flow runs twice. Separate defect, out of scope.
- `gofmt -l` flags `installer/internal/app/install.go` (pre-existing, outside this change).

## Next Step
- User decision: chain strategy + branch/commit for the ~1101-line change (ask-on-risk). Once a work-unit commit exists, run the native RDD review on that candidate.
