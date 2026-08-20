## phase-runner (New)

### Requirement: phase_runner CLI (REQ-818)

The system MUST provide a `phase_runner` CLI under `sdk/quantlab/campaign/` that bridges a `PhaseDirective` to its production executor (REQ-815) and returns a validated `PhaseResult`. The CLI SHALL accept `--phase` and `--directive <json>`, enforce REQ-803 scope deny-first, and emit the envelope as JSON. Long-op handoff SHALL target `/tmp/opencode` with `timeout >= 240`, a cleanup command, and a per-phase report.

#### Scenario: Runner executes a phase

- GIVEN `phase_runner` invoked with `--phase research --directive <json>`
- WHEN the executor runs
- THEN a validated `PhaseResult` is emitted as JSON
- AND the phase id matches the directive

#### Scenario: Out-of-scope directive rejected

- GIVEN a directive whose scope contains a forbidden action
- WHEN `phase_runner` validates it
- THEN execution is rejected with an authority error
- AND no SDK stage runs

#### Scenario: Handoff script under /tmp/opencode

- GIVEN a mechanical phase returning a `LongOpSpec`
- WHEN the runner emits the handoff
- THEN `log_path` is under `/tmp/opencode`, `timeout >= 240`, and `cleanup` is set
- AND the per-phase report records the handoff
