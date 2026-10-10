# Spec: quantlab-installer (change pointer)

> No delta in this change. The normative contracts already live in
> `sdd/specs/` and the implementation was verified against them
> (see `../verify-report.md`). This file exists so the archived change
> carries a `specs/` artifact per the SDD convention.

## Canonical specs

- `sdd/specs/quantlab-installer/` — installer binary: install/uninstall/sync/
  configure/update/status/dashboard, pipeline prepare→apply→rollback,
  mutation journal, `~/.quantlab/state.json`, `quantlab-*` namespace
  (never touch `gentle-*`/`sdd-*`), embedded assets.
- `sdd/specs/quantlab-config-wizard/` — wizard: SQX paths, JForex credentials,
  API keys, environment validation.
- `sdd/specs/installer-onboarding/` — onboarding consent flow.
- `sdd/specs/installer-tools-install/` — third-party tools with consent
  (checksum-verified binary, display-only fallback).

## Requirement

- The installer SHALL satisfy the four canonical specs above with zero deltas.
- Verified: 38/38 tasks, 363 tests green (`go test -short ./...`, 19 pkgs).

## Scenario: close without delta

- **Given** the canonical specs are normative and unchanged
- **When** the change is archived
- **Then** this pointer is recorded instead of a delta spec
