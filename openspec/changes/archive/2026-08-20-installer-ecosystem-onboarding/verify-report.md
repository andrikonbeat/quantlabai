```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:1dca110ad76c8b9fa5aad0738aac1b9ba6471c1dd1c801f76217facc3c4e8748
verdict: fail
blockers: 2
critical_findings: 3
requirements: 3/17
scenarios: 14/37
test_command: go test ./... -short -count=1 -timeout 120s
test_exit_code: 0
test_output_hash: sha256:f441563c465356d84295ef2794768494a62f882ebf57bc2f8b8ece919d23e599
build_command: go build ./...
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Verification Report

**Change**: installer-ecosystem-onboarding
**Version**: N/A
**Mode**: Standard (`strict_tdd: false` per `openspec/config.yaml`)

### Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 66 |
| Tasks complete | 66 |
| Tasks incomplete | 0 |

### Build & Tests Execution

**Build**: ✅ Passed
```text
go build ./...  → PASS (no output)
```

**Tests (Go)**: ✅ 330 passed / ❌ 0 failed / ⚠️ 0 skipped
```text
go test ./... -short -count=1 -timeout 120s  → PASS (330 passed in 19 packages)
```

**Tests (Python)**: ✅ 70 passed / ❌ 0 failed / ⚠️ 0 skipped
```text
SQX_FORCE_MOCK=1 python3 -m pytest -q tests/test_orchestrator_prompt.py  → PASS (70 passed)
```

**Coverage**: Not available

### Spec Compliance Matrix

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| REQ-ONB-1 | Primer onboarding completo | (none found) | ❌ UNTESTED |
| REQ-ONB-1 | Estado legacy sin flag | `state_test.go > TestLegacyStateWithoutOnboardingFlags` | ✅ COMPLIANT |
| REQ-ONB-1 | Install sugiere onboarding | `install_test.go > TestInstall_SuggestsOnboardingWhenMissing` | ✅ COMPLIANT |
| REQ-ONB-2 | Flujo de 14 fases en orden | (none found) | ❌ UNTESTED |
| REQ-ONB-3 | Herramienta ya instalada | (none found) | ❌ UNTESTED |
| REQ-ONB-3 | Rechazo no bloquea | `onboarding_test.go > TestOnboarding_Flow` | ✅ COMPLIANT |
| REQ-ONB-4 | Carpeta SQX válida | `onboarding_test.go > TestOnboarding_Flow` | ✅ COMPLIANT |
| REQ-ONB-4 | Carpeta inválida | (none found) | ❌ UNTESTED |
| REQ-ONB-5 | Config JForex demo | `onboarding_test.go > TestOnboarding_Flow` | ⚠️ PARTIAL |
| REQ-ONB-5 | Modo live seleccionado | `onboarding_test.go > TestOnboarding_JForexLiveMode` | ✅ COMPLIANT |
| REQ-ONB-6 | Guía con checkmarks según estado | (none found) | ❌ UNTESTED |
| REQ-TOOLS-1 | Herramienta instalada | `detect_test.go` | ✅ COMPLIANT |
| REQ-TOOLS-1 | Herramienta ausente | `detect_test.go` | ✅ COMPLIANT |
| REQ-TOOLS-2 | npm escribible → instala | `npm_test.go`, `opencode_test.go` | ✅ COMPLIANT |
| REQ-TOOLS-2 | npm requiere sudo → display-only | `npm_test.go` | ✅ COMPLIANT |
| REQ-TOOLS-2 | Fallo de red | `npm_test.go` | ✅ COMPLIANT |
| REQ-TOOLS-3 | Release disponible → binario instalado | `gentleai_test.go` | ✅ COMPLIANT |
| REQ-TOOLS-3 | Checksum inválido | `gentleai_test.go` | ✅ COMPLIANT |
| REQ-TOOLS-3 | Plataforma sin release | `gentleai_test.go` | ✅ COMPLIANT |
| INSTALL | First install on clean machine | `install_test.go > TestBuildInstallPlan_Stages`, `TestMergeOpenCodeAgents_CreatesFile` | ⚠️ PARTIAL |
| INSTALL | Agent count coincide con overlay | (none found) | ❌ UNTESTED |
| STATUS | Carpeta SQX movida | (none found) | ❌ FAILING |
| STATUS | SQX configurado y presente | (none found) | ❌ UNTESTED |
| REQ-INS-1 | Resolución con override | (none found) | ❌ UNTESTED |
| REQ-INS-1 | Resolución derivada | (none found) | ❌ UNTESTED |
| REQ-INS-1 | Validación de carpeta | (none found) | ❌ UNTESTED |
| REQ-INS-1 | AccountMode por defecto | (none found) | ❌ UNTESTED |
| REQ-INS-2 | Overlay contiene guardian | `overlay_golden_test.go`, `test_orchestrator_prompt.py` | ✅ COMPLIANT |
| REQ-INS-2 | Uninstall limpia el set derivado | (none found) | ❌ UNTESTED |
| REQ-1 | Agent appears in opencode.json | (none found) | ❌ UNTESTED |
| REQ-1 | Agent prompt references file | (none found) | ❌ UNTESTED |
| REQ-1 | Agent has scoped tools | (none found) | ❌ UNTESTED |
| REQ-1 | Modo consistente con overlay | (none found) | ❌ UNTESTED |

**Compliance summary**: 14/37 scenarios compliant, 2 partial, 1 failing, 20 untested

### Correctness (Static Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| REQ-ONB-1 | ⚠️ Partial | `quantlab onboarding` command exists; state flags `OnboardingCompleted`/`OnboardingCompletedAt` implemented; install suggests onboarding; help documents it. State persistence tests added but no end-to-end test verifies full flow writes state. |
| REQ-ONB-2 | ⚠️ Partial | Intro text includes 14 phases and tool purposes. No test verifies exact content or order. |
| REQ-ONB-3 | ✅ Implemented | Consent screen shows `[✓]` for detected tools via `DetectOpenCode`/`DetectGentleAI`; rejection advances flow. |
| REQ-ONB-4 | ✅ Implemented | `ValidateSQXPath` wired into SQX step handler; checks root and `bin/`. |
| REQ-ONB-5 | ⚠️ Partial | JForex password masked with `EchoPassword`; `WriteConfig` uses 0600; `NormalizeAccountMode` validates demo/live. No test verifies password absence from state.json. |
| REQ-ONB-6 | ⚠️ Partial | Post-install screen shows checkmarks for opencode/gentle-ai/primary-agent based on real state. Missing sqx/jforex checks; `steps.json` `check` field ignored. |
| REQ-TOOLS-1 | ✅ Implemented | `DetectOpenCode`/`DetectGentleAI` via LookPath + version. |
| REQ-TOOLS-2 | ✅ Implemented | `InstallOpenCode` with npm writable preflight, sudo display-only, red fail display-only. |
| REQ-TOOLS-3 | ✅ Implemented | `InstallGentleAI` with GitHub release, checksum fail-closed, atomic swap via `update.ApplyUpdate`, display-only fallback. |
| INSTALL | ⚠️ Partial | Count derived from `len(opencode.QuantLabAgentNames())`. Install suggests onboarding when missing. No test verifies guardian-orchestrator is included in merged agents or that count matches overlay. |
| STATUS | ❌ Missing | `detectIssues` does NOT emit "SQX folder moved — run 'quantlab configure' to update" when `InstallPath` is missing. Required by spec. |
| REQ-INS-1 | ✅ Implemented | `SQXConfig{InstallPath, CLIPath}` + `ResolveSQXCliPath` + `ValidateSQXPath`; `JForexConfig` with `AccountMode demo|live`, default `demo`. |
| REQ-INS-2 | ✅ Implemented | `QuantLabAgentNames()` derived from overlay JSON; overlay contains `guardian-orchestrator` + 3 delegates. |
| CONFIGURE-WIZARD | ⚠️ Partial | Wizard collects API key, model, and SDK path. Does NOT collect SQX `install_path` or JForex `account_mode`/`install_path` as required by spec. |
| VALIDATE-PATH | ✅ Implemented | `ValidateSQXPath` checks root and `bin/` for `sqcli`/`sqcli.exe`. |
| REQ-WIZ-1 | ✅ Implemented | `NormalizeAccountMode` restricts to `demo|live`, default `demo`. |
| REQ-1 | ✅ Implemented | `quantlab-orchestrator` registered as `mode: primary` in overlay with deny-first permissions. |

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| AD-1 A2 paquete nuevo | ✅ Yes | `tui/onboarding/` + `cmdOnboarding` in `app.go` |
| AD-2 B3 híbrido | ✅ Yes | `InstallOpenCode`/`InstallGentleAI` with display-only fallback |
| AD-3 Instalaciones en handler | ✅ Yes | `cmdOnboarding` runs installs with spinner |
| AD-4 C1+C3-lite SQX | ✅ Yes | `SQXConfig{InstallPath, CLIPath}` + `ResolveSQXCliPath` + `ValidateSQXPath` |
| AD-5 D1+D2-lite JForex | ✅ Yes | `JForexConfig` with `AccountMode demo|live`, password only in config.yaml 0600 |
| AD-6 E2+E3-lite guía | ⚠️ Partial | `steps.json` embedded with checks, but `viewPostInstall` hardcodes check logic for 3 items and ignores `check` field from `steps.json`. Missing sqx/jforex checks. |
| AD-7 QuantLabAgentNames derivado | ✅ Yes | `merge.go` reads `overlay["agents"]` and derives names |
| AD-8 Model.Update() directo | ✅ Yes | Tests use `Model.Update()` without teatest |
| AD-9 `*time.Time` | ✅ Yes | `OnboardingCompletedAt *time.Time` with `omitempty` |
| AD-10 Solo SetDefaultAgent | ✅ Yes | `cmdOnboarding` calls `SetDefaultAgent` only if chosen |

### Issues Found

**CRITICAL**:
1. `detectIssues` does not implement "SQX folder moved — run 'quantlab configure' to update" when `SQX.InstallPath` is missing. Spec `quantlab-installer/spec.md` line 28 REQUIRES this. Feature is absent from current `status.go`.
2. `config_test.go` has no tests for `ResolveSQXCliPath`, `ValidateSQXPath`, or `NormalizeAccountMode`. Apply-progress claimed these were tested but they are not present in the codebase.
3. 20 spec scenarios have no covering tests: REQ-ONB-1 (primer onboarding completo), REQ-ONB-2 (flujo 14 fases), REQ-ONB-3 (herramienta ya instalada), REQ-ONB-4 (carpeta inválida), REQ-ONB-5 (password ausente de state.json), REQ-ONB-6 (checkmarks post-install), INSTALL (agent count coincide), STATUS (SQX configurado), REQ-INS-1 (4 scenarios), REQ-INS-2 (uninstall limpia), REQ-1 (4 scenarios).

**WARNING**:
4. `status.go` does not display JForex configuration (only SQX `CLIPath` shown). Spec requires status to show configured services (SQX, JForex, API keys masked).
5. `wizard.go` does not collect SQX `install_path` or JForex `account_mode`/`install_path`. Spec `quantlab-config-wizard/spec.md` requires these fields.
6. `viewPostInstall` hardcodes check logic for 3 items (`opencode`, `gentle-ai`, `primary-agent`) and ignores the `check` field from `steps.json`. Missing `sqx`/`jforex` checks.
7. `help_test.go` does not verify `onboarding` appears in general help output.
8. `TestInstallOpenCode_Integration` runs real `npm install -g` without `-short` skip. Would timeout in full suite.

**SUGGESTION**:
9. Add tests for `ResolveSQXCliPath`, `ValidateSQXPath`, and `NormalizeAccountMode` to cover REQ-INS-1 scenarios.
10. Implement "SQX folder moved" detection in `detectIssues` and add `TestDetectIssues_SQXFolderMoved`.
11. Use the `check` field from `steps.json` in `viewPostInstall` instead of hardcoding checks.
12. Add SQX/JForex collection steps to `wizard.go` or update `quantlab-config-wizard` spec to reflect the simplified wizard scope.

### Verdict

FAIL

2 blocking gaps (missing SQX folder moved implementation, missing core config tests) and 20 untested spec scenarios prevent passing verification. Build and tests pass, but spec compliance is insufficient.

## Key Learnings

1. Apply-progress claims can diverge from actual working tree; always verify file existence and test coverage independently.
2. Spec requirements marked MUST must be implemented even when not explicitly tested by the apply phase.
3. The installer overlay structure changed from `agent` to `agents` (plural), requiring coordinated updates in both Go and Python tests.
4. State persistence tests must cover end-to-end flows, not just unit-level save/load, to satisfy spec scenarios.
5. Missing `ValidateSQXPath` and `NormalizeAccountMode` tests in `config_test.go` represent a coverage gap despite the functions being implemented.
