# Exploration: QuantLab Installer

## Current State

### QuantLab AI Hoy

QuantLab AI es un SDK de trading algorítmico con:

- **SDK Python** (`sdk/quantlab/`): ~25 módulos que cubren desde CLI, daemon management de SQX, depliegue JForex, pipelines de trading, agents, MCP, dashboard, reporting, etc.
- **Agents OpenCode existentes**: Ya hay un `quantlab-orchestrator` definido en `opencode.json` con sub-agentes como `quantlab-run`, `quantlab-monitor`, `quantlab-compare`, `quantlab-status`. Sin embargo, estos agents usan permisos bash/task específicos y refieren a un prompt file externo.
- **Prompts**: Solo existe `prompts/quantlab/orchestrator.md`.
- **Skills**: No hay skills específicos de QuantLab instalados.
- **CLI Python**: Ya existe `quantlab.cli.main` con comandos para daemon, optimizer, retester, pipeline, jforex.
- **Configuración**: No hay estado de instalación trackeado. No hay mecanismo de rollback. No hay wizard de configuración inicial.

### Lo que falta para ser instalable

1. **No hay un binario independiente** — el CLI está en Python, requiere venv, no es discoverable para no-developers
2. **No hay wizard de configuración** — SQX paths, JForex credentials, API keys se configuran manualmente
3. **No hay instalación de skills/agents OpenCode automatizada** — el `quantlab-orchestrator` existe pero fue creado a mano
4. **No hay mecanismo de estado** — no se trackea qué se instaló, no se puede desinstalar limpiamente
5. **No hay rollback** — si algo falla, no hay vuelta atrás
6. **No hay merge seguro de opencode.json** — los cambios se hacen manualmente
7. **El SDK Python no está en PyPI** — no hay `pip install quantlab` disponible

---

## Gentle AI Pattern Analysis

### 1. Cómo Inyecta Agents en opencode.json

**Pattern**: `MergeJSONObjects(base, overlay)` del paquete `filemerge`.

El flujo es:

1. Lee el `opencode.json` existente como `base`
2. Ejecuta migraciones legacy (`migrateLegacyOpenCodeAgentsKey`, `migrateLegacyOpenCodeSDDOrchestrator`, `migrateLegacyOpenCodeCommandPrompt`)
3. Carga un `overlay` JSON con los nuevos agents desde assets embebidos
4. Llama a `filemerge.MergeJSONObjects(base, overlay)` que hace deep merge:
   - Objetos anidados se mergean recursivamente
   - Arrays se reemplazan (no se concatenan)
   - Usa el sentinel `__replace__` para forzar reemplazo atómico cuando es necesario
5. Escribe atómicamente via `WriteFileAtomic` (temp file + rename)

**Clave**: El overlay SOLO agrega/actualiza keys específicas. Si el usuario ya tiene agents en `opencode.json`, el deep merge los preserva porque `mergeObjects` recorre el overlay y solo pisa keys que existen en el overlay, dejando las otras intactas.

**Implementación**: `sdd/inject.go` → `mergeJSONFile()` → `filemerge.MergeJSONObjects()`

### 2. Cómo Maneja default_agent Sin Conflicto

**Pattern**: Ownership file + state capture en `opencodedefault/ownership.go`.

El flujo:

1. **PrepareInstall**: Lee el `default_agent` actual y crea un `InstallPlan` que registra el valor anterior (si existe) como "previous"
2. **Apply**: 
   - Si no existía `default_agent` antes → guarda `previous_state: "absent"`
   - Si existía otro valor → guarda `previous_state: "value"` con `previous_default: "{valor anterior}"`
   - Setea `default_agent` a `gentle-orchestrator`
   - Escribe un archivo de ownership: `.gentle-ai-default-agent.json`
3. **Uninstall**:
   - Lee el ownership file
   - Si previous era "absent" → elimina la key `default_agent`
   - Si previous tenía valor → restaura ese valor
   - Limpia el ownership file

Este mecanismo permite que Gentle AI tome control de `default_agent` durante su instalación y lo restaure exactamente al desinstalar.

### 3. Cómo Instala Skills Sin Conflictos

**Pattern**: `skills.InjectWithCapability()` y `filemerge.WriteFileAtomic()`.

El flujo:

