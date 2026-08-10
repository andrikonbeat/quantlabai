"""T-3.1 RED — unified execution handoff forwards monitoring hooks (REQ-2).

Strict TDD: written before ``_dispatch_single`` accepted the hooks, so every
test here fails (RED) until T-3.2 (builder) and T-3.3 (dispatch stage) land.

Spec (builder-agent/spec.md): the handoff SHALL include the monitoring hooks
``llm_config``, ``on_watcher_event``, ``on_llm_verdict``, ``confirm_stop`` and
``gate_event_dir``; a handoff failure preserves the CFX artifact and the
campaign enters HOLD for human review (scenario 2).
"""

from __future__ import annotations

import pathlib

import pytest

from quantlab.agents.builder_agent import BuilderAgent, DispatchResult
from quantlab.dsl.models import IterationConfig, LLMConfig, ResearchConfig
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.dispatch_stage import (
    GATE_DECISION_ARTIFACT,
    DispatchStage,
)

# The five monitoring hooks named by the spec (builder-agent/spec.md).
HOOK_KEYS = (
    "llm_config",
    "on_watcher_event",
    "on_llm_verdict",
    "confirm_stop",
    "gate_event_dir",
)


def _research_config() -> ResearchConfig:
    return ResearchConfig(
        campaign="HooksCampaign",
        market="EURUSD",
        timeframe="H1",
        iteration_config=IterationConfig(max_iterations=1),
    )


def _hooks() -> dict:
    """Distinct, identity-checkable hook values."""
    return {
        "llm_config": LLMConfig(provider="opencode", model="test"),
        "on_watcher_event": lambda ev: None,
        "on_llm_verdict": lambda verdict: None,
        "confirm_stop": lambda verdict: True,
        "gate_event_dir": "/tmp/sqx-gates",
    }


