# Design: Installer Ecosystem Onboarding

## Technical Approach

Convertir el installer en una experiencia guiada sin tocar el pipeline técnico. Tres capas nuevas sobre el esqueleto existente:

1. **`quantlab onboarding`** (A2): TUI Bubbletea nueva en `installer/internal/tui/onboarding/`, desacoplada del wizard técnico (`wizard.go:32-40`) que queda intacto para install/configure. El modelo recolecta decisiones; el handler `cmdOnboarding` las aplica tras el `tea.Program` (las instalaciones corren con spinner, patrón `update.go:55`), manteniendo el `Model` puro y testeable.
2. **`internal/tools/`** (B3 híbrido): detección `LookPath` + preflight npm escribible (patrón gentle-ai `resolver.go:41-54,149-160`); instalación sin sudo, degradación display-only ante sudo/red/plataforma — nunca bloquea el flujo.
3. **Modelo/config extendido + overlay alineado**: `SQXConfig{InstallPath, CLIPath}` con `ResolveSQXCliPath()`/`ValidateSQXPath()`; `JForexConfig` con `AccountMode demo|live`; `QuantLabAgentNames()` derivado del overlay embebido (única fuente de verdad, corrige el bug `merge.go:16-23` vs `overlay.json`).

Specs cubiertas: REQ-ONB-1..6, REQ-TOOLS-1..3, REQ-INS-1..2, VALIDATE-PATH/MODE, REQ-1.

## Architecture Decisions

| # | Decisión | Opciones | Tradeoffs | Elección |
|---|----------|----------|-----------|----------|
| AD-1 | Ubicación del onboarding | A1 extender wizard / A2 paquete nuevo / A3 pasos discretos | A1 contamina configure (KD-3); A3 pierde narrativa guiada | **A2**: `tui/onboarding/` + comando `onboarding` en `app.go:27-52`; re-ejecutable vía flag de estado |
| AD-2 | Instalación de terceros | B1 auto total / B2 display-only / B3 híbrido | B1 ejecuta sudo (riesgo entorno); B2 no es "automático" | **B3**: npm writable → `exec`; sudo → display-only; fallo red → display-only (`resolver.go:264-268` como referencia) |
| AD-3 | Dónde corren las instalaciones | Dentro del `Model` (tea.Cmd) / en `cmdOnboarding` tras el Program | Cmd async complica tests y el journal; síncrono con spinner es el patrón del repo | **En el handler** (`update.go:55` spinner); el `Model` solo recolecta consentimiento → `Model.Update()` puro testeable |
| AD-4 | Modelo SQX | C1 install_path+cli_path override / C2 solo cli_path / C3 autodetección | C2 confunde (carpeta vs binario); C3 heurístico frágil | **C1+C3-lite**: `InstallPath` canónico, `CLIPath` override (migración segura KD-4); validación en raíz o `bin/` |
| AD-5 | JForex | D1 campos+modo / D2 validación / D3 login check | D3 I/O externo frágil (KD-5) | **D1+D2-lite**: `account_mode demo\|live`, default `demo`; password solo `config.yaml` 0600 (`config.go:96`) |
| AD-6 | Guía post-instalación | E1 texto fijo / E2 embed.FS / E3 dinámica | E1 no actualizable; E3 compleja | **E2+E3-lite**: `assets/onboarding/steps.json` con checkmarks según estado real (patrón `assets.go:10`) |
| AD-7 | Fuente de `QuantLabAgentNames()` | Lista hardcodeada / derivada del overlay | Hardcodeada ya mintió (4 vs 2) | **Derivada del overlay embebido** (`merge.go:11-12`), ordenada; count en `install.go:308` = `len(...)` |
| AD-8 | Tests TUI | teatest / `Model.Update()` directo | teatest no está en `go.mod` (dependencia nueva) | **`Model.Update()` directo**, patrón `wizard_test.go:46-66`; cero deps nuevas |
| AD-9 | `OnboardingCompletedAt` | `time.Time` / `*time.Time` | `time.Time` con `omitempty` NO se omite en JSON (struct) | **`*time.Time`** — `nil` → campo ausente (retro-compatible) |
| AD-10 | Agente primario vs ownership | Re-capturar marker / solo mutar valor | Re-capturar invalida la restauración pre-QuantLab | **Solo `SetDefaultAgent`** (`config.go:132`); el marker (`ownership.go:76-83`) ya capturó `PreviousDefaultAgent` — uninstall restaura el valor original |

