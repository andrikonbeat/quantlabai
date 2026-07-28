"""Tests for Campaign Monitor — helpers, models, and CampaignMonitor class."""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quantlab.sqx.campaign_monitor import (
    BaselineConfig,
    CampaignMonitor,
    WatcherEvent,
    compute_baseline,
    extract_error_patterns,
    extract_results_count,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def baseline_m1() -> BaselineConfig:
    """Standard M1 baseline for testing."""
    return BaselineConfig(
        startup_grace_s=60.0,
        expected_gen_time_s=32.0,
        early_gen_multiplier=2.0,
        early_gen_count=3,
        stall_polls_threshold=21,
        rejection_warn_gens=3,
    )


@pytest.fixture
def baseline_h1() -> BaselineConfig:
    """Standard H1 baseline for testing."""
    return BaselineConfig(
        startup_grace_s=15.0,
        expected_gen_time_s=32.0,
        early_gen_multiplier=2.0,
        early_gen_count=3,
        stall_polls_threshold=21,
        rejection_warn_gens=3,
    )


@pytest.fixture
def fast_baseline() -> BaselineConfig:
    """Fast baseline (short thresholds) for integration tests."""
    return BaselineConfig(
        startup_grace_s=1.0,
        expected_gen_time_s=2.0,
        early_gen_multiplier=1.0,
        early_gen_count=1,
        stall_polls_threshold=3,
        rejection_warn_gens=2,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4.1: extract_results_count
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractResultsCount:
    """Unit tests for ``extract_results_count``."""

    def test_found_standard(self) -> None:
        """Standard status text with strategies generated."""
        text = (
            "Status of project TestCampaign\n"
            "--------------------------------------------------\n"
            "Strategies generated                         255\n"
            "Running time so far                          30 s.\n"
            "In databank                                      5\n"
        )
        assert extract_results_count(text) == 255

    def test_found_small_number(self) -> None:
        """Single-digit strategy count."""
        text = (
            "Strategies generated                           3\n"
        )
        assert extract_results_count(text) == 3

    def test_found_large_number(self) -> None:
        """Four-digit strategy count."""
        text = (
            "Strategies generated                        1024\n"
        )
        assert extract_results_count(text) == 1024

    def test_missing_line(self) -> None:
        """Status text without 'Strategies generated' returns 0."""
        text = (
            "Status of project X\n"
            "--------------------------------------------------\n"
            "Running time so far                          5 s.\n"
        )
        assert extract_results_count(text) == 0

    def test_empty_string(self) -> None:
        """Empty string returns 0."""
        assert extract_results_count("") == 0

    def test_none_coerced(self) -> None:
        """None is treated as empty and returns 0."""
        assert extract_results_count("") == 0

    def test_malformed_number(self) -> None:
        """Non-numeric value after label returns 0."""
        text = "Strategies generated  abc\n"
        assert extract_results_count(text) == 0

    def test_zero_count(self) -> None:
        """Strategies generated 0 is valid."""
        text = "Strategies generated                           0\n"
        assert extract_results_count(text) == 0

    def test_case_insensitive(self) -> None:
        """The label match is case-insensitive."""
        text = "STRATEGIES GENERATED                          42\n"
        assert extract_results_count(text) == 42

    def test_variable_whitespace(self) -> None:
        """Handles variable whitespace between label and number."""
        text = "Strategies generated 7\n"
        assert extract_results_count(text) == 7


# ═══════════════════════════════════════════════════════════════════════════
# 4.2: extract_error_patterns
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractErrorPatterns:
    """Unit tests for ``extract_error_patterns``."""

    def test_clean_status(self) -> None:
        """Clean status with no errors returns empty list."""
        text = (
            "Strategies generated                          42\n"
            "Running time so far                          5 s.\n"
            "In databank                                      3\n"
        )
        assert extract_error_patterns(text) == []

    def test_cannot_start_project(self) -> None:
        """Lines containing 'Cannot start project' are caught."""
        text = (
            "Strategies generated                           0\n"
            "Cannot start project 'Test', it has config errors in task 'Build'\n"
        )
        errors = extract_error_patterns(text)
        assert len(errors) == 1
        assert "Cannot start project" in errors[0]

    def test_config_errors_pattern(self) -> None:
        """Lines containing 'config errors' are caught."""
        text = (
            "Project 'X' has config errors in task 'Build'\n"
            "Strategies generated                           0\n"
        )
        errors = extract_error_patterns(text)
        assert len(errors) == 1
        assert "config errors" in errors[0]

    def test_error_prefix(self) -> None:
        """Lines starting with 'Error:' are caught."""
        text = (
            "Error: Project configuration is invalid\n"
        )
        errors = extract_error_patterns(text)
        assert len(errors) == 1
        assert "Error:" in errors[0]

    def test_cannot_get_pattern(self) -> None:
        """Lines containing 'Cannot get' are caught."""
        text = (
            "Cannot get project status\n"
        )
        errors = extract_error_patterns(text)
        assert len(errors) == 1
        assert "Cannot get" in errors[0]

    def test_multiple_errors(self) -> None:
        """Multiple error lines are all returned."""
        text = (
            "Error: Invalid engine\n"
            "Cannot start project 'Test'\n"
            "Project has config errors\n"
        )
        errors = extract_error_patterns(text)
        assert len(errors) == 3

    def test_max_three_errors(self) -> None:
        """At most 3 error lines are returned when 4+ are present."""
        text = "\n".join([
            "Error: First error",
            "Error: Second error",
            "Error: Third error",
            "Error: Fourth error — should be omitted",
            "Error: Fifth error — should be omitted",
        ])
        errors = extract_error_patterns(text)
        assert len(errors) == 3
        assert "Fourth" not in errors[2]

    def test_empty_string(self) -> None:
        """Empty string returns empty list."""
        assert extract_error_patterns("") == []

    def test_case_insensitive(self) -> None:
        """Pattern matching is case-insensitive."""
        text = "CANNOT START PROJECT 'X'\n"
        errors = extract_error_patterns(text)
        assert len(errors) == 1

    def test_error_in_running_status(self) -> None:
        """Error detected even when strategy output exists."""
        text = (
            "Strategies generated                          12\n"
            "Running time so far                          10 s.\n"
            "Error: Cannot get databank\n"
        )
        errors = extract_error_patterns(text)
        assert len(errors) == 1
        assert "Cannot get" in errors[0]


# ═══════════════════════════════════════════════════════════════════════════
# 4.3: compute_baseline
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeBaseline:
    """Unit tests for ``compute_baseline``."""

    def test_m1_timeframe_sixty_seconds_grace(self) -> None:
        """M1 timeframe gets 60s startup grace."""
        config = {"timeframe": "M1", "walk_forward": True, "monte_carlo": True}
        baseline = compute_baseline(config, poll_interval=5.0)
        assert baseline.startup_grace_s == 60.0

    def test_h1_timeframe_fifteen_seconds_grace(self) -> None:
        """H1 timeframe gets 15s startup grace."""
        config = {"timeframe": "H1", "walk_forward": True, "monte_carlo": True}
        baseline = compute_baseline(config, poll_interval=5.0)
        assert baseline.startup_grace_s == 15.0

    @pytest.mark.parametrize("tf", ["M5", "M15", "M30", "D1", "W1"])
    def test_non_m1_timeframes_get_fifteen_seconds(self, tf: str) -> None:
        """All non-M1 timeframes get 15s grace."""
        config = {"timeframe": tf, "walk_forward": True, "monte_carlo": True}
        baseline = compute_baseline(config, poll_interval=5.0)
        assert baseline.startup_grace_s == 15.0

    def test_wf_mc_doubles_early_gen_time(self) -> None:
        """WF + MC enabled doubles the early gen multiplier."""
        config = {"walk_forward": True, "monte_carlo": True}
        baseline = compute_baseline(config)
        assert baseline.early_gen_multiplier == 2.0

    def test_no_wf_standard_multiplier(self) -> None:
        """No WF gives standard multiplier (1.0)."""
        config = {"walk_forward": False, "monte_carlo": False}
        baseline = compute_baseline(config)
        assert baseline.early_gen_multiplier == 1.0

    def test_wf_only_standard_multiplier(self) -> None:
        """WF only (no MC) gives standard multiplier."""
        config = {"walk_forward": True, "monte_carlo": False}
        baseline = compute_baseline(config)
        assert baseline.early_gen_multiplier == 1.0

    def test_mc_only_standard_multiplier(self) -> None:
        """MC only (no WF) gives standard multiplier."""
        config = {"walk_forward": False, "monte_carlo": True}
        baseline = compute_baseline(config)
        assert baseline.early_gen_multiplier == 1.0

    def test_expected_gen_time_minimum(self) -> None:
        """Expected gen time is never below 15s."""
        config = {"population": 10, "generations": 10}
        baseline = compute_baseline(config)
        assert baseline.expected_gen_time_s >= 15.0
        assert baseline.expected_gen_time_s == 15.0  # exactly the floor

    def test_stall_polls_threshold_scales_with_poll_interval(self) -> None:
        """Stall polls threshold adjusts with poll interval."""
        config = {"population": 200, "generations": 80}
        # With 5s poll interval and ~32s expected gen
        b1 = compute_baseline(config, poll_interval=5.0)
        # ceil(32/5)=7, ×3=21
        assert b1.stall_polls_threshold == 21

        # With 10s poll interval: ceil(32/10)=4, ×3=12
        b2 = compute_baseline(config, poll_interval=10.0)
        assert b2.stall_polls_threshold == 12

    def test_rejection_warn_gens_small_campaign(self) -> None:
        """Campaigns with < 100 generations get 3 warn gens."""
        config = {"generations": 80}
        baseline = compute_baseline(config)
        assert baseline.rejection_warn_gens == 3

    def test_rejection_warn_gens_large_campaign(self) -> None:
        """Campaigns with >= 100 generations get 5 warn gens."""
        config = {"generations": 100}
        baseline = compute_baseline(config)
        assert baseline.rejection_warn_gens == 5

    def test_default_config(self) -> None:
        """Empty config uses sensible defaults."""
        baseline = compute_baseline({})
        assert baseline.startup_grace_s == 15.0  # H1 default
        assert baseline.expected_gen_time_s >= 15.0
        # Defaults for walk_forward / monte_carlo are True (matching project_builder),
        # so early_gen_multiplier is 2.0
        assert baseline.early_gen_multiplier == 2.0
        assert baseline.early_gen_count == 3
        assert baseline.rejection_warn_gens == 3  # 80 default < 100

    def test_stall_polls_minimum_of_three(self) -> None:
        """Stall polls threshold never below 3."""
        config = {"population": 2, "generations": 2}
        baseline = compute_baseline(config, poll_interval=60.0)
        assert baseline.stall_polls_threshold >= 3


# ═══════════════════════════════════════════════════════════════════════════
# 4.4: WatcherEvent JSON round-trip
# ═══════════════════════════════════════════════════════════════════════════


class TestWatcherEvent:
    """Unit tests for ``WatcherEvent`` dataclass."""

    @pytest.mark.parametrize(
        "event_type,severity,details",
        [
            ("startup_stall", "WARNING", {"elapsed_s": 95.0, "count": 0}),
            ("config_error", "CRITICAL", {"errors": ["Config invalid"]}),
            (
                "zero_growth_stall",
                "WARNING",
                {"count": 42, "elapsed_s": 200.0, "stalled_polls": 12},
            ),
            ("campaign_complete", "INFO", {"elapsed_s": 350.0}),
            (
                "excessive_rejection",
                "INFO",
                {"generation": 5, "rejection_rate": 1.0},
            ),
        ],
    )
    def test_to_dict_round_trip(
        self,
        event_type: str,
        severity: str,
        details: dict,
    ) -> None:
        """All event types survive a JSON serialise/deserialise cycle."""
        event = WatcherEvent(
            timestamp="2026-01-15T10:30:00+00:00",
            campaign_id="test-campaign",
            event_type=event_type,  # type: ignore[arg-type]
            severity=severity,  # type: ignore[arg-type]
            details=details,
        )

        # Serialise to JSON
        raw = json.dumps(event.to_dict())
        restored = json.loads(raw)

        assert restored["timestamp"] == "2026-01-15T10:30:00+00:00"
        assert restored["campaign_id"] == "test-campaign"
        assert restored["event_type"] == event_type
        assert restored["severity"] == severity
        assert restored["details"] == details

    def test_default_fields_present(self) -> None:
        """A WatcherEvent has all required fields."""
        event = WatcherEvent(
            timestamp="2026-01-15T10:30:00+00:00",
            campaign_id="test",
            event_type="campaign_complete",
            severity="INFO",
            details={},
        )
        d = event.to_dict()
        assert set(d.keys()) == {
            "timestamp", "campaign_id", "event_type", "severity", "details",
        }

    def test_details_dict_arbitrary(self) -> None:
        """Details dict can hold arbitrary JSON-serialisable data."""
        details = {
            "string": "hello",
            "number": 42,
            "float": 3.14,
            "list": [1, 2, 3],
            "nested": {"key": "value"},
        }
        event = WatcherEvent(
            timestamp="2026-01-15T10:30:00+00:00",
            campaign_id="test",
            event_type="config_error",
            severity="CRITICAL",
            details=details,
        )
        restored = json.loads(json.dumps(event.to_dict()))
        assert restored["details"] == details

    def test_timestamp_iso_format(self) -> None:
        """Timestamp is a valid ISO 8601 string at creation time."""
        event = WatcherEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            campaign_id="test",
            event_type="campaign_complete",
            severity="INFO",
            details={},
        )
        # Verify parseable
        parsed = datetime.fromisoformat(event.timestamp)
        assert parsed.tzinfo is not None  # timezone-aware


# ═══════════════════════════════════════════════════════════════════════════
# 4.5: CampaignMonitor — unit / integration
# ═══════════════════════════════════════════════════════════════════════════


class TestCampaignMonitorUnit:
    """Unit tests for ``CampaignMonitor`` internals (no HTTP)."""

    # ── _poll_tick: startup_stall ───────────────────────────────────────

    def test_startup_stall_triggers_after_grace_plus_gen(self, baseline_m1: BaselineConfig) -> None:
        """startup_stall fires when elapsed exceeds grace + expected gen time."""
        monitor = CampaignMonitor("test", "http://localhost:5050", baseline_m1)
        monitor._start_time = time.monotonic() - 100.0  # pretend 100s elapsed
        events = monitor._poll_tick(
            "Strategies generated                           0\n",
            elapsed=100.0,
        )
        assert len(events) == 1
        assert events[0].event_type == "startup_stall"
        assert events[0].severity == "WARNING"
        assert events[0].details["count"] == 0

    def test_startup_stall_not_before_threshold(self, baseline_m1: BaselineConfig) -> None:
        """No startup_stall before grace + gen time has passed."""
        monitor = CampaignMonitor("test", "http://localhost:5050", baseline_m1)
        events = monitor._poll_tick(
            "Strategies generated                           0\n",
            elapsed=30.0,  # well under 60+32=92s
        )
        assert len(events) == 0

    def test_startup_no_stall_when_count_nonzero(self, baseline_m1: BaselineConfig) -> None:
        """No startup_stall when strategies have been generated."""
        monitor = CampaignMonitor("test", "http://localhost:5050", baseline_m1)
        events = monitor._poll_tick(
            "Strategies generated                           5\n",
            elapsed=100.0,
        )
        # Count > 0, so no startup_stall
        stall_events = [e for e in events if e.event_type == "startup_stall"]
        assert len(stall_events) == 0

    # ── _poll_tick: config_error ────────────────────────────────────────

    def test_config_error_critical(self, baseline_h1: BaselineConfig) -> None:
        """Config errors produce CRITICAL event."""
        monitor = CampaignMonitor("test", "http://localhost:5050", baseline_h1)
        events = monitor._poll_tick(
            "Cannot start project 'X', it has config errors in task 'Build'\n",
            elapsed=10.0,
        )
        assert len(events) == 1
        assert events[0].event_type == "config_error"
        assert events[0].severity == "CRITICAL"
        assert len(events[0].details["errors"]) >= 1

    def test_config_error_returns_early_no_stall_check(self, baseline_h1: BaselineConfig) -> None:
        """When errors are present, stall checks are skipped."""
        monitor = CampaignMonitor("test", "http://localhost:5050", baseline_h1)
        monitor._last_count = 42
        events = monitor._poll_tick(
            (
                "Strategies generated                          42\n"
                "Error: Something went wrong\n"
            ),
            elapsed=200.0,
        )
        # Only config_error, no stall events even though elapsed is large
        assert len(events) == 1
        assert events[0].event_type == "config_error"

    # ── _poll_tick: zero_growth_stall ───────────────────────────────────

    def test_zero_growth_stall_after_threshold(self, fast_baseline: BaselineConfig) -> None:
        """Zero-growth stall fires after stall_polls_threshold consecutive same-count polls."""
        monitor = CampaignMonitor("test", "http://localhost:5050", fast_baseline)
        monitor._last_count = 42

        # Simulate stall_polls_threshold consecutive same-count ticks
        events: list = []
        for i in range(fast_baseline.stall_polls_threshold):
            events = monitor._poll_tick(
                "Strategies generated                          42\n",
                elapsed=30.0 + i * 5.0,
            )

        # The last tick should trigger the event
        stall_events = [e for e in events if e.event_type == "zero_growth_stall"]
        assert len(stall_events) >= 1
        assert stall_events[0].severity == "WARNING"
        assert stall_events[0].details["count"] == 42

    def test_zero_growth_resets_on_count_change(self, fast_baseline: BaselineConfig) -> None:
        """Stall counter resets when count finally changes."""
        monitor = CampaignMonitor("test", "http://localhost:5050", fast_baseline)
        monitor._last_count = 42

        # One tick with same count
        events1 = monitor._poll_tick(
            "Strategies generated                          42\n",
            elapsed=30.0,
        )
        assert monitor._stall_polls == 1
        assert len(events1) == 0

        # Count changes
        events2 = monitor._poll_tick(
            "Strategies generated                          55\n",
            elapsed=35.0,
        )
        assert monitor._stall_polls == 0  # reset
        assert len(events2) == 0

    def test_first_tick_does_not_count_as_stall(self, fast_baseline: BaselineConfig) -> None:
        """First tick (-1 → N) initialises last_count, does not stall."""
        monitor = CampaignMonitor("test", "http://localhost:5050", fast_baseline)
        events = monitor._poll_tick(
            "Strategies generated                          10\n",
            elapsed=5.0,
        )
        assert monitor._last_count == 10
        assert len(events) == 0

    # ── _poll_tick: excessive_rejection ─────────────────────────────────

    def test_excessive_rejection_fires_once(self, fast_baseline: BaselineConfig) -> None:
        """Excessive rejection fires INFO after rejection_warn_gens same-count ticks."""
        monitor = CampaignMonitor("test", "http://localhost:5050", fast_baseline)

        # Establish some throughput first
        monitor._poll_tick(
            "Strategies generated                          50\n"
            "In databank                                      3\n",
            elapsed=10.0,
        )

        # Now stall — after rejection_warn_gens ticks, fire rejection event
        all_events: list[WatcherEvent] = []
        for i in range(fast_baseline.rejection_warn_gens + 1):
            tick_events = monitor._poll_tick(
                "Strategies generated                          50\n"
                "In databank                                      3\n",
                elapsed=20.0 + i * 5.0,
            )
            all_events.extend(tick_events)

        rejection_events = [e for e in all_events if e.event_type == "excessive_rejection"]
        assert len(rejection_events) >= 1
        assert rejection_events[0].severity == "INFO"
        assert rejection_events[0].details["rejection_rate"] == 1.0

    def test_excessive_rejection_only_once(self, fast_baseline: BaselineConfig) -> None:
        """excessive_rejection is emitted at most once."""
        monitor = CampaignMonitor("test", "http://localhost:5050", fast_baseline)
        monitor._last_count = 50

        # Push through rejection_warn_gens same-count ticks
        all_events: list = []
        for i in range(fast_baseline.rejection_warn_gens + 5):
            evts = monitor._poll_tick(
                "Strategies generated                          50\n",
                elapsed=30.0 + i * 5.0,
            )
            all_events.extend(evts)

        rejection_events = [e for e in all_events if e.event_type == "excessive_rejection"]
        assert len(rejection_events) == 1  # exactly once

    def test_excessive_rejection_requires_established_throughput(self, fast_baseline: BaselineConfig) -> None:
        """No excessive_rejection if we never had throughput (last_count == -1)."""
        monitor = CampaignMonitor("test", "http://localhost:5050", fast_baseline)
        assert monitor._last_count == -1  # no throughput yet

        events = monitor._poll_tick(
            "Strategies generated                          50\n",
            elapsed=30.0,
        )
        # Should not fire excessive_rejection on first tick
        rejection_events = [e for e in events if e.event_type == "excessive_rejection"]
        assert len(rejection_events) == 0

    # ── _is_campaign_done ───────────────────────────────────────────────

    @pytest.mark.parametrize(
        "text",
        [
            "Project execution stopped.\n",
            "Project execution stopped",
            "completed",
            "Campaign finished",
            "done",
            "Success",
        ],
    )
    def test_is_campaign_done_true(self, text: str) -> None:
        """Various completion indicators are recognised."""
        assert CampaignMonitor._is_campaign_done(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "Strategies generated                          42\n",
            "running",
            "Status of project TestCampaign\n",
        ],
    )
    def test_is_campaign_done_false(self, text: str) -> None:
        """Non-completion texts return False."""
        assert CampaignMonitor._is_campaign_done(text) is False

    # ── _make_event ─────────────────────────────────────────────────────

    def test_make_event_creates_valid_event(self, baseline_h1: BaselineConfig) -> None:
        """_make_event produces a WatcherEvent with the right metadata."""
        monitor = CampaignMonitor("test-camp", "http://localhost:5050", baseline_h1)
        ev = monitor._make_event("config_error", "CRITICAL", {"errors": ["test"]})
        assert ev.campaign_id == "test-camp"
        assert ev.event_type == "config_error"
        assert ev.severity == "CRITICAL"
        assert ev.details == {"errors": ["test"]}
        # Valid ISO timestamp
        parsed = datetime.fromisoformat(ev.timestamp)
        assert parsed.tzinfo is not None


