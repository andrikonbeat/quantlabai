"""Slice A: ``BuilderStage`` gates on ``portfolio_state``.

Spec requirement "State Machine Enforcement (Issue 3)":

- ``BuilderStage`` MUST block when ``portfolio_state`` is ``QUARANTINE`` or
  ``DEFENSIVE`` by raising ``PortfolioStateBlockedError`` before any CFX
  write.
- Permitted states (and the legacy absent artifact) MUST fall through to the
  normal stage behaviour instead of blocking.

``portfolio_state`` is an optional gate input rather than a declared
``requires`` key: the canonical 14-phase flow runs ``builder`` before
``guardian_evaluate``, so it can never be an upstream ``provides`` key.

Strict TDD: written first — RED until Slice A lands.
"""

from __future__ import annotations

import pytest

from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.errors import PortfolioStateBlockedError
from quantlab.pipeline.stages.agent_stages import BuilderStage


def _ctx(portfolio_state: str | None) -> PipelineContext:
    artifacts: dict = {"research_config": {}}
    if portfolio_state is not None:
        artifacts["portfolio_state"] = portfolio_state
    return PipelineContext(config={}, artifacts=artifacts)


class TestBlockedStates:
    """QUARANTINE and DEFENSIVE fail closed."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("state", ["QUARANTINE", "DEFENSIVE"])
    async def test_blocked_state_raises(self, state: str) -> None:
        """GIVEN a blocked portfolio_state
        WHEN BuilderStage executes
        THEN PortfolioStateBlockedError is raised.
        """
        with pytest.raises(PortfolioStateBlockedError):
            await BuilderStage().execute(_ctx(state))

    @pytest.mark.asyncio
    async def test_error_carries_state_and_stage(self) -> None:
        """The error exposes the blocking state and the stage that refused."""
        with pytest.raises(PortfolioStateBlockedError) as exc_info:
            await BuilderStage().execute(_ctx("QUARANTINE"))

        assert exc_info.value.portfolio_state == "QUARANTINE"
        assert exc_info.value.stage_name == "builder"

    @pytest.mark.asyncio
    async def test_blocked_before_any_cfx_artifact_write(self) -> None:
        """A blocked stage must not write CFX artifacts downstream."""
        ctx = _ctx("DEFENSIVE")

        with pytest.raises(PortfolioStateBlockedError):
            await BuilderStage().execute(ctx)

        assert "cfx_bytes" not in ctx.artifacts


class TestPermittedStates:
    """NORMAL, VIGILANCE, RECOVERY and the legacy absent artifact do not block."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("state", ["NORMAL", "VIGILANCE", "RECOVERY"])
    async def test_permitted_state_proceeds(self, state: str) -> None:
        """A permitted state falls through to the stage's own behaviour."""
        with pytest.raises(NotImplementedError):
            await BuilderStage().execute(_ctx(state))

    @pytest.mark.asyncio
    async def test_absent_portfolio_state_does_not_block(self) -> None:
        """Legacy flows without a guardian evaluation must still reach builder."""
        with pytest.raises(NotImplementedError):
            await BuilderStage().execute(_ctx(None))

    def test_portfolio_state_is_not_a_declared_required_artifact(self) -> None:
        """The gate input is optional, so it must not appear in `requires`."""
        assert "portfolio_state" not in BuilderStage.requires
