# Propuesta: Installer Ecosystem Onboarding

## Intent

Convertir el instalador TUI de QuantLab AI (`installer/`) de un wizard técnico mínimo a una guía interactiva completa: explicar qué es QuantLab y el flujo de 14 fases, instalar con consentimiento granular las herramientas de terceros, configurar SQX y JForex, y enseñar a usar la herramienta tras la instalación.

Gaps verificados (exploration.md): el wizard solo recolecta API key/modelo/SDK path (`wizard.go:32-40`); no instala OpenCode ni gentle-ai (`install.go:77-81` solo advierte); el overlay de agentes declara 4 pero define 2 (`merge.go:16-23` vs `overlay.json`) y `guardian-orchestrator` está ausente (incumple REQ-822); `configure.go:89-92` descarta el sdkPath (nada persiste SQX/JForex); `state.go:17-27` no tiene flag de onboarding.

## Scope

### In Scope
1. **Flujo `quantlab onboarding`** (A2): paquete `installer/internal/tui/onboarding/` + comando en `app.go` + flag `OnboardingCompleted`/`OnboardingCompletedAt` en `state.State`. Pantallas: intro educativa → consentimiento por herramienta → SQX → JForex → post-install. Re-ejecutable; `install` sugiere onboarding si no está completado; `help.go` lo menciona.
2. **Instalación de terceros con consentimiento** (B3): `installer/internal/tools/` con `DetectOpenCode()`, `DetectGentleAI()` (LookPath + versión), `InstallOpenCode()` (preflight npm writable → install sin sudo; sudo → display-only), `InstallGentleAI()` (release binario a `~/.local/bin` con checksum, patrón `update.go`; fallback display-only install.sh). SDK QuantLab: solo explicar (ya se instala).
3. **Config extendida**: `SQXConfig{InstallPath, CLIPath}` + `ResolveSQXCliPath()` + `ValidateSQXPath()`; `JForexConfig{InstallPath, AccountMode, Host, Port, Username, Password}` (AccountMode default `demo`); aviso de carpeta movida en `status.go`/`detectIssues`; migración compatible (cli_path existente = override).
4. **Guía post-instalación** (E2/E3-lite): assets embebidos `internal/assets/onboarding/` con pasos + ejemplo de prompt de campaña.
5. **Alineación del overlay de agentes** (decisión 1): `guardian-orchestrator` mode primary + delegates (`quantlab-guardian`, `quantlab-guardian-alert`, `quantlab-replacement`) en overlay.json; corregir `QuantLabAgentNames()` y el count hardcodeado (`install.go:308`).

### Out of Scope
- Instalación de SQX/JForex (descarga manual guiada, no automatizable).
- Login check de JForex (D3 descartado: I/O externo frágil).
- Modificar el wizard existente para install/configure (A1 descartado: contamina configure).
- Auto-install con sudo (B1 descartado: riesgo de rotura de entorno).
- Nuevos skills/prompts del SDK; cambios al pipeline de campañas.

## Capabilities

### New
- `installer-onboarding`: flujo interactivo re-ejecutable, consentimiento granular, estado OnboardingCompleted, guía post-instalación.
- `installer-tools-install`: detección e instalación de OpenCode y gentle-ai (B3 híbrido, fallback display-only).

### Modified
- `quantlab-installer`: modelo SQX install_path/cli_path; JForex install_path/account_mode; aviso de carpeta movida; overlay alineado (guardian-orchestrator + delegates); install sugiere onboarding.
- `quantlab-config-wizard`: recolecta/valida install_path de SQX (carpeta) y account_mode de JForex.
- `quantlab-orchestrator`: REQ-1 — alinear `mode` a `primary` (spec dice subagent; overlay y máquina viva dicen primary; consistente con REQ-822).

## Approach

1. **Onboarding TUI (A2)**: paquete nuevo `internal/tui/onboarding/` (reutiliza estilos/progressBar por paquete compartido), `cmdOnboarding` en `app.go`, flags en `state.State` (retro-compatibles, JSON opcional). Pantalla intro usa `docs/PRD.md` + `quantlab-run-campaign/SKILL.md` (14 fases: research → … → live-ops) y las herramientas (OpenCode, gentle-ai, SQX, JForex 4, Dukascopy). Consentimiento por herramienta con skip si ya instalada ("already installed ✓"). Re-ejecución siempre disponible.
2. **Tools (B3)**: preflight npm writable (detecta nvm/fnm/volta); sin sudo → `npm install -g opencode-ai`; con sudo → display-only (patrón `gentle-ai internal/installcmd/resolver.go:41-54`). gentle-ai: descarga GoReleaser a `~/.local/bin` con checksum; plataforma sin release o fallo de red → display-only. Nunca bloquear el onboarding por fallo de instalación.
3. **Config**: `ResolveSQXCliPath()` = InstallPath + `/sqcli` (o `sqcli.exe`), CLIPath como override; `ValidateSQXPath()` busca binario en raíz y `bin/`. `detectIssues` emite "SQX folder moved — run 'quantlab configure' to update" si InstallPath no existe. JForex: solo persiste config en `~/.quantlab/config.yaml` (0600 ya garantizado); password nunca en logs ni estado.
4. **Guía post-instalación**: `embed.FS` con pasos + checkmarks según estado real: (1) crear carpeta de campañas (ej. `~/trading/`), (2) abrir OpenCode ahí, (3) elegir `quantlab-orchestrator` (campañas, 14 fases) o `guardian-orchestrator` (live-ops 24/7: monitoreo, alertas, reemplazo — REQ-822/823), (4) prompt de ejemplo de campaña.
5. **Overlay**: agregar `guardian-orchestrator` (mode primary, deny-first espejo de quantlab-orchestrator) + 3 delegates al overlay.json; `QuantLabAgentNames()` derivado del overlay (única fuente de verdad) en vez de lista hardcodeada; count de `install.go` derivado; delta spec para REQ-1.

