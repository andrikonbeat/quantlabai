"""T-3.6 RED — on-demand status snapshot (REQ-38, ADR-5/6).

Strict TDD: written before ``CampaignMonitor`` persisted any snapshot and
before ``heuristic_recommendation`` / ``load_snapshot`` existed — every test
here fails (RED) until T-3.7 (campaign_monitor) and T-3.8 (CLI) land.

Spec (campaign-monitor/spec.md): ``campaign status --live`` and
``generation status`` return a ``current_snapshot`` plus a recommendation of
``continue``, ``stop`` or ``reconfigure``; with ``llm_config`` None the status
makes ZERO LLM calls (heuristics only) and never blocks a long-running
campaign. Threat matrix: the snapshot path is sanitized via
``sanitize_campaign_id`` — ``../`` traversal is rejected.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

from quantlab.gates.callbacks import sanitize_campaign_id
from quantlab.sqx.campaign_monitor import BaselineConfig, CampaignMonitor
from quantlab.sqx.llm_generation_monitor import MonitorSnapshot

SNAPSHOT_DIR = Path("/tmp/sqx-status")


def _baseline() -> BaselineConfig:
    return BaselineConfig(
        startup_grace_s=60.0,
        expected_gen_time_s=300.0,
        early_gen_multiplier=2.0,
    )


def _monitor(campaign_id: str = "StatusCamp") -> CampaignMonitor:
    return CampaignMonitor(
        campaign_id=campaign_id,
        base_url="http://127.0.0.1:9",
        baseline=_baseline(),
    )


def _snapshot(**overrides) -> MonitorSnapshot:
    """A realistic snapshot with a baseline context (BaselineConfig merged)."""
    data = {
        "status_text": "Strategies generated: 5",
        "generated_count": 5,
        "databank_counts": {"EURUSD_H1": 100},
        "elapsed_s": 120.0,
        "baseline": {
            "startup_grace_s": 60.0,
            "expected_gen_time_s": 300.0,
            "early_gen_multiplier": 2.0,
            "early_gen_count": 3,
            "stall_polls_threshold": 9,
            "rejection_warn_gens": 3,
        },
        "strategy_counts": {"AGGR": 2, "CONSERVATIVE": 3},
    }
    data.update(overrides)
    return MonitorSnapshot(**data)


class TestPollTickPersistsSnapshot:
    """T-3.7 RED: _poll_tick persists current_snapshot() per poll."""

    def test_poll_tick_writes_snapshot_json(self, tmp_path, monkeypatch) -> None:
        """GIVEN a running monitor
        WHEN a poll tick completes
        THEN snapshot.json exists under /tmp/sqx-status/{campaign_id} with
        the snapshot fields."""
        monkeypatch.setattr(
            "quantlab.sqx.campaign_monitor.DEFAULT_SNAPSHOT_DIR", tmp_path
        )
        monitor = _monitor("StatusCamp")
        monitor._poll_tick(
            status_text="Strategies generated: 3",
            elapsed=90.0,
        )

        path = tmp_path / "StatusCamp" / "snapshot.json"
        assert path.is_file()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["generated_count"] == 3
        assert data["elapsed_s"] == 90.0
        assert data["baseline"]["startup_grace_s"] == 60.0

    def test_poll_tick_rejects_path_traversal(self, tmp_path, monkeypatch) -> None:
        """GIVEN a campaign_id attempting ../ traversal
        THEN no snapshot is written outside the base dir and the poll tick
        never raises (threat matrix: snapshot path sanitization)."""
        monkeypatch.setattr(
            "quantlab.sqx.campaign_monitor.DEFAULT_SNAPSHOT_DIR", tmp_path
        )
        with pytest.raises(ValueError):
            sanitize_campaign_id("../evil")
        monitor = _monitor("../evil")
        monitor._poll_tick(status_text="Strategies generated: 1", elapsed=10.0)

        assert not (tmp_path / ".." / "evil" / "snapshot.json").exists()
        assert not (tmp_path / "evil" / "snapshot.json").exists()


class TestHeuristicRecommendation:
    """T-3.7 RED: zero-LLM heuristic continue/stop/reconfigure."""

    def test_config_error_stops(self) -> None:
        """GIVEN the status text shows config errors
        THEN the recommendation is stop (cannot proceed)."""
        snap = _snapshot(status_text="Error: Invalid databank 'XXX'")
        from quantlab.sqx.campaign_monitor import heuristic_recommendation

        assert heuristic_recommendation(snap) == "stop"

    def test_startup_stall_stops(self) -> None:
        """GIVEN zero generations past the startup+expected window
        THEN the recommendation is stop (startup stall)."""
        snap = _snapshot(
            status_text="Strategies generated: 0",
            generated_count=0,
            elapsed_s=400.0,  # > 60 + 300
        )
        from quantlab.sqx.campaign_monitor import heuristic_recommendation

        assert heuristic_recommendation(snap) == "stop"

    def test_zero_growth_within_window_reconfigures(self) -> None:
        """GIVEN zero generations after the startup grace window
        THEN the recommendation is reconfigure (config may be wrong)."""
        snap = _snapshot(
            status_text="Strategies generated: 0",
            generated_count=0,
            elapsed_s=120.0,  # 60 < elapsed <= 360
        )
        from quantlab.sqx.campaign_monitor import heuristic_recommendation

        assert heuristic_recommendation(snap) == "reconfigure"

    def test_within_startup_grace_continues(self) -> None:
        """GIVEN zero generations still inside the startup grace window
        THEN the recommendation is continue."""
        snap = _snapshot(
            status_text="Strategies generated: 0",
            generated_count=0,
            elapsed_s=30.0,
        )
        from quantlab.sqx.campaign_monitor import heuristic_recommendation

        assert heuristic_recommendation(snap) == "continue"

    def test_progress_continues(self) -> None:
        """GIVEN the campaign is generating strategies
        THEN the recommendation is continue."""
        snap = _snapshot()
        from quantlab.sqx.campaign_monitor import heuristic_recommendation

        assert heuristic_recommendation(snap) == "continue"


class TestSnapshotRead:
    """T-3.8 RED: the status commands read the persisted snapshot."""

    def test_load_snapshot_returns_monitor_snapshot(self, tmp_path, monkeypatch) -> None:
        """GIVEN a persisted snapshot.json
        WHEN load_snapshot reads it
        THEN it returns a MonitorSnapshot with the stored fields."""
        from quantlab.sqx.campaign_monitor import load_snapshot

        snap_dir = tmp_path / "StatusCamp"
        snap_dir.mkdir(parents=True)
        (snap_dir / "snapshot.json").write_text(
            json.dumps(_snapshot().__dict__), encoding="utf-8"
        )
        loaded = load_snapshot("StatusCamp", base_dir=tmp_path)
        assert isinstance(loaded, MonitorSnapshot)
        assert loaded.generated_count == 5
        assert loaded.baseline["startup_grace_s"] == 60.0

    def test_load_snapshot_missing_raises(self, tmp_path) -> None:
        """GIVEN no snapshot for the campaign
        WHEN load_snapshot reads it
        THEN FileNotFoundError is raised."""
        from quantlab.sqx.campaign_monitor import load_snapshot

        with pytest.raises(FileNotFoundError):
            load_snapshot("NoSuchCampaign", base_dir=tmp_path)

    def test_load_snapshot_rejects_traversal(self, tmp_path) -> None:
        """GIVEN a campaign_id attempting traversal
        WHEN load_snapshot reads it
        THEN ValueError is raised before any path is touched."""
        from quantlab.sqx.campaign_monitor import load_snapshot

        with pytest.raises(ValueError):
            load_snapshot("../evil", base_dir=tmp_path)


@pytest.mark.asyncio
class TestStatusCommands:
    """T-3.8 RED: campaign status --live and generation status."""

    async def test_campaign_status_live_returns_snapshot_and_recommendation(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        """GIVEN a persisted snapshot
        WHEN campaign status --live --json runs
        THEN it returns current_snapshot + recommendation and exits 0."""
        snap_dir = tmp_path / "StatusCamp"
        snap_dir.mkdir(parents=True)
        (snap_dir / "snapshot.json").write_text(
            json.dumps(_snapshot().__dict__), encoding="utf-8"
        )
        monkeypatch.setattr(
            "quantlab.sqx.campaign_monitor.DEFAULT_SNAPSHOT_DIR", tmp_path
        )
        from quantlab.cli.campaign_commands import cmd_campaign_status

        args = argparse.Namespace(
            campaign_id="StatusCamp",
            live=True,
            json=True,
            knowledge_root="knowledge",
        )
        code = await cmd_campaign_status(args)

        assert code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["current_snapshot"]["generated_count"] == 5
        assert out["recommendation"] in ("continue", "stop", "reconfigure")

    async def test_campaign_status_live_missing_snapshot_fails(self, monkeypatch, tmp_path) -> None:
        """GIVEN no snapshot for the campaign
        WHEN campaign status --live runs
        THEN it fails with a clear error (exit 1)."""
        monkeypatch.setattr(
            "quantlab.sqx.campaign_monitor.DEFAULT_SNAPSHOT_DIR", tmp_path
        )
        from quantlab.cli.campaign_commands import cmd_campaign_status

        args = argparse.Namespace(
            campaign_id="NoSuchCampaign",
            live=True,
            json=True,
            knowledge_root="knowledge",
        )
        code = await cmd_campaign_status(args)
        assert code == 1

    async def test_generation_status_returns_snapshot_without_llm(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        """GIVEN a persisted snapshot and llm_config None
        WHEN generation status runs
        THEN it returns the snapshot + heuristic recommendation with ZERO
        LLM calls (the LLM monitor module is never imported)."""
        snap_dir = tmp_path / "StatusCamp"
        snap_dir.mkdir(parents=True)
        (snap_dir / "snapshot.json").write_text(
            json.dumps(_snapshot().__dict__), encoding="utf-8"
        )
        monkeypatch.setattr(
            "quantlab.sqx.campaign_monitor.DEFAULT_SNAPSHOT_DIR", tmp_path
        )
        # Prove zero LLM calls: importing the LLM monitor would fail here.
        import builtins

        real_import = builtins.__import__

        def _blocking_import(name, *args, **kwargs):
            if name == "quantlab.sqx.llm_generation_monitor":
                raise AssertionError("LLM monitor imported during status --live")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _blocking_import)
        from quantlab.cli.campaign_commands import cmd_generation_status

        args = argparse.Namespace(campaign_id="StatusCamp", json=True)
        code = await cmd_generation_status(args)

        assert code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["current_snapshot"]["generated_count"] == 5
        assert out["recommendation"] == "continue"
