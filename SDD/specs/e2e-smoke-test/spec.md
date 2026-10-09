# E2E Smoke Test Specification

## Purpose

Single end-to-end integration test validating the complete Phase 5b-5e pipeline flow:
1. Create temporary Knowledge Lake
2. Run pipeline with `--dry-run` (11 stages)
3. Verify pipeline history saved to Knowledge Lake
4. Generate HTML/JSON report
5. Query knowledge lake with `--sharpe ">1.0"`
6. Clean up temp directory on exit

No external SQX required (uses `--dry-run`). Single test file, < 30s execution in CI.

---

## Requirements

### Requirement: FR-001 — Test Fixture: Isolated Temporary Knowledge Lake

The system SHALL provide a pytest fixture that creates an isolated temporary directory for the Knowledge Lake root using `tempfile.TemporaryDirectory()`.

The fixture SHALL:
- Create temporary directory before test execution
- Set `QUANTLAB_KNOWLEDGE_ROOT` environment variable to the temp path
- Initialize Knowledge Lake structure (`knowledge/structured/`, `knowledge/results/`, `knowledge/pipeline-runs/`, `knowledge/index.yaml`)
- Clean up temp directory on test completion (pass or fail)
- Isolate test from user's actual Knowledge Lake

#### Scenario: Temp directory lifecycle
- GIVEN test starts with fixture
- WHEN fixture sets up
- THEN `QUANTLAB_KNOWLEDGE_ROOT` points to temp path
- AND Knowledge Lake directories exist
- AND on test exit, temp directory is removed

---

### Requirement: FR-002 — Pipeline Dry-Run Executes All 11 Stages

The system SHALL execute `quantlab pipeline run <pipeline_name> --dry-run` via CLI and verify all 11 stages execute.

The 11 stages (from Phase 4 SQX stages) SHALL be:
1. `validate` — SQX validation
2. `translate` — SQX → CFX translation
3. `optimize` — Walk-forward optimization
4. `walkforward` — Walk-forward analysis
5. `montecarlo` — Monte Carlo simulation
6. `portfolio` — Portfolio composition
7. `risk` — Risk analysis
8. `report` — Report generation
9. `knowledge_store` — Knowledge Lake persistence
10. `history` — Pipeline run history
11. `finalize` — Cleanup and summary

#### Scenario: Dry-run executes all stages
- GIVEN temp Knowledge Lake, valid pipeline config exists
- WHEN `quantlab pipeline run wf_opt --dry-run` executes
- THEN exit code 0
- AND stdout contains CFX base64 output
- AND all 11 stages logged as executed (mock/dry-run)
- AND no external SQX process spawned

---

### Requirement: FR-003 — Pipeline History Persisted to Knowledge Lake

The system SHALL persist pipeline run history to `knowledge/pipeline-runs/pipe-run-{timestamp}-{uuid}.yaml` after dry-run execution.

History entry SHALL include:
- `run_id`: `pipe-run-{YYYYMMDD-HHMMSS}-{short_uuid}`
- `pipeline_name`: name of pipeline executed
- `status`: `"completed"` (dry-run) or `"failed"`
- `started_at`, `completed_at`: ISO8601 timestamps
- `duration_seconds`: float
- `stages`: list of 11 stage objects with `name`, `status`, `duration_seconds`, `output`
- `config_snapshot`: pipeline config used
- `error`: null (or error message if failed)

#### Scenario: History file created after dry-run
- GIVEN pipeline dry-run completes
- WHEN test checks `knowledge/pipeline-runs/`
- THEN exactly one YAML file exists
- AND file has all required fields
- AND `stages` list has 11 entries
- AND all stages have `status: "completed"`

---

### Requirement: FR-004 — Report Generation Produces HTML and JSON

The system SHALL execute `quantlab report generate <campaign_id> --output-dir <temp>/reports` and produce both HTML and JSON outputs.

The test SHALL:
- Create a mock campaign with statistics in Knowledge Lake (using test fixtures)
- Run report generation
- Verify both `.html` and `.json` files exist
- Verify HTML contains 4 charts (equity, drawdown, trades, metrics)
- Verify JSON validates against `report.schema.json`
- Verify JSON contains campaign statistics, equity curve, trades, phases