1. Lee los assets embebidos de `skills/{skill-id}/`
2. Para SDD skills, extrae solo la sección correspondiente al modelo (capable/small) usando `ExtractHTMLCommentSection`
3. Escribe cada archivo a `~/.config/opencode/skills/{skill-id}/`
4. `WriteFileAtomic` hace compare-and-swap: si el contenido es idéntico al existente, no escribe (evita writes innecesarios)
5. Skills existentes de otros orígenes (Gentle AI, etc.) NO se tocan porque tienen IDs diferentes (`sdd-*`, `branch-pr`, etc.)
6. Los skills QuantLab usarían IDs como `quantlab-*` — no hay colisión posible

**Protección contra conflictos**: Cada skill tiene un ID único. El `skills.Inject` itera sobre los skill IDs solicitados y solo escribe esos. Skills existentes con otros IDs no se modifican.

### 4. Cómo Trackea el Estado (Marker Files)

**Pattern**: `state.InstallState` en `~/.gentle-ai/state.json`.

El estado incluye:
- `InstalledAgents`: qué agents fueron instalados
- `Components`: qué componentes (SDD, Engram, etc.)
- `Skills`: qué skills
- `Preset`, `SDDMode`, `StrictTDD`: configuración
- `ModelAssignments`: modelos elegidos
- `Persona`: persona activa

Para QuantLab, replicaríamos con un state file similar en `~/.quantlab/state.json`.

### 5. Cómo Hace Rollback

**Pattern**: Dos mecanismos complementarios.

#### A. MutationJournal (`mutationjournal/journal.go`)
- Antes de modificar cualquier archivo, captura el "before image" (contenido completo)
- Si un paso posterior falla, llama a `journal.Restore()` que:
  - Restaura cada archivo a su before-image
  - Si el archivo no existía antes, lo elimina
  - Verifica con compare-and-swap que nadie más modificó el archivo entre la captura y el restore

#### B. Pipeline de instalación (`pipeline/orchestrator.go`)
- **Stage 1 — Prepare**: Todos los pasos preparatorios (validaciones, capturas de before-images)
- **Stage 2 — Apply**: Ejecuta los cambios reales
- **Rollback**: Si Apply falla, ejecuta `ExecuteRollback` que recorre los steps en orden inverso y llama a `Rollback()` en cada uno que implemente `RollbackStep`
- Política default: rollback automático en failure de Apply

### 6. Cómo Desinstala

**Pattern**: `componentuninstall` + `state.MergeAgents`.

El flujo:
1. Lee el state file para saber qué se instaló
2. Para cada componente/skill/agent, ejecuta su lógica de uninstall:
   - Remueve entries de `opencode.json` (agents, MCP servers)
   - Elimina archivos copiados (skills, prompts, plugins)
   - Restaura `default_agent` si era manejado por el ownership
3. Limpia el state file

**Importante**: Uninstall NUNCA toca configuraciones que no fueron creadas por el installer. Cada cambio está trackeado en el state file y en los ownership files.

---

## Affected Areas

### Archivos Nuevos a Crear

| Archivo | Propósito |
|---------|-----------|
| `installer/main.go` | Entry point del Go binary |
| `installer/cmd/install.go` | Comando install con wizard TUI |
| `installer/cmd/uninstall.go` | Comando uninstall |
| `installer/cmd/sync.go` | Sincronización de config |
| `installer/internal/config/wizard.go` | Wizard de configuración (SQX, JForex, API keys) |
| `installer/internal/opencode/inject.go` | Inyección de agents QuantLab en opencode.json |
| `installer/internal/opencode/ownership.go` | Manejo de default_agent |
| `installer/internal/skills/inject.go` | Instalación de skills QuantLab |
| `installer/internal/prompts/inject.go` | Instalación de prompts QuantLab |
| `installer/internal/state/state.go` | State tracking (~/.quantlab/state.json) |
| `installer/internal/rollback/journal.go` | Mutation journal para rollback |
| `installer/internal/sdk/install.go` | Instalación del SDK Python (pip install) |
| `installer/go.mod` | Dependencias Go |
| `skills/quantlab/` | Skills OpenCode para QuantLab |
| `prompts/quantlab/` | Prompts adicionales para agents QuantLab |
| `.github/workflows/release-installer.yml` | CI para build y release del binary |

### Archivos Existentes a Modificar

| Archivo | Cambio |
|---------|--------|
| `~/.config/opencode/opencode.json` | **Solo agregar**: nuevo `agent.quantlab-orchestrator` con sub-agentes QuantLab. Nunca borrar entries existentes. |
| `~/.config/opencode/opencode.jsonc` | **Solo agregar**: MCP servers de QuantLab si es necesario. |
| `~/.quantlab/config.yaml` (nuevo) | Archivo de configuración generado por el wizard |

---

## Approaches

### 1. Go Binary con Bubbletea TUI (recomendado)

