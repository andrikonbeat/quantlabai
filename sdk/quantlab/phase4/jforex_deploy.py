"""Phase 4 — JForex Deployer for StrategyQuant → JForex 4 export."""

from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Callable, Optional

from quantlab.compiler import (
    JfxArtifact,
    is_compiler_enabled,
)
from quantlab.compiler.compiler import CompilerPipeline
from quantlab.phase4.http_client import DEFAULT_PORT, AsyncSQXClient
from quantlab.phase4.errors import (
    JForexError,
    JForexConnectionError,
    JForexStrategyNotFoundError,
    JForexServerError,
)

logger = logging.getLogger(__name__)


class JForexDeployer:
    """Exports SQX strategies to JForex 4 compatible .java files and deploys custom indicators.

    Usage:
        async with AsyncSQXClient("http://127.0.0.1:8888") as client:
            deployer = JForexDeployer(client)
            java_path = await deployer.export_strategy("strat-123", "/output/dir")
            await deployer.deploy_indicators(Path("/path/to/jforex/strategies"))
    """

    # Valid JForex fitness functions
    VALID_FITNESS_FUNCTIONS = {
        "NetProfit",
        "ReturnDDRatio",
        "SharpeRatio",
        "SortinoRatio",
        "ProfitFactor",
        "RecoveryFactor",
        "KRatio",
    }

    def __init__(
        self,
        client: AsyncSQXClient | None = None,
        *,
        sqx_install_path: str | None = None,
    ) -> None:
        if client is None:
            client = AsyncSQXClient(f"http://127.0.0.1:{DEFAULT_PORT}")
        self._client = client
        self._sqx_install_path = sqx_install_path

    async def export_strategy(
        self,
        strategy_id: str,
        output_dir: str | Path,
        *,
        strategy_name: Optional[str] = None,
    ) -> Path:
        """Export a strategy by ID as a JForex-compatible .java file.

        Args:
            strategy_id: SQX strategy ID (as shown in SQX GUI).
            output_dir: Directory to write the .java file.
            strategy_name: Optional custom class name. If omitted, uses strategy_id.

        Returns:
            Path to the generated .java file.

        Raises:
            JForexStrategyNotFoundError: If strategy_id not found in SQX.
            JForexConnectionError: If SQX server unreachable.
            JForexServerError: If SQX returns 5xx.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Export via SQX HTTP API
        java_source = await self._client.export_sourcecode(strategy_id)

        # Use custom name or strategy_id
        class_name = strategy_name or strategy_id
        # Sanitize: Java class names must start with letter, alphanumeric + _
        class_name = re.sub(r"[^a-zA-Z0-9_]", "_", class_name)
        if class_name[0].isdigit():
            class_name = f"Strategy_{class_name}"

        # Ensure the Java file has the correct class name
        # SQX output should already have the right class name, but we can override
        if f"class {strategy_id}" in java_source and strategy_id != class_name:
            java_source = java_source.replace(
                f"class {strategy_id}",
                f"class {class_name}",
            )

        output_path = output_dir / f"{class_name}.java"
        output_path.write_text(java_source, encoding="utf-8")
        return output_path

    def compile_strategy(
        self,
        java_path: str | Path,
        *,
        jdk_home: Optional[str | Path] = None,
        env: Optional[dict[str, str]] = None,
        fixer: Optional[Callable[[str, list[str]], str]] = None,
        max_fix_iterations: int = 5,
    ) -> JfxArtifact | Path:
        """Route an exported ``.java`` through the compiler pipeline (REQ-39).

        The deploy path continues: javac from the external JDK
        (``QUANTLAB_JDK_HOME``) compiles the source and packages the result as
        a ``.jfx`` (REQ-29). Compile errors route into the bounded fix loop
        (REQ-30); when the bound is exhausted a :class:`CompileError` is
        raised and deployment is blocked — no ``.jfx`` and no deployable JAR
        are produced (REQ-39 scenario 2).

        Rollback boundary (design slice 3): ``QUANTLAB_COMPILER=0`` keeps the
        ``.java``-only path — the *java_path* is returned unchanged and no
        compile step runs.

        Returns:
            The packaged :class:`JfxArtifact`, or the original *java_path*
            when the compiler is disabled.

        Raises:
            CompilerConfigError: JDK/javac missing or non-executable —
                fail-closed before javac runs (REQ-29).
            CompileError: javac failed with a structured error report, or the
                fix loop exhausted its bound with full history (REQ-30).
        """
        env = os.environ if env is None else env
        if not is_compiler_enabled(env):
            logger.info("QUANTLAB_COMPILER=0 — keeping .java-only deploy path")
            return Path(java_path)
        return CompilerPipeline.compile(
            java_path,
            jdk_home=jdk_home,
            env=env,
            fixer=fixer,
            max_fix_iterations=max_fix_iterations,
            sqx_install_path=self._sqx_install_path,
        )

    async def export_and_compile(
        self,
        strategy_id: str,
        output_dir: str | Path,
        *,
        strategy_name: Optional[str] = None,
        jdk_home: Optional[str | Path] = None,
        env: Optional[dict[str, str]] = None,
        fixer: Optional[Callable[[str, list[str]], str]] = None,
        max_fix_iterations: int = 5,
    ) -> JfxArtifact | Path:
        """Export a strategy and route it through the compiler (REQ-39).

        ``export_strategy`` writes the ``.java``; ``compile_strategy`` then
        routes it through :class:`CompilerPipeline` and packages the ``.jfx``
        (REQ-39 scenario 1: "export then compile to .jfx"). A compile failure
        blocks deploy (REQ-39 scenario 2) — no JAR is produced.
        """
        java_path = await self.export_strategy(
            strategy_id, output_dir, strategy_name=strategy_name
        )
        return self.compile_strategy(
            java_path,
            jdk_home=jdk_home,
            env=env,
            fixer=fixer,
            max_fix_iterations=max_fix_iterations,
        )
    async def deploy_indicators(
        self,
        jforex_strategies_dir: str | Path,
        *,
        sqx_custom_indicators_dir: Optional[str | Path] = None,
    ) -> list[Path]:
        """Copy custom indicators from SQX installation to JForex strategies directory.

        Args:
            jforex_strategies_dir: JForex SDK strategies directory (e.g., .../JForex/strategies).
            sqx_custom_indicators_dir: SQX custom_indicators/JForex directory.
                If None, tries to infer from SQX installation.

        Returns:
            List of copied indicator file paths.

        Raises:
            JForexError: If source directory not found.
        """
        target = Path(jforex_strategies_dir)
        target.mkdir(parents=True, exist_ok=True)

        if sqx_custom_indicators_dir:
            source = Path(sqx_custom_indicators_dir)
        else:
            # Try to find SQX install's custom_indicators/JForex
            # This would need to be configured or passed explicitly
            raise JForexError(
                "sqx_custom_indicators_dir must be provided (SQX install path unknown)"
            )

        if not source.exists():
            raise JForexError(f"SQX custom indicators dir not found: {source}")

        copied = []
        for item in source.rglob("*.java"):
            rel = item.relative_to(source)
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
            copied.append(dest)

        return copied

    async def dry_run_export(self, strategy_id: str) -> str:
        """Export strategy source without writing to disk.

        Returns:
            Java source code as string.
        """
        return await self._client.export_sourcecode(strategy_id)

    async def validate_strategy_exists(self, strategy_id: str) -> bool:
        """Check if a strategy exists in SQX without exporting.

        Returns:
            True if strategy exists, False otherwise.
        """
        try:
            await self._client.export_sourcecode(strategy_id)
            return True
        except JForexStrategyNotFoundError:
            return False
        except Exception:
            return False