"""Task 3.3 RED: bounded error-fix loop (REQ-30).

Scenario 1 "Fix loop self-corrects": a fix attempt amends the source and
recompiles; a .jfx is produced within the iteration bound.
Scenario 2 "Loop bound halts": still failing after max_fix_iterations → the
pipeline halts with a CompileError and full error history; the failing source
is not deployed (no .jfx produced).

Per-iteration logging: every iteration records its fix, errors, and outcome.
"""

from __future__ import annotations

import pytest

from quantlab.compiler.compiler import CompileError, CompilerPipeline
from quantlab.compiler.fixloop import (
    FixIteration,
    FixLoopResult,
    run_fix_loop,
)


def _fix_adds_import(source: str, errors: list[str]) -> str:
    """Fixer that cures the missing-import error."""
    if "import java.util.List;" in source:
        return source
    return source.replace("public class", "import java.util.List;\npublic class")


class TestFixLoopSelfCorrects:
    """REQ-30 scenario 1 — fix loop self-corrects within the bound."""

    def test_pipeline_self_corrects_and_packages_jfx(self, tmp_path, make_jdk, make_java_source):
        # javac fails until the source carries the missing import.
        jdk_dir = make_jdk(
            javac_script="""#!/bin/sh
set -e
classes=""
src=""
while [ $# -gt 0 ]; do
  case "$1" in
    -d) classes="$2"; shift 2 ;;
    *) src="$1"; shift ;;
  esac
done
if grep -q "import java.util.List" "$src"; then
  mkdir -p "$classes"
  name=$(basename "$src" .java)
  printf 'fake class bytes' > "$classes/$name.class"
  echo "compiled $src"
  exit 0
else
  echo "$src:3: error: cannot find symbol" >&2
  exit 1
fi
""",
        )
        src = make_java_source()

        artifact = CompilerPipeline.compile(
            src,
            env={"QUANTLAB_JDK_HOME": str(jdk_dir)},
            fixer=_fix_adds_import,
            max_fix_iterations=3,
        )

        # The amended source now contains the fix, and the .jfx was produced
        # within the bound.
        assert "import java.util.List;" in src.read_text(encoding="utf-8")
        assert artifact.path == tmp_path / "MyStrategy.jfx"
        assert artifact.path.exists()

    def test_self_correcting_loop_logs_each_iteration(self, make_jdk, make_java_source):
        jdk_dir = make_jdk(
            javac_script="""#!/bin/sh
set -e
classes=""
src=""
while [ $# -gt 0 ]; do
  case "$1" in
    -d) classes="$2"; shift 2 ;;
    *) src="$1"; shift ;;
  esac
done
if grep -q "import java.util.List" "$src"; then
  mkdir -p "$classes"
  name=$(basename "$src" .java)
  printf 'fake class bytes' > "$classes/$name.class"
  exit 0
else
  echo "error: cannot find symbol" >&2
  exit 1
fi
""",
        )
        src = make_java_source()

        with pytest.raises(CompileError) as exc_info:
            CompilerPipeline.compile(
                src,
                env={"QUANTLAB_JDK_HOME": str(jdk_dir)},
                fixer=lambda s, e: s,  # never fixes
                max_fix_iterations=2,
            )

        history = exc_info.value.history
        assert len(history) == 2
        assert [h.iteration for h in history] == [1, 2]
        assert all(h.compiled is False for h in history)
        assert all("cannot find symbol" in e for h in history for e in h.report.errors)