#### Scenario: Report generated from mock campaign
- GIVEN mock campaign `smoke-test-campaign` with trades, equity, stats in Knowledge Lake
- WHEN `quantlab report generate smoke-test-campaign --output-dir /tmp/reports` runs
- THEN `/tmp/reports/smoke-test-campaign-report.html` exists
- AND `/tmp/reports/smoke-test-campaign-report.json` exists
- AND HTML file size > 10KB (has embedded content)
- AND JSON validates against schema

---

### Requirement: FR-005 — Knowledge Query Returns Results for Sharpe Filter

The system SHALL execute `quantlab knowledge query --sharpe ">1.0" --json --limit 10` and return matching campaigns.

The test SHALL:
- Ensure mock campaign has `sharpe: 1.5` in index
- Run query with Sharpe filter
- Verify JSON output contains the mock campaign
- Verify campaign_id matches
- Verify exit code 0

#### Scenario: Query filters by Sharpe > 1.0
- GIVEN Knowledge Lake has campaign with `sharpe: 1.5`
- WHEN `quantlab knowledge query --sharpe ">1.0" --json` executes
- THEN exit code 0
- AND JSON array length ≥ 1
- AND returned campaign has `sharpe >= 1.0`
- AND campaign_id is `smoke-test-campaign`

---

### Requirement: FR-006 — No External SQX Dependency

The system SHALL execute the entire smoke test without invoking external SQX binary.

The test SHALL:
- Use `--dry-run` for pipeline (produces CFX base64, no SQX)
- Use mock campaign data for report (no SQX results needed)
- Use mock index data for knowledge query (no SQX needed)
- Verify no subprocess calls to `sqx` or `java` occur

#### Scenario: No SQX subprocess spawned
- GIVEN test runs full sequence
- WHEN monitoring subprocess calls
- THEN no process named `sqx`, `java`, or `javaw` spawned
- AND all operations complete via Python internals

---

### Requirement: FR-007 — Test Completes in Under 30 Seconds

The system SHALL execute the full smoke test (setup → pipeline → history → report → query → teardown) in < 30 seconds.

#### Scenario: CI execution time
- GIVEN test runs in CI environment
- WHEN test completes
- THEN total elapsed time < 30 seconds

---

### Requirement: FR-008 — Single Test File Structure

The system SHALL implement the smoke test in a single pytest file: `tests/test_phase5b_e_smoke.py`.

File structure:
```python
# tests/test_phase5b_e_smoke.py
import pytest
import tempfile
import os
import subprocess
import yaml
import json
from pathlib import Path

@pytest.fixture
def temp_knowledge_lake():
    """Create isolated temp Knowledge Lake."""
    ...

def test_phase5b_e_smoke_full_pipeline(temp_knowledge_lake):
    """Full E2E smoke test: temp lake → pipeline dry-run → history → report → query."""
    ...
```

#### Scenario: Test file exists and passes
- GIVEN `tests/test_phase5b_e_smoke.py` exists
- WHEN `pytest tests/test_phase5b_e_smoke.py -v` runs
- THEN 1 test passes
- AND test duration < 30s

---

## Interface Specifications

### CLI Commands Used

```bash
# Pipeline dry-run
quantlab pipeline run wf_opt --dry-run

# Pipeline history
quantlab pipeline history --json --limit 5

# Report generation
quantlab report generate <campaign_id> --output-dir <path> --html --json

# Knowledge query
quantlab knowledge query --sharpe ">1.0" --json --limit 10
```

### Environment Variable

```bash
QUANTLAB_KNOWLEDGE_ROOT=/tmp/quantlab-smoke-test-xyz123
```

### Mock Campaign Data Structure (Knowledge Lake)

```
knowledge/
├── structured/
│   └── smoke-test-campaign/
│       ├── metadata.yaml
│       ├── statistics.yaml      # Contains sharpe: 1.5, pf: 2.1, etc.
│       ├── equity_curve.yaml
│       └── trades.yaml
├── results/
├── pipeline-runs/
└── index.yaml                   # v2 schema with metrics
```

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| Single test file `tests/test_phase5b_e_smoke.py` exists | `ls tests/test_phase5b_e_smoke.py` |
| Test passes in CI | `pytest tests/test_phase5b_e_smoke.py -v` exit code 0 |
| Test completes < 30s | CI log shows duration < 30s |
| Temp Knowledge Lake created and cleaned | Fixture creates `QUANTLAB_KNOWLEDGE_ROOT`, removes on exit |
| Pipeline dry-run executes 11 stages | History YAML has 11 stage entries, all completed |
| Pipeline history saved to `knowledge/pipeline-runs/` | YAML file exists with correct schema |
| Report generates HTML + JSON | Both files exist, HTML > 10KB, JSON validates schema |
| Knowledge query filters by Sharpe | JSON output contains campaign with sharpe ≥ 1.0 |
| No external SQX process spawned | Subprocess monitoring confirms |
| Test uses only stdlib + pytest + existing deps | No new dependencies in pyproject.toml |

