# Tasks: SDD Reorganization — consolidación sin commit

Objetivo: dejar la reorg SDD lista en el árbol, sin commitear.
Estado heredado (2026-10-10): `openspec/` → `sdd/` renombrado, `sdd/PROJECT_STATE.md` creado como canónico, `docs/STATE.md` reducido a shim, `docs/specs/sdd-phase5f-consolidated.md` eliminado, stray `openspec/` removido. 16/16 tests de contrato en verde. 23 fallos en `test_orchestrator_prompt.py` por drift de config viva — fuera de alcance.

Regla: no commitear. Dejar `git status` + `git diff --stat` listos para revisión humana.

- [x] T1 Mapear solapamientos docs/ vs sdd/PROJECT_STATE.md (PRD, HANDOFF, CHANGELOG, LINT-CLEANUP, INSTALL_INTERACTIVE, index)
- [x] T2 Congelar docs/CHANGELOG.md como histórico inmutable + apuntar a sdd/PROJECT_STATE.md para entradas nuevas
- [x] T3 Unificar docs/INSTALL_INTERACTIVE.md (15 líneas) en docs/HANDOFF.md + eliminar original
- [x] T4 Reducir docs/LINT-CLEANUP-HANDOFF.md a puntero canónico (conservar las 4 decisiones en PROJECT_STATE §8, no duplicar estado)
- [x] T5 Actualizar docs/index.md (mapa canónico, sin duplicar estado) + verificar 16/16 tests contrato
- [ ] T6 Reportar árbol listo: diff stat, próximos pasos (commit humano, sync viva opcional)

Cierre: sin commit. Verificación: `SQX_FORCE_MOCK=1 .venv/bin/python -m pytest tests/test_project_agents.py tests/test_campaign_docs.py`.