class TestRunFixLoopPure:
    """run_fix_loop as a pure function — compile_fn/fix_fn injected."""

    def test_success_path_logs_iterations(self, tmp_path, make_java_source):
        src = make_java_source()
        from quantlab.compiler.compiler import CompileReport

        # Success requires TWO patch markers — so the first fix attempt is
        # insufficient and the loop must run a second (failing → passing) pass.
        def compile_fn(s):
            if "// patch // patch" in s.read_text(encoding="utf-8"):
                return CompileReport(exit_code=0)
            return CompileReport(exit_code=1, stderr="x.java:1: error: boom")

        result = run_fix_loop(
            src=src,
            compile_fn=compile_fn,
            fix_fn=lambda s, e: s + "// patch ",
            max_fix_iterations=3,
            initial_report=compile_fn(src),
        )

        assert isinstance(result, FixLoopResult)
        assert result.success is True
        assert len(result.iterations) == 2
        first, second = result.iterations
        assert isinstance(first, FixIteration)
        assert first.iteration == 1
        assert first.compiled is False
        assert first.report.exit_code == 1
        assert second.iteration == 2
        assert second.compiled is True
        assert result.final_report is not None
        assert result.final_report.ok is True

    def test_zero_bound_never_fixes(self, tmp_path, make_java_source):
        src = make_java_source()
        initial = None

        from quantlab.compiler.compiler import CompileReport

        def compile_fn(s):
            return CompileReport(exit_code=1, stderr="x.java:1: error: boom")

        result = run_fix_loop(
            src=src,
            compile_fn=compile_fn,
            fix_fn=lambda s, e: s + "\n// patched",
            max_fix_iterations=0,
            initial_report=compile_fn(src),
        )

        assert result.success is False
        assert result.iterations == []
        assert result.final_report is not None
        assert result.final_report.ok is False

    def test_failing_fix_fn_still_recompiles_each_iteration(
        self, tmp_path, make_java_source
    ):
        """The fixer's output is written back before EVERY recompile."""
        src = make_java_source()
        from quantlab.compiler.compiler import CompileReport

        reads = []

        def compile_fn(s):
            reads.append(s.read_text(encoding="utf-8"))
            return CompileReport(exit_code=1, stderr="x.java:1: error: boom")

        run_fix_loop(
            src=src,
            compile_fn=compile_fn,
            fix_fn=lambda s, e: s + "\n// patch",
            max_fix_iterations=2,
            initial_report=compile_fn(src),
        )

        # reads[0] is the initial report probe; iterations 1..2 recompile the
        # amended source, so both subsequent reads carry the patch.
        assert len(reads) == 3
        assert "// patch" in reads[1]
        assert "// patch" in reads[2]


class TestLoopBoundHalts:
    """REQ-30 scenario 2 — bound exhausted → CompileError + full history."""

    def test_bound_exhausted_raises_compile_error(self, tmp_path, jdk_fail, make_java_source):
        src = make_java_source()

        with pytest.raises(CompileError) as exc_info:
            CompilerPipeline.compile(
                src,
                env={"QUANTLAB_JDK_HOME": str(jdk_fail)},
                fixer=lambda s, e: s,  # never fixes
                max_fix_iterations=3,
            )

        assert "3" in str(exc_info.value)  # bound named in the error
        assert len(exc_info.value.history) == 3  # full error history
        assert exc_info.value.report is not None
        assert exc_info.value.report.exit_code == 1

    def test_bound_halt_does_not_deploy(self, tmp_path, jdk_fail, make_java_source):
        src = make_java_source()

        with pytest.raises(CompileError):
            CompilerPipeline.compile(
                src,
                env={"QUANTLAB_JDK_HOME": str(jdk_fail)},
                fixer=lambda s, e: s,
                max_fix_iterations=3,
            )

        # Failing source is never packaged → no .jfx (not deployed, REQ-30 s2).
        assert list(tmp_path.rglob("*.jfx")) == []

    def test_history_entries_carry_error_lines(self, tmp_path, make_java_source):
        src = make_java_source()
        from quantlab.compiler.compiler import CompileReport

        def compile_fn(s):
            return CompileReport(
                exit_code=1, stderr="Broken.java:3: error: cannot find symbol"
            )

        result = run_fix_loop(
            src=src,
            compile_fn=compile_fn,
            fix_fn=lambda s, e: s,
            max_fix_iterations=2,
            initial_report=compile_fn(src),
        )

        assert result.success is False
        assert len(result.iterations) == 2
        for iteration in result.iterations:
            assert iteration.report.errors == ["Broken.java:3: error: cannot find symbol"]