### AD-10 detalle — ownership NO cambia

`PrepareInstall` captura `PreviousDefaultAgent` una sola vez durante install (`ownership.go:46-55`). El onboarding, si el usuario elige agente primario en la pantalla final, llama `opencode.SetDefaultAgent` + `WriteSettings` y espeja el valor en `sdk-config.yaml` (`DefaultAgent`, `sdk/config.go:21,31`). El marker queda intacto: `UninstallPlan.Apply` (`ownership.go:120-152`) restaura el valor pre-QuantLab (p. ej. `gentle-orchestrator` en la máquina viva, `exploration.md:33`). La elección es un delta del valor actual, no una re-captura de propiedad.

## Sequence Diagrams

### 1. Flujo `quantlab onboarding`

```
user ──quantlab onboarding──▶ app.cmdOnboarding (nuevo: app/onboarding.go)
  ├─▶ state.LoadOrInit(qlDir) ──▶ state.json (legacy sin flag = no completado)
  ├─▶ tools.DetectOpenCode / DetectGentleAI ──▶ PATH (--version)
  ├─▶ tea.NewProgram(onboarding.Model)           ┌─ StepIntro (14 fases + herramientas)
  │    5 pantallas (wizard.go:32-40 como patrón) ├─ StepConsent (3 tools, "already installed ✓")
  │                                              ├─ StepSQX (ValidateSQXPath)
  │                                              ├─ StepJForex (demo|live, password enmascarada)
  │                                              └─ StepPostInstall (guía embed, checkmarks)
  ├─ Model.Result() ──▶ {consent, sqx, jforex, primaryAgent}
  ├─▶ config.WriteConfig(0600) ──▶ ~/.quantlab/config.yaml   (jamás password en logs)
  ├─▶ tools.Install* consentidos (spinner) ──▶ npm / ~/.local/bin ──degradan──▶ display-only
  ├─▶ opencode.SetDefaultAgent (si primaryAgent) ──▶ ~/.config/opencode/opencode.json
  │     └─▶ sdk.WriteSDKConfig (default_agent espejo)
  └─▶ st.OnboardingCompleted=true; Save ──▶ state.json
```

`install` (tras `install.go:137-138`): si `!st.OnboardingCompleted` imprime `Run 'quantlab onboarding' to learn how to use QuantLab`.

### 2. `InstallOpenCode` (REQ-TOOLS-2)

```
consent(opencode)=true
  ─▶ DetectNpmWritable()            # nvm (~/.nvm/NVM_DIR), fnm, volta + npm prefix
      ├─ writable ─▶ exec npm install -g --ignore-scripts opencode-ai@latest
      │               ├─ ok ─▶ ✓ Installed
      │               └─ err ─▶ display-only: "sudo npm install -g --ignore-scripts opencode-ai@latest"
      └─ no-writable ─▶ display-only (NUNCA se ejecuta sudo)
```

### 3. `InstallGentleAI` (REQ-TOOLS-3)

```
consent(gentle-ai)=true
  ─▶ update.LatestGitHubRelease("gentleman-programming","gentle-ai")   # reuso update.go:37
      ├─ asset gentle-ai_{v}_{os}_{arch}.tar.gz (FindAssetForPlatform, update.go:76)
      │    ├─ sí ─▶ descarga (update.go:236) → ParseChecksum (update.go:159, fail-closed)
      │    │         ├─ match ─▶ extraer tar.gz → swap atómico ~/.local/bin/gentle-ai
      │    │         └─ mismatch ─▶ descartar → display-only install.sh
      │    └─ no (Windows) ─▶ display-only install.ps1
      └─ red fail ─▶ display-only
```

## Data / Config Model