Go binary standalone que empaqueta assets (skills, prompts, config templates) via `embed`.

**Pros**:
- No depende de Python ni del SDK — funciona aunque no haya venv
- Bubbletea TUI da experiencia pulida (checkboxes, progress bars, spinners)
- WriteFileAtomic + MutationJournal ya están probados en Gentle AI
- Cross-compilation fácil (Go → Linux, macOS, Windows)
- Idempotente: install, sync, uninstall sin estado inconsistente
- Puede instalar el SDK Python (crear venv, pip install)
- Desinstalación limpia: remueve todo lo que instaló, no toca lo demás
- Binario único, fácil de distribuir vía GitHub Releases

**Cons**:
- Requiere mantener un codebase Go separado (más mantenimiento)
- Bubbletea es otra dependencia nueva que aprender
- No puede reusar directamente la lógica Python del CLI existente

**Effort**: High (3-4 semanas para MVP)

### 2. Python CLI con Rich/Questionary

Extender el CLI Python existente (`quantlab.cli.main`) con subcomandos de instalación.

**Pros**:
- Reusa el SDK Python y la lógica existente
- Rich y Questionary son libraries Python maduras para TUI
- Un solo lenguaje en el proyecto
- Más fácil para contribuciones de la comunidad Python

**Cons**:
- Requiere Python + virtualenv para funcionar — no es zero-dependency
- No puede manejar su propia instalación (chicken-and-egg: necesitás Python para instalar Python)
- Rollback complejo: no hay WriteFileAtomic fácil en Python sin librerías externas
- Desinstalación frágil sin state tracking atómico
- La experiencia TUI con Rich es menos pulida que Bubbletea para wizards interactivos

**Effort**: Medium (2-3 semanas)

### 3. Script Shell + Wizard Bash

Script bash/sh + `whiptail`/`dialog` para el wizard, con `pip` para el SDK.

**Pros**:
- Zero dependencias (viene con el OS)
- Fácil de implementar rápidamente
- Portátil en Linux/macOS

**Cons**:
- No portable a Windows
- Sin TUI atractiva (whiptail es feo)
- Sin rollback atómico
- Manejo de errores frágil
- Difícil de testear
- Escalado limitado para features complejas
- No hay type safety

**Effort**: Low (1 semana para MVP, pero limitado)

---

## Recommendation

**Go Binary con Bubbletea TUI** (Approach 1).

Razones:

1. **Es el mismo patrón que Gentle AI** — ya tenemos el código de referencia, los patrones de merge, rollback, state tracking, y ownership. Replicarlos en Go es directo.

2. **Zero-dependency installer** — el usuario no necesita tener Python, Node.js, ni nada. Descarga un binary y lo ejecuta. Esto es crítico para no-developers.

3. **Instalación del SDK** — el Go binary puede crear el venv, hacer `pip install`, y verificar que el SDK funciona. Todo desde un solo tool.

4. **Rollback atómico** — el MutationJournal de Gentle AI ya resuelve este problema. Copiamos el patrón.

5. **Coexistencia con Gentle AI** — ambos installers escriben a `opencode.json` usando el mismo mecanismo de deep merge. QuantLab solo agrega sus propios agents (`quantlab-orchestrator`, `quantlab-*`) y skills (`quantlab-*`). No toca `gentle-orchestrator`, `default_agent`, ni los skills SDD. La ownership de `default_agent` solo cambia si QuantLab necesita ser el default (configurable).

6. **Desinstalación limpia** — cada archivo creado está trackeado en `~/.quantlab/state.json`. Uninstall remueve exactamente eso y nada más.

7. **Experiencia de usuario** — Bubbletea con spinners, progress bars, y checkboxes da una experiencia profesional.

### Arquitectura Propuesta