## Key Decisions

- **KD-1 — Overlay en este change**: el onboarding promete `guardian-orchestrator` como opción de agente primario; lo que promete debe instalar. Justificado por REQ-822 (MUST mode primary) y el prompt `ai/opencode/agents/guardian-orchestrator.md`. Alternativa (cambio hermano) descartada: acoplamiento y promesa vacía en la guía.
- **KD-2 — B3 híbrido confirmado**: tradeoff — B1 automatiza todo pero ejecuta sudo (riesgo de rotura de entorno); B2 es cero riesgo pero no es "automático" como pide el requisito. B3 cubre el 80% sin sudo y degrada a display-only (red de seguridad de gentle-ai). Costo: dos caminos de código y tests.
- **KD-3 — A2 separado**: onboarding es experiencia educativa re-ejecutable; install/configure quedan como pipeline técnico intacto.
- **KD-4 — SQX C1+C3-lite**: install_path es la semántica del requisito ("carpeta donde está instalado"); cli_path sobrevive como override (migración segura).
- **KD-5 — JForex D1+D2-lite**: sin verificación de credenciales (los agentes operan vía SDK local, no GUI); password solo en config.yaml 0600.

## Risks

| Riesgo | Prob. | Mitigación |
|--------|-------|------------|
| Red/npm/brew fallan al instalar | Med | Degradar a display-only con instrucciones; nunca bloquear el onboarding |
| gentle-ai sin release para la plataforma | Baja | Detectar y degradar a display-only (install.sh / install.ps1) |
| Demo JForex de 14 días hábiles expira | Alta | Documentar renovación con gate `HUMAN_APPROVE_DEMO` (fail-closed) en la guía |
| Password JForex en config | Baja | 0600 ya garantizado; explícito: no loguear ni mostrar |
| Migración cli_path → install_path rompe configs | Baja | cli_path queda como override válido |
| Tamaño > 400 líneas de review | Alta | Chained PRs desde sdd-tasks (delivery auto-chain confirmado) |
| TUI nueva sin cobertura | Med | Tests `teatest`/`Model.Update()` (strict_tdd, RED-first) por pantalla |

## Rollback Plan

- **Config**: campos nuevos opcionales (JSON retro-compatible); quitar InstallPath restaura comportamiento previo (CLIPath sigue funcionando). `detectIssues` avisa, no bloquea.
- **Overlay**: revertir overlay.json (fuente de verdad); `RemoveAgents` usa `QuantLabAgentNames()` — si se revierte la lista, uninstall limpia el set previo; los agentes guardian agregados se remueven con uninstall.
- **Tools**: instalaciones externas idempotentes (`npm -g`, binario en `~/.local/bin`); el journal de mutación no aplica a terceros; re-ejecución del onboarding es idempotente; display-only nunca ejecuta nada.
- **Estado**: si `onboarding_completed=true` no convence, `quantlab onboarding` siempre disponible (el flag no bloquea re-ejecución).

## Dependencies

- Patrón de referencia verificado: gentle-ai `internal/installcmd/resolver.go` (display-only) y `update.go` (checksum + swap atómico).
- REQ-822/823 (`openspec/specs/guardian-orchestrator/spec.md`) y REQ-1 (`quantlab-orchestrator`).
- Red/npm/brew para instalación; `sqcli` (SQX CLI) para validación posterior.

## Deliverables

1. Comando `quantlab onboarding` + TUI de 5 pantallas + flags de estado.
2. `internal/tools/` — Detect/Install OpenCode + gentle-ai (B3).
3. Config extendida (SQX/JForex) + `ValidateSQXPath` + aviso en `detectIssues`.
4. Assets embebidos de guía post-instalación (E2/E3-lite).
5. Overlay alineado + deltas spec: `installer-onboarding`, `installer-tools-install`, `quantlab-installer`, `quantlab-config-wizard`, `quantlab-orchestrator` (REQ-1).

**Criterios de éxito**: onboarding completo → `state.json` con `onboarding_completed=true`; `status` muestra SQX/JForex configurados y emite aviso de carpeta movida; overlay contiene `guardian-orchestrator` mode primary y el count de agentes coincide con el overlay; `quantlab onboarding` re-ejecutable; tests TUI verdes (`SQX_FORCE_MOCK=1 python3 -m pytest -q` para SDK, `go test ./...` para installer); cada PR ≤ 400 líneas.