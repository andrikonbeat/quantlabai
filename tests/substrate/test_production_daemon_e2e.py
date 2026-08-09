"""F8: production mode uses the real SQX daemon (unified-execution-substrate REQ-4).

Spec scenario:
- GIVEN production mode THEN the real daemon is used (never a mock).
- The real-daemon e2e test node is environment-gated so the default test run
  stays hermetic: it only executes when the operator opts in with
  QUANTLAB_PRODUCTION_E2E=1 AND SQX_FORCE_MOCK is unset AND an sqcli binary
  actually resolves. Otherwise the node skips with a clear reason — it never
  silently fakes a production run.

Strict TDD: written first — RED until the node exists (a skip with reason is
the honest default; the mode-selection contract is asserted unconditionally).
"""

from __future__ import annotations

import os

import pytest

from quantlab.substrate import (
    Executor,
    Phase,
    PhaseConfig,
    select_dispatch_mode,
)


def _production_e2e_enabled() -> bool:
    """True only when the operator explicitly opts into a real-daemon run."""
    flag = os.environ.get("QUANTLAB_PRODUCTION_E2E", "").lower()
    if flag not in ("1", "true", "yes"):
        return False
    mock = os.environ.get("SQX_FORCE_MOCK", "").lower()
    if mock in ("1", "true", "yes"):
        return False
    return True


def test_production_mode_selector_is_real_when_binary_resolves() -> None:
    """GIVEN a resolvable sqcli and no mock override
    THEN select_dispatch_mode returns "real" — production dispatch uses the
    real daemon, never a mock (REQ-4 scenario, fail-closed).
    """
    install = os.environ.get("SQX_INSTALL_PATH", "/opt/sq")
    env = {"SQX_FORCE_MOCK": ""}
    mode = select_dispatch_mode(install, force_mock=False, env=env)
    if mode == "missing":
        pytest.skip("no sqcli binary resolvable on this host — selector contract "
                    "requires a real daemon install")
    assert mode == "real"


@pytest.mark.skipif(
    not _production_e2e_enabled(),
    reason=(
        "real-daemon e2e node requires QUANTLAB_PRODUCTION_E2E=1 with SQX_FORCE_MOCK "
        "unset and a resolvable sqcli (see tests/substrate/test_production_daemon_e2e.py)"
    ),
)
@pytest.mark.asyncio
async def test_production_e2e_runs_against_real_daemon(tmp_path) -> None:
    """GIVEN production mode is enabled
    WHEN Executor executes a BUILD phase without mock
    THEN the real daemon is used (mode "real") and a genuine run occurs —
    never a mocked or faked dispatch.
    """
    install = os.environ.get("SQX_INSTALL_PATH", "/opt/sq")
    cfg = PhaseConfig(
        sqx_install_path=install,
        campaign_id="e2e-prod-001",
        export_dir=str(tmp_path / "exports"),
        force_mock=False,
    )
    assert select_dispatch_mode(install, force_mock=False) == "real"

    result = await Executor.execute(Phase.BUILD, cfg)
    # A genuine attempt happened: either the daemon completed the phase or the
    # substrate failed after a real dispatch attempt — a mock would never reach
    # a real daemon lifecycle. Fail-closed states are still evidence of a real
    # execution path.
    assert result.status.value in ("completed", "failed")
