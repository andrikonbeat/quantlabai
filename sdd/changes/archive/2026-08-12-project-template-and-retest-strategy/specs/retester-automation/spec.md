# Delta for Retester Automation

## ADDED Requirements

### Requirement: CFX-Sourced Configuration (Traceability: `retester-automation`)

The system MUST accept retester configuration from `.cfx` archive files in addition to DSL blocks. When a CFX path is provided, the system MUST parse `config.xml` and relevant task XMLs to extract Monte Carlo runs, Walk-Forward cycles, databanks, and acceptance criteria. DSL-based configuration MUST remain the default path.

**Acceptance Criteria:** CFX config parsed correctly; DSL path unchanged; missing CFX sections raise clear errors.

#### Scenario: Retester config loaded from CFX

- GIVEN a `.cfx` archive containing a Retest task with MonteCarloRuns=100 and WalkForwardCycles=5
- WHEN `RetesterAutomation.from_cfx(cfx_path)` is called
- THEN a RetesterConfig is returned with monte_carlo_runs=100 and walkforward_cycles=5
- AND databanks are extracted from the CFX Data section

#### Scenario: DSL config path is unchanged

- GIVEN existing DSL-based RetesterConfig instantiation
- WHEN `RetesterAutomation.run(config, strategy_id, output_dir)` is called
- THEN behavior is identical to pre-change output
- AND no CFX parsing is attempted

### Requirement: Adaptive Retest Selection Hooks (Traceability: `retester-automation`)

The system MUST expose a `select_retest_mode(cfx_signals)` hook that returns either `AutomaticRetest` or `Retest`. The hook MUST be callable before `RetesterAutomation.run()` to allow adaptive mode selection. The hook MUST accept optional CFX metadata overrides.

**Acceptance Criteria:** Hook returns valid retest mode; integrates with Adaptive Retest Agent signals; CFX metadata override is respected.

#### Scenario: Hook selects AutomaticRetest for low-trade strategy

- GIVEN CFX signals with trade_count=25
- WHEN `select_retest_mode(signals)` is called
- THEN `AutomaticRetest` is returned
- AND the mode is valid for RetesterStage

#### Scenario: Hook respects CFX metadata override

- GIVEN CFX signals suggesting Retest but metadata `retest_mode=AutomaticRetest`
- WHEN `select_retest_mode(signals, metadata)` is called
- THEN `AutomaticRetest` is returned
- AND signal-based heuristics are bypassed