```go
// state.go:17-27 — campos nuevos (AD-9)
type State struct {
    // ...existentes...
    OnboardingCompleted   bool       `json:"onboarding_completed,omitempty"`
    OnboardingCompletedAt *time.Time `json:"onboarding_completed_at,omitempty"`
}

// config.go:16-27 — modelo extendido (AD-4/5)
type SQXConfig struct {
    InstallPath string `yaml:"install_path"`          // carpeta canónica
    CLIPath     string `yaml:"cli_path"`              // override opcional (migración)
}
func (c *SQXConfig) ResolveSQXCliPath() string        // CLIPath gana; si no, InstallPath + /sqcli (o sqcli.exe en windows); default /opt/SQX/sqcli
func ValidateSQXPath(dir string) error                // sqcli|sqcli.exe en raíz o bin/

type JForexConfig struct {
    InstallPath string `yaml:"install_path"`
    AccountMode string `yaml:"account_mode"`          // demo|live, "" → "demo"
    Host        string `yaml:"host"`
    Port        int    `yaml:"port"`
    Username    string `yaml:"username"`
    Password    string `yaml:"password"`              // SOLO config.yaml 0600
}
func NormalizeAccountMode(mode string) (string, error) // validación reutilizable (wizard + onboarding)

// internal/tools/ — API nueva (vars package-level para testability, patrón resolver.go:17)
type DetectResult struct { Installed bool; Path, Version string }
func DetectOpenCode() DetectResult
func DetectGentleAI() DetectResult
type NpmPreflight struct { Writable bool; Manager, Reason string }
func DetectNpmWritable() NpmPreflight
type InstallOutcome struct { Installed bool; DisplayOnly string }
func InstallOpenCode() InstallOutcome                  // degrada, no retorna error fatal
func InstallGentleAI() InstallOutcome

// internal/tui/onboarding/
type Step int
const ( StepIntro Step = iota; StepConsent; StepSQX; StepJForex; StepPostInstall; stepCount )
type Model struct {
    step Step
    detections map[string]tools.DetectResult
    consent    map[string]bool   // opencode | gentle-ai | quantlab-sdk (ya instalado: solo explicar)
    sqxInput   textinput.Model   // EchoMode password para JForex (patrón wizard.go:81-82)
    primaryAgent string          // "quantlab-orchestrator" | "guardian-orchestrator" | ""
}
func (m Model) Result() Result
type Result struct {
    Consent        map[string]bool
    SQXInstallPath string
    JForex         config.JForexConfig
    PrimaryAgent   string
}
```

**`sdk-config.yaml`**: el onboarding NO lo reescribe salvo `default_agent` cuando el usuario elige agente primario (AD-10). `DefaultSDKConfig` (`sdk/config.go:31`) conserva `quantlab-orchestrator` como default. `install.go:205-219` sigue escribiendo el archivo como hasta ahora.

**Overlay** (`overlay.json` — fuente única de verdad): añade `guardian-orchestrator` (mode `primary`, deny-first espejo de REQ-822: `bash *:deny` + allow `sdk/quantlab/*`, `knowledge/*`, `/tmp/opencode/*`; `task *:deny` + los 3 delegates; `question allow`; prompt `{file:~/.config/opencode/prompts/quantlab/guardian-orchestrator.md}`) + subagents `quantlab-guardian`, `quantlab-guardian-alert`, `quantlab-replacement` (mode `subagent`, hidden, deny-first). REQ-1 ya está satisfecho en código (`overlay.json:5` `mode: primary`); el delta spec solo alinea la documentación.

```go
// merge.go — QuantLabAgentNames() derivado (AD-7)
func QuantLabAgentNames() []string {
    var overlay map[string]any
    if err := json.Unmarshal(overlayJSON, &overlay); err != nil { return nil }
    agents, _ := overlay["agent"].(map[string]any)
    names := make([]string, 0, len(agents))
    for name := range agents { names = append(names, name) }
    sort.Strings(names) // determinismo en tests
    return names
}
```

**Guía post-instalación** (`assets/onboarding/steps.json`, embed vía `assets.go:10` extendido): pasos `{id, title, body, check}` donde `check ∈ {opencode, gentleai, sqx, jforex, always, none}` — el render del paso final consulta detección/config real para checkmarks (E3-lite). Contenido: (1) crear carpeta de campañas (`~/trading/`), (2) `opencode` ahí, (3) elegir agente primario (`quantlab-orchestrator` 14 fases vs `guardian-orchestrator` live-ops REQ-822/823, con renovación demo `HUMAN_APPROVE_DEMO` fail-closed — `docs/PRD.md` + `exploration.md:47`), (4) prompt ejemplo de campaña.

## File Changes

