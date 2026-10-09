# Delta for knowledge-store

## ADDED Requirements

### Requirement: Real OHLC Dataset Seeding

The system MUST seed `knowledge/datasets/` with real Dukascopy OHLC via `DataManager`/`JForexProvider` for a small symbol set at M1/M5/H1, exposed as a CLI command (`sqx kb seed`-style, seeder precedent). Seeding MUST NOT fabricate market data; tests MUST run under `SQX_FORCE_MOCK=1`.

#### Scenario: Seed writes dataset files

- GIVEN `SQX_FORCE_MOCK=1` and a configured symbol set
- WHEN the seed command runs
- THEN `knowledge/datasets/{symbol}/` contains OHLC samples
- AND `rebuild_index` records them

#### Scenario: Environment unavailable fails clearly

- GIVEN no JForex history and no SQCLI_PATH
- WHEN the seed command runs
- THEN it exits with a clear error naming the missing dependency
- AND any partially written files are reported

### Requirement: Operational Directory Population

`campaign-phases/` and `pipeline-runs/` MUST be populated organically by the flow: every campaign run MUST write phase envelopes and pipeline runs via the artifact writers.

#### Scenario: Campaign run populates operational dirs

- GIVEN a campaign executing all 14 phases
- WHEN the run completes
- THEN `campaign-phases/{campaign_id}/` holds one envelope per phase
- AND `pipeline-runs/` holds the run record

#### Scenario: Re-run is idempotent

- GIVEN a re-executed campaign phase
- WHEN the envelope is written again
- THEN the existing envelope is updated, not duplicated
- AND no error is raised

### Requirement: Index v5 Migration Acceptance

The deployed `knowledge/index.yaml` MUST report `_version: '5'` and include `campaign_phases`, `parameter_matrix`, `guardian_feedback`, and `maintenance` keys after rebuild (store.py:470-483). `test_knowledge_store_v5.py` MUST stay green.

#### Scenario: Stale v4 index migrates

- GIVEN index.yaml with `_version: '4'`
- WHEN `read_index()` runs
- THEN the version is upgraded to 5
- AND the v5 keys are present in the index