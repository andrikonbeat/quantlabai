# Exploración: Installer Ecosystem Onboarding

**Change**: `installer-ecosystem-onboarding`
**Fecha**: 2026-08-19
**Fase**: sdd-explore (hybrid: OpenSpec + Engram)

---

## 1. Estado Actual (gaps verificados con file:line)

### 1.1 Wizard actual (Go, Bubbletea)
- `installer/internal/tui/wizard/wizard.go:32-40` — wizard lineal de 6 pasos: `StepWelcome → StepAPIKey → StepModel → StepSDKPath → StepSummary → StepConfirm`. `stepCount` sentinel.
- `wizard.go:314-326` — `welcomeView()` minimalista: solo dice "This wizard will help you configure your QuantLab AI SDK connection" + 3 bullets (API key, model, SDK path). NO explica qué es QuantLab, el flujo de 14 fases, ni el valor.
- `wizard.go:385-387` — `Result()` devuelve solo `(apiKey, model, sdkPath)`. No hay colección de SQX path, JForex, ni consentimiento de herramientas.
- El wizard se usa tanto en `install` (`install.go:84-110`) como en `configure` (`configure.go:54-64`) — ambos crean `wizard.NewModel()` directamente.

### 1.2 Instalación de herramientas
- `installer/internal/app/install.go:77-81` — solo **warning** si OpenCode no está en `~/.config/opencode/opencode.json`: "OpenCode is recommended for full QuantLab functionality". NO instala OpenCode.
- NO hay mención de gentle-ai en todo el installer (grep verificado).
- `install.go:222-232` — sí instala el QuantLab SDK (venv + pip, editable si `--sdk-path`).
- `install.go:235-245` — merge de agentes en opencode.json.
- `install.go:248-285` — skills + prompts.
- `install.go:288-298` — ownership marker de `default_agent` (NO lo modifica, solo captura — `opencode/ownership.go:57-59`).

### 1.3 Overlay de agentes — inconsistencia verificada
- `installer/internal/opencode/overlay.json` define SOLO 2 agentes: `quantlab-orchestrator` (mode primary) y `quantlab-campaign` (subagent hidden).
- `opencode/merge.go:16-23` — `QuantLabAgentNames()` declara 4: `quantlab-orchestrator`, `quantlab-campaign`, `quantlab-deploy`, `quantlab-monitor`. **`quantlab-deploy` y `quantlab-monitor` NO tienen definición en el overlay** → el estado registra "4 agents" (`install.go:308` hardcodea count=4) pero solo se crean 2.
- `guardian-orchestrator` NO está en el overlay del installer, aunque:
  - Existe el prompt en repo: `ai/opencode/agents/guardian-orchestrator.md` (6.1K, con routing GUARDIAN-LIVE y delegados `quantlab-guardian`, `quantlab-guardian-alert`, `quantlab-replacement`).
  - Existe spec: `openspec/specs/guardian-orchestrator/spec.md` REQ-822: "MUST define `guardian-orchestrator` as a first-class OpenCode agent ... `mode: primary`, visible, deny-first permissions mirroring quantlab-orchestrator".
  - En la máquina viva (`~/.config/opencode/opencode.json`) SÍ está definido `guardian-orchestrator` (mode primary) + `quantlab-guardian` + `quantlab-guardian-alert` + `quantlab-replacement` + 14 `quantlab-phase-*` — pero **ninguno de esos está en el overlay.json del installer**. Fueron agregados por otros cambios (guardian-orchestrator-feedback, archived 2026-08-13) o manualmente, no por el installer.
  - La spec `quantlab-orchestrator/spec.md` REQ-1 dice que debe registrarse como `mode: subagent`, pero el overlay lo define como `mode: primary`. Contradicción de spec vs. realidad.
- `default_agent` en la máquina viva: `gentle-orchestrator` (ownership marker: `~/.config/opencode/.quantlab-default-agent.json` con `previous_default_agent: gentle-orchestrator`).

### 1.4 SQX
- `installer/internal/config/config.go:17-19` — `SQXConfig{CLIPath string}` default `/opt/SQX/sqcli` (`config.go:47-49`).
- `installer/internal/app/configure.go:89-92` — el sdkPath del wizard se **descarta**: "Store SDK path as SQX path placeholder for now (the config structure uses SQX for generic paths)" — comentario que delata que nunca se persiste.
- `status.go:160` — imprime `cfg.SQX.CLIPath` sin validar que exista ni que sea ejecutable.
- `detectIssues` (`status.go:184-240`) no chequea SQX path.
- No hay noción de `install_path` (carpeta) vs `cli_path` (binario). El modelo actual es solo binario.

