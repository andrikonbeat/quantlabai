# JForex Deploy Specification

## Purpose

Export a compiled SQX strategy to JForex 4 as runnable Java source (`.java`),
optionally routing it through the compiler pipeline to a `.jfx` artifact so it
can be deployed to a live JForex account.

## Requirements

### JFD-REQ-01: Export strategy source

The system SHALL export a strategy's Java source code from SQX via the HTTP API
into a target directory, naming the file after the strategy (or an explicit
`strategy_name`), and SHALL create the output directory when missing.

#### Scenario: Export a strategy

- GIVEN a running SQX daemon and a valid `strategy_id`
- WHEN `export_strategy(strategy_id, output_dir)` is called
- THEN a `.java` file is written under `output_dir` and a `JfxArtifact` is returned

#### Scenario: Export failure raises typed error

- GIVEN an unreachable SQX server
- WHEN `export_strategy` is called
- THEN `JForexConnectionError` is raised

#### Scenario: Server error maps to typed error

- GIVEN the SQX HTTP API returns a 5xx response
- WHEN `export_strategy` is called
- THEN `JForexServerError` is raised

### JFD-REQ-02: Compile route

The system SHALL route an exported `.java` through `CompilerPipeline` when the
compiler is enabled (`QUANTLAB_COMPILER` unset or non-zero), packaging a `.jfx`
artifact; when the compiler is disabled (`QUANTLAB_COMPILER=0`) it SHALL keep
the `.java`-only path.

#### Scenario: Compiler enabled produces jfx

- GIVEN `QUANTLAB_COMPILER` is enabled and a `java_path` to a valid export
- WHEN `compile_strategy(java_path)` is called
- THEN the result is a compiled artifact (`.jfx`)
- AND compilation failure blocks deploy — no artifact is produced

#### Scenario: Compiler disabled keeps java path

- GIVEN `QUANTLAB_COMPILER=0` in the environment
- WHEN `compile_strategy(java_path)` is called
- THEN the original `java_path` is returned unchanged (`.java`-only deploy)

### JFD-REQ-03: Export-and-compile pipeline

The system SHALL support a single `export_and_compile()` entry point that
exports the strategy and then routes it through the compiler, so deploy flows
have one call.

#### Scenario: Full export-then-compile

- GIVEN a valid strategy and an enabled compiler
- WHEN `export_and_compile(strategy_id, output_dir)` is called
- THEN the strategy is exported and compiled to a `.jfx` artifact

### JFD-REQ-04: Deploy custom indicators

The system SHALL copy custom indicators from the SQX install into the JForex
strategies directory when the source directory is provided, creating the
target directory when missing.

#### Scenario: Deploy indicators

- GIVEN an existing `sqx_custom_indicators_dir`
- WHEN `deploy_indicators(jforex_strategies_dir, sqx_custom_indicators_dir)` is called
- THEN indicator sources are copied into the target directory

#### Scenario: Missing source raises

- GIVEN no usable `sqx_custom_indicators_dir`
- WHEN `deploy_indicators` is called
- THEN `JForexError` is raised and nothing is copied

## Test Coverage Notes

`tests/phase4/test_jforex_deploy.py` does NOT exist. The deploy routing is
exercised indirectly by `tests/compiler/test_jforex_routing.py`. The
export/compile/indicator scenarios above are derived from module source;
scenarios JFD-REQ-03 and JFD-REQ-04 currently lack a direct unit test file.