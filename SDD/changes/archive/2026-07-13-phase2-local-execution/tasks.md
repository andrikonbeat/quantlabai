# Tasks: Phase 2 — SQX Local Execution Pipeline

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,140 total across 3 PRs (~380, ~390, ~370) |
| 400-line budget risk | Low |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Foundation) → PR 2 (CampaignRunner) → PR 3 (Resilience) |
| Delivery strategy | auto-chain |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Foundation — models, dispatcher, license, executor fix | PR 1 | Base = feature/tracker branch |
| 2 | Core CampaignRunner — sequential flow + progress | PR 2 | Base = PR 1 branch |
| 3 | Resilience — checkpoint, retry, timeout | PR 3 | Base = PR 2 branch |

## PR 1 — Foundation

- [x] 1.1 Create `sdk/quantlab/pipeline/models.py` with `CampaignPhase`, `CampaignStatus`, `LicenseStatus` enums
- [x] 1.2 Create `sdk/quantlab/pipeline/error.py` with `LicenseError` and `CampaignError` extending `QuantLabError`
- [x] 1.3 Create `sdk/quantlab/pipeline/dispatcher.py` with `CommandDispatcher` — structured key=value arg construction, daemon lifecycle methods
- [x] 1.4 Create `sdk/quantlab/pipeline/license.py` with `LicenseManager` — status check via `action=info`, activation via `action=update`
- [x] 1.5 Modify `sdk/quantlab/cli/runner.py` — `RealExecutor.execute()` from `command.split()` to `[binary, *args]` list
- [x] 1.6 Modify `sdk/quantlab/tools/platform.py` — add `get_sqcli_dir()` for asset base resolution
- [x] 1.7 Create `sdk/tests/test_pipeline.py` — unit tests for models, dispatcher with MockExecutor, license manager parsing

Also created `pipeline/__init__.py` as package init with public API re-exports.

## PR 2 — Core CampaignRunner

- [x] 2.1 Create `sdk/quantlab/pipeline/progress.py` with `ProgressCallback` protocol and `PhaseStatus` enum
- [x] 2.2 Create `sdk/quantlab/pipeline/campaign.py` with `CampaignConfig`, `CampaignResult`, `CampaignRunner` — 7-phase sequential flow with polling loop and progress callbacks
- [x] 2.3 Update `sdk/quantlab/pipeline/__init__.py` — re-export public API (models, error, dispatcher, license, campaign, progress)
- [x] 2.4 Modify `sdk/tests/test_pipeline.py` — add integration tests for CampaignRunner full flow, callback firing, poll loop timing

## PR 3 — Resilience

- [x] 3.1 Create `sdk/quantlab/pipeline/checkpoint.py` with `CheckpointManager` — JSON load/save/resume
- [x] 3.2 Modify `sdk/quantlab/pipeline/models.py` — add `CampaignCheckpoint` dataclass
- [x] 3.3 Modify `sdk/quantlab/pipeline/campaign.py` — add checkpoint save/restore, retry wrapper, per-phase timeout
- [x] 3.4 Modify `sdk/tests/test_pipeline.py` — add tests for checkpoint recovery, retry logic, timeout error scenarios
