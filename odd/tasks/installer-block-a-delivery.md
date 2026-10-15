# ODD Task Document: installer-block-a-delivery

## Objective

Deliver the complete Block A installer experience per the user spec (S1-S8): environment pre-check with OS detection, QuantLab intro, interactive OpenCode install (official command, retry ≤3, manual fallback with URL, agent-doc link), gentle-ai install (command + engram detection), SQX/JForex manual guide with licensing, SQX path required + unified auto-detect, agent-driven path (auto deps first, manual last), functional verification checklist, and closing message with `quantlab-orchestrator` + 100USD campaign prompt.

## Problem

Three ODD tasks exist with overlapping scope but incomplete delivery:
- `installer-tui-thirdparty-deps`: wizard steps + SQX/gentle-ai detection + verify checklist — **completed** but in wizard flow only
- `installer-interactive-setup-script`: `install.sh` with full UX — **completed** but separate from Go onboarding
- `installer-onboarding-consent-flow`: **T1-T4 implemented** (consent Sí/No, install runners, retry→manual, verify, post-install) — **119 tests pass, diff ~1101 lines pending commit** on branch `rescue/pre-recovery-20261005-200314`

Gaps vs spec not covered by any task:
1. OS detection in pre-check
2. Official OpenCode install command (currently `npm i -g opencode-ai`)
3. Agent-doc link for delegation instruction when already detected
4. gentle-ai install as command (not prose) + engram detection
5. SQX path required + license guide (30-day free/paid) + unify auto-detect paths
6. Agent-driven path S7 (auto deps first, manual last)
7. `steps.json` example prompt update (EURUSD M5 1% → 100USD portfolio)

## Why

Unify the two TUI flows (wizard + onboarding) into the single onboarding flow that matches the spec, commit the implemented T1-T4 work with proper chained PRs, and close the remaining gaps so the installer is truly "ready for non-developer traders" and agent-delegable.

## Scope

### In Scope (Delivery of existing T1-T4)
- Commit the ~1101-line diff from `installer-onboarding-consent-flow` as 4 work-unit commits (T1, T2, T3, T4) ≤400 lines each, stacked-to-main
- Ensure `install.sh` uses the onboarding flow (fix double-run bug noted in consent-flow task)

### In Scope (Remaining gaps)
- G1: OS detection step in onboarding pre-check
- G2: Replace npm-based OpenCode install with official installer command/script
- G3: Add agent documentation URL to detected-tool branch in consent screens
- G4: gentle-ai install via verifiable command + detect engram presence
- G5: Make SQX path required, add license explanation, unify auto-detect (single source of truth)
- G7: Agent-driven path variant (reorder steps: auto-install OpenCode+gentle-ai first, then manual SQX/JForex)
- G8: Update `steps.json` example prompt

### Out of Scope
- Downloading SQX/JForex binaries (licensing)
- Modifying `quantlab install` wizard (`internal/tui/wizard`) — keep separate
- JForex login check (fragile I/O)
- Campaign pipeline changes

## Authorized Scope

- `installer/internal/tui/onboarding/onboarding.go` (steps, views, logic)
- `installer/internal/tui/onboarding/onboarding_test.go`
- `installer/internal/app/onboarding.go` (result consumption)
- `installer/internal/app/onboarding_test.go`
- `installer/internal/tools/opencode.go` (InstallOpenCode)
- `installer/internal/tools/gentleai.go` (InstallGentleAI, DetectGentleAI + engram)
- `installer/internal/tools/detect.go` (OS detection, OpenCode/gentle-ai/engram detect)
- `installer/internal/config/config.go` (SQX path required, unified auto-detect)
- `installer/internal/assets/onboarding/steps.json` (example prompt)
- `install.sh` (fix double-run, delegate to onboarding)
- `docs/INSTALL_INTERACTIVE.md` (update if needed)

## Acceptance Criteria

### Delivery of existing T1-T4
- [ ] Branch `feature/installer-block-a` created from `main`
- [ ] 4 work-unit commits: T1 (consent steps), T2 (install execution), T3 (verify+post-install), T4 (app wiring) — each ≤400 lines, conventional commits
- [ ] Stacked PRs created (auto-chain)
- [ ] All tests pass: `cd installer && go test ./internal/tui/onboarding/... ./internal/app/... ./internal/tools/...`
- [ ] `go build ./...` && `go vet ./...` clean
- [ ] Native RDD review passed on each work-unit commit

### Remaining gaps
- [ ] G1: Onboarding shows OS/arch/distro detection at start (before intro)
- [ ] G2: `InstallOpenCode` uses official command (`curl -fsSL https://opencode.ai/install | bash` or equivalent) with retry ≤3, then manual URL
- [ ] G3: Detected OpenCode branch shows "Para instalación delegada al agente: [comando] + [instrucción] + [docs URL]"
- [ ] G4: `InstallGentleAI` runs official install command; `DetectGentleAI` also checks engram
- [ ] G5: SQX path field required (✗ if empty), license note shown, single auto-detect function used by both onboarding and wizard
- [ ] G7: New flag/mode `--agent-driven` reorders flow: auto installs → verify → manual guides
- [ ] G8: `steps.json` step 3 example prompt = "Comienza una campaña para un portafolio de 100USD"

## Tasks

### Phase 1: Commit existing T1-T4 (chained)
- [ ] T1.1: Create feature branch `feature/installer-block-a` from `main`
- [ ] T1.2: Stage/commit T1 changes (consent step enum + interactive Sí/No + detected branches) — ~250 lines
- [ ] T1.3: Stage/commit T2 changes (install runners + queue + retry/manual) — ~350 lines
- [ ] T1.4: Stage/commit T3 changes (Verify checklist + PostInstall message) — ~250 lines
- [ ] T1.5: Stage/commit T4 changes (app/onboarding.go wiring + tests) — ~250 lines
- [ ] T1.6: Push branch + create 4 stacked PRs (auto-chain)
- [ ] T1.7: Run native RDD review on each PR candidate

### Phase 2: Remaining gaps (new work)
- [ ] G1: Add OS detection step in onboarding (new `StepOSDetect` before `StepIntro`)
- [ ] G2: Rewrite `tools.InstallOpenCode` with official command + retry logic
- [ ] G3: Add agent-doc URL constant + render in detected branches
- [ ] G4: Rewrite `tools.InstallGentleAI` as command; extend `DetectGentleAI` for engram
- [ ] G5: Make SQX path required in verify; add license text; unify auto-detect
- [ ] G7: Add `--agent-driven` flag + conditional step ordering
- [ ] G8: Update `steps.json` example prompt
- [ ] G9: Fix `install.sh` double-run bug (remove `main2` call)

## Progress

- Created: 2026-01-15 (this session)
- Status: Phase 1 in progress (T1-T4 implemented, pending chained commit)
- Active Task: T1.1 — create feature branch

## Rationale For Accepted Changes

Consolidates three overlapping ODD tasks into a single delivery plan. The existing T1-T4 implementation is solid (119 tests) but needs chained commits for reviewability. The 8 gaps are the delta between current implementation and the user's full spec.

## Next Step

Execute Phase 1: create feature branch and split the existing ~1101-line diff into 4 work-unit commits for stacked PRs.