### 1.5 JForex
- `config.go:22-27` — `JForexConfig{Host, Port, Username, Password}` default `localhost:19790`.
- Nada escribe JForex desde el wizard ni el installer. No hay account_mode (demo/live), no hay install_path, no hay validación.
- SDK: `sdk/quantlab/phase4/jforex_deploy.py` — `JForexDeployer`: exporta estrategias SQX a `.java` vía HTTP API del daemon SQX (`AsyncSQXClient`, `DEFAULT_PORT=5050` en `http_client.py:25`), compila a `.jfx` con JDK (`QUANTLAB_JDK_HOME`), `deploy_indicators` copia a la carpeta de estrategias de JForex.
- `docs/multi-agent/deployment.md` — `jforex_path: "/opt/JForex"`, estrategias en `/opt/JForex/strategies/`.
- `sdk/quantlab/phase4/demo_deploy.py` — ventana demo de **14 días hábiles** (WINDOW_DAYS=14), renovación con gate `HUMAN_APPROVE_DEMO` fail-closed.
- `docs/sqx-builder-config/4 - Conectar-LLM-a-Trading.md:1012-1022` — MCP oficial de Dukascopy (`ai.dukascopy.com`), JForex API/FIX API, `dukas-proxy`/`dukascopy-node`.

### 1.6 Post-instalación y estado
- `install.go:137-138` — tras instalar solo dice "Run 'quantlab status' to verify". NO hay guía de uso.
- `installer/internal/state/state.go:17-27` — `State` NO tiene flag `onboarding_completed` ni marca de SQX/JForex configurados.
- `help.go` — texto estático, sin mencionar onboarding.
- No existe comando `onboarding` en `app.go:27-52` (install/uninstall/sync/update/configure/dashboard/status/version/help).

---

## 2. Análisis de Opciones de Diseño

### 2a. Arquitectura de la guía interactiva

| Opción | Pros | Contras | Esfuerzo |
|--------|------|---------|----------|
| **A1: Extender el wizard existente** con más steps (intro educativa, consentimiento por herramienta, SQX path, JForex, post-install) | Un solo flujo; reutiliza `progressBar()`, estilos, tests existentes | El wizard se usa también en `configure` — mezclaría onboarding con re-configuración; los steps educativos/consentimiento no aplican a configure; wizard.js se vuelve monolítico (hoy 390 líneas, ~1000+ proyectadas) | Med |
| **A2: Nuevo wizard de onboarding separado** (`internal/tui/onboarding/`) + comando `quantlab onboarding` + flag `onboarding_completed` en state.json | Separación de concerns: install/configure quedan como están; onboarding es re-ejecutable (`onboarding_completed=false` re-triggers); pantallas educativas no contaminan configure | Duplicación parcial de estilos/progressBar (se puede compartir por paquete); requiere wiring nuevo en app.go + state.go + tests nuevos | Med |
| **A3: Onboarding como secuencia de pantallas de estado (no-wizard)** — comandos `quantlab onboarding` que ejecutan pasos discretos con confirmaciones puntuales | Menos TUI state-machine; más fácil de testear (cada paso es una función pura) | Pierde la narrativa guiada continua; el usuario pierde el hilo; menos "experiencia de guía" que pide el requisito | Bajo-Med |

**Recomendación 2a: A2.** El requisito pide una "guía interactiva" con storytelling (explicar → consentir → instalar → configurar → guiar uso), lo cual es un flujo distinto al wizard de configuración existente. A2 permite que `install` siga siendo el pipeline técnico y `onboarding` sea la experiencia educativa, re-ejecutable con flag en state.json. El wizard existente se mantiene intacto para install/configure.

### 2b. Instalación automática de OpenCode + gentle-ai + QuantLab SDK

Referencia verificada en gentle-ai (`/home/ogzuz/Proyectos/gentle-ai`):
- `internal/installcmd/resolver.go:41-54` — `resolveOpenCodeInstall()`: macOS → `brew install anomalyco/tap/opencode`; linux/windows → `npm install -g opencode-ai` (con `sudo` si npm no es escribible — preflight npm). 
- `scripts/install.sh` — gentle-ai se instala vía: brew tap `Gentleman-Programming/homebrew-tap` (recomendado), `go install` (beta), o binario de GitHub Releases (GoReleaser: `gentle-ai_{version}_{os}_{arch}.tar.gz`). Requiere curl+git. Solo macOS/Linux (Windows vía install.ps1).
- `internal/installcmd/` — la mayoría de comandos son **display-only** (muestran el comando al usuario, no lo ejecutan) — ver `agentInstallStep` en `internal/cli/run.go` (Claude Code/Kilocode "display text only, never executed").

