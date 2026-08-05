"""Task 2.4 RED: sqcli selectors — relative path, missing binary, SQCLI_PATH
env fallback, and SQX_FORCE_MOCK override. Fail-closed: a missing binary must
never dispatch silently.

Threat-matrix row (subprocess: sqcli invocation):
  resolve via assets/.../sqcli or SQCLI_PATH env; validate existence before
  dispatch; mock server under SQX_FORCE_MOCK. One RED per selector.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from quantlab.substrate.executor import (
    Executor,
    Phase,
    PhaseConfig,
    SubstrateConfigError,
    resolve_sqcli_path,
    select_dispatch_mode,
)


def _make_executable(path):
    path.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def _cfg(campaign_id: str, sqx_install_path, **kwargs) -> PhaseConfig:
    return PhaseConfig(
        sqx_install_path=sqx_install_path,
        campaign_id=campaign_id,
        project=f"{campaign_id}.cfx",
        poll_interval=0.3,
        timeout=10.0,
        **kwargs,
    )


class TestResolveSqcliPath:
    """Selector 1: relative path resolves; selector 2: missing → None."""

    def test_relative_install_path_resolves_to_absolute(self, tmp_path, monkeypatch):
        sqcli = _make_executable(tmp_path / "sqcli")
        monkeypatch.chdir(tmp_path)

        resolved = resolve_sqcli_path(".", env={})

        assert resolved is not None
        assert Path(resolved) == sqcli.resolve()
        assert Path(resolved).is_absolute()

    def test_missing_binary_returns_none(self, tmp_path):
        assert resolve_sqcli_path(str(tmp_path), env={}) is None

    def test_missing_binary_respects_sqcli_path_env(self, tmp_path):
        """Selector 3: SQCLI_PATH env fallback wins over the install dir."""
        sqcli = _make_executable(tmp_path / "sqcli")
        empty_install = tmp_path / "install"
        empty_install.mkdir()

        resolved = resolve_sqcli_path(str(empty_install), env={"SQCLI_PATH": str(sqcli)})

        assert resolved == str(sqcli.resolve())


class TestSelectDispatchMode:
    """Selector 4: mock override under SQX_FORCE_MOCK; fail-closed otherwise."""

    def test_mock_override_when_binary_missing(self, tmp_path):
        mode = select_dispatch_mode(
            str(tmp_path), force_mock=True, env={"SQX_FORCE_MOCK": "0"}
        )
        assert mode == "mock"

    def test_mock_override_via_env(self, tmp_path):
        mode = select_dispatch_mode(
            str(tmp_path), force_mock=False, env={"SQX_FORCE_MOCK": "1"}
        )
        assert mode == "mock"

    def test_missing_binary_is_fail_closed(self, tmp_path):
        mode = select_dispatch_mode(str(tmp_path), force_mock=False, env={})
        assert mode == "missing"


class TestExecutorFailClosed:
    """No dispatch when the binary is missing and mock is not forced."""

    async def test_missing_binary_raises_before_any_command(
        self, campaign_id, tmp_path, monkeypatch
    ):
        # Deterministic regardless of the harness's ambient SQX_FORCE_MOCK=1.
        monkeypatch.delenv("SQX_FORCE_MOCK", raising=False)
        monkeypatch.delenv("SQCLI_PATH", raising=False)
        cfg = _cfg(
            campaign_id,
            tmp_path,
            force_mock=False,
            http_client=_NeverCalledClient(),
        )

        with pytest.raises(SubstrateConfigError) as exc_info:
            await Executor.execute(Phase.BUILD, cfg)

        message = str(exc_info.value)
        assert "sqcli" in message.lower()
        assert "SQCLI_PATH" in message or "SQX_FORCE_MOCK" in message

    async def test_force_mock_dispatches_despite_missing_binary(
        self, campaign_id, tmp_path
    ):
        cfg = _cfg(campaign_id, tmp_path, force_mock=True)

        result = await Executor.execute(Phase.BUILD, cfg)

        from quantlab.phase4.models import PhaseStatus

        assert result.status == PhaseStatus.COMPLETED


class _NeverCalledClient:
    """Client that fails loudly if any command is sent (fail-closed proof)."""

    async def send_command(self, command: str) -> str:
        raise AssertionError(f"dispatch attempted despite missing binary: {command}")

    async def close(self) -> None:
        pass
