# Delta for quantlab-installer

## MODIFIED Requirements

### Requirement: INSTALL — Bootstrap QuantLab

El sistema MUST validar prerrequisitos (Python 3.11+, OpenCode instalado), MUST capturar before-images vía mutation journal, MUST ejecutar el config wizard cuando no exista config, MUST crear venv + pip install del SDK, MUST deep-merge los agentes `quantlab-orchestrator`, `guardian-orchestrator` y `quantlab-*` en opencode.json, MUST escribir skills bajo `~/.config/opencode/skills/quantlab-*`, MUST setear el ownership marker de `default_agent` y MUST escribir el estado en `~/.quantlab/state.json`. Ante cualquier fallo, MUST hacer rollback de todos los pasos previos. El count de agentes registrado SHALL derivarse del overlay (única fuente de verdad), no de una lista hardcodeada; si el onboarding no está completado, install SHALL sugerir `quantlab onboarding` al final.
(Previously: merge de `quantlab-orchestrator` + `quantlab-*` desde una lista hardcodeada de 4 agentes con count fijo; sin sugerencia de onboarding)

#### Scenario: First install on clean machine (happy path)

- GIVEN una máquina con Python 3.12 y OpenCode instalados, sin instalación previa de QuantLab
- WHEN el usuario ejecuta `quantlab install`
- THEN el wizard recolecta install_path de SQX y API keys
- AND el pipeline valida prerrequisitos, crea venv, instala SDK, mergea agentes (incluido guardian-orchestrator), instala skills/prompts y escribe state.json
- AND `quantlab status` muestra todo "installed"
- AND install sugiere `quantlab onboarding`

#### Scenario: Agent count coincide con el overlay

- GIVEN el overlay.json actualizado
- WHEN install registra el componente de agentes
- THEN el count registrado es igual al número de agentes definidos en el overlay
- AND todo agente gestionado tiene definición (sin nombres fantasma)

### Requirement: STATUS — Inspect state

El sistema MUST mostrar versión, componentes, servicios configurados (SQX, JForex, API keys sin revelar valores) y detectar inconsistencias. `detectIssues` MUST emitir el aviso "SQX folder moved — run 'quantlab configure' to update" cuando `SQX.InstallPath` no existe en disco; el aviso SHALL ser no bloqueante.
(Previously: imprimía el CLI path de SQX sin validar su existencia; detectIssues no chequeaba el path de SQX)

#### Scenario: Carpeta SQX movida

- GIVEN `sqx.install_path` apunta a una carpeta eliminada
- WHEN `quantlab status` ejecuta detectIssues
- THEN se emite el aviso "SQX folder moved — run 'quantlab configure' to update"
- AND status termina con éxito (aviso no bloqueante)

#### Scenario: SQX configurado y presente

- GIVEN un install_path de SQX válido
- WHEN status imprime los servicios configurados
- THEN SQX se muestra como configurado
- AND no se emite el aviso de carpeta movida

## ADDED Requirements

### Requirement: Modelo de config SQX/JForex (REQ-INS-1)

El modelo MUST definir `SQXConfig{InstallPath, CLIPath}` (`InstallPath` = carpeta; `CLIPath` = override opcional). `ResolveSQXCliPath()` MUST devolver `InstallPath + "/sqcli"` (o `sqcli.exe` en Windows) salvo override `CLIPath` seteado, que MUST ganar (los `cli_path` existentes siguen siendo válidos). `ValidateSQXPath()` MUST aceptar la carpeta solo si `sqcli`/`sqcli.exe` existe en su raíz o en `bin/`. El modelo MUST además definir `JForexConfig{InstallPath, AccountMode, Host, Port, Username, Password}` con `AccountMode` restringido a `demo|live` y default `demo`. La password MUST almacenarse solo en `~/.quantlab/config.yaml` (0600) y MUST NOT aparecer en logs ni en el estado.

#### Scenario: Resolución con override

- GIVEN config con `install_path=/opt/SQX` y `cli_path=/custom/sqcli`
- WHEN `ResolveSQXCliPath()` corre
- THEN devuelve `/custom/sqcli`

#### Scenario: Resolución derivada

- GIVEN config con solo `install_path=/opt/SQX`
- WHEN `ResolveSQXCliPath()` corre
- THEN devuelve `/opt/SQX/sqcli` (o `sqcli.exe` en Windows)

#### Scenario: Validación de carpeta

- GIVEN `/opt/SQX/bin` contiene `sqcli`
- WHEN `ValidateSQXPath("/opt/SQX")` corre
- THEN acepta la carpeta
- AND rechaza carpetas sin binario en raíz o en `bin/`

#### Scenario: AccountMode por defecto

- GIVEN config sin account_mode
- WHEN se lee JForexConfig
- THEN account_mode es `demo`

### Requirement: Overlay como única fuente de verdad (REQ-INS-2)

`QuantLabAgentNames()` MUST derivar su lista del overlay (no hardcodeada) e incluir `guardian-orchestrator` (mode primary, deny-first espejo de `quantlab-orchestrator` — REQ-822) y los delegados `quantlab-guardian`, `quantlab-guardian-alert`, `quantlab-replacement`. El count de agentes reportado por install/status MUST derivarse del mismo overlay. `uninstall`/`sync` MUST usar la lista derivada para remoción y matching (sin duplicados).

#### Scenario: Overlay contiene guardian

- GIVEN el overlay.json actualizado
- WHEN se enumeran los agentes gestionados
- THEN `guardian-orchestrator` está presente con mode primary
- AND `quantlab-guardian`, `quantlab-guardian-alert` y `quantlab-replacement` están definidos
- AND `QuantLabAgentNames()` coincide con el overlay

#### Scenario: Uninstall limpia el set derivado

- WHEN `quantlab uninstall` corre
- THEN remueve todos los agentes de `QuantLabAgentNames()`
- AND no quedan agentes guardian huérfanos