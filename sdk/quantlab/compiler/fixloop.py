"""Bounded error-fix loop (REQ-30).

Compile failures route here: the structured error report feeds a fix attempt
(LLM-guided via an injected fixer), the source is amended and recompiled, up
to ``max_fix_iterations``. Every iteration is logged. Exceeding the bound
halts the pipeline with a :class:`CompileError` carrying the full history
(design slice 3: "bound exhausted → CompileError + full error history, not
deployed").
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from quantlab.compiler.compiler import CompileReport

logger = logging.getLogger(__name__)


@dataclass
class FixIteration:
    """One logged fix-loop attempt (REQ-30: each iteration MUST be logged)."""

    iteration: int
    report: CompileReport
    fix: str
    compiled: bool


@dataclass
class FixLoopResult:
    """Outcome of the fix loop."""

    success: bool
    iterations: list[FixIteration] = field(default_factory=list)
    final_report: Optional[CompileReport] = None


CompileFn = Callable[[Path], CompileReport]
FixFn = Callable[[str, list[str]], str]


def run_fix_loop(
    *,
    src: str | Path,
    compile_fn: CompileFn,
    fix_fn: FixFn,
    max_fix_iterations: int,
    initial_report: CompileReport,
) -> FixLoopResult:
    """Run the bounded fix loop: fix → recompile → re-validate (REQ-30).

    Args:
        src: path to the failing ``.java`` source. The amended text returned
            by *fix_fn* is written back to this path before each recompile.
        compile_fn: compiles *src* and returns a :class:`CompileReport`.
        fix_fn: LLM-guided fixer — ``(source_text, error_lines) -> amended_text``.
        max_fix_iterations: hard bound; ``<= 0`` means no fix attempt.
        initial_report: the failing report that triggered the loop.

    Returns:
        :class:`FixLoopResult` — ``success`` when a recompile passed within
        the bound; otherwise ``success=False`` with the full iteration log and
        the final failing report (the caller raises :class:`CompileError`).
    """
    src = Path(src)
    report = initial_report
    iterations: list[FixIteration] = []

    for attempt in range(1, max_fix_iterations + 1):
        source_text = src.read_text(encoding="utf-8")
        fix = fix_fn(source_text, list(report.errors))
        if fix != source_text:
            src.write_text(fix, encoding="utf-8")
        report = compile_fn(src)
        compiled = report.ok
        iterations.append(
            FixIteration(iteration=attempt, report=report, fix=fix, compiled=compiled)
        )
        logger.info(
            "fix iteration %d: compiled=%s (%d error(s))",
            attempt,
            compiled,
            len(report.errors),
        )
        if compiled:
            return FixLoopResult(
                success=True, iterations=iterations, final_report=report
            )

    return FixLoopResult(
        success=False, iterations=iterations, final_report=report
    )
