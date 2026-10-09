# Proposal: KB Re-verification Pipeline

## Intent

**Blocker first (Finding 0).** `KbParameter` (`sdk/quantlab/knowledge/kb/models.py:64-97`) omits `xml_path`/`element_name`. Pydantic `extra="ignore"` + `to_yaml`'s `model_dump(exclude_none=True)` strips both on **every** store write (`verify`/`invalidate`/drift → `_load_file`+`_save_file`). The REQ-208 drift hook in PR #22 already triggers this, deleting the XML anchors on the 10 `Cross checks` YAMLs and failing `tests/knowledge/test_crosschecks_schema.py:96-110` on a real lake. Live data loss.

**Then the gap.** Nothing re-verifies after drift: 82 entries, only manual `sqx kb verify`.

## Scope

### In Scope
- Declare `xml_path`/`element_name` as optional `str` on `KbParameter` — explicit fields, not `extra="allow"`, keeping `to_yaml` deterministic.
- Pure `knowledge/kb/reverify.py`: evidence loader (ZIP → `Build-Task1.xml`/`config.xml`), XML walker, decision table.
- Thin `KbStore.reverify_against_build(evidence, *, tab, sqx_version, apply=False)`.
- CLI `sqx kb reverify --evidence <path> [--tab T] [--apply]`, dry-run by default.
- `tests/knowledge/test_kb_reverify.py` on the tracked template.

| Entry evidence state | Outcome |
|---|---|
| `xml_path` resolves, element present | `verified` + fresh `evidence_ref` |
| Element absent | stays `needs_review` (`field_absent`) |
| Markdown anchor (doc gap) | skipped, never promoted (`not_xml_backed`) |
| Artifact unreadable | zero writes, distinct exit code |

### Out of Scope
- Artifact auto-discovery; point-version detection (`detect_installed` = major only).
- `DriftWorkflow.run()` wiring; status-gating `build_review_teaching_table`.
- `index.yaml` staleness policy; `xml_path` beyond the 10 entries; pipeline stage.

## Capabilities

### New Capabilities
- `kb-reverification`: operator-supplied XML evidence → per-entry verdicts under a non-promotion contract.

### Modified Capabilities
- `sqx-parameter-kb`: REQ-208 gains re-verification scenarios; the field set gains `xml_path`/`element_name`.

## Approach

Fix Finding 0 first, then pure decision logic behind one store method: `list()` picks the population, `verify()` is the single write path. Only positive XML resolutions promote; everything else stays as found with a reason. ~375 authored lines; the `structured/sqx-version/{old}→{new}/` report file is deferrable.

## Affected Areas

| Area | Impact |
|---|---|
| `knowledge/kb/models.py` | Modified |
| `knowledge/kb/reverify.py` | New |
| `knowledge/kb/store.py` | Modified |
| `cli/sq_commands.py` | Modified |
| `tests/knowledge/test_kb_reverify.py` | New |
| `specs/sqx-parameter-kb/spec.md` | Modified |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Wrong XML path fabricates semantics | Med | Only positive resolutions promote |
| 144.x evidence after a 145 install | High | `--evidence` explicit |
| `validate_seed` band shifts | Med | Never promote doc gaps |
| Base lacks the drift hook | High | Verify base first |

## Rollback Plan

Additive model change. Revert `models.py`, `reverify.py`, the wrapper, and the subparser; re-populate the two keys from the `Cross checks` sources if stripped. No migration, no schema break.

## Dependencies

- Base `feat/crosschecks-p6-w3-drift-hook` @ `ebe0bbb` is not on `main`. Verify before apply.

## Success Criteria

- [ ] `xml_path` survives a `verify()` write; schema test green on a real lake.
- [ ] Four outcomes covered; dry-run and missing evidence write nothing.
- [ ] Suite green under `SQX_FORCE_MOCK=1`; ≤400 changed lines.

## Proposal question round

1. Report file under `structured/sqx-version/{old}→{new}/`, or stdout only?
2. Does `evidence_ref` carry the XML anchor or the artifact alone?