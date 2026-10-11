# Tasks: Close quantlab-installer SDD change

Objetivo: cerrar el cambio activo `sdd/changes/quantlab-installer/` con ritual SDD completo, sin commit (salvo orden explícita).
Estado inicial: tasks.md 38/38 `[x]`, código `installer/` + `install.sh` implementado, sin `apply-progress.md` / `verify-report.md` / `archive-report.md` / `specs/`, sigue en `changes/` activo. `sdd/PROJECT_STATE.md` §5 lo marca "Planned, not started" (stale).

Regla: no commitear. `git mv` al archive deja el árbol listo; el commit lo decide el humano.

- [ ] T1 Verificar implementación contra tasks+specs (sdd-verify: go tests, 38/38, specs canónicas)
- [ ] T2 Escribir `apply-progress.md` + `verify-report.md` con evidencia real (comandos, counts, HEAD)
- [ ] T3 Escribir `archive-report.md` + `specs/` (delta o puntero a `sdd/specs/quantlab-installer`, `quantlab-config-wizard`, etc.)
- [ ] T4 `git mv` a `sdd/changes/archive/YYYY-MM-DD-quantlab-installer/` (sin commit)
- [ ] T5 Actualizar `sdd/PROJECT_STATE.md` (§5 activo→0, §6 último archivado, counts 52→53)
- [x] T6 Verificar contrato 16/16 + reportar árbol listo (diff stat, commit pendiente)

Cierre 2026-10-10: verify `go test -short` 363/19pkgs, `git mv` a `archive/2026-10-10-quantlab-installer/`, PROJECT_STATE activo 0 / arch 53, contrato 16/16. Sin commit.

Cierre SDD = archive-report + verify-report presentes y cambio bajo `archive/` vía `git mv`.
Verificación contrato: `SQX_FORCE_MOCK=1 .venv/bin/python -m pytest tests/test_project_agents.py tests/test_campaign_docs.py`.
Verificación installer: `cd installer && go test ./...`.