| File | Acción | Descripción |
|------|--------|-------------|
| `installer/internal/tui/onboarding/onboarding.go` | Create | Model Bubbletea 5 pasos + Result() (reusa estilos `wizard/style.go` exportados) |
| `installer/internal/tui/onboarding/onboarding_test.go` | Create | Tests `Model.Update()` directo por pantalla (AD-8) |
| `installer/internal/tools/detect.go` | Create | `DetectOpenCode/DetectGentleAI` (LookPath + `--version`) |
| `installer/internal/tools/npm.go` | Create | `DetectNpmWritable` (nvm/fnm/volta + npm prefix) |
| `installer/internal/tools/opencode.go` | Create | `InstallOpenCode` (exec sin sudo / display-only) |
| `installer/internal/tools/gentleai.go` | Create | `InstallGentleAI` (release + checksum + swap atómico / display-only) |
| `installer/internal/tools/*_test.go` | Create | Table-driven con mocks de `cmdLookPath`/HTTP |
| `installer/internal/assets/onboarding/steps.json` | Create | Guía post-instalación (E2/E3-lite) |
| `installer/internal/assets/prompts/guardian-orchestrator.md` | Create | Prompt instalado vía `InstallPrompts` (patrón `skills.go:70-106`) |
| `installer/internal/app/onboarding.go` | Create | `cmdOnboarding` (persiste config/state, instala, display-only) |
| `installer/internal/app/app.go` | Modify | `case "onboarding"` (`app.go:27-52`) |
| `installer/internal/app/help.go` | Modify | Listar `onboarding` en general help + `commandHelp` + `validCommands` (`help.go:203-206`) |
| `installer/internal/app/install.go` | Modify | count derivado (`install.go:308` → `len(opencode.QuantLabAgentNames())`); sugerencia onboarding tras `install.go:137-138` |
| `installer/internal/app/status.go` | Modify | Mostrar SQX/JForex configurados (`status.go:160`); `detectIssues` gana param `cfg` + aviso carpeta movida (`status.go:184`) |
| `installer/internal/app/configure.go` | Modify | Persistir `install_path`/`account_mode` (hoy descartado, `configure.go:89-92`) |
| `installer/internal/config/config.go` | Modify | Structs + `ResolveSQXCliPath`/`ValidateSQXPath`/`NormalizeAccountMode` |
| `installer/internal/state/state.go` | Modify | Flags onboarding (AD-9) |
| `installer/internal/opencode/merge.go` | Modify | `QuantLabAgentNames()` derivado del overlay |
| `installer/internal/opencode/overlay.json` | Modify | `guardian-orchestrator` + 3 delegates |
| `installer/internal/tui/wizard/wizard.go` | Modify | Steps nuevos SQX path / JForex (install_path, account_mode) + `Result()` struct — instalación/configure recolectan el modelo nuevo (spec config-wizard) |
| `installer/internal/assets/assets.go` | Modify | `//go:embed skills prompts templates onboarding` |

## Test Strategy (strict_tdd, RED-first)

| Pieza | Tests RED | Enfoque |
|-------|-----------|---------|
| state | Legacy sin flags → `OnboardingCompleted=false` sin error; Save persiste `onboarding_completed_at` | Table-driven, `t.TempDir()` (`state_test.go` patrón) |
| config | `ResolveSQXCliPath` override/derivado/windows; `ValidateSQXPath` raíz/`bin/`/inválido; `NormalizeAccountMode` "" → demo, `paper` → error | Table-driven puro |
| tools detect | OpenCode/gentle-ai instalado (mock `cmdLookPath`+version) / ausente → no fatal | Mock vars (patrón `resolver.go:17`) |
| tools npm | writable → ejecuta npm; no-writable → NO exec + display-only con sudo; red fail → display-only | Mock `exec.Command` + `t.TempDir()` |
| tools gentleai | checksum mismatch → no activa; swap atómico en `~/.local/bin`; plataforma sin release → display-only | Mock HTTP + `t.TempDir()` |
| onboarding TUI | intro→consent; rechazo avanza a SQX; SQX inválido → error, permanece; password enmascarada; post-install checkmarks según estado | `Model.Update()` directo (`wizard_test.go:46-66`), sin teatest (AD-8) |
| app onboarding | home aislado: state.json `onboarding_completed=true`, password AUSENTE de state.json; install sin onboarding → sugiere (stdout capturado); help lista onboarding | `cmdInstallHome` patrón (`install.go:42`), `t.TempDir()` |
| opencode overlay | `QuantLabAgentNames()` == keys overlay; `MergeAgents` incluye guardian+delegates; `RemoveAgents` limpia set completo | Golden/table-driven (`merge_test.go` patrón) |
| status | "SQX folder moved — run 'quantlab configure' to update" cuando install_path no existe; silencio cuando existe | `detectIssues` con cfg fabricado |

