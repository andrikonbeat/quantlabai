# Tasks: Knowledge Seeding & Education

## Review Workload Forecast

| Slice | WUs | Est. lines | Risk |
|---|---|---|---|
| PR 1 | WU1+WU2: seed flow+gate+goldens+index | ~350 | Medium |
| PR 2 | WU3+WU4: generator+matrix | ~480 | High |
| PR 3 | WU5: plan doc+test module | ~150 | Low |

Goldens (~82 YAML+index.yaml) excluded from authored budget; in verification identity.

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

## Work Units

| # | PR | Focused test | Runtime harness | Rollback |
|---|---|---|---|---|
| 1 seed+goldens+band | 1 | pytest sdk/tests/test_kb_seed_validation.py | sqx kb seed (real install) | delete 144.2953/+restore index |
| 2 gate+CLI+RED | 1 | same as WU1 | sqx kb seed && validate (exit 0/1) | revert validation/seeding_flow/CLI |
| 3 gen+conformance+fixtures | 2 | pytest sdk/tests/test_kb_educational.py | sqx kb table (seeded lake) | delete educational/**, revert writer |
| 4 matrix lazy hook | 2 | pytest sdk/tests/test_kb_educational.py -k matrix | generate_run_matrix w/ dataset | revert parameter_matrix.py |
| 5 plan doc+integration | 3 | pytest sdk/tests/test_kb_seed_validation.py -k cfx | N/A doc; .cfx via conftest | delete doc_dev plan |

## Phase 1: Seed flow + gate

- [x] T-1.1 [WU1|PR1] RED `sdk/tests/test_kb_seed_validation.py`: schema violation names field, stale index, dangling evidence_ref, band, needs_review success (tmp lakes) | AC: violations fail, needs_review passes
- [x] T-1.2 [WU2|PR1] GREEN `sdk/quantlab/knowledge/kb/validation.py`: SeedValidationReport + validate_seed (pure) | AC: tests green
- [x] T-1.3 [WU2|PR1] GREEN `sdk/quantlab/knowledge/kb/seeding_flow.py`: CFX_EVIDENCE_MAP (~71) + run_seed_flow (seed→verify→index→gate) | AC: E2E synthetic
- [x] T-1.4 [WU2|PR1] Wire `sdk/quantlab/cli/sq_commands.py`: cmd_kb_seed runs gate exit 0/1; add cmd_kb_validate | AC: exit codes 0/1
- [x] T-1.5 [WU1|PR1] First real seed; record distribution; confirm band [65,73]/[9,15] or adjust; freeze | AC: distribution logged
- [x] T-1.6 [WU1|PR1] Commit ~82 goldens `knowledge/structured/sqx-kb/144.2953/parameters/{tab}/*.yaml` + rebuild `knowledge/index.yaml` v4 kb_parameters==82 (generated) | AC: gate 0, legacy index green

## Phase 2: Educational generator + matrix

- [ ] T-2.1 [WU3|PR2] RED `sdk/tests/test_kb_educational.py`: row/param, REQ-205 headers, empty-KB placeholder, 15-field schema, byte-identical re-run, template-missing | AC: tests fail as designed
- [ ] T-2.2 [WU3|PR2] Fixtures `sdk/tests/fixtures/tpl_build_mini.xml` + `config_mini.xml`; conftest.make_cfx() ZIP builder | AC: fixture parses
- [ ] T-2.3 [WU3|PR2] GREEN `sdk/quantlab/knowledge/kb/educational.py`: parse_tpl_build (ElementTree) + TPL_KEY_MAP (~30) | AC: unmapped → template-missing
- [ ] T-2.4 [WU3|PR2] GREEN `educational.py`: EducationalRecord (15 fields) + build_educational_dataset + build_educational_table | AC: 82 records, no empties
- [ ] T-2.5 [WU3|PR2] Writer `educational_generator` in `sdk/quantlab/knowledge/conformance.py` → `structured/sqx-kb/144.2953/educational/` | AC: conformance green
- [ ] T-2.6 [WU3|PR2] Add cmd_kb_table in sq_commands.py; run on lake; commit dataset+table.md (generated) | AC: byte-identical re-run
- [ ] T-2.7 [WU4|PR2] parameter_matrix.py: generate_run_matrix lazy-loads dataset; name+tab match; fallback manual/optimized | AC: fallback passes, no invention

## Phase 3: Test module + plan doc

- [ ] T-3.1 [WU5|PR3] Integration: .cfx spot-checks via make_cfx(); run_seed_flow E2E; matrix fallback vs rationale | AC: integration green
- [ ] T-3.2 [WU5|PR3] `doc_dev/SQX-KB Seed Validation Plan.md`: steps, evidence ledger, spot-checks, rollback, frozen band | AC: covers REQ-209
- [ ] T-3.3 [WU5|PR3] Verify sqx kb status: 82 params; snapshot = goldens+index+dataset+table | AC: all green
