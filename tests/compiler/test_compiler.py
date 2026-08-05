"""Task 3.2 spec scenarios: javac compile + structured error report (REQ-29).

Scenario 1 "Export compiles and packages": javac from the external JDK
compiles the source; a ``.jfx`` archive is produced next to the source; compile
errors return a structured error report.
"""

from __future__ import annotations

from zipfile import ZipFile

import pytest

from quantlab.compiler.compiler import (
    CompileError,
    CompilerPipeline,
    JfxArtifact,
)


class TestHappyCompile:
    """REQ-29 scenario 1 — successful export compiles and packages."""

    def test_compile_produces_jfx_next_to_source(self, tmp_path, jdk_ok, make_java_source):
        src = make_java_source()

        artifact = CompilerPipeline.compile(
            src, env={"QUANTLAB_JDK_HOME": str(jdk_ok)}
        )

        assert isinstance(artifact, JfxArtifact)
        assert artifact.path == tmp_path / "MyStrategy.jfx"
        assert artifact.path.exists()
        assert artifact.source == src
        assert artifact.class_name == "MyStrategy"

    def test_jfx_contains_compiled_class(self, jdk_ok, make_java_source):
        src = make_java_source()

        artifact = CompilerPipeline.compile(
            src, env={"QUANTLAB_JDK_HOME": str(jdk_ok)}
        )

        with ZipFile(artifact.path) as zf:
            names = zf.namelist()
        assert "MyStrategy.class" in names

    def test_compile_accepts_default_env(self, jdk_ok, make_java_source, monkeypatch):
        src = make_java_source()
        monkeypatch.setenv("QUANTLAB_JDK_HOME", str(jdk_ok))

        artifact = CompilerPipeline.compile(src)  # env from os.environ

        assert artifact.path.exists()

    def test_warning_output_is_not_a_failure(self, make_java_source, make_jdk):
        """javac warnings (non-'error:' lines) must not flip the report to
        failed, and a successful compile still packages."""
        src = make_java_source()
        jdk_dir = make_jdk(
            javac_script="""#!/bin/sh
set -e
out=""
while [ $# -gt 0 ]; do
  case "$1" in
    -d) out="$2"; shift 2 ;;
    *) src="$1"; shift ;;
  esac
done
mkdir -p "$out"
echo "Note: Some input files use unchecked or unsafe operations."
echo "Note: Recompile with -Xlint:unchecked for details."
name=$(basename "$src" .java)
printf 'fake class bytes' > "$out/$name.class"
exit 0
""",
        )

        artifact = CompilerPipeline.compile(
            src, env={"QUANTLAB_JDK_HOME": str(jdk_dir)}
        )

        assert artifact.path.exists()


class TestCompileErrors:
    """REQ-29 scenario 1 — compile errors return a structured error report."""

    def test_compile_error_raises_compile_error_with_report(
        self, jdk_fail, make_java_source
    ):
        src = make_java_source()

        with pytest.raises(CompileError) as exc_info:
            CompilerPipeline.compile(
                src, env={"QUANTLAB_JDK_HOME": str(jdk_fail)}, fixer=None
            )

        report = exc_info.value.report
        assert report is not None
        assert report.exit_code == 1
        assert "cannot find symbol" in report.stderr
        assert any("cannot find symbol" in e for e in report.errors)

    def test_compile_failure_produces_no_jfx(self, tmp_path, jdk_fail, make_java_source):
        src = make_java_source()

        with pytest.raises(CompileError):
            CompilerPipeline.compile(
                src, env={"QUANTLAB_JDK_HOME": str(jdk_fail)}, fixer=None
            )

        assert list(tmp_path.rglob("*.jfx")) == []

    def test_error_report_parses_only_error_lines(self):
        """Structured parsing: warning/note lines never count as errors."""
        from quantlab.compiler.compiler import CompileReport

        report = CompileReport(
            exit_code=1,
            stderr=(
                "Note: uses unchecked operations.\n"
                "Broken.java:5: error: cannot find symbol\n"
                "Broken.java:9: error: ';' expected\n"
            ),
        )

        assert len(report.errors) == 2
        assert all("error:" in e for e in report.errors)

    def test_zero_exit_is_ok(self):
        from quantlab.compiler.compiler import CompileReport

        assert CompileReport(exit_code=0).ok is True
        assert CompileReport(exit_code=1).ok is False
