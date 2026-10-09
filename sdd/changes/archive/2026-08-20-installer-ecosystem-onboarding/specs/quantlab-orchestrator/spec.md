# Delta for quantlab-orchestrator

## MODIFIED Requirements

### Requirement: Agent registration in opencode.json (REQ-1)

El sistema MUST registrar `quantlab-orchestrator` como agente primario en `opencode.json` con `mode: primary`, una descripción, una referencia al archivo de prompt y un set de herramientas scoped.
(Previously: registrado como `mode: subagent`, contradiciendo el overlay del installer y la máquina viva; inconsistente con REQ-822)

#### Scenario: Agent appears in opencode.json agents map

- GIVEN `opencode.json` existe en `~/.config/opencode/opencode.json`
- WHEN se configura el agente quantlab-orchestrator
- THEN `agents.quantlab-orchestrator` existe en el JSON
- AND su `mode` es `"primary"`
- AND su `description` contiene "QuantLab orchestrator"

#### Scenario: Agent prompt references the orchestrator prompt file

- GIVEN el agente está registrado en `opencode.json`
- WHEN se lee la config del agente
- THEN `prompt` apunta a `{file:~/.config/opencode/prompts/quantlab/orchestrator.md}`

#### Scenario: Agent has scoped tools

- GIVEN la config del agente quantlab-orchestrator
- WHEN se listan las herramientas
- THEN `bash`, `edit`, `read`, `write` y `task` están permitidas
- AND `question` está permitida para prompts de permiso

#### Scenario: Modo consistente con overlay y REQ-822

- GIVEN el overlay del installer y la config de la máquina viva
- WHEN se compara el mode del agente
- THEN `mode: primary` coincide con la definición del overlay
- AND es consistente con la registración first-class de `guardian-orchestrator` (REQ-822)