```
quantlab-installer/
├── main.go                    # Entry point (cobra o CLI simple)
├── go.mod
├── go.sum
├── cmd/
│   ├── install.go             # Install command con wizard TUI
│   ├── uninstall.go           # Uninstall command
│   ├── sync.go               # Re-aplica config después de cambios externos
│   └── configure.go          # Re-ejecuta wizard de configuración
├── internal/
│   ├── app/
│   │   └── app.go            # Punto de entrada, dispatch de comandos
│   ├── pipeline/
│   │   ├── orchestrator.go   # Pipeline prepare → apply → rollback
│   │   ├── stages.go         # Step interface, StagePlan
│   │   ├── runner.go         # Step executor con progress
│   │   └── rollback.go       # Rollback policy + execution
│   ├── state/
│   │   └── state.go          # ~/.quantlab/state.json
│   ├── journal/
│   │   └── journal.go        # Before-image capture + restore
│   ├── opencode/
│   │   ├── inject.go         # Merge agents en opencode.json
│   │   ├── ownership.go      # Default agent ownership
│   │   └── merge.go          # Deep merge de JSON objects
│   ├── sdk/
│   │   └── install.go        # Python venv + pip install
│   ├── config/
│   │   └── wizard.go         # TUI wizard para SQX/JForex/API keys
│   └── tui/
│       ├── model.go          # Bubbletea model
│       └── views.go          # Pantallas del wizard
├── assets/
│   ├── skills/               # Skills embebidos
│   │   └── quantlab/
│   ├── prompts/              # Prompts embebidos
│   │   └── quantlab/
│   └── config/               # Templates de configuración
│       └── quantlab.yaml
└── Makefile                  # Build targets
```

### Mecanismo de Coexistencia con Gentle AI

| Recurso | Gentle AI | QuantLab | Conflicto? |
|---------|-----------|----------|------------|
| `agent.gentle-orchestrator` | Creado por Gentle | NO tocar | No |
| `agent.quantlab-orchestrator` | NO existe | Crear | No |
| `default_agent` | `gentle-orchestrator` | No cambiar (opcional: preguntar) | Solo si QuantLab pide ser default |
| `skills/sdd-*` | SDD skills | NO tocar | No |
| `skills/quantlab-*` | NO existen | Crear | No |
| `prompts/sdd/` | Prompts SDD | NO tocar | No |
| `prompts/quantlab/` | NO existen | Crear | No |
| `mcp.*` | context7, engram, codegraph | NO tocar (agregar solo si QuantLab necesita MCP propio) | No |

### Flujo de Instalación

```
quantlab-install
│
├── 1. Detect: OpenCode config exists? Gentle AI installed? Python available?
├── 2. PREPARE phase:
│   ├── Capturar before-images (opencode.json, etc.)
│   └── Validar prerequisites (Python 3.11+, SQX path, etc.)
├── 3. WIZARD (TUI):
│   ├── SQX path configuration
│   ├── JForex credentials
│   ├── API keys (OpenAI, etc.)
│   └── Confirm installation
├── 4. APPLY phase:
│   ├── Create Python venv → pip install quantlab SDK
│   ├── Inject quantlab-orchestrator agent → opencode.json (deep merge)
│   ├── Install quantlab skills → ~/.config/opencode/skills/quantlab/
│   ├── Install quantlab prompts → ~/.config/opencode/prompts/quantlab/
│   ├── Write config → ~/.quantlab/config.yaml
│   └── Write state → ~/.quantlab/state.json
├── 5. VERIFY:
│   ├── Verify opencode.json has quantlab-orchestrator
│   ├── Verify SDK import works
│   └── Verify skills are on disk
└── 6. Complete (o rollback si algo falla en APPLY)
```

---

## Risks

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| **Conflicto con Gentle AI** si se pisa `default_agent` o `opencode.json` | Medio | Usar deep merge + ownership pattern. No tocar keys existentes de otros. |
| **SDK Python no instalable** (dependencias rotas, versión equivocada) | Alto | Validar prerequisitos antes de apply. Usar venv aislado. Mensaje claro si falla. |
| **Wizard captura datos sensibles** (API keys, JForex creds) | Alto | Guardar config en `~/.quantlab/config.yaml` con permisos 600. No loguear credenciales. |
| **Rollback incompleto** si el proceso se mata durante apply | Medio | Usar mutation journal con write atomic. Si se mata, en el próximo intento detectar estado inconsistente y ofrecer rollback o continuar. |
| **Python no instalado en el sistema** | Bajo | Detectar temprano en PREPARE. Guiar al usuario a instalarlo. |
| **opencode.json con formato personalizado** (JSONC, comentarios) | Bajo | Usar el mismo normalizeJSON que Gentle AI (strip comments, trailing commas) antes de mergear. |
| **Multiple instalaciones de QuantLab** (dev, prod) | Bajo | State file trackea versión. Sync actualiza si es necesario. |

---

## Ready for Proposal

**Yes** — El análisis es suficientemente profundo para avanzar a la fase de propuesta formal.

La arquitectura es clara: replicar el pipeline de Gentle AI (prepare → apply → rollback) con deep merge para opencode.json, ownership pattern para default_agent, mutation journal para rollback, y state file para trackear instalación.

El siguiente paso es `sdd-propose` para definir el alcance exacto del MVP y la estrategia de entrega.
