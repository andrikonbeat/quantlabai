"""WU-6: builder split — orchestrated dispatch skip + hard data pre-flight.

Covers REQ-13 (data-manager spec) and AD-3/AD-8 (design): in orchestrated
mode ``BuilderAgent.run`` skips Phase-4 dispatch (dispatch moves to the
DispatchStage boundary) and ``BuilderAgent._ensure_data`` becomes a HARD
pre-flight that aborts dispatch; the ``skip_data_check`` flag disables it.

Strict TDD: written first — FAIL (RED) until the split exists.
"""

import pytest

from quantlab.agents.builder_agent import BuilderAgent
from quantlab.dsl.models import IterationConfig, ResearchConfig
from quantlab.pipeline.base import PipelineContext


def _cfg() -> ResearchConfig:
    from quantlab.dsl.models import Strategy

    return ResearchConfig(
        campaign="BuilderSplit",
        market="EURUSD",
        timeframe="H1",
        strategies=[Strategy(name="StratA", direction="BOTH")],
        iteration_config=IterationConfig(max_iterations=1),
    )


class TestRunOrchestratedSplit:
    """AD-3/AD-8: BuilderAgent.run skips dispatch when orchestrated."""

    @pytest.mark.asyncio
    async def test_run_orchestrated_skips_dispatch(self) -> None:
        """GIVEN orchestrated=True in the context config
        WHEN run() executes
        THEN it translates/validates/licenses but never dispatches: no
        campaign_id / sqcli_status / export_paths, and the in-flight
        build_config is published for ConfigReviewStage.
        """
        from quantlab.sqx.project_builder import BuildConfig

        agent = BuilderAgent()

        async def _explode(*args, **kwargs):
            raise AssertionError("dispatch must not run in orchestrated mode")

        agent._dispatch_single = _explode

        build_config = BuildConfig()
        ctx = PipelineContext(
            config={"orchestrated": True, "build_config": build_config},
            artifacts={"research_config": _cfg()},
        )

        result = await agent.run(ctx)

        # Dispatch boundary moved out: no dispatch artifacts anywhere.
        assert "cfx_bytes" in ctx.artifacts
        assert ctx.artifacts["build_config"] is build_config
        assert "campaign_id" not in ctx.artifacts
        assert "sqcli_status" not in ctx.artifacts
        assert "export_paths" not in ctx.artifacts
        assert "campaign_id" not in result
        assert "sqcli_status" not in result
        assert "build_config" in result

    @pytest.mark.asyncio
    async def test_run_non_orchestrated_keeps_dispatch_artifacts(self) -> None:
        """GIVEN no orchestrated flag (legacy path)
        WHEN run() executes
        THEN dispatch artifacts are still written (REQ-11 unchanged).
        """
        agent = BuilderAgent()

        async def _fake_dispatch_single(cfx_bytes, config, **kwargs):
            from quantlab.agents.builder_agent import DispatchResult

            return DispatchResult(
                campaign_id="sqx_legacy_1",
                cfx_bytes=cfx_bytes,
                sqcli_status="completed",
                export_paths=["/tmp/legacy.csv"],
                dispatch_log=[{"ok": True}],
            )

        agent._dispatch_single = _fake_dispatch_single

        ctx = PipelineContext(config={}, artifacts={"research_config": _cfg()})
        result = await agent.run(ctx)

        assert ctx.artifacts["campaign_id"] == "sqx_legacy_1"
        assert result["sqcli_status"] == "completed"
        assert len(result["export_paths"]) >= 1


class TestEnsureDataPreFlight:
    """REQ-13: _ensure_data is hard in orchestrated mode, best-effort otherwise."""

    @pytest.mark.asyncio
    async def test_ensure_data_hard_in_orchestrated_mode(self) -> None:
        """GIVEN orchestrated mode and _ensure_data failing (DataManager absent)
        WHEN _ensure_data runs
        THEN a data error is raised — dispatch must abort.
        """
        agent = BuilderAgent()

        with pytest.raises(RuntimeError, match="Data pre-flight failed"):
            await agent._ensure_data(_cfg(), orchestrated=True)

    @pytest.mark.asyncio
    async def test_ensure_data_best_effort_legacy(self) -> None:
        """GIVEN legacy mode (orchestrated=False)
        WHEN _ensure_data fails
        THEN it logs and returns — dispatch proceeds (non-blocking).
        """
        agent = BuilderAgent()

        result = await agent._ensure_data(_cfg(), orchestrated=False)

        assert result is None  # no exception raised

    @pytest.mark.asyncio
    async def test_dispatch_single_orchestrated_aborts_on_data_error(self) -> None:
        """GIVEN orchestrated=True without the skip flag
        WHEN dispatch is attempted
        THEN dispatch aborts with the data error (REQ-13 scenario).
        """
        agent = BuilderAgent()

        with pytest.raises(RuntimeError, match="Data pre-flight failed"):
            await agent._dispatch_single(b"cfx", _cfg(), orchestrated=True)

    @pytest.mark.asyncio
    async def test_dispatch_single_skip_flag_proceeds(self) -> None:
        """GIVEN orchestrated=True with skip_data_check=True
        WHEN dispatch is attempted
        THEN the data pre-flight is skipped and dispatch proceeds
        (REQ-13 scenario).
        """
        import quantlab.sqx.cli_wrapper as cli_wrapper

        agent = BuilderAgent()

        async def _fake_dispatch_campaign(
            cfx_bytes=None,
            campaign_id=None,
            config=None,
            force_mock=None,
            build_config=None,
        ):
            return {
                "status": "completed",
                "export_paths": ["/tmp/dispatched.csv"],
                "campaign_id": campaign_id or "sqx_skip_1",
            }

        # Patch the cli wrapper to avoid the real sqcli path.
        import pytest

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(cli_wrapper, "dispatch_campaign", _fake_dispatch_campaign)
            result = await agent._dispatch_single(
                b"cfx",
                _cfg(),
                skip_data_check=True,
                orchestrated=True,
            )

        assert result.sqcli_status == "completed"
        assert result.export_paths == ["/tmp/dispatched.csv"]