class _RecordingDispatch:
    """Fake ``cli_wrapper.dispatch_campaign`` that records every call."""

    def __init__(self, return_value: dict | None = None, exc: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self._return_value = return_value or {"status": "completed", "export_paths": []}
        self._exc = exc

    async def __call__(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        if self._exc is not None:
            raise self._exc
        return dict(self._return_value)


def _patch_fixture_io(monkeypatch) -> None:
    """Make only the Builder.cfx fixture path 'exist' (fallback dispatch site).

    Patches the ``exists``/``read_bytes`` instance methods on the real
    ``pathlib.PosixPath`` class so every other path keeps its real behavior.
    Never rebind ``pathlib.Path`` itself: in Python 3.14 ``Path.__new__``
    references the module-global ``Path`` name, so rebinding it breaks path
    construction (plain ``PosixPath`` with no ``_raw_paths``).
    """
    real_exists = pathlib.PosixPath.exists
    real_read_bytes = pathlib.PosixPath.read_bytes

    def _exists(self) -> bool:
        return str(self).endswith("Builder.cfx") or real_exists(self)

    def _read_bytes(self) -> bytes:
        if str(self).endswith("Builder.cfx"):
            return b"fixture-cfx"
        return real_read_bytes(self)

    monkeypatch.setattr(pathlib.PosixPath, "exists", _exists)
    monkeypatch.setattr(pathlib.PosixPath, "read_bytes", _read_bytes)


@pytest.mark.asyncio
class TestDispatchSingleForwardsHooks:
    """T-3.2 RED: ``_dispatch_single`` forwards the five hooks."""

    async def test_primary_dispatch_forwards_all_five_hooks(self, monkeypatch) -> None:
        """GIVEN a dispatch with monitoring configured
        WHEN ``_dispatch_single`` hands off to the substrate
        THEN all five hooks reach ``cli_wrapper.dispatch_campaign``."""
        from quantlab.sqx import cli_wrapper

        fake = _RecordingDispatch(return_value={"status": "completed", "export_paths": ["/tmp/export.csv"]})
        monkeypatch.setattr(cli_wrapper, "dispatch_campaign", fake)
        monkeypatch.setenv("SQX_FORCE_MOCK", "1")

        hooks = _hooks()
        result = await BuilderAgent()._dispatch_single(
            cfx_bytes=b"cfx",
            config=_research_config(),
            skip_data_check=True,
            **hooks,
        )

        assert len(fake.calls) == 1
        forwarded = fake.calls[0]
        for key in HOOK_KEYS:
            assert forwarded.get(key) is hooks[key], f"hook '{key}' not forwarded"

    async def test_fixture_fallback_dispatch_forwards_all_five_hooks(self, monkeypatch) -> None:
        """GIVEN the primary dispatch produced no exports
        WHEN the Builder fixture fallback runs
        THEN the fallback ``dispatch_campaign`` call also receives the hooks."""
        from quantlab.sqx import cli_wrapper

        fake = _RecordingDispatch(return_value={"status": "completed", "export_paths": []})
        monkeypatch.setattr(cli_wrapper, "dispatch_campaign", fake)
        monkeypatch.setenv("SQX_FORCE_MOCK", "1")
        _patch_fixture_io(monkeypatch)

        hooks = _hooks()
        result = await BuilderAgent()._dispatch_single(
            cfx_bytes=b"cfx",
            config=_research_config(),
            skip_data_check=True,
            **hooks,
        )

        assert len(fake.calls) == 2, "fixture fallback should trigger a second dispatch"
        for call in fake.calls:
            for key in HOOK_KEYS:
                assert call.get(key) is hooks[key], f"hook '{key}' not forwarded in fallback"
        assert result.export_paths == []


class TestHandoffFailurePreservesArtifact:
    """Spec scenario 2: substrate handoff failure keeps the CFX artifact."""

    @pytest.mark.asyncio
    async def test_builder_failure_keeps_cfx_and_fails_closed(self, monkeypatch) -> None:
        """GIVEN the substrate handoff fails
        WHEN ``_dispatch_single`` detects the failure
        THEN the CFX archive remains (preserved for Knowledge Lake) and the
        dispatch fails closed instead of reporting success."""
        from quantlab.sqx import cli_wrapper

        fake = _RecordingDispatch(exc=RuntimeError("substrate down"))
        monkeypatch.setattr(cli_wrapper, "dispatch_campaign", fake)
        monkeypatch.setenv("SQX_FORCE_MOCK", "1")

        agent = BuilderAgent()
        result = DispatchResult(campaign_id="HooksCampaign", cfx_bytes=b"cfx")
        with pytest.raises(RuntimeError, match="substrate down"):
            await agent._dispatch_single(
                cfx_bytes=b"cfx",
                config=_research_config(),
                skip_data_check=True,
                **_hooks(),
            )
        assert result.cfx_bytes == b"cfx"  # artifact preserved for recovery


class _SpyBuilder:
    """Builder double that captures the kwargs it receives."""

    def __init__(self) -> None:
        self.kwargs: dict | None = None

    async def _dispatch_single(self, **kwargs):
        self.kwargs = kwargs
        return DispatchResult(
            campaign_id="HooksCampaign",
            cfx_bytes=kwargs.get("cfx_bytes", b""),
            sqcli_status="completed",
            export_paths=["/tmp/export.csv"],
        )


@pytest.mark.asyncio
class TestDispatchStageForwardsCtxConfigHooks:
    """T-3.3 RED: DispatchStage reads the hooks from ``ctx.config``."""

    async def test_execute_forwards_hooks_from_ctx_config(self) -> None:
        """GIVEN monitoring hooks present in ``ctx.config``
        WHEN DispatchStage executes
        THEN every hook is passed through to ``builder._dispatch_single``."""
        hooks = _hooks()
        ctx = PipelineContext(config={
            "campaign_id": "HooksCampaign",
            **hooks,
        })
        ctx.artifacts["cfx_bytes"] = b"cfx"
        ctx.artifacts["research_config"] = _research_config()
        ctx.artifacts[GATE_DECISION_ARTIFACT] = {"action": "approved", "reason": "ok"}

        builder = _SpyBuilder()
        result = await DispatchStage(builder=builder).execute(ctx)

        assert builder.kwargs is not None
        assert result["sqcli_status"] == "completed"
        for key in HOOK_KEYS:
            assert builder.kwargs.get(key) is hooks[key], f"hook '{key}' not passed through"
        assert builder.kwargs.get("orchestrated") is True

    async def test_execute_without_hooks_defaults_to_none(self) -> None:
        """GIVEN no hooks in ``ctx.config``
        THEN DispatchStage still executes with hooks defaulting to None."""
        ctx = PipelineContext(config={"campaign_id": "HooksCampaign"})
        ctx.artifacts["cfx_bytes"] = b"cfx"
        ctx.artifacts["research_config"] = _research_config()
        ctx.artifacts[GATE_DECISION_ARTIFACT] = {"action": "approved", "reason": "ok"}

        builder = _SpyBuilder()
        result = await DispatchStage(builder=builder).execute(ctx)

        assert builder.kwargs is not None
        assert result["sqcli_status"] == "completed"
        for key in HOOK_KEYS:
            assert builder.kwargs.get(key) is None, f"hook '{key}' should default to None"
