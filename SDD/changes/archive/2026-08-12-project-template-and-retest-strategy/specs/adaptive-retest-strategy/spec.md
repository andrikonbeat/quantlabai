# Adaptive Retest Strategy Specification

## Purpose

Inspects CFX runtime signals and dynamically selects between AutomaticRetest and full Retest configurations via CfxPatcher mutations.

## Requirements

### Requirement: CFX Runtime Signal Inspection (Traceability: `adaptive-retest-strategy`)

The system MUST read a `.cfx` archive and extract runtime signals: `last_run_status`, `trade_count`, `monte_carlo_passed`, `walkforward_passed`, and `databank_coverage`. Inspection MUST NOT modify the archive. Signals MUST be returned as a structured `RetestSignals` object.

**Acceptance Criteria:** All signals extracted; archive unmodified; missing optional signals default to None.

#### Scenario: Inspect CFX with completed retest signals

- GIVEN a CFX archive with trade_count=150 and monte_carlo_passed=true
- WHEN `inspect_cfx_signals(cfx_path)` runs
- THEN RetestSignals.trade_count == 150
- AND RetestSignals.monte_carlo_passed is True
- AND archive file hash is unchanged

#### Scenario: Inspect CFX with missing optional signals

- GIVEN a CFX archive from a template with no prior retest runs
- WHEN `inspect_cfx_signals(cfx_path)` runs
- THEN RetestSignals.last_run_status is None
- AND no exception is raised

### Requirement: Retest Mode Selection (Traceability: `adaptive-retest-strategy`)

The system MUST select between `AutomaticRetest` and `Retest` based on CFX signals: IF `trade_count` < 50 THEN `AutomaticRetest`; IF `monte_carlo_passed` is False THEN `Retest`; IF `walkforward_passed` is False THEN `Retest`; IF `databank_coverage` < 0.8 THEN `Retest`; DEFAULT `AutomaticRetest` when no signals are present. An explicit `retest_mode` override in CFX metadata MUST take precedence.

**Acceptance Criteria:** Selection follows all rules; CFX metadata override wins; default applies when no signals present.

#### Scenario: Low trade count selects AutomaticRetest

- GIVEN RetestSignals(trade_count=30, monte_carlo_passed=True, walkforward_passed=True, databank_coverage=0.9)
- WHEN `select_retest_mode(signals)` runs
- THEN mode == AutomaticRetest

#### Scenario: Failed Monte Carlo selects full Retest

- GIVEN RetestSignals(trade_count=200, monte_carlo_passed=False)
- WHEN `select_retest_mode(signals)` runs
- THEN mode == Retest

#### Scenario: CFX metadata override takes precedence

- GIVEN RetestSignals(trade_count=200) and CFX metadata `retest_mode=AutomaticRetest`
- WHEN `select_retest_mode(signals, metadata)` runs
- THEN mode == AutomaticRetest

### Requirement: CfxPatcher Mutation Application (Traceability: `adaptive-retest-strategy`)

The system MUST apply adaptive retest configuration mutations to a `.cfx` archive via CfxPatcher. Mutations MUST set the selected retest task type, update CrossChecks parameters, and preserve all other CFX content. Round-trip validation MUST confirm the mutated archive is valid.

**Acceptance Criteria:** Mutated CFX reflects selected mode; non-retest content preserved; round-trip validation passes.

#### Scenario: Mutate CFX to AutomaticRetest

- GIVEN a CFX archive with a `Retest` task
- WHEN `apply_adaptive_mutations(cfx_path, mode=AutomaticRetest)` runs
- THEN the task type changes to `AutomaticRetest`
- AND CrossChecks are updated accordingly

#### Scenario: Mutation preserves unrelated CFX content

- GIVEN a CFX archive with Build, Filtering, Retest, and Optimize tasks
- WHEN `apply_adaptive_mutations(cfx_path, mode=Retest)` runs
- THEN Build, Filtering, and Optimize task XMLs are unchanged
- AND only the Retest task is modified
