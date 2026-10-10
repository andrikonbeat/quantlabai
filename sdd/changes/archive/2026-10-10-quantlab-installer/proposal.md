# Proposal: QuantLab Installer (quantlab-installer)

## Intent

QuantLab AI solo es usable hoy por developers que clonan el repo, crean venv y configuran SQX/JForex manualmente. Necesitamos un installer zero-dependency para que traders no-developers puedan instalar, configurar y mantener QuantLab con experiencia TUI profesional, integrándose con OpenCode sin afectar configuraciones existentes (Gentle AI, SDD).

## Scope

### In Scope
- Go binary standalone con Bubbletea TUI: `install`, `uninstall`, `sync`, `configure`, `update`
- Pipeline prepare→apply→rollback con mutation journal
- Deep merge JSON para opencode.json (solo agrega, nunca borra)
- Wizard TUI: SQX path, JForex credentials, API keys
- Instalación de SDK Python (venv + pip install desde GitHub/wheel)
- Inyección de agents `quantlab-orchestrator`, `quantlab-*` en opencode.json
- Instalación de skills `quantlab-*` y prompts en `~/.config/opencode/`
- Ownership pattern para `default_agent` (guarda anterior, restaura en uninstall)
- State file en `~/.quantlab/state.json`
- Assets embebidos vía `embed.FS` (skills, prompts, config templates)
- Release pipeline: GitHub Actions → cross-compile → release artifacts
- Detección temprana de prerequisitos (Python 3.11+, SQX/JForex paths)

### Out of Scope
- Desktop app (Tauri/Electron) → cambio futuro separado
- Publicación en PyPI → cambio futuro
- Interfaz web tipo SaaS → no es el target
- Marketplace de skills/plugins QuantLab → futuro
- Dashboard web (ya existe en SDK) → no tocar
- Modificación de agents de terceros (`gentle-*`, `sdd-*`) → prohibido

## Capabilities

### New Capabilities
- `quantlab-installer`: Go binary con TUI (Bubbletea) implementando install/uninstall/sync/configure/update, pipeline, rollback, state tracking e integración OpenCode
- `quantlab-config-wizard`: Wizard TUI para configurar SQX paths, JForex DAS credentials, API keys (OpenAI, etc.) y validación de entorno

### Modified Capabilities
None — `quantlab-orchestrator` spec behavior no cambia; el installer automatiza su deployment sin alterar requirements. Todas las demás specs existentes (SDK, CLI, dashboard, etc.) quedan intactas.

## Approach

Go binary replicando pipeline de Gentle AI: Prepare (validar + capturar before-images) → Wizard TUI (recolectar config) → Apply (merge opencode.json, install SDK, copiar skills/prompts, escribir state) → Verify → Complete/Rollback. Deep merge JSON overlay. Mutation journal para rollback atómico. Ownership file para default_agent. Assets embebidos con `embed.FS`. Namespace `quantlab-*` garantiza coexistencia.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `installer/` | New | Go binary tree completo |
| `~/.config/opencode/opencode.json` | Modified | Deep merge: agrega agents `quantlab-*` |
| `~/.config/opencode/skills/quantlab-*/` | New | Skills instalados por el installer |
| `~/.config/opencode/prompts/quantlab/` | New | Prompts QuantLab |
| `~/.quantlab/` | New | state.json, config.yaml, ownership |
| `.github/workflows/release-installer.yml` | New | CI/CD build + release |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Coexistencia con Gentle AI | Low | Deep merge + namespace `quantlab-*`. Nunca tocar `gentle-*` ni `sdd-*`. |
| Python no instalado | Medium | Detección temprana + guía de instalación. |
| SDK Python falla al instalarse | Medium | Venv aislado + validación post-install + rollback. |
| Config sensible (API keys) | Low | `config.yaml` con permisos 600. No loguear. |
| Kill durante Apply | Low | Mutation journal + detección de estado inconsistente. |
| opencode.json con JSONC | Low | NormalizeJSON antes de merge. |

## Rollback Plan

Mutation journal captura before-image de cada archivo antes de modificarlo. Si Apply falla: recorrer steps en reversa, restaurar cada before-image vía WriteFileAtomic, limpiar state file. Si el proceso se mata durante Apply, en próximo `install`/`sync` detectar estado inconsistente y ofrecer rollback o continuar.

## Dependencies

- Go 1.22+ (solo build-time, no runtime para usuarios)
- Bubbletea + Bubbles + Lipgloss para TUI
- Python 3.11+ (prerequisito detectado en runtime)
- OpenCode instalado (detectado en PREPARE)
- Opcional: SQX, JForex DAS (detección + guía en wizard)

## Success Criteria

- [ ] `./quantlab install` completa wizard y deja QuantLab usable en < 5 min
- [ ] opencode.json contiene `agent.quantlab-orchestrator` sin perder configs existentes
- [ ] `~/.quantlab/state.json` trackea todos los componentes instalados
- [ ] `quantlab uninstall` remueve TODO lo creado, restaura `default_agent`, no deja rastros
- [ ] `quantlab update` actualiza skills/prompts sin duplicar agents
- [ ] Si Apply falla, rollback deja sistema exactamente como antes