---

## Non-Functional Requirements

- **Performance**: Full test < 30s (target: ~15s)
- **Dependencies**: Zero new dependencies (uses `pytest`, `tempfile`, `subprocess`, `yaml`, `json`, existing quantlab modules)
- **Isolation**: Complete filesystem isolation via `TemporaryDirectory`
- **Determinism**: Same mock data every run; no flakiness
- **CI-friendly**: No network, no external binaries, no services
- **Debuggable**: On failure, temp dir preserved if `QUANTLAB_SMOKE_KEEP_TMP=1` set

---

## Implementation Notes

### Test Fixture Pattern

```python
@pytest.fixture
def temp_knowledge_lake(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        kl_root = Path(tmpdir) / "knowledge"
        kl_root.mkdir(parents=True)
        (kl_root / "structured").mkdir()
        (kl_root / "results").mkdir()
        (kl_root / "pipeline-runs").mkdir()
        # Write initial index.yaml v2
        index = {"version": 2, "structured": {}, "results": {}}
        (kl_root / "index.yaml").write_text(yaml.dump(index))
        # Set env var
        monkeypatch.setenv("QUANTLAB_KNOWLEDGE_ROOT", str(kl_root))
        yield kl_root
        # Cleanup automatic via TemporaryDirectory context manager
```

### Mock Campaign Creation

```python
def create_mock_campaign(kl_root: Path, campaign_id: str = "smoke-test-campaign"):
    camp_dir = kl_root / "structured" / campaign_id
    camp_dir.mkdir(parents=True)
    # metadata.yaml
    (camp_dir / "metadata.yaml").write_text(yaml.dump({
        "campaign_id": campaign_id,
        "created": "2024-07-18T12:00:00Z",
        "tags": {"test": "smoke"},
        "links": []
    }))
    # statistics.yaml (sharpe=1.5 for query test)
    (camp_dir / "statistics.yaml").write_text(yaml.dump({
        "sharpe": 1.5,
        "profit_factor": 2.1,
        "win_rate": 58.3,
        "max_drawdown": 12.5,
        "total_trades": 150,
        "net_profit": 25000.0
    }))
    # equity_curve.yaml (minimal)
    (camp_dir / "equity_curve.yaml").write_text(yaml.dump([
        {"timestamp": "2024-01-01T00:00:00Z", "equity": 100000},
        {"timestamp": "2024-01-02T00:00:00Z", "equity": 100150},
    ]))
    # trades.yaml (minimal)
    (camp_dir / "trades.yaml").write_text(yaml.dump([
        {"entry_time": "2024-01-01T01:00:00Z", "exit_time": "2024-01-01T02:00:00Z",
         "direction": "long", "profit": 150.0, "symbol": "EURUSD"}
    ] * 150))
    # Rebuild index
    from quantlab.knowledge.indexer import Indexer
    Indexer(kl_root).build_index()
```

### Pipeline Config for Dry-Run

Minimal pipeline YAML at `config/pipelines/wf_opt.yaml` (existing from Phase 5d):
```yaml
name: "wf_opt"
description: "Walk-forward optimization"
version: "1.0"
stages:
  - name: validate
    type: validate
    config: {}
  - name: translate
    type: translate
    config: {}
  # ... all 11 stages with type matching registry
```

### CLI Invocation Helper

```python
def run_cli(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    cmd = ["quantlab"] + args
    return subprocess.run(cmd, capture_output=True, text=True, env=env or os.environ)
```

---

## Rollback Plan

If smoke test causes issues:
1. Delete `tests/test_phase5b_e_smoke.py`
2. No other files modified (test-only)
3. CI passes without smoke test