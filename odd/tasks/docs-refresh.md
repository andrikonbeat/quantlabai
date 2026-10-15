# Tasks: Docs refresh total (2026-10-10)

Objetivo: dejar toda la doc del proyecto en su versión más actual.
Alcance acordado: barrido total en slices ≤400 líneas. Entrega: un commit por
slice, sin push (commits autorizados explícitamente por el usuario).

Hallazgos de auditoría (2026-10-10, HEAD `d0c5299`, main, remote
`andrikonbeat/quantlabai`):
- `sdd/config.yaml` context dice "Brand-new project, no code yet" — STALE.
- `sdd/PROJECT_STATE.md` snapshot de suite del 2026-10-03 — re-medir.
- `docs/PRD.md` Draft v0.1.0 del 2026-08-08 — revisar scope (installer ya existe).
- README install + HANDOFF remote ya actuales (install.sh, andrikonbeat).
- `openspec/` restante en PROJECT_STATE §7 es nota histórica legítima.
- Sin refs `ogzuz/quantlab` en docs vivos. Counts: 53 archivados, 0 activos, 107 specs.

Slices (uno = leer → editar → checks → commit → registrar identidad):

- [x] S1 `sdd/config.yaml`: reescribir `context` al presente (stack real, ODD, 53 archivados). Checks: parse YAML + `test_orchestrator_prompt.py` sin nuevas fallas. Commit: `1c970fe`.
- [x] S2 `sdd/PROJECT_STATE.md`: re-medir suite (§3: 4380/37/29/4 + triage), fechas, §10 (installer DONE). Commit: `881224b`.
- [x] S8 Unidades preexistentes: `4779ef8` reorg (33 files, incluye 4 renames installer) + `5ab66cf` installer-close (6 files). Sin contaminación (checks negativos). Sin push.
- [x] S3 `README.md`: un fix (flag order `go test -short`). Checks 16/16. Commit: `6d67613`.
- [x] S4 `docs/HANDOFF.md`: §8 snapshot vigente + flag order. Commit: `2220ecc`.
- [x] S5 `docs/PRD.md`: v0.2.0, gaps post-installer, checklist + §15. Commit: `579d7b4`.
- [x] S6 gates/pipeline scope notes (5-gate legacy vs `HUMAN_*`). Checks 16/16. Commit: `edc6345`.
- [x] S7 `docs/index.md` gates row + linkcheck + sweep openspec + 16/16. Commit: `f526ba9`.

Notas: trabajo ajeno en vuelo NO tocado (`sync_prompts.py`, `managed.go`, TUI screens, `PROJECT_STATE.md` +6 uninstall-fix, `.atl/skill-registry.md`). Subagentes del runtime fallaron (sdd-verify/explore/worker) — verificación inline acotada.

Reglas: sin push; cada commit Conventional, sin atribución AI; tests y docs viajan juntos;
`docs/STATE.md` shim y frozen (`CHANGELOG`, `LINT-CLEANUP`) no se tocan salvo header.
