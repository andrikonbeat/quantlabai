"""Tests for TimeSeriesStore — SQLite time-series persistence.

RED phase: tests reference TimeSeriesStore which does not exist yet.
Covers tasks 1.1 (indirectly) + 1.3.
"""

from __future__ import annotations

import pytest

from quantlab.knowledge.store import TimeSeriesStore


class TestTimeSeriesStore:
    """TimeSeriesStore CRUD and query round-trip tests."""

    @pytest.fixture
    def store(self) -> TimeSeriesStore:
        """Create an in-memory TimeSeriesStore for testing."""
        return TimeSeriesStore(":memory:")

    # ── Metrics ────────────────────────────────────────────────────────────────

    def test_append_and_query_metrics_single(self, store: TimeSeriesStore) -> None:
        """Append a single metric dict and query it back by strategy + time range."""
        store.append_metrics("strat_a", 100.0, {"sharpe": 1.5, "drawdown": 0.05})

        results = store.query_metrics("strat_a", 0.0, 999.0)
        assert len(results) == 2  # one row per metric_name

        sharpe = [r for r in results if r["metric_name"] == "sharpe"][0]
        assert sharpe["value"] == 1.5
        assert sharpe["strategy_id"] == "strat_a"
        assert sharpe["timestamp"] == 100.0

        dd = [r for r in results if r["metric_name"] == "drawdown"][0]
        assert dd["value"] == 0.05

    def test_append_and_query_metrics_multiple_batches(self, store: TimeSeriesStore) -> None:
        """Append multiple batches and verify all rows are queryable."""
        store.append_metrics("strat_a", 100.0, {"sharpe": 1.5, "drawdown": 0.05})
        store.append_metrics("strat_a", 200.0, {"sharpe": 1.2, "drawdown": 0.08})

        results = store.query_metrics("strat_a", 0.0, 999.0)
        assert len(results) == 4  # 2 metrics × 2 batches

        sharpe_values = sorted(
            [r for r in results if r["metric_name"] == "sharpe"],
            key=lambda r: r["timestamp"],
        )
        assert len(sharpe_values) == 2
        assert sharpe_values[0]["value"] == 1.5
        assert sharpe_values[1]["value"] == 1.2

    def test_query_metrics_time_range_filter(self, store: TimeSeriesStore) -> None:
        """Only metrics within [since, until) are returned."""
        store.append_metrics("strat_a", 100.0, {"sharpe": 1.5})
        store.append_metrics("strat_a", 200.0, {"sharpe": 1.2})
        store.append_metrics("strat_a", 300.0, {"sharpe": 1.0})

        results = store.query_metrics("strat_a", 150.0, 250.0)
        assert len(results) == 1
        assert results[0]["value"] == 1.2

    def test_query_metrics_empty_for_wrong_strategy(self, store: TimeSeriesStore) -> None:
        """A strategy with no metrics returns an empty list."""
        store.append_metrics("strat_a", 100.0, {"sharpe": 1.5})

        results = store.query_metrics("strat_b", 0.0, 999.0)
        assert results == []

    def test_query_metrics_no_results_outside_range(self, store: TimeSeriesStore) -> None:
        """Query range that excludes all data returns empty list."""
        store.append_metrics("strat_a", 500.0, {"sharpe": 1.5})

        results = store.query_metrics("strat_a", 0.0, 100.0)
        assert results == []

    # ── Alerts ─────────────────────────────────────────────────────────────────

    def test_append_and_query_alerts(self, store: TimeSeriesStore) -> None:
        """Append an alert and verify it is stored with all fields."""
        alert = {
            "timestamp": "2026-07-29T12:00:00",
            "type": "DRAWDOWN_BREACH",
            "severity": "CRITICAL",
            "strategy_id": "strat_a",
            "message": "Drawdown exceeded threshold",
            "details": '{"current": "18%", "threshold": "15%"}',
        }
        store.append_alert(alert)

        cursor = store._conn.execute(
            "SELECT type, severity, strategy_id, message FROM alerts"
        )
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0]["type"] == "DRAWDOWN_BREACH"
        assert rows[0]["severity"] == "CRITICAL"
        assert rows[0]["strategy_id"] == "strat_a"
        assert rows[0]["message"] == "Drawdown exceeded threshold"

    def test_append_multiple_alerts(self, store: TimeSeriesStore) -> None:
        """Multiple alerts accumulate."""
        store.append_alert({"timestamp": "T1", "type": "A", "severity": "WARNING",
                           "strategy_id": "s1", "message": "m1", "details": ""})
        store.append_alert({"timestamp": "T2", "type": "B", "severity": "CRITICAL",
                           "strategy_id": "s1", "message": "m2", "details": ""})

        cursor = store._conn.execute("SELECT count(*) FROM alerts")
        assert cursor.fetchone()[0] == 2

    # ── Heartbeats ─────────────────────────────────────────────────────────────

    def test_append_and_query_heartbeats(self, store: TimeSeriesStore) -> None:
        """Append heartbeats and verify stored fields."""
        store.append_heartbeat({
            "timestamp": 1000.0,
            "strategy_id": "strat_a",
            "equity_count": 42,
            "alert_count": 3,
        })
        store.append_heartbeat({
            "timestamp": 2000.0,
            "strategy_id": "strat_a",
            "equity_count": 50,
            "alert_count": 5,
        })

        cursor = store._conn.execute(
            "SELECT strategy_id, equity_count, alert_count FROM heartbeats "
            "ORDER BY timestamp"
        )
        rows = cursor.fetchall()
        assert len(rows) == 2
        assert tuple(rows[0]) == ("strat_a", 42, 3)
        assert tuple(rows[1]) == ("strat_a", 50, 5)

    def test_heartbeat_with_defaults(self, store: TimeSeriesStore) -> None:
        """Heartbeats with minimal fields still store correctly."""
        store.append_heartbeat({
            "timestamp": 500.0,
            "strategy_id": "strat_b",
        })

        cursor = store._conn.execute(
            "SELECT equity_count, alert_count FROM heartbeats"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["equity_count"] == 0
        assert row["alert_count"] == 0

    # ── Runtime-harness round-trip ─────────────────────────────────────────────

    def test_exact_runtime_harness(self, store: TimeSeriesStore) -> None:
        """Match the exact command from the work-unit evidence::
            t=TimeSeriesStore(':memory:')
            t.append_metrics('x',1,{'s':2.0})
            print(t.query_metrics('x',0,2))
        """
        store.append_metrics("x", 1.0, {"s": 2.0})
        results = store.query_metrics("x", 0.0, 2.0)

        assert len(results) == 1
        assert results[0]["strategy_id"] == "x"
        assert results[0]["timestamp"] == 1.0
        assert results[0]["metric_name"] == "s"
        assert results[0]["value"] == 2.0
