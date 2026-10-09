# Tasks: Installer Ecosystem Onboarding

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,900 (adds+del; goldens excluidos) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: config+state → PR 2: overlay → PR 3: tools detect/OpenCode → PR 4: gentle-ai → PR 5: onboarding TUI → PR 6: wiring+guía |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Config+state extendido | PR 1 | `go test ./internal/config/... ./internal/state/...` | N/A — unit puro, t.TempDir, sin I/O externo | Revertir config.go/state.go; CLIPath override y flags omitempty siguen válidos |
| 2 | Overlay guardian+delegates | PR 2 | `go test ./internal/opencode/...` | N/A — unit + golden embebido | Revertir overlay.json+merge.go; uninstall limpia set derivado |
| 3 | Detect+OpenCode npm | PR 3 | `go test ./internal/tools/... -run 'Detect|Npm|OpenCode'` | N/A — integración npm real marcada `-short` skip | Revertir tools/; npm -g idempotente; display-only no ejecuta |
| 4 | gentle-ai checksum+swap | PR 4 | `go test ./internal/tools/... -run GentleAI` | N/A — HTTP mockeado, t.TempDir | Revertir gentleai.go; binario ~/.local/bin removible |
| 5 | Model onboarding 5 pasos | PR 5 | `go test ./internal/tui/onboarding/...` | N/A — Model.Update() directo (AD-8, sin teatest) | Revertir tui/onboarding/; app.go aún sin case |
| 6 | Wiring app + guía + wizard/status | PR 6 | `go test ./...` (installer) | `go run ./cmd/quantlab onboarding --home $(mktemp -d)` (patrón cmdInstallHome) | Revertir wiring/guía; onboarding re-ejecutable, flag no bloquea |

## Phase 1 — Config + Estado (base, PR 1)

- [x] 1.1 RED: `config/config_test.go` — tabla: ResolveSQXCliPath override/derivado/windows; ValidateSQXPath raíz/`bin/`/inválido; NormalizeAccountMode ""→demo, `paper`→error. Fallan.
- [x] 1.2 GREEN: `config/config.go` — SQXConfig{InstallPath,CLIPath}+ResolveSQXCliPath+ValidateSQXPath; JForexConfig{InstallPath,AccountMode,Host,Port,Username,Password}+NormalizeAccountMode. Completo: tabla 1.1 verde.
- [x] 1.3 RED+GREEN: `state/state_test.go`+`state.go` — legacy sin flags → false sin error; Save persiste `onboarding_completed_at` (`*time.Time`, AD-9).

## Phase 2 — Overlay de agentes (PR 2)

- [x] 2.1 RED: `opencode/merge_test.go` — golden/table: QuantLabAgentNames()==keys overlay; MergeAgents incluye guardian+delegates; RemoveAgents limpia set. Fallan.
- [x] 2.2 GREEN: `opencode/overlay.json` — `guardian-orchestrator` (mode primary, deny-first espejo REQ-822) + `quantlab-guardian`, `quantlab-guardian-alert`, `quantlab-replacement` (subagent hidden).
- [x] 2.3 GREEN: `opencode/merge.go` — QuantLabAgentNames() derivado+ordenado del overlay; `app/install.go:308` count=`len(...)`; delta spec quantlab-orchestrator REQ-1 documenta mode primary.

## Phase 3 — Tools install (PR 3 + 4)

- [x] 3.1 RED: `tools/detect_test.go` — mock cmdLookPath+`--version`: instalado→versión; ausente→no fatal. Fallan.
- [x] 3.2 GREEN: `tools/detect.go` — DetectOpenCode/DetectGentleAI (LookPath + versión); única fuente de "already installed ✓".
- [x] 3.3 RED: `tools/npm_test.go`+`opencode_test.go` — writable→exec npm; no-writable→NO exec+display-only con sudo; red fail→display-only. Fallan.
- [x] 3.4 GREEN: `tools/npm.go`+`opencode.go` — DetectNpmWritable (nvm/fnm/volta+prefix); InstallOpenCode exec sin sudo / degrada display-only, nunca bloquea.
- [x] 3.5 RED: `tools/gentleai_test.go` — checksum mismatch→no activa; swap atómico en `~/.local/bin`; plataforma sin release→display-only; red fail→display-only. Fallan.
- [x] 3.6 GREEN: `tools/gentleai.go` — release GoReleaser + ParseChecksum fail-closed + swap atómico (patrón update.go) / display-only install.sh/ps1.

## Phase 4 — Onboarding TUI (PR 5)

- [x] 4.1 RED: `tui/onboarding/onboarding_test.go` — Model.Update() directo: intro→consent; rechazo→avanza SQX; SQX inválido→error permanece; password enmascarada; SDK "already installed ✓" informativo (decisión UX 1); post-install checkmarks según estado. Fallan.
- [x] 4.2 GREEN: `tui/onboarding/onboarding.go` — Model 5 pasos (StepIntro…StepPostInstall)+Result() reusando estilos wizard; consent map con `quantlab-sdk` informativo; primaryAgent opcional default `quantlab-orchestrator` (decisión UX 2, AD-10).

## Phase 5 — Wiring app + Guía (PR 6)

- [x] 5.1 GREEN: `assets/onboarding/steps.json` (4 pasos+check ∈ opencode/gentleai/sqx/jforex/always/none) + `assets/assets.go` embed onboarding+prompts + `assets/prompts/guardian-orchestrator.md` (patrón skills.go:70-106).
- [x] 5.2 GREEN: `app/onboarding.go` cmdOnboarding — persiste config 0600 + state; instala consentidos con spinner; SetDefaultAgent solo si primaryAgent elegido (AD-10); nunca password en logs/state.
- [x] 5.3 GREEN: `app/app.go` case `"onboarding"`; `app/help.go` help+validCommands.
- [x] 5.4 GREEN: `app/install.go` sugerencia post-install si `!OnboardingCompleted`; `app/configure.go` persiste install_path/account_mode (hoy descartado); `tui/wizard/wizard.go` steps nuevos; `app/status.go` muestra SQX/JForex + detectIssues aviso carpeta movida (param cfg).
- [x] 5.5 RED+GREEN: `app/onboarding_test.go`+`status_test.go` — password AUSENTE de state.json; install sin onboarding sugiere (stdout); help lista onboarding; "SQX folder moved — run 'quantlab configure' to update" / silencio.

## Phase 6 — Verificación final

- [x] 6.1 `go test ./...` en installer verde; `SQX_FORCE_MOCK=1 python3 -m pytest -q` verde (SDK intacto); cada PR ≤400 líneas (adds+del, goldens excluidos).