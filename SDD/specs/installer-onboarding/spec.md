# Delta for installer-onboarding

## ADDED Requirements

### Requirement: Comando onboarding re-ejecutable (REQ-ONB-1)

El sistema MUST proporcionar el comando `quantlab onboarding` con una TUI de 5 pantallas (intro, consentimiento, SQX, JForex, post-install) y MUST persistir `OnboardingCompleted`/`OnboardingCompletedAt` en `state.json` (campos opcionales retro-compatibles; su ausencia = no completado). Re-ejecutable siempre; `install` SHALL sugerirlo si falta; `help.go` SHALL documentarlo.

#### Scenario: Primer onboarding completo

- GIVEN una máquina sin state.json previo
- WHEN el usuario completa las 5 pantallas
- THEN state.json contiene `onboarding_completed=true` y `onboarding_completed_at`
- AND el comando puede re-ejecutarse sin error

#### Scenario: Estado legacy sin flag

- GIVEN un state.json sin campos de onboarding
- WHEN se lee el estado
- THEN el onboarding se trata como no completado
- AND la lectura no falla

#### Scenario: Install sugiere onboarding

- GIVEN una instalación sin onboarding
- WHEN `quantlab install` termina
- THEN sugiere `quantlab onboarding`
- AND `quantlab help` lo lista

### Requirement: Pantalla 1 — Intro educativa (REQ-ONB-2)

La intro MUST explicar qué es QuantLab, el flujo canónico de 14 fases en orden (research → hypothesis → config → review → dispatch → monitor → retest → optimize → portfolio → compile → deploy → demo → archive → live-ops, REQ-37) y cada herramienta con su propósito: OpenCode (director de investigación), gentle-ai (orquestación SDD), StrategyQuantX (backtest vía sqcli), JForex 4 (ejecución) y Dukascopy (datos FX).

#### Scenario: Flujo de 14 fases en orden

- GIVEN el usuario inicia el onboarding
- WHEN se muestra la intro
- THEN las 14 fases aparecen en orden canónico
- AND cada herramienta lista su propósito

### Requirement: Pantalla 2 — Consentimiento granular (REQ-ONB-3)

Debe presentar por herramienta (OpenCode, gentle-ai, QuantLab SDK) por qué se necesita. El consentimiento SHALL ser individual por herramienta (aceptar/rechazar). Toda herramienta detectada como instalada SHALL mostrarse como "already installed ✓" y saltar su instalación. La instalación de terceros MUST NOT bloquear el flujo: ante fallo de red o rechazo, el flujo SHALL avanzar.

#### Scenario: Herramienta ya instalada

- GIVEN OpenCode presente en PATH
- WHEN se muestra la pantalla de consentimiento
- THEN OpenCode aparece como "already installed ✓"
- AND no se ofrece su instalación

#### Scenario: Rechazo no bloquea

- GIVEN el usuario rechaza instalar gentle-ai
- WHEN confirma la pantalla de consentimiento
- THEN el flujo avanza a la pantalla SQX

### Requirement: Pantalla 3 — Guía SQX (REQ-ONB-4)

Debe mostrar una guía breve con enlace oficial y MUST pedir la carpeta de instalación (install_path, no el binario), advirtiendo que moverla exige re-ejecutar `quantlab configure`. La validación SHALL aceptar solo carpetas con `sqcli`/`sqcli.exe` en raíz o `bin/` (ValidateSQXPath).

#### Scenario: Carpeta SQX válida

- GIVEN el usuario ingresa `/opt/SQX` con `sqcli` en la raíz
- WHEN valida la carpeta
- THEN la validación pasa y se persiste install_path
- AND `ResolveSQXCliPath()` deriva `/opt/SQX/sqcli`

#### Scenario: Carpeta inválida

- GIVEN el usuario ingresa una carpeta sin binario
- WHEN valida la carpeta
- THEN se muestra un error
- AND el usuario puede corregir o saltar la pantalla

### Requirement: Pantalla 4 — Guía JForex (REQ-ONB-5)

Debe guiar la descarga manual (exe/dmg/JForex-Installer.sh), la cuenta demo (email, 14 días hábiles) y live (verificación), y MUST pedir: carpeta, modo (`demo|live`, default `demo`) y credenciales. La password MUST persistirse solo en `~/.quantlab/config.yaml` (0600) y MUST NOT aparecer en logs, state.json ni la TUI. La guía SHALL documentar la renovación de la demo con `HUMAN_APPROVE_DEMO` (fail-closed).

#### Scenario: Config JForex demo

- GIVEN el usuario completa la pantalla con modo demo
- WHEN confirma
- THEN config.yaml guarda install_path, account_mode=demo y credenciales con 0600
- AND la password no aparece en state.json ni en logs

#### Scenario: Modo live seleccionado

- GIVEN el usuario elige account_mode=live
- WHEN se persiste la configuración
- THEN config.yaml guarda account_mode=live
- AND la guía recuerda que live requiere verificación de cuenta

### Requirement: Pantalla 5 — Post-instalación (REQ-ONB-6)

La pantalla final MUST mostrar: (1) crear carpeta de campañas (ej. `~/trading/`), (2) abrir OpenCode ahí, (3) elegir agente primario: `quantlab-orchestrator` (campañas de 14 fases) o `guardian-orchestrator` (live-ops 24/7 — REQ-822/823), (4) un prompt de ejemplo. Los pasos SHALL marcarse con checkmarks según el estado real.

#### Scenario: Guía con checkmarks según estado

- GIVEN SQX y JForex ya configurados
- WHEN se muestra la pantalla final
- THEN los pasos de SQX/JForex aparecen marcados
- AND los pasos restantes aparecen pendientes