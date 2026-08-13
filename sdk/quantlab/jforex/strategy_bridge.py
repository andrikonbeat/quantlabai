"""JForex4 strategy bridge — compile, deploy, start, and stop .jfx strategies."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


class JForexStrategyBridge:
    """Bridge between QuantLab and JForex4 strategy lifecycle.

    Compiles Java strategy sources, deploys ``.jfx`` packages, and
    controls the start/stop lifecycle through the JForex4 CLI.

    Attributes:
        java_home: Optional Java installation directory. When set, the
            bridge uses ``{java_home}/bin/javac`` instead of the system
            ``javac``.
        jforex_home: Optional JForex4 installation directory. When set,
            the bridge uses ``{jforex_home}/bin/jforex`` instead of the
            system ``jforex`` binary.
    """

    def __init__(
        self,
        java_home: Optional[str] = None,
        jforex_home: Optional[str] = None,
    ) -> None:
        self.java_home = Path(java_home) if java_home else None
        self.jforex_home = Path(jforex_home) if jforex_home else None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def compile(self, source_path: Path, output_dir: Path) -> Path:
        """Compile a Java strategy source file.

        Args:
            source_path: Path to the ``.java`` source file.
            output_dir: Directory where compiled ``.class`` files are
                written.

        Returns:
            Path to the compiled ``.class`` file.

        Raises:
            RuntimeError: If the Java compiler returns a non-zero exit
                code.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        javac = (
            self.java_home / "bin" / "javac"
            if self.java_home
            else Path("javac")
        )
        cmd = [
            str(javac),
            "-d",
            str(output_dir),
            str(source_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"Compilation failed: {result.stderr.strip()}"
            )
        return output_dir / f"{source_path.stem}.class"

    def deploy(self, jfx_path: Path) -> None:
        """Deploy a ``.jfx`` strategy package to JForex4.

        Args:
            jfx_path: Path to the ``.jfx`` package to deploy.

        Raises:
            RuntimeError: If the deploy command returns a non-zero exit
                code.
        """
        jforex = (
            self.jforex_home / "bin" / "jforex"
            if self.jforex_home
            else Path("jforex")
        )
        cmd = [str(jforex), "deploy", str(jfx_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"Deploy failed: {result.stderr.strip()}"
            )

    def start(self, strategy_id: str) -> None:
        """Start a deployed strategy by identifier.

        Args:
            strategy_id: The JForex4 strategy identifier.

        Raises:
            RuntimeError: If the start command returns a non-zero exit
                code.
        """
        jforex = (
            self.jforex_home / "bin" / "jforex"
            if self.jforex_home
            else Path("jforex")
        )
        cmd = [str(jforex), "start", strategy_id]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"Start failed: {result.stderr.strip()}"
            )

    def stop(self, strategy_id: str) -> None:
        """Stop a running strategy by identifier.

        Args:
            strategy_id: The JForex4 strategy identifier.

        Raises:
            RuntimeError: If the stop command returns a non-zero exit
                code.
        """
        jforex = (
            self.jforex_home / "bin" / "jforex"
            if self.jforex_home
            else Path("jforex")
        )
        cmd = [str(jforex), "stop", strategy_id]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"Stop failed: {result.stderr.strip()}"
            )