# ═══════════════════════════════════════════════════════════════════════════
# CampaignMonitor: Integration tests (mock HTTP)
# ═══════════════════════════════════════════════════════════════════════════


class TestCampaignMonitorIntegration:
    """Integration tests for CampaignMonitor with mocked HTTP responses.

    All tests register a ``MagicMock`` callback to bypass CLI prompts.
    """

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _make_monitor(
        campaign_id: str,
        baseline: BaselineConfig,
        **kwargs: Any,
    ) -> CampaignMonitor:
        """Create a monitor with a mock callback to suppress CLI prompts."""
        kwargs.setdefault("poll_interval", 0.01)
        kwargs.setdefault(
            "on_watcher_event", MagicMock(),
        )
        return CampaignMonitor(
            campaign_id,
            "http://127.0.0.1:5050",
            baseline,
            **kwargs,
        )

    @staticmethod
    def _seq(*responses: str):
        """Build an iterator that will be exhausted cleanly.

        After the given responses, returns a sentinel that *also* triggers
        ``_is_campaign_done`` so the loop terminates without hitting
        ``StopIteration``.
        """
        return iter(list(responses) + ["Project execution stopped.\n"])

    # ── Tests ──────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_healthy_campaign_emits_no_events(self, fast_baseline: BaselineConfig) -> None:
        """A campaign generating strategies at a healthy rate emits no events."""
        monitor = self._make_monitor("test-healthy", fast_baseline)

        responses = self._seq(
            "Strategies generated                          10\n"
            "Running time so far                          2 s.\n"
            "In databank                                      1\n",
            "Strategies generated                          25\n"
            "Running time so far                          4 s.\n"
            "In databank                                      2\n",
            "Strategies generated                          42\n"
            "Running time so far                          6 s.\n"
            "In databank                                      3\n",
        )

        with patch.object(monitor, "_fetch_status", side_effect=responses):
            events = await monitor.run()

        stall_or_error = [
            e for e in events
            if e.event_type != "campaign_complete"
        ]
        assert len(stall_or_error) == 0, f"Unexpected events: {stall_or_error}"

    @pytest.mark.asyncio
    async def test_config_error_detected(self, fast_baseline: BaselineConfig) -> None:
        """Config error in status text produces CRITICAL event."""
        callback = MagicMock()
        monitor = self._make_monitor(
            "test-error", fast_baseline, on_watcher_event=callback,
        )

        responses = self._seq(
            "Strategies generated                           0\n"
            "Cannot start project 'Test', it has config errors\n",
        )

        with patch.object(monitor, "_fetch_status", side_effect=responses):
            await monitor.run()

        # Callback should have received config_error
        callback_calls = [
            args[0][0]
            for args in callback.call_args_list
            if args[0][0].event_type == "config_error"
        ]
        assert len(callback_calls) >= 1
        assert callback_calls[0].severity == "CRITICAL"

    @pytest.mark.asyncio
    async def test_cancel_stops_monitor(self, fast_baseline: BaselineConfig) -> None:
        """Calling cancel() stops the monitor loop promptly."""
        monitor = self._make_monitor("test-cancel", fast_baseline)

        # Infinite supply of same status (return_value, not side_effect)
        status = (
            "Strategies generated                          10\n"
            "Running time so far                          2 s.\n"
        )

        async def delayed_cancel():
            await asyncio.sleep(0.05)
            await monitor.cancel()

        with patch.object(monitor, "_fetch_status", return_value=status):
            cancel_task = asyncio.create_task(delayed_cancel())
            events = await monitor.run()
            await cancel_task

        assert isinstance(events, list)
        # Should have collected at least one tick
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_callback_receives_events(self, fast_baseline: BaselineConfig) -> None:
        """Registered callback receives events instead of CLI prompt."""
        callback = MagicMock()
        monitor = self._make_monitor(
            "test-callback", fast_baseline, on_watcher_event=callback,
        )

        responses = self._seq(
            "Strategies generated                           0\n"
            "Error: Invalid config\n",
        )

        with patch.object(monitor, "_fetch_status", side_effect=responses):
            await monitor.run()

        # Callback should have been called at least twice (config_error + campaign_complete)
        assert callback.call_count >= 2
        # First call should be config_error
        first_event: WatcherEvent = callback.call_args_list[0][0][0]
        assert isinstance(first_event, WatcherEvent)
        assert first_event.event_type == "config_error"

    @pytest.mark.asyncio
    async def test_dispatch_event_callback_mode_skips_prompt(self, fast_baseline: BaselineConfig) -> None:
        """When a callback is registered, no Confirm prompt is shown."""
        callback = MagicMock()
        monitor = CampaignMonitor(
            "test-callback",
            "http://127.0.0.1:5050",
            fast_baseline,
            on_watcher_event=callback,
        )
        monitor._start_time = time.monotonic()

        ev = monitor._make_event("config_error", "CRITICAL", {"errors": ["test"]})

        with patch("rich.prompt.Confirm") as mock_confirm:
            await monitor._dispatch_event(ev)

        mock_confirm.ask.assert_not_called()
        callback.assert_called_once_with(ev)

    @pytest.mark.asyncio
    async def test_http_failure_tracking(self, fast_baseline: BaselineConfig) -> None:
        """Three consecutive HTTP failures emit a WARNING and stop."""
        monitor = self._make_monitor("test-http-fail", fast_baseline)

        # Return None for failure (3+ times to trigger threshold)
        with patch.object(monitor, "_fetch_status", return_value=None):
            events = await monitor.run()

        config_errors = [e for e in events if e.event_type == "config_error"]
        assert len(config_errors) >= 1
        assert config_errors[0].severity == "WARNING"
        assert "3 consecutive HTTP failures" in config_errors[0].details["errors"]

    @pytest.mark.asyncio
    async def test_zero_growth_stall_in_run(self, fast_baseline: BaselineConfig) -> None:
        """Run loop detects zero-growth stall when count stays the same."""
        callback = MagicMock()
        same_status = (
            "Strategies generated                          42\n"
            "Running time so far                          10 s.\n"
        )

        # Need enough responses: one initial tick + stall threshold + terminal
        n = 1 + fast_baseline.stall_polls_threshold
        responses = self._seq(*([same_status] * n))

        monitor = self._make_monitor(
            "test-stall", fast_baseline, on_watcher_event=callback,
        )

        with patch.object(monitor, "_fetch_status", side_effect=responses):
            events = await monitor.run()

        stall_events = [e for e in events if e.event_type == "zero_growth_stall"]
        assert len(stall_events) >= 1

    @pytest.mark.asyncio
    async def test_cancel_during_run(self, fast_baseline: BaselineConfig) -> None:
        """Cancelling the monitor asyncio task returns collected events."""
        callback = MagicMock()
        monitor = self._make_monitor(
            "test-cancel-task", fast_baseline,
            poll_interval=0.5,
            on_watcher_event=callback,
        )

        # Use return_value so it never exhausts
        status = "Strategies generated                          42\n"

        async def run_and_cancel():
            task = asyncio.create_task(monitor.run())
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                return await task
            except asyncio.CancelledError:
                # Monitor catches CancelledError internally
                return monitor._events

        with patch.object(monitor, "_fetch_status", return_value=status):
            events = await run_and_cancel()

        assert isinstance(events, list)


# ═══════════════════════════════════════════════════════════════════════════
# BaselineConfig serialisation
# ═══════════════════════════════════════════════════════════════════════════


class TestBaselineConfig:
    """Unit tests for ``BaselineConfig`` serialisation."""

    def test_to_dict_round_trip(self) -> None:
        """BaselineConfig survives JSON serialise/deserialise."""
        config = BaselineConfig(
            startup_grace_s=60.0,
            expected_gen_time_s=32.0,
            early_gen_multiplier=2.0,
            early_gen_count=3,
            stall_polls_threshold=21,
            rejection_warn_gens=3,
        )
        raw = json.dumps(config.to_dict())
        restored = json.loads(raw)

        assert restored["startup_grace_s"] == 60.0
        assert restored["expected_gen_time_s"] == 32.0
        assert restored["early_gen_multiplier"] == 2.0
        assert restored["early_gen_count"] == 3
        assert restored["stall_polls_threshold"] == 21
        assert restored["rejection_warn_gens"] == 3