| Opción | Pros | Contras | Esfuerzo |
|--------|------|---------|----------|
| **B1: Ejecutar instalación directa desde el installer** (replicar resolver.go: brew/npm para OpenCode; download release binario de gentle-ai con checksum; pip para SDK) | Automatización real como pide el requisito; UX integrada | Ejecutar `sudo npm install -g` requiere manejo de elevación y fallos; descargar binarios de GitHub requiere lógica de releases/checksum (similar a `update.go` ya existente); riesgo de romper config del usuario si brew/npm falla a medias | Alto |
| **B2: Mostrar comandos (display-only) + verificación** — patrón exacto de gentle-ai: detectar si está instalado (`which opencode`/`which gentle-ai`), si no, mostrar el comando exacto a copiar, y verificar después de que el usuario lo ejecute | Cero riesgo de ejecución; consistente con el patrón verificado de gentle-ai; el requisito dice "con el consentimiento del usuario y explicando por qué" — mostrar+confirmar cumple; mucho más simple y testeable | Menos "automático" — el usuario debe salir de la TUI a ejecutar | Bajo |
| **B3: Híbrido** — instalar automáticamente lo seguro (npm opencode con preflight npm writable, binario gentle-ai a `~/.local/bin` SIN sudo, pip SDK ya existente) y display-only lo que requiere sudo | Cubre el 80% sin sudo; el resto se delega al usuario con instrucciones | Dos caminos = más código y tests; la detección de "npm writable" es frágil (nvm/fnm/volta) | Med-Alto |

**Recomendación 2b: B3 con preflight estricto.** El requisito pide "instalar automáticamente todas las herramientas de terceros que pueda CON el consentimiento del usuario". "Que pueda" es la clave: instalar sin sudo cuando el entorno lo permite (npm writable, binario a `~/.local/bin`), y degradar a display-only cuando se requiera elevación. La detección de ya-instalado (`LookPath` + `--version`) debe ofrecer skip con "already installed ✓". El SDK QuantLab ya se instala (`install.go:222-232`), solo falta explicarlo en el onboarding. El patrón de display-only de gentle-ai es la red de seguridad para los casos sudo.

### 2c. SQX: persistencia y validación del path

| Opción | Pros | Contras | Esfuerzo |
|--------|------|---------|----------|
| **C1: Cambiar modelo a `install_path` + resolver de `cli_path`** — `SQXConfig{InstallPath, CLIPath}`; CLIPath queda como override opcional; `ResolveSQXCliPath()` = install_path + `/sqcli` (o `sqcli.exe` en Windows) | Semánticamente correcto: el usuario indica la carpeta descomprimida; cli_path derivado; compatible con docs (`/opt/SQX`) y con el SDK | Migración de config existente (`cli_path` ya seteado debe seguir funcionando); validación de ambos paths | Med |
| **C2: Mantener solo `cli_path`** y pedir el binario directamente en el wizard | Cero cambio de modelo | Confunde al usuario (debe buscar el binario dentro de la carpeta); el requisito pide "la carpeta donde está instalado SQX" | Bajo |
| **C3: `install_path` + detección automática** (buscar `sqcli`/`sqcli.exe` en candidates comunes + `which`) | Mejor UX si se encuentra; el wizard pre-rellena | Candidates son heurísticos; en Windows el layout difiere (sqcli.exe puede estar en `bin/`); falso-negativos confunden | Med |

**Recomendación 2c: C1 + C3-lite.** `SQXConfig{InstallPath string, CLIPath string}` donde `CLIPath` es opcional override; validación `ValidateSQXPath()` que busca `sqcli`/`sqcli.exe` en `InstallPath` (y en subcarpetas comunes `bin/`, raíz); persistencia en `~/.quantlab/config.yaml` (ya 0600 via `config.go:85-102`). Aviso de movimiento de carpeta: en `status.go`/`detectIssues` — si `InstallPath` no existe, emitir issue "SQX folder moved — run 'quantlab configure' to update" (el requisito pide avisar al usuario que si mueve la carpeta debe reconfigurar). El path se guarda en `state.json` como `sqx_install_path` derivado (o en config.yaml — config.yaml es el lugar canónico).

### 2d. JForex: campos, validación y guía

