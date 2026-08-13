"""Tests for JForexStrategyBridge."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quantlab.jforex.strategy_bridge import JForexStrategyBridge


class TestJForexStrategyBridge:
    """Test the JForexStrategyBridge implementation."""

    def test_bridge_initialization_without_paths(self):
        """Test that bridge can be initialized with default paths."""
        bridge = JForexStrategyBridge()
        assert bridge.java_home is None
        assert bridge.jforex_home is None

    def test_bridge_initialization_with_paths(self):
        """Test that bridge stores custom java and jforex homes."""
        bridge = JForexStrategyBridge(
            java_home="/opt/java",
            jforex_home="/opt/jforex",
        )
        assert bridge.java_home == Path("/opt/java")
        assert bridge.jforex_home == Path("/opt/jforex")

    @patch("subprocess.run")
    def test_compile_success(self, mock_run: MagicMock, tmp_path: Path):
        """Test compile invokes javac and returns class path on success."""
        mock_run.return_value = MagicMock(returncode=0)
        source = tmp_path / "Strategy.java"
        source.write_text("public class Strategy {}")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        bridge = JForexStrategyBridge(java_home="/opt/java")
        result = bridge.compile(source, out_dir)

        assert result == out_dir / "Strategy.class"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "javac" in cmd[0]
        assert str(source) in cmd
        assert str(out_dir) in cmd

    @patch("subprocess.run")
    def test_compile_failure_raises(self, mock_run: MagicMock, tmp_path: Path):
        """Test compile raises RuntimeError when javac fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="error: bad syntax")
        source = tmp_path / "Bad.java"
        source.write_text("bad code")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        bridge = JForexStrategyBridge()
        with pytest.raises(RuntimeError, match="Compilation failed"):
            bridge.compile(source, out_dir)

    @patch("subprocess.run")
    def test_deploy_success(self, mock_run: MagicMock, tmp_path: Path):
        """Test deploy invokes jforex deploy on success."""
        mock_run.return_value = MagicMock(returncode=0)
        jfx = tmp_path / "strategy.jfx"

        bridge = JForexStrategyBridge(jforex_home="/opt/jforex")
        bridge.deploy(jfx)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "jforex" in cmd[0]
        assert "deploy" in cmd
        assert str(jfx) in cmd

    @patch("subprocess.run")
    def test_deploy_failure_raises(self, mock_run: MagicMock, tmp_path: Path):
        """Test deploy raises RuntimeError when jforex deploy fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="deploy error")
        jfx = tmp_path / "strategy.jfx"

        bridge = JForexStrategyBridge()
        with pytest.raises(RuntimeError, match="Deploy failed"):
            bridge.deploy(jfx)

    @patch("subprocess.run")
    def test_start_success(self, mock_run: MagicMock):
        """Test start invokes jforex start with strategy id."""
        mock_run.return_value = MagicMock(returncode=0)

        bridge = JForexStrategyBridge(jforex_home="/opt/jforex")
        bridge.start("STRAT-001")

        cmd = mock_run.call_args[0][0]
        assert "jforex" in cmd[0]
        assert "start" in cmd
        assert "STRAT-001" in cmd

    @patch("subprocess.run")
    def test_start_failure_raises(self, mock_run: MagicMock):
        """Test start raises RuntimeError when jforex start fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="start error")

        bridge = JForexStrategyBridge()
        with pytest.raises(RuntimeError, match="Start failed"):
            bridge.start("STRAT-001")

    @patch("subprocess.run")
    def test_stop_success(self, mock_run: MagicMock):
        """Test stop invokes jforex stop with strategy id."""
        mock_run.return_value = MagicMock(returncode=0)

        bridge = JForexStrategyBridge(jforex_home="/opt/jforex")
        bridge.stop("STRAT-001")

        cmd = mock_run.call_args[0][0]
        assert "jforex" in cmd[0]
        assert "stop" in cmd
        assert "STRAT-001" in cmd

    @patch("subprocess.run")
    def test_stop_failure_raises(self, mock_run: MagicMock):
        """Test stop raises RuntimeError when jforex stop fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="stop error")

        bridge = JForexStrategyBridge()
        with pytest.raises(RuntimeError, match="Stop failed"):
            bridge.stop("STRAT-001")

    def test_compile_default_java_home_uses_javac(self, tmp_path: Path):
        """Test compile uses plain javac when java_home is not set."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            source = tmp_path / "S.java"
            source.write_text("public class S {}")
            out_dir = tmp_path / "out"
            out_dir.mkdir()

            bridge = JForexStrategyBridge()
            bridge.compile(source, out_dir)

            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "javac"

    def test_compile_with_java_home_uses_full_path(self, tmp_path: Path):
        """Test compile uses {java_home}/bin/javac when java_home is set."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            source = tmp_path / "S.java"
            source.write_text("public class S {}")
            out_dir = tmp_path / "out"
            out_dir.mkdir()

            bridge = JForexStrategyBridge(java_home="/opt/java")
            bridge.compile(source, out_dir)

            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "/opt/java/bin/javac"

    def test_deploy_with_jforex_home_uses_full_path(self, tmp_path: Path):
        """Test deploy uses {jforex_home}/bin/jforex when set."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            jfx = tmp_path / "strategy.jfx"

            bridge = JForexStrategyBridge(jforex_home="/opt/jforex")
            bridge.deploy(jfx)

            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "/opt/jforex/bin/jforex"

    def test_start_with_jforex_home_uses_full_path(self):
        """Test start uses {jforex_home}/bin/jforex when set."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            bridge = JForexStrategyBridge(jforex_home="/opt/jforex")
            bridge.start("STRAT-001")

            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "/opt/jforex/bin/jforex"

    def test_stop_with_jforex_home_uses_full_path(self):
        """Test stop uses {jforex_home}/bin/jforex when set."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            bridge = JForexStrategyBridge(jforex_home="/opt/jforex")
            bridge.stop("STRAT-001")

            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "/opt/jforex/bin/jforex"
