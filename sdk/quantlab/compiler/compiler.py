"""Compiler pipeline (REQ-29/30) — javac compile + ``.jfx`` packaging.

Flow (design slice 3): exported ``.java`` source → javac from the external
JDK (``QUANTLAB_JDK_HOME``; missing → :class:`CompilerConfigError`, no
partial ``.jfx``) → on compile errors, the bounded error-fix loop (REQ-30) →
``.jfx`` package next to the source.

Rollback gate: ``QUANTLAB_COMPILER=0`` keeps the ``.java``-only deploy path
(design slice 3 rollback boundary).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from quantlab.compiler.errors import CompilerConfigError, CompileError
from quantlab.compiler.jfx import JfxArtifact, package_classes

logger = logging.getLogger(__name__)

# AD-5: external JDK via env; never fall back to ``j64/`` (a JRE has no javac).
JDK_ENV_VAR = "QUANTLAB_JDK_HOME"
DEFAULT_MAX_FIX_ITERATIONS = 5


def is_compiler_enabled(env: Optional[dict[str, str]] = None) -> bool:
    """Rollback gate (design slice 3): ``QUANTLAB_COMPILER=0`` keeps the
    ``.java``-only path; the compiler pipeline is the default deploy route.
    """
    env = os.environ if env is None else env
    return env.get("QUANTLAB_COMPILER", "1") != "0"


def resolve_javac(
    jdk_home: Optional[str | Path] = None,
    env: Optional[dict[str, str]] = None,
) -> Optional[Path]:
    """Resolve javac from the external JDK root, fail-closed.

    Order: explicit *jdk_home* argument → ``QUANTLAB_JDK_HOME`` env. Returns
    the absolute ``bin/javac`` path only when it exists AND is executable;
    ``None`` otherwise (the caller raises :class:`CompilerConfigError`).
    Never probes ``j64/`` — AD-5.
    """
    env = os.environ if env is None else env
    root = jdk_home if jdk_home is not None else env.get(JDK_ENV_VAR)
    if not root:
        return None
    javac = Path(root) / "bin" / ("javac.exe" if os.name == "nt" else "javac")
    if javac.is_file() and os.access(javac, os.X_OK):
        return javac
    return None


@dataclass
class CompileReport:
    """Structured result of one javac invocation (REQ-29 s1)."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""

    @property
    def errors(self) -> list[str]:
        """Parsed error lines from javac stderr — ``error:`` lines only."""
        return [line for line in self.stderr.splitlines() if "error:" in line]

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def run_javac(
    javac: Path,
    src: str | Path,
    classes_dir: str | Path,
    *,
    timeout: float = 60.0,
    classpath: list[str | Path] | None = None,
) -> CompileReport:
    """Invoke ``javac -d <classes_dir> [-cp <classpath>] <src>`` with a fresh
    output directory.

    The output dir is wiped before each invocation so stale classes from a
    failed attempt can never leak into a later package.  When *classpath* is
    non-empty, ``-cp <os.pathsep.join(classpath)>`` is injected before the
    source (SQX-generated strategies import ``com.strategyquant.datalib`` /
    ``com.strategyquant.tradinglib`` from ``internal/libs/*.jar`` — without it
    javac fails with ``package com.strategyquant.datalib does not exist``).
    """
    classes_dir = Path(classes_dir)
    if classes_dir.exists():
        shutil.rmtree(classes_dir)
    classes_dir.mkdir(parents=True)
    cmd = [str(javac), "-d", str(classes_dir)]
    if classpath:
        cmd += ["-cp", os.pathsep.join(str(p) for p in classpath)]
    cmd.append(str(src))
    logger.debug("javac %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return CompileReport(
        exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
    )


# The fixer is LLM-guided: takes the source text and the parsed error lines,
# returns the amended source. Real LLM wiring is a later integration; the fix
# loop itself (REQ-30) is what the pipeline owns.
Fixer = Callable[[str, list[str]], str]


class CompilerPipeline:
    """Compile exported ``.java`` sources and package ``.jfx`` (REQ-29/30)."""

    @staticmethod
    def compile(
        src: str | Path,
        *,
        jdk_home: Optional[str | Path] = None,
        env: Optional[dict[str, str]] = None,
        fixer: Optional[Fixer] = None,
        max_fix_iterations: int = DEFAULT_MAX_FIX_ITERATIONS,
        timeout: float = 60.0,
        classes_dir: Optional[str | Path] = None,
        sqx_install_path: Optional[str | Path] = None,
    ) -> JfxArtifact:
        """Compile *src* with the external JDK and package the result.

        Raises:
            CompilerConfigError: JDK/javac missing or non-executable — raised
                BEFORE javac runs; no partial ``.jfx`` (REQ-29 s2, threat
                matrix row "subprocess: javac").
            CompileError: javac failed — carrying the structured error report
                (REQ-29 s1); when a fixer is configured and the loop exhausts
                its bound, carrying the full per-iteration history (REQ-30 s2).
                The failing source is never packaged nor deployed.
        """
        env = os.environ if env is None else env
        javac = resolve_javac(jdk_home=jdk_home, env=env)
        if javac is None:
            raise CompilerConfigError(
                "javac not found — an external JDK is required (REQ-29). "
                f"Set {JDK_ENV_VAR} to a JDK (Java 25-compatible) whose "
                "bin/javac exists and is executable. Missing or non-executable "
                "javac fails closed: no partial .jfx is produced."
            )

        src = Path(src)
        classes = (
            Path(classes_dir)
            if classes_dir is not None
            else src.parent / ".classes"
        )

        # SQX-generated strategies import com.strategyquant.datalib /
        # com.strategyquant.tradinglib (SQTradingLib.jar), SQ.Calculators /
        # SQ.Internal (Snippets.jar), etc. — feed every jar from the SQX
        # install's internal/libs as the javac classpath when available.
        classpath: list[Path] | None = None
        if sqx_install_path is not None:
            libs = Path(sqx_install_path) / "internal" / "libs"
            jars = sorted(libs.glob("*.jar")) if libs.is_dir() else []
            classpath = jars or None

        report = run_javac(javac, src, classes, timeout=timeout, classpath=classpath)
        if not report.ok:
            if fixer is not None and max_fix_iterations > 0:
                from quantlab.compiler.fixloop import run_fix_loop  # REQ-30

                result = run_fix_loop(
                    src=src,
                    compile_fn=lambda s: run_javac(
                        javac, s, classes, timeout=timeout, classpath=classpath
                    ),
                    fix_fn=fixer,
                    max_fix_iterations=max_fix_iterations,
                    initial_report=report,
                )
                if not result.success:
                    raise CompileError(
                        f"compilation failed after {max_fix_iterations} fix "
                        "iterations (REQ-30 bound)",
                        report=result.final_report,
                        history=result.iterations,
                    )
                report = result.final_report
            else:
                raise CompileError(
                    "javac compilation failed",
                    report=report,
                    history=[],
                )

        return package_classes(classes, src)