| Opción | Pros | Contras | Esfuerzo |
|--------|------|---------|----------|
| **D1: Extender `JForexConfig`** con `InstallPath string`, `AccountMode string` (demo\|live, default demo), mantener Host/Port/Username/Password | Modelo completo; default demo alineado con el flujo (demo 14 días, live requiere verificación); compatible con SDK actual (host/port localhost:19790) | Password en config.yaml (ya 0600 ✓); más campos = más validación | Bajo-Med |
| **D2: D1 + validación de instalación** (detectar `JForex` binario/`JForex-Installer.sh` en InstallPath, verificar que la carpeta existe) | El wizard avisa si la instalación manual no está completa | Detectar instalación JForex es frágil (layout varía por OS; macOS .app, linux script, windows exe) | Med |
| **D3: D1 + verificación de credenciales** (ping TCP a host:port / login check) | Confirma que la cuenta demo funciona | Login check contra Dukascopy es I/O externo frágil y lento; el SDK no tiene endpoint de login (los agentes operan via SDK local, no GUI); riesgo de timeouts en la TUI | Alto |

**Recomendación 2d: D1 + D2-lite.** Agregar `install_path` y `account_mode` (demo|live) a `JForexConfig`, con validación "carpeta existe + contiene binario/lanzador reconocible" como aviso (no bloqueante). La guía de creación de cuenta demo (email, 14 días) y live (verificación) se embebe como texto de la pantalla de onboarding. **Qué escribe el wizard**: solo config.yaml (0600, ya garantizado). **Qué NO**: nunca credenciales en logs ni en estado; password se guarda solo en config.yaml 0600; no toca la GUI de JForex ni hace login. Los agentes OpenCode operan la cuenta vía SDK (`JForexDeployer` exporta estrategias → compila → deploy a la carpeta de estrategias; la conexión real la hace la plataforma JForex con las credenciales guardadas). Documentar en la guía que el usuario debe tener JForex corriendo y logueado.

### 2e. Guía post-instalación

| Opción | Pros | Contras | Esfuerzo |
|--------|------|---------|----------|
| **E1: Pantalla final estática embebida** (texto fijo en la TUI: pasos 1-4) | Simple, testeable, sin assets | No se puede actualizar sin recompilar el binario | Bajo |
| **E2: Material embebido vía `embed.FS`** (markdown/JSON de pasos en `internal/assets/onboarding/`) | Actualizable en el binario sin tocar código; consistente con el patrón existente de skills/prompts (`assets.go`); permite texto largo legible | Un paso más de indirección (parser de markdown o estructura JSON) | Bajo-Med |
| **E3: Guía generada dinámicamente según estado** (si falta SQX → paso 1 es SQX; si ya hay todo → resumen + cómo usar) | Personalizada al estado real del usuario | Más lógica condicional y tests; la guía "ideal" del requisito es fija | Med |

**Recomendación 2e: E2 + E3-lite.** Material de pasos embebido (E2, patrón `embed.FS` ya usado) con una pasada de personalización mínima (E3-lite): marcar checkmarks según qué ya está configurado (SQX/JForex/OpenCode/gentle-ai). El contenido del paso final: (1) crear carpeta de campañas (ej. `~/trading/`), (2) `cd` + `opencode` en esa carpeta, (3) elegir agente primario: **quantlab-orchestrator** (campañas de investigación/generación: research→…→archive, 14 fases) o **guardian-orchestrator** (live-ops 24/7: monitoreo, alertas, reemplazo — REQ-822/823), (4) ejemplo de prompt de campaña ("Ejecuta una campaña completa para EURUSD M5 con riesgo 1%…").

---

## 3. Recomendación (enfoque elegido)

**Un solo change, 4 piezas coherentes:**

1. **Nuevo flujo `quantlab onboarding`** (A2): paquete `installer/internal/tui/onboarding/` + comando en `app.go` + flag `OnboardingCompleted bool` (+ `OnboardingCompletedAt`) en `state.State` (`state.go:17-27`). Pantallas: intro educativa (qué es QuantLab, flujo 14 fases — fuente `docs/PRD.md` + `skills/quantlab-run-campaign/SKILL.md`, herramientas y para qué) → consentimiento por herramienta (OpenCode, gentle-ai, SDK) → SQX (guía + carpeta) → JForex (guía demo/live + carpeta + modo) → post-install (cómo usar). Re-ejecutable: si `state.json` no tiene `onboarding_completed=true`, `install` lo sugiere al final; `quantlab onboarding` siempre disponible.

