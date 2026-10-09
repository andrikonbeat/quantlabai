# Execution Substrate Specification

## Purpose

A unified execution and monitoring substrate replacing the three overlapping dispatch paths (`CommandDispatcher`, `cli_wrapper._dispatch_real`, `CampaignOrchestrator`): one daemon + project lifecycle + polling + event detection + checkpoint + export, parameterized per phase (build/retest/optimize/portfolio). Data scope is Dukascopy-only.

## Requirements

### Requirement: Unified Substrate (REQ-26)

The system MUST provide a single execution substrate parameterized by phase, providing daemon lifecycle, project load/start/status/stop, polling, event detection, checkpoint/resume, and export. When the unified flag is enabled, each phase MUST run on the substrate and produce output identical to the legacy path it replaces for the same inputs.

#### Scenario: Phase runs on substrate

- GIVEN the unified flag enabled and a build phase config
- WHEN the phase executes
- THEN the substrate loads the project, polls status, detects events, and exports results
- AND output artifacts match the legacy path for identical inputs

#### Scenario: Checkpoint resume

- GIVEN a phase interrupted at checkpoint N
- WHEN the phase is re-run
- THEN execution resumes at checkpoint N+1 without redoing completed work

### Requirement: Chained Multi-Task Runs (REQ-27)

The substrate SHALL execute retest and optimize chained in ONE project load via a multi-task Custom Project (REQ-23), preserving phase order and human gates between tasks. Only Dukascopy databanks MUST be used.

#### Scenario: Retest then optimize in one load

- GIVEN a multi-task project declaring Retest then Optimize tasks
- WHEN the substrate runs the project
- THEN SQX executes both tasks in declared order in a single load
- AND each task's exports land in its phase checkpoint

#### Scenario: Gate holds between chained tasks

- GIVEN a human gate configured between retest and optimize
- WHEN retest completes
- THEN the substrate holds before optimize until the gate resolves

### Requirement: Legacy Parity (REQ-28)

The substrate MUST keep legacy dispatch paths operational behind a flag until parity is proven; the 2790-test suite MUST keep passing on the legacy path. `SQX_FORCE_MOCK` SHALL remain honored for the suite.

#### Scenario: Legacy path unchanged

- GIVEN the unified flag disabled
- WHEN dispatch runs
- THEN the legacy path executes with prior behavior
- AND the full test suite passes

#### Scenario: Mock mode retained

- GIVEN `SQX_FORCE_MOCK` set
- WHEN the substrate runs
- THEN mock server responses are used
