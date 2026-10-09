# Delta for full-campaign-lifecycle

## ADDED Requirements

### Requirement: Canonical Pipeline Entry Counts (G5)

Code is authoritative: `build_pipeline` (agents/research_director.py:221-487) MUST be treated as the source of truth for stage counts — 16 non-orchestrated entries (11 agent stages + 5 gates), 25 orchestrated entries (17 agent stages + 8 gates), and 27 when retest/optimize are configured (19 agent stages + 8 gates). The retired "17-stage pipeline" wording MUST NOT be reintroduced; the 14-phase lifecycle (REQ-37) and `flow.py PHASES` remain the canonical phase set.

#### Scenario: Counts match code per mode

- GIVEN the code builds the default orchestrated pipeline
- WHEN the pipeline entries are counted
- THEN the non-orchestrated build yields 16, the orchestrated 25, and with retest/optimize 27
- AND an integrity test pins these counts

#### Scenario: Stale doc wording flagged

- GIVEN a doc claiming "17 stages"
- WHEN the doc is reviewed against `build_pipeline`
- THEN the claim is flagged stale
- AND the code counts win