2. **Instalación de terceros con consentimiento** (B3): `installer/internal/tools/` (o reusar `installcmd`-like) con `DetectOpenCode()`, `DetectGentleAI()` (LookPath + version), `InstallOpenCode()` (npm preflight writable → install sin sudo; si requiere sudo → display-only del comando exacto, patrón gentle-ai resolver.go), `InstallGentleAI()` (release binario a `~/.local/bin` con checksum — patrón `update.go` existente; fallback display-only install.sh). SDK QuantLab ya instalado — solo explicar.

3. **Config extendida**: `SQXConfig{InstallPath, CLIPath}` con `ResolveSQXCliPath()` + `ValidateSQXPath()`; `JForexConfig{InstallPath, AccountMode, Host, Port, Username, Password}` (AccountMode default `demo`). Aviso de carpeta movida en `status.go`/`detectIssues`. Migración: `cli_path` existente sigue funcionando como override.

4. **Guía post-instalación** (E2/E3-lite): assets embebidos con pasos + ejemplo de prompt de campaña.

**Alternativas descartadas:**
- A1 (extender wizard): contamina `configure` y mezcla onboarding con configuración.
- B1 (instalación 100% automática incl. sudo): riesgo alto de rotura de entorno, contra el patrón display-only verificado de gentle-ai.
- C2 (solo cli_path): modelo semánticamente incorrecto vs. requisito "carpeta donde está instalado SQX".
- D3 (login check): I/O externo frágil e innecesario — los agentes operan vía SDK local.
- E1 (texto fijo): no actualizable sin recompilar.

**Overlay de agentes (gap colateral detectado, decidir en spec/design):** el onboarding va a explicar `quantlab-orchestrator` y `guardian-orchestrator` como opciones de agente primario, pero el overlay del installer solo define 2 agentes y `guardian-orchestrator` no está entre ellos. Recomendación: alinear el overlay con el set real (agregar `guardian-orchestrator` mode primary + definir `quantlab-deploy`/`quantlab-monitor` o corregir `QuantLabAgentNames()` a 2) — como parte de este change o cambio hermano, para que lo que el onboarding promete sea lo que el installer instala.

---

## 4. Riesgos y Límites

- **Instalación de OpenCode/gentle-ai requiere red y npm/brew funcionales.** Fallo de red → degradar a display-only con instrucciones; nunca bloquear el onboarding.
- **gentle-ai puede no tener release binario para todas las plataformas** (GoReleaser: darwin/linux amd64+arm64; Windows vía install.ps1). Detectar y degradar a display-only.
- **JForex no es automatizable** (descarga manual exe/dmg/sh + cuenta demo/live manual). La TUI solo guía y persiste config.
- **Demo de 14 días hábiles** expira; renovación semi-manual con gate `HUMAN_APPROVE_DEMO` (fail-closed, `demo_deploy.py`). Documentar en la guía.
- **Password JForex en config.yaml**: mitigado por 0600 (`config.go:85-102`), pero debe quedar explícito que no se loguea ni se muestra.
- **Cambio de modelo SQX (cli_path → install_path)**: riesgo de migración para configs existentes; el override `cli_path` cubre.
- **Overlay de agentes desalineado** (declara 4, define 2; guardian-orchestrator ausente): si no se corrige, el onboarding promete agentes que no instala.
- **Wizard actual sin tests de cobertura completa** (codegraph: "no covering tests found" para Step*); el nuevo onboarding debe llevar tests (`teatest`/`Model.Update()` per go-testing skill).
- **Presupuesto de review 400 líneas**: el cambio es grande (TUI nueva + config + estado + tools + assets). Requiere chained PRs desde `sdd-tasks`.

---

## 5. Ready for Proposal

**Sí.** Exploración completa con evidencia file:line verificada. El orquestador debe pasar a `sdd-propose` con: (a) la decisión del overlay de agentes (incluir guardian-orchestrator + corregir QuantLabAgentNames en este change o cambio hermano), (b) confirmar B3 híbrido (auto-install sin sudo + display-only con sudo) como alcance.

## Key Learnings

1. El wizard existente de QuantLab solo recolecta API key, modelo y SDK path; no toca SQX ni JForex en la práctica.
2. El overlay.json del installer declara 4 agentes pero define solo 2; guardian-orchestrator existe en repo y live config pero no en el overlay.
3. gentle-ai instala OpenCode con display-only cuando se requiere sudo, patrón de referencia para el onboarding.
4. El SDK JForex ya integra JForexDeployer (export vía HTTP API del daemon SQX en puerto 5050) y ventana demo de 14 días hábiles.
5. La config de JForex (host/port/username/password) ya existe en config.yaml con permisos 0600 pero nada la escribe desde el wizard.