"""MCP Bridge — central server that registers and runs all QuantLab MCP tools.

``QuantLabMCPServer`` creates a ``FastMCP`` instance, lazily initialises
subsystem singletons (pipeline runner, evolution orchestrator, health
calculator, data providers), and loads domain tool modules via their
``register()`` function.

Usage::

    from quantlab.mcp.bridge import QuantLabMCPServer

    server = QuantLabMCPServer()
    await server.run()
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def main() -> None:
    """Boot the MCP server and run it synchronously.

    This is the entry point called by ``quantlab.mcp.__main__``.
    """
    import asyncio

    server = QuantLabMCPServer()
    asyncio.run(server.run())


class QuantLabMCPServer:
    """QuantLab MCP server — owns the FastMCP instance and subsystem singletons.

    Subsystem singletons are lazily initialised on first access so that
    imports are deferred until a tool actually needs the subsystem.
    """

    def __init__(self) -> None:
        self._mcp = FastMCP("quantlab-mcp")

        # ── Lazy subsystem singletons ──────────────────────────────────────
        self._pipeline_runner: Any = None
        self._evolution_orchestrator: Any = None
        self._candidate_pool: Any = None
        self._health_calculator: Any = None
        self._meta_guardian: Any = None
        self._yahoo_provider: Any = None
        self._fred_provider: Any = None

        self._register_tools()

    # ── Public: access to the underlying MCP server ─────────────────────────

    @property
    def mcp(self) -> FastMCP:
        """The underlying ``FastMCP`` instance — used by domain tool registrations."""
        return self._mcp

    # ── Lazy subsystem properties ───────────────────────────────────────────

    @property
    def pipeline_runner(self) -> Any:
        """Lazy ``PipelineRunner`` singleton."""
        if self._pipeline_runner is None:
            from quantlab.pipeline import PipelineRunner

            self._pipeline_runner = PipelineRunner(max_retries=1)
            logger.debug("Lazy-init: PipelineRunner")
        return self._pipeline_runner

    @property
    def evolution_orchestrator(self) -> Any:
        """Lazy ``EvolutionOrchestrator`` singleton."""
        if self._evolution_orchestrator is None:
            from quantlab.evolution.config import EvolutionConfig
            from quantlab.evolution.orchestrator import EvolutionOrchestrator

            config = EvolutionConfig()
            self._evolution_orchestrator = EvolutionOrchestrator(config=config)
            logger.debug("Lazy-init: EvolutionOrchestrator")
        return self._evolution_orchestrator

    @property
    def candidate_pool(self) -> Any:
        """Lazy ``CandidatePool`` singleton (aliases the orchestrator's pool)."""
        if self._candidate_pool is None:
            self._candidate_pool = self.evolution_orchestrator.pool
            logger.debug("Lazy-init: CandidatePool")
        return self._candidate_pool

    @property
    def health_calculator(self) -> Any:
        """Lazy ``HealthScoreCalculator`` singleton."""
        if self._health_calculator is None:
            from quantlab.health.calculator import HealthScoreCalculator

            self._health_calculator = HealthScoreCalculator()
            logger.debug("Lazy-init: HealthScoreCalculator")
        return self._health_calculator

    @property
    def meta_guardian(self) -> Any:
        """Lazy ``MetaGuardianOrchestrator`` singleton."""
        if self._meta_guardian is None:
            from quantlab.guardian.models import MetaGuardianConfig
            from quantlab.guardian.orchestrator import MetaGuardianOrchestrator

            config = MetaGuardianConfig()
            self._meta_guardian = MetaGuardianOrchestrator(config=config, guardians=[])
            logger.debug("Lazy-init: MetaGuardianOrchestrator")
        return self._meta_guardian

    @property
    def yahoo_provider(self) -> Any:
        """Lazy ``YahooFinanceProvider`` singleton."""
        if self._yahoo_provider is None:
            from quantlab.data.fundamental import YahooFinanceProvider

            self._yahoo_provider = YahooFinanceProvider()
            logger.debug("Lazy-init: YahooFinanceProvider")
        return self._yahoo_provider

    @property
    def fred_provider(self) -> Any:
        """Lazy ``FredProvider`` singleton."""
        if self._fred_provider is None:
            from quantlab.data.fundamental import FredProvider

            self._fred_provider = FredProvider()
            logger.debug("Lazy-init: FredProvider")
        return self._fred_provider

    # ── Tool registration ───────────────────────────────────────────────────

    def _register_tools(self) -> None:
        """Import and register all domain tool modules.

        Each module must expose a ``register(QuantLabMCPServer)`` function
        that attaches tools to ``server.mcp`` via the ``@mcp.tool()``
        decorator or ``mcp.add_tool()``.
        """
        from quantlab.mcp import pipeline_tools
        from quantlab.mcp import evolution_tools
        from quantlab.mcp import fundamental_tools
        from quantlab.mcp import health_tools
        from quantlab.mcp import seg_tools

        pipeline_tools.register(self)
        evolution_tools.register(self)
        health_tools.register(self)
        fundamental_tools.register(self)
        seg_tools.register(self)

        logger.info(
            "Registered tool modules: pipeline, evolution, health, fundamental, seg"
        )

    # ── Lifecycle ───────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Run the MCP server over stdio.

        This is the primary entry point.  Callers should ``await`` this
        method — it blocks until the stdin/stdout transport is closed.
        """
        logger.info("QuantLab MCP server starting (stdio transport)")
        await self._mcp.run_stdio_async()
