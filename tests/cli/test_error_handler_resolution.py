"""Every ``except`` handler in the CLI must name a resolvable exception.

An ``except`` clause evaluates its expression at the moment an exception
propagates to it. If the name is not bound in the module, Python raises
``NameError`` *while handling the original exception* — and because an
exception raised inside one ``except`` clause is not caught by its siblings,
the ``NameError`` escapes the whole handler chain. The user loses the real
diagnostic and gets an unrelated crash traceback instead.

That is not hypothetical: ``cmd_jforex_deploy`` caught
``JForexConnectionError`` without importing it, so the single most common
deploy failure — the SQX daemon being unreachable — reported

    NameError: name 'JForexConnectionError' is not defined

instead of "Connection failed: Cannot connect to SQX server at host:port".
Ruff's F821 flags it, but the lint job is still non-blocking, so the defect
shipped. This test is the executable guard for that whole class of bug.
"""

from __future__ import annotations

import ast
import builtins
from pathlib import Path

import pytest

import quantlab.cli.main as cli_main

CLI_MAIN = Path(cli_main.__file__)


def _handler_exception_names(tree: ast.Module) -> list[tuple[int, str]]:
    """Collect ``(lineno, name)`` for every bare-Name ``except`` handler."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        exc = node.type
        if isinstance(exc, ast.Name):
            found.append((exc.lineno, exc.id))
    return found


HANDLERS = _handler_exception_names(ast.parse(CLI_MAIN.read_text(encoding="utf-8")))


class TestExceptHandlersResolve:
    """An except clause must reference a name that actually exists."""

    def test_handlers_were_discovered(self) -> None:
        """Guard the collector: an empty result means the scan silently matched nothing."""
        assert len(HANDLERS) >= 5, f"only found {len(HANDLERS)} except handlers — collector is broken"

    @pytest.mark.parametrize(
        ("lineno", "name"),
        HANDLERS,
        ids=[f"L{ln}:{name}" for ln, name in HANDLERS],
    )
    def test_handler_name_resolves(self, lineno: int, name: str) -> None:
        """The name must be a builtin or bound in the module namespace."""
        assert hasattr(cli_main, name) or hasattr(builtins, name), (
            f"{CLI_MAIN.name}:{lineno} catches {name!r}, but that name is never imported "
            f"or defined. When this clause is reached Python raises NameError instead "
            f"of handling the original exception, so the real error is lost."
        )