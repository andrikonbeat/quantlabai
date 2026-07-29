"""Tests for MonitorConfig — YAML loading + AUTONOMOUS_MONITOR_* env override.

RED phase: tests reference MonitorConfig which does not exist yet.
Covers tasks 1.2 (indirectly) + 1.4.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from quantlab.agents.autonomous_monitor import MonitorConfig


class TestMonitorConfig:
    """MonitorConfig creation, YAML loading, and env-var override."""

    # ── Default values ─────────────────────────────────────────────────────────

    def test_default_values(self) -> None:
        """A config with only strategy_id uses spec defaults."""
        cfg = MonitorConfig(strategy_id="test_strat")
        assert cfg.strategy_id == "test_strat"
        assert cfg.drawdown_threshold == 0.15
        assert cfg.sharpe_degradation_pct == 0.4
        assert cfg.compute_interval == 60
        assert cfg.stream_timeout == 60
        assert cfg.heartbeat_interval == 30
        assert cfg.max_retries == 5
        assert cfg.knowledge_root == "knowledge"
        assert cfg.notifiers == {}

    def test_explicit_values(self) -> None:
        """Override every field explicitly."""
        cfg = MonitorConfig(
            strategy_id="explicit",
            drawdown_threshold=0.20,
            sharpe_degradation_pct=0.5,
            compute_interval=120,
            stream_timeout=90,
            heartbeat_interval=15,
            max_retries=3,
            knowledge_root="/tmp/knowledge",
            notifiers={"slack": {"webhook": "https://hooks.example.com"}},
        )
        assert cfg.drawdown_threshold == 0.20
        assert cfg.sharpe_degradation_pct == 0.5
        assert cfg.compute_interval == 120
        assert cfg.stream_timeout == 90
        assert cfg.heartbeat_interval == 15
        assert cfg.max_retries == 3
        assert cfg.knowledge_root == "/tmp/knowledge"
        assert cfg.notifiers["slack"]["webhook"] == "https://hooks.example.com"

    # ── YAML loading ──────────────────────────────────────────────────────────

    def test_from_yaml_full(self) -> None:
        """Load a fully-specified YAML config."""
        yaml_content = """
        strategy_id: yaml_strat
        drawdown_threshold: 0.25
        sharpe_degradation_pct: 0.6
        compute_interval: 300
        stream_timeout: 120
        heartbeat_interval: 60
        max_retries: 10
        knowledge_root: /custom/knowledge
        notifiers:
          slack:
            webhook: https://hooks.example.com/slack
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            tmp_path = f.name

        try:
            cfg = MonitorConfig.from_yaml(tmp_path)
            assert cfg.strategy_id == "yaml_strat"
            assert cfg.drawdown_threshold == 0.25
            assert cfg.compute_interval == 300
            assert cfg.notifiers["slack"]["webhook"] == "https://hooks.example.com/slack"
        finally:
            os.unlink(tmp_path)

    def test_from_yaml_partial(self) -> None:
        """Partial YAML fills missing fields with defaults."""
        yaml_content = """
        strategy_id: partial_strat
        drawdown_threshold: 0.30
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            tmp_path = f.name

        try:
            cfg = MonitorConfig.from_yaml(tmp_path)
            assert cfg.strategy_id == "partial_strat"
            assert cfg.drawdown_threshold == 0.30
            # Defaults for unset fields
            assert cfg.sharpe_degradation_pct == 0.4
            assert cfg.compute_interval == 60
            assert cfg.notifiers == {}
        finally:
            os.unlink(tmp_path)

    def test_from_yaml_minimal(self) -> None:
        """Minimal YAML with only strategy_id uses defaults everywhere else."""
        yaml_content = "strategy_id: minimal_strat\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            tmp_path = f.name

        try:
            cfg = MonitorConfig.from_yaml(tmp_path)
            assert cfg.strategy_id == "minimal_strat"
            assert cfg.drawdown_threshold == 0.15
            assert cfg.compute_interval == 60
        finally:
            os.unlink(tmp_path)

    # ── Environment variable overrides ─────────────────────────────────────────

    def test_env_override_float(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AUTONOMOUS_MONITOR_DRAWDOWN_THRESHOLD overrides the YAML value."""
        monkeypatch.setenv("AUTONOMOUS_MONITOR_DRAWDOWN_THRESHOLD", "0.35")
        cfg = MonitorConfig(strategy_id="env_test")
        assert cfg.drawdown_threshold == 0.35

    def test_env_override_int(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AUTONOMOUS_MONITOR_COMPUTE_INTERVAL overrides the default."""
        monkeypatch.setenv("AUTONOMOUS_MONITOR_COMPUTE_INTERVAL", "300")
        cfg = MonitorConfig(strategy_id="env_int")
        assert cfg.compute_interval == 300

    def test_env_override_precedence_over_yaml(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ENV var takes precedence over YAML value for the same key."""
        yaml_content = """
        strategy_id: prec_test
        drawdown_threshold: 0.10
        compute_interval: 60
        """
        monkeypatch.setenv("AUTONOMOUS_MONITOR_DRAWDOWN_THRESHOLD", "0.50")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            tmp_path = f.name

        try:
            cfg = MonitorConfig.from_yaml(tmp_path)
            # Env wins over YAML
            assert cfg.drawdown_threshold == 0.50
            # Non-overridden fields still come from YAML
            assert cfg.compute_interval == 60
        finally:
            os.unlink(tmp_path)

    def test_env_override_notifiers_not_affected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Env override of a numeric field does not clobber notifiers from YAML."""
        yaml_content = """
        strategy_id: notif_test
        notifiers:
          slack:
            webhook: https://hooks.example.com
        """
        monkeypatch.setenv("AUTONOMOUS_MONITOR_COMPUTE_INTERVAL", "999")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            tmp_path = f.name

        try:
            cfg = MonitorConfig.from_yaml(tmp_path)
            assert cfg.compute_interval == 999
            assert cfg.notifiers["slack"]["webhook"] == "https://hooks.example.com"
        finally:
            os.unlink(tmp_path)

    def test_env_unknown_var_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unknown AUTONOMOUS_MONITOR_* vars are silently ignored."""
        monkeypatch.setenv("AUTONOMOUS_MONITOR_NONEXISTENT", "99")
        cfg = MonitorConfig(strategy_id="safe")
        # No crash, defaults preserved
        assert cfg.drawdown_threshold == 0.15
        assert cfg.compute_interval == 60

    def test_env_invalid_value_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Invalid env var values (non-numeric for float fields) fall back to default."""
        monkeypatch.setenv("AUTONOMOUS_MONITOR_DRAWDOWN_THRESHOLD", "not-a-number")
        cfg = MonitorConfig(strategy_id="fallback")
        # Should fall back to the YAML/default value without crashing
        assert cfg.drawdown_threshold == 0.15
