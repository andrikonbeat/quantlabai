"""Compiler pipeline (REQ-29/30) — PR-3.

Public surface:
- ``CompilerPipeline.compile(src) -> JfxArtifact`` (design contract)
- ``resolve_javac`` / ``is_compiler_enabled`` — fail-closed JDK selectors
- ``run_fix_loop`` — bounded error-fix loop (REQ-30)
- errors: :class:`CompilerError` / :class:`CompilerConfigError` /
  :class:`CompileError`
"""

from quantlab.compiler.compiler import (
    DEFAULT_MAX_FIX_ITERATIONS,
    JDK_ENV_VAR,
    CompileReport,
    CompilerPipeline,
    is_compiler_enabled,
    resolve_javac,
)
from quantlab.compiler.errors import (
    CompileError,
    CompilerConfigError,
    CompilerError,
)
from quantlab.compiler.fixloop import FixIteration, FixLoopResult, run_fix_loop
from quantlab.compiler.jfx import JfxArtifact, package_classes

__all__ = [
    "DEFAULT_MAX_FIX_ITERATIONS",
    "JDK_ENV_VAR",
    "CompileError",
    "CompileReport",
    "CompilerConfigError",
    "CompilerError",
    "CompilerPipeline",
    "FixIteration",
    "FixLoopResult",
    "JfxArtifact",
    "is_compiler_enabled",
    "package_classes",
    "resolve_javac",
    "run_fix_loop",
]