Integración `sqcli`/`.cfx`: `ValidateSQXPath` es el gate de la carpeta cuyo `sqcli` genera los `.cfx` (config.yaml del repo: `agents.quantlab-orchestrator.sqcli.path` apunta a `assets/SQX_144_2953_linux_20260601/sqcli`, `openspec/config.yaml:74`); el aviso de carpeta movida protege la generación posterior de `.cfx` en el SDK.

## Threat Matrix

`references/threat-matrix.md` — aplica parcialmente (este diseño añade ejecución de comandos externos y activación de binarios):

| Boundary | Casos mínimos adversos | Aplicabilidad | Respuesta de diseño | Tests RED planeados |
|---|---|---|---|---|
| Documentation-like paths | `requirements.txt`, `CMakeLists.txt`, executable Markdown, `README.sh` | N/A — los assets de guía son markdown/JSON informativo; ningún asset se ejecuta ni se clasifica como ejecutable | — | — |
| Git repository selection | `git -C`, rutas relativas/absolutas | N/A — el diseño no invoca git | — | — |
| Commit state | staged, `commit -a`, empty index | N/A — sin git | — | — |
| Push state | tracking branch, primer push, refspec | N/A — sin git | — | — |
| PR commands | `--head` explícito, prefijo env, comandos compuestos | N/A — sin automatización de PRs | — | — |
| **Ejecución de comandos externos** | `npm install -g --ignore-scripts opencode-ai@latest`; descarga+activación de binario en `~/.local/bin` | **Applicable** | Consentimiento granular por herramienta; preflight npm escribible antes de `exec`; `sudo` NUNCA se ejecuta (display-only); checksum SHA-256 fail-closed antes de activar (`update.go:266-275`); swap atómico; todo fallo degrada a display-only sin bloquear el onboarding | Uno por caso: writable→exec; no-writable→no exec+display-only; checksum mismatch→no activa; release ausente→display-only; fallo red→display-only |

## Migration / Rollout

- **Config**: campos nuevos opcionales; `cli_path` existente sigue siendo override válido (`ResolveSQXCliPath` lo gana). Sin migración de datos.
- **Estado**: flags `omitempty`; ausencia = no completado (REQ-ONB-1).
- **Overlay**: `sync` re-mergea los agentes nuevos (`sync.go:76-103`); `uninstall` limpia el set derivado (`RemoveAgents`); agentes guardian ya presentes en la máquina viva se absorben sin duplicados. No requiere rollout por fases.
- **SDK**: sin cambios; `sdk-config.yaml` intacto salvo `default_agent` si el usuario elige.

## Risks

| Riesgo | Prob. | Mitigación |
|--------|-------|------------|
| teatest ausente del go.mod (AD-8) | Alta | Tests `Model.Update()` directo — patrón del repo, sin dependencia nueva |
| Ejecución real de `npm install -g` en tests | Med | Integración marcada `testing.Short()` skip (skill go-testing); mocks de `exec.Command` |
| Overlay cambia el count de agentes (4→6) en estados existentes | Med | `sync` actualiza componentes; count derivado elimina los "nombres fantasma" (`merge.go:16-23`) |
| Wizard extendido rompe `install_test.go` existente | Baja | Steps nuevos son aditivos; `Result()` → struct con campos legacy primero |
| Password JForex en state.json por error de wiring | Baja | Test explícito: password ausente de state.json (table del app layer) |
| Tamaño > 400 líneas de review | Alta | Chained PRs desde sdd-tasks (auto-chain confirmado) |

## Open Questions

- [ ] ¿`quantlab-sdk` se ofrece como herramienta "explicar solo" en el consentimiento, o se omite de la lista (ya lo instala `install`)? (Diseño asume: aparece como "already installed ✓" informativo.)
- [ ] ¿La elección de agente primario debe ser obligatoria en la pantalla final o opcional (default `quantlab-orchestrator`)? (Diseño asume: opcional, no cambia nada si se omite.)