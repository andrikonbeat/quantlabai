"""RED tests for WU-8: strategies.csv artifact signal (REQ-14, REQ-21).

Covers:
- ``parse_strategy_counts_csv`` — missing/empty/garbage tolerated, partial
  rows tolerated, duplicate names accumulate (REQ-21).
- ``MonitorSnapshot.strategy_counts`` — new field, default ``{}``,
  surfaced through ``CampaignMonitor.current_snapshot`` (REQ-14).
- ``build_prompt`` — exported strategy counts included in the LLM prompt
  (REQ-14).
- Stall detection — zero-growth stall considers artifact progress: CSV
  growth resets the stall counter even when the status-text count is flat
  (REQ-21); legacy polls without the artifact behave unchanged.
"""

from __future__ import annotations

import pytest

from quantlab.sqx.campaign_monitor import (
    BaselineConfig,
    CampaignMonitor,
    parse_strategy_counts_csv,
)
from quantlab.sqx.llm_generation_monitor import (
    MonitorSnapshot,
    build_prompt,
)

CSV_HEADER = "Name,Profit Factor,Sharpe Ratio\n"
CSV_ALPHA = "strat_alpha,1.4,1.2\n"


def _baseline() -> BaselineConfig:
    return BaselineConfig(
        startup_grace_s=1000.0,
        expected_gen_time_s=1.0,
        early_gen_multiplier=1.0,
        early_gen_count=3,
        stall_polls_threshold=3,
        rejection_warn_gens=3,
    )


def _monitor(**kwargs: object) -> CampaignMonitor:
    return CampaignMonitor(
        campaign_id="csv-sig",
        base_url="http://127.0.0.1:5050",
        baseline=_baseline(),
        **kwargs,
    )


class TestParseStrategyCountsCsv:
    """T8.1: parse_strategy_counts_csv tolerates missing/partial input."""

    def test_none_returns_empty(self) -> None:
        assert parse_strategy_counts_csv(None) == {}

    def test_empty_string_returns_empty(self) -> None:
        assert parse_strategy_counts_csv("") == {}

    def test_whitespace_only_returns_empty(self) -> None:
        assert parse_strategy_counts_csv("   \n\t\n") == {}

    def test_garbage_text_returns_empty(self) -> None:
        # Not CSV at all — header has no "Name" column → tolerated as {}.
        assert parse_strategy_counts_csv("just some prose\nand more prose\n") == {}

    def test_single_strategy(self) -> None:
        text = CSV_HEADER + CSV_ALPHA
        assert parse_strategy_counts_csv(text) == {"strat_alpha": 1}

    def test_multiple_strategies(self) -> None:
        text = (
            CSV_HEADER
            + CSV_ALPHA
            + "strat_beta,1.8,0.9\n"
            + "strat_gamma,1.2,1.5\n"
        )
        assert parse_strategy_counts_csv(text) == {
            "strat_alpha": 1,
            "strat_beta": 1,
            "strat_gamma": 1,
        }

    def test_duplicate_names_accumulate(self) -> None:
        text = (
            CSV_HEADER
            + CSV_ALPHA
            + CSV_ALPHA
            + "strat_beta,1.8,0.9\n"
        )
        assert parse_strategy_counts_csv(text) == {
            "strat_alpha": 2,
            "strat_beta": 1,
        }

    def test_rows_without_name_skipped(self) -> None:
        text = (
            "Name,Profit Factor\n"
            "strat_alpha,1.4\n"
            ",1.9\n"  # missing Name — tolerated, skipped
            "strat_beta,1.7\n"
        )
        assert parse_strategy_counts_csv(text) == {
            "strat_alpha": 1,
            "strat_beta": 1,
        }

    def test_header_without_name_returns_empty(self) -> None:
        text = "Profit Factor,Sharpe Ratio\n1.4,1.2\n"
        assert parse_strategy_counts_csv(text) == {}


class TestSnapshotStrategyCounts:
    """T8.1/REQ-14: MonitorSnapshot carries strategy_counts."""

    def test_default_is_empty(self) -> None:
        snap = MonitorSnapshot(status_text="", generated_count=0)
        assert snap.strategy_counts == {}

    def test_constructor_sets_counts(self) -> None:
        snap = MonitorSnapshot(
            status_text="",
            generated_count=0,
            strategy_counts={"strat_alpha": 1},
        )
        assert snap.strategy_counts == {"strat_alpha": 1}

    def test_current_snapshot_exposes_counts(self) -> None:
        monitor = _monitor()
        monitor._last_status_text = "Strategies generated  10\n"
        monitor._last_count = 10
        events = monitor._poll_tick(
            "Strategies generated  10\n",
            elapsed=5.0,
            strategy_counts={"strat_alpha": 1, "strat_beta": 1},
        )
        assert events == []
        snap = monitor.current_snapshot()
        assert snap.strategy_counts == {"strat_alpha": 1, "strat_beta": 1}

    def test_snapshot_defaults_empty_counts(self) -> None:
        snap = _monitor().current_snapshot()
        assert snap.strategy_counts == {}


class TestBuildPromptStrategyCounts:
    """T8.1/REQ-14: build_prompt includes exported strategy counts."""

    def test_prompt_includes_counts(self) -> None:
        snap = MonitorSnapshot(
            status_text="Strategies generated  10",
            generated_count=10,
            strategy_counts={"strat_alpha": 1, "strat_beta": 2},
        )
        prompt = build_prompt(snap)
        assert "Exported strategy counts" in prompt
        assert "strat_alpha: 1" in prompt
        assert "strat_beta: 2" in prompt

    def test_prompt_says_unknown_when_empty(self) -> None:
        snap = MonitorSnapshot(status_text="", generated_count=0)
        prompt = build_prompt(snap)
        assert "Exported strategy counts" in prompt
        assert "unknown" in prompt


class TestArtifactGrowthStall:
    """T8.1/REQ-21: zero-growth stall considers artifact progress."""

    STATUS = "Strategies generated  5\nGeneration: 3\n"

    def test_artifact_growth_resets_zero_growth_stall(self) -> None:
        """Flat status count + growing strategies.csv → NOT a stall."""
        monitor = _monitor()
        monitor._last_count = 5  # established throughput
        types: list[str] = []
        for i in range(5):
            events = monitor._poll_tick(
                self.STATUS,
                elapsed=100.0,
                strategy_counts={f"strat_{j}": 1 for j in range(i + 1)},
            )
            types += [e.event_type for e in events]
        assert "zero_growth_stall" not in types

    def test_flat_artifact_and_flat_status_stalls(self) -> None:
        """Flat status count + flat strategies.csv → stall after threshold."""
        monitor = _monitor()
        monitor._last_count = 5
        types: list[str] = []
        for _ in range(4):
            events = monitor._poll_tick(
                self.STATUS,
                elapsed=100.0,
                strategy_counts={"strat_alpha": 1},
            )
            types += [e.event_type for e in events]
        assert "zero_growth_stall" in types

    def test_legacy_poll_without_artifact_unchanged(self) -> None:
        """No strategy_counts param → stall detection behaves as before."""
        monitor = _monitor()
        monitor._last_count = 5
        types: list[str] = []
        for _ in range(3):
            events = monitor._poll_tick(self.STATUS, elapsed=100.0)
            types += [e.event_type for e in events]
        assert "zero_growth_stall" in types
