"""Compiler pipeline errors (REQ-29/30) — typed, fail-closed.

Mirrors the ``phase4/errors.py`` convention: a leaf module with no imports
from sibling compiler modules, so ``fixloop.py`` and ``jfx.py`` can depend on
it without cycles.
"""

from __future__ import annotations

from typing import Any, Optional


class CompilerError(Exception):
    """Base error for the compiler pipeline (REQ-29/30)."""


class CompilerConfigError(CompilerError):
    """Fail-closed configuration error: external JDK/javac missing or
    non-executable (REQ-29 scenario 2, design AD-5).

    Raised BEFORE javac runs; no partial ``.jfx`` is ever produced.
    """


class CompileError(CompilerError):
    """Compilation failed — with a structured error report (REQ-29 s1) or
    after the fix-loop bound with full history (REQ-30 s2).

    Attributes:
        report: the final failing :class:`CompileReport`.
        history: per-iteration ``FixIteration`` records when a fix loop ran.
    """

    def __init__(
        self,
        message: str,
        *,
        report: Any = None,
        history: Optional[list] = None,
    ):
        super().__init__(message)
        self.message = message
        self.report = report
        self.history = list(history) if history else []

    def __str__(self) -> str:
        if self.report is not None and getattr(self.report, "errors", None):
            detail = "; ".join(self.report.errors)
            return f"{self.message}: {detail}"
        return self.message
