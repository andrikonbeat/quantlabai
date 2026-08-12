"""Task 3.4 RED: jforex_deploy ``.jfx`` routing (REQ-39).

Scenario 1 "Export then compile to .jfx": the deploy path routes exported
``.java`` sources through the compiler pipeline (REQ-29) and produces a
``.jfx``.
Scenario 2 "Compile failure blocks deploy": the fix loop (REQ-30) exhausts its
bound → deployment is blocked with the compile error; no JAR is produced.

Rollback boundary: ``QUANTLAB_COMPILER=0`` keeps the ``.java``-only path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantlab.compiler import JfxArtifact
from quantlab.compiler.errors import CompilerConfigError, CompileError
from quantlab.phase4.jforex_deploy import JForexDeployer


class _StubClient:
    """AsyncSQXClient stand-in: returns fixed Java source for any strategy."""

    def __init__(self, source: str = "public class MyStrategy {}\n"):
        self.source = source

    async def export_sourcecode(self, strategy_id: str) -> str:
        return self.source

    async def close(self) -> None:
        pass


class TestCompileFailureBlocksDeploy:
    """REQ-39 scenario 2 — compile failure blocks deploy, no JAR."""

    async def test_bound_exhausted_blocks_deploy(
        self, tmp_path, jdk_fail, make_java_source
    ):
        deployer = JForexDeployer(_StubClient())
        java_path = await deployer.export_strategy("strat-1", tmp_path)

        with pytest.raises(CompileError):
            deployer.compile_strategy(
                java_path,
                env={"QUANTLAB_JDK_HOME": str(jdk_fail)},
                fixer=lambda s, e: s,  # never fixes
                max_fix_iterations=2,
            )

        # Deploy blocked: no .jfx, no JAR produced (REQ-39 s2).
        assert list(tmp_path.rglob("*.jfx")) == []
        assert list(tmp_path.rglob("*.jar")) == []
        assert java_path.exists()  # exported source is retained for inspection

    async def test_missing_jdk_blocks_deploy_fail_closed(
        self, tmp_path, make_java_source
    ):
        deployer = JForexDeployer(_StubClient())
        java_path = await deployer.export_strategy("strat-1", tmp_path)

        with pytest.raises(CompilerConfigError):
            deployer.compile_strategy(java_path, env={})

        assert list(tmp_path.rglob("*.jfx")) == []

    async def test_compile_error_carries_structured_report(
        self, tmp_path, jdk_fail
    ):
        deployer = JForexDeployer(_StubClient())
        java_path = await deployer.export_strategy("strat-1", tmp_path)

        with pytest.raises(CompileError) as exc_info:
            deployer.compile_strategy(
                java_path,
                env={"QUANTLAB_JDK_HOME": str(jdk_fail)},
                fixer=None,
            )

        assert exc_info.value.report is not None
        assert exc_info.value.report.exit_code == 1
        assert any("cannot find symbol" in e for e in exc_info.value.report.errors)


class TestExportRoutesToJfx:
    """REQ-39 scenario 1 — export then compile to .jfx."""

    async def test_export_and_compile_produces_jfx(self, tmp_path, jdk_ok):
        deployer = JForexDeployer(_StubClient())

        artifact = await deployer.export_and_compile(
            "strat-1", tmp_path, env={"QUANTLAB_JDK_HOME": str(jdk_ok)}
        )

        assert isinstance(artifact, JfxArtifact)
        # export_strategy names the file from strategy_id ("strat-1" → "strat_1");
        # the .jfx inherits that name next to the source (REQ-29 s1).
        assert artifact.class_name == "strat_1"
        assert artifact.path == tmp_path / "strat_1.jfx"
        assert artifact.path.exists()

    async def test_compile_strategy_accepts_exported_java(
        self, tmp_path, jdk_ok
    ):
        deployer = JForexDeployer(_StubClient())
        java_path = await deployer.export_strategy("strat-1", tmp_path)

        artifact = deployer.compile_strategy(
            java_path, env={"QUANTLAB_JDK_HOME": str(jdk_ok)}
        )

        assert isinstance(artifact, JfxArtifact)
        assert artifact.source == java_path
        assert artifact.path.exists()

    async def test_export_name_controls_class_and_jfx_name(
        self, tmp_path, jdk_ok
    ):
        deployer = JForexDeployer(_StubClient())

        artifact = await deployer.export_and_compile(
            "strat-1",
            tmp_path,
            strategy_name="AlphaStrategy",
            env={"QUANTLAB_JDK_HOME": str(jdk_ok)},
        )

        assert artifact.class_name == "AlphaStrategy"
        assert artifact.path == tmp_path / "AlphaStrategy.jfx"

    async def test_fix_loop_routes_through_deploy(self, tmp_path, make_jdk):
        """Self-correcting fixer + failing-first javac → deploy succeeds."""
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
        deployer = JForexDeployer(_StubClient())

        artifact = await deployer.export_and_compile(
            "strat-1",
            tmp_path,
            env={"QUANTLAB_JDK_HOME": str(jdk_dir)},
            fixer=lambda s, e: (
                "import java.util.List;\n" + s
                if "import java.util.List;" not in s
                else s
            ),
            max_fix_iterations=3,
        )

        assert artifact.path.exists()


class TestCompilerRollbackFlag:
    """QUANTLAB_COMPILER=0 keeps the .java-only deploy path."""

    async def test_flag_off_returns_java_path_no_jfx(self, tmp_path, jdk_ok):
        deployer = JForexDeployer(_StubClient())
        java_path = await deployer.export_strategy("strat-1", tmp_path)

        result = deployer.compile_strategy(
            java_path,
            env={
                "QUANTLAB_COMPILER": "0",
                "QUANTLAB_JDK_HOME": str(jdk_ok),
            },
        )

        assert result == java_path
        assert list(tmp_path.rglob("*.jfx")) == []


class TestExportSourcecodeWiring:
    """REQ-601/39: export_and_compile chains export_sourcecode then compile."""

    async def test_export_and_compile_calls_export_sourcecode_first(
        self, tmp_path, jdk_ok
    ):
        """GIVEN JForexDeployer with a client that tracks calls
        WHEN export_and_compile() is called
        THEN export_sourcecode is called with the strategy_id before compile.
        """
        from unittest.mock import AsyncMock, MagicMock

        from quantlab.phase4.http_client import AsyncSQXClient

        mock_client = MagicMock(spec=AsyncSQXClient)
        mock_client.export_sourcecode = AsyncMock(
            return_value="public class WiredStrategy {}\n"
        )

        deployer = JForexDeployer(mock_client)
        artifact = await deployer.export_and_compile(
            "wired-1", tmp_path, env={"QUANTLAB_JDK_HOME": str(jdk_ok)}
        )

        mock_client.export_sourcecode.assert_awaited_once_with("wired-1")
        assert isinstance(artifact, JfxArtifact)

    async def test_dry_run_export_uses_client_export_sourcecode(self):
        """GIVEN JForexDeployer with a client that tracks calls
        WHEN dry_run_export() is called
        THEN the client's export_sourcecode is called with the strategy_id.
        """
        from unittest.mock import AsyncMock, MagicMock

        from quantlab.phase4.http_client import AsyncSQXClient

        mock_client = MagicMock(spec=AsyncSQXClient)
        mock_client.export_sourcecode = AsyncMock(
            return_value="public class DryStrategy {}\n"
        )

        deployer = JForexDeployer(mock_client)
        source = await deployer.dry_run_export("dry-1")

        mock_client.export_sourcecode.assert_awaited_once_with("dry-1")
        assert "DryStrategy" in source
