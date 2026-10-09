# Delta for campaign-phase-delegation

## ADDED Requirements

### Requirement: Stage Artifact Persistence (REQ-819)

The delegation layer MUST persist every artifact key claimed in `PhaseResult.artifacts` to the Knowledge Lake. `_run_sdk_stage` SHALL call `save_phase_envelope` (knowledge/store.py:638) for each completed stage, writing `campaign-phases/{campaign_id}/{phase}/envelope.json` with status, timestamps, artifacts, and next gate. A stage MUST NOT claim an artifact key it did not persist.

#### Scenario: Stage artifacts persisted

- GIVEN a completed research stage returning an artifacts list
- WHEN `execute_phase()` returns the `PhaseResult`
- THEN `campaign-phases/{campaign_id}/research/envelope.json` exists
- AND each artifact key resolves to a real file

#### Scenario: Missing knowledge_root degrades, does not crash

- GIVEN a directive payload without `knowledge_root`
- WHEN the stage completes
- THEN the result records the gap in `risks`
- AND no artifact is claimed as persisted

#### Scenario: Failed stage still leaves an envelope

- GIVEN a retest stage that fails with an SQX error
- WHEN the envelope is written
- THEN `envelope.json` carries failed status and lists the error log
- AND the next gate is HOLD