# Unified Execution Substrate Specification

## Purpose

Single execution runner for all SQX campaign phases (build, retest, optimize, portfolio), replacing overlapping CommandDispatcher, cli_wrapper._dispatch_real, and CampaignOrchestrator paths.

## Requirements

### Requirement: Single Parameterized Runner

The system MUST provide one execution substrate (daemon + lifecycle + polling + event detection + checkpoint/resume + export) parameterized per phase. The substrate SHALL support build, retest, optimize, and portfolio phases through configuration, not separate code paths.

#### Scenario: Build phase uses substrate

- GIVEN phase=build configuration
- WHEN the substrate starts
- THEN it loads the CFX project via the unified daemon path
- AND polls for completion with stall detection

#### Scenario: Retest phase reuses same runner

- GIVEN phase=retest configuration
- WHEN the substrate starts
- THEN it reuses the same runner code path
- AND produces retest artifacts in Knowledge Lake

#### Scenario: Legacy fallback when flag disabled

- GIVEN QUANTLAB_LEGACY_EXECUTION=true
- WHEN a build phase runs
- THEN the legacy CommandDispatcher path is used
- AND behavior matches the current implementation

### Requirement: Checkpoint and Resume

The system MUST persist execution checkpoints at phase boundaries and on stall detection. The substrate SHALL support resume from the last checkpoint without restarting the phase.

#### Scenario: Stall triggers checkpoint

- GIVEN an optimize phase running for 30 minutes
- WHEN stall detection triggers after 2x expected duration
- THEN a checkpoint is written with current progress
- AND the phase enters HOLD for human review

#### Scenario: Resume from checkpoint

- GIVEN a checkpoint exists for a retest phase
- WHEN the substrate resumes
- THEN it continues from the checkpoint
- AND does not restart the phase from scratch

### Requirement: Event Detection

The system MUST detect completion, error, stall, and daemon-lost events during polling. Events SHALL be emitted to the campaign event bus and logged to Knowledge Lake.

#### Scenario: Completion event advances pipeline

- GIVEN a build phase completing successfully
- WHEN the substrate detects completion
- THEN a completion event is emitted
- AND the pipeline advances to the next phase

#### Scenario: Daemon lost triggers HOLD

- GIVEN the SQX daemon becomes unreachable
- WHEN the substrate detects daemon-lost
- THEN a daemon_lost event is emitted
- AND the campaign enters HOLD state

### Requirement: SQX_FORCE_MOCK Compliance

The substrate MUST honor the SQX_FORCE_MOCK environment variable. When set, all SQX interactions SHALL use the mock server path; when unset, the real daemon path is used.

#### Scenario: Mock mode uses mock server

- GIVEN SQX_FORCE_MOCK=1
- WHEN the substrate starts a build phase
- THEN it connects to the mock server
- AND no real SQX process is launched

#### Scenario: Production mode uses real daemon

- GIVEN SQX_FORCE_MOCK is unset
- WHEN the substrate starts a build phase
- THEN it connects to the real SQX daemon
- AND real backtest execution occurs
