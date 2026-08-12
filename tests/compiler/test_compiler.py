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


class TestStrategyIdCompileWiring:
    """REQ-602/603: CompilerPipeline.compile() with strategy_ids."""

    def test_compile_with_strategy_ids_returns_mapping(self, jdk_ok, make_java_source):
        """GIVEN strategy_ids=["s1","s2"] and matching sources
        WHEN compile() is called with strategy_ids
        THEN compiled_strategies contains artifacts keyed under each strategy_id.
        """
        src1 = make_java_source("Strategy1")
        src2 = make_java_source("Strategy2")
        sources = {"s1": src1, "s2": src2}

        result = CompilerPipeline.compile(
            sources,
            strategy_ids=["s1", "s2"],
            env={"QUANTLAB_JDK_HOME": str(jdk_ok)},
        )

        assert isinstance(result, dict)
        assert "s1" in result
        assert "s2" in result
        assert result["s1"].path.exists()
        assert result["s2"].path.exists()

    def test_missing_strategy_id_falls_back_to_filename(self, jdk_ok, make_java_source, caplog):
        """GIVEN a strategy_id with no explicit source mapping
        WHEN compile() runs
        THEN filename inference is used and a warning is logged.
        """
        # Create a file that matches the strategy_id via filename inference.
        inferred = make_java_source("missing")
        sources = {"s1": make_java_source("s1")}

        result = CompilerPipeline.compile(
            sources,
            strategy_ids=["s1", "missing"],
            env={"QUANTLAB_JDK_HOME": str(jdk_ok)},
        )

        assert "missing" in result
        assert result["missing"].path.exists()
        assert any("missing" in record.message for record in caplog.records)

    def test_multi_strategy_isolation(self, tmp_path, make_java_source):
        """GIVEN "s1" succeeds and "s2" fails
        WHEN compile() runs
        THEN s1 appears in compiled_strategies
        AND s2 appears in compilation_failed artifacts.
        """
        from quantlab.compiler.compiler import CompileError

        src1 = make_java_source("GoodStrategy")
        src2 = make_java_source("BadStrategy")
        sources = {"s1": src1, "s2": src2}

        # Build a fake JDK that fails only for BadStrategy.
        jdk = tmp_path / "jdk"
        bin_dir = jdk / "bin"
        bin_dir.mkdir(parents=True)
        javac = bin_dir / "javac"
        javac.write_text(
            """#!/bin/sh
set -e
classes=""
src=""
while [ $# -gt 0 ]; do
  case "$1" in
    -d) classes="$2"; shift 2 ;;
    *) src="$1"; shift ;;
  esac
done
mkdir -p "$classes"
if grep -q "BadStrategy" "$src"; then
  echo "error: cannot compile BadStrategy" >&2
  exit 1
fi
name=$(basename "$src" .java)
printf 'fake class bytes' > "$classes/$name.class"
exit 0
""",
            encoding="utf-8",
        )
        javac.chmod(javac.stat().st_mode | 0o755)

        result = CompilerPipeline.compile(
            sources,
            strategy_ids=["s1", "s2"],
            env={"QUANTLAB_JDK_HOME": str(jdk)},
            fixer=None,
            max_fix_iterations=0,
        )

        assert isinstance(result, dict)
        assert "s1" in result
        assert "s2" in result
        # s1 should be a JfxArtifact (success)
        from quantlab.compiler.jfx import JfxArtifact
        assert isinstance(result["s1"], JfxArtifact)
        # s2 should be a CompileError (failure)
        assert isinstance(result["s2"], CompileError)

    def test_partial_failure_does_not_block_success(self, tmp_path, make_java_source):
        """GIVEN strategy "s1" succeeds and "s2" fails
        WHEN compile() completes
        THEN the pipeline does not halt silently.
        """
        from quantlab.compiler.compiler import CompileError

        src1 = make_java_source("GoodStrategy")
        src2 = make_java_source("BadStrategy")
        sources = {"s1": src1, "s2": src2}

        # Build a fake JDK that fails only for BadStrategy.
        jdk = tmp_path / "jdk"
        bin_dir = jdk / "bin"
        bin_dir.mkdir(parents=True)
        javac = bin_dir / "javac"
        javac.write_text(
            """#!/bin/sh
set -e
classes=""
src=""
while [ $# -gt 0 ]; do
  case "$1" in
    -d) classes="$2"; shift 2 ;;
    *) src="$1"; shift ;;
  esac
done
mkdir -p "$classes"
if grep -q "BadStrategy" "$src"; then
  echo "error: cannot compile BadStrategy" >&2
  exit 1
fi
name=$(basename "$src" .java)
printf 'fake class bytes' > "$classes/$name.class"
exit 0
""",
            encoding="utf-8",
        )
        javac.chmod(javac.stat().st_mode | 0o755)

        # Should NOT raise — failures go into the result dict.
        result = CompilerPipeline.compile(
            sources,
            strategy_ids=["s1", "s2"],
            env={"QUANTLAB_JDK_HOME": str(jdk)},
            fixer=None,
            max_fix_iterations=0,
        )

        assert isinstance(result, dict)
        assert "s1" in result
        assert "s2" in result

    def test_empty_strategy_ids_returns_empty_dict(self, jdk_ok):
        """GIVEN no strategy_ids
        WHEN compile() runs with an empty list
        THEN an empty dict is returned.
        """
        result = CompilerPipeline.compile(
            {},
            strategy_ids=[],
            env={"QUANTLAB_JDK_HOME": str(jdk_ok)},
        )
        assert result == {}

    def test_single_strategy_id_returns_dict(self, jdk_ok, make_java_source):
        """GIVEN a single strategy_id
        WHEN compile() runs
        THEN the result is a dict with that strategy_id.
        """
        src = make_java_source("Solo")
        result = CompilerPipeline.compile(
            {"solo": src},
            strategy_ids=["solo"],
            env={"QUANTLAB_JDK_HOME": str(jdk_ok)},
        )
        assert isinstance(result, dict)
        assert "solo" in result
        from quantlab.compiler.jfx import JfxArtifact
        assert isinstance(result["solo"], JfxArtifact)

    def test_batch_mode_missing_jdk_raises_config_error(self):
        """GIVEN no JDK
        WHEN compile() runs with strategy_ids
        THEN CompilerConfigError is raised before any compile attempt.
        """
        from quantlab.compiler.compiler import CompilerConfigError

        with pytest.raises(CompilerConfigError):
            CompilerPipeline.compile(
                {},
                strategy_ids=["s1"],
                env={},
            )
