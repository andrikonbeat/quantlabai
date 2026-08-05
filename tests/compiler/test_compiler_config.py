"""Task 3.1 RED: missing JDK → CompilerConfigError, no partial .jfx; non-exec
javac (REQ-29). Threat-matrix row (subprocess: javac, external JDK):
resolve ``{QUANTLAB_JDK_HOME}/bin/javac``; fail-closed CompilerConfigError if
absent; NEVER fall back to ``j64/`` (JRE). One RED per selector.

These tests reference production code that does not exist yet — the whole
``quantlab.compiler`` package is the RED target.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from quantlab.compiler.compiler import (
    CompilerConfigError,
    CompilerPipeline,
    resolve_javac,
)


class TestMissingJdk:
    """Selector 1: no external JDK configured → fail closed before javac."""

    def test_no_jdk_env_raises_config_error(self, tmp_path, make_java_source):
        src = make_java_source()

        with pytest.raises(CompilerConfigError) as exc_info:
            CompilerPipeline.compile(src, env={})

        message = str(exc_info.value)
        assert "javac" in message.lower() or "jdk" in message.lower()
        assert "QUANTLAB_JDK_HOME" in message

    def test_nonexistent_jdk_home_raises_config_error(
        self, tmp_path, make_java_source
    ):
        src = make_java_source()
        missing = tmp_path / "does-not-exist"

        with pytest.raises(CompilerConfigError):
            CompilerPipeline.compile(
                src, env={"QUANTLAB_JDK_HOME": str(missing)}
            )

    def test_missing_jdk_produces_no_partial_jfx(self, tmp_path, make_java_source):
        src = make_java_source()

        with pytest.raises(CompilerConfigError):
            CompilerPipeline.compile(src, env={})

        artifacts = list(tmp_path.rglob("*.jfx"))
        classes = list(tmp_path.rglob("*.class"))
        assert artifacts == []  # no partial .jfx
        assert classes == []  # javac never ran

    def test_missing_jdk_never_falls_back_to_jre(
        self, tmp_path, make_java_source
    ):
        """AD-5: ``j64/`` is a JRE (no javac) — must NOT be used as fallback."""
        src = make_java_source()
        jre_root = tmp_path / "j64"
        (jre_root / "bin").mkdir(parents=True)  # JRE layout, no javac anywhere

        with pytest.raises(CompilerConfigError):
            CompilerPipeline.compile(
                src, env={"QUANTLAB_JDK_HOME": str(jre_root)}
            )

        assert list(tmp_path.rglob("*.jfx")) == []


class TestNonExecutableJavac:
    """Selector 2: javac present but not executable → fail closed."""

    def test_non_executable_javac_raises_config_error(
        self, tmp_path, make_java_source, make_jdk
    ):
        src = make_java_source()
        jdk = make_jdk(javac_script=None)  # file exists, no +x

        with pytest.raises(CompilerConfigError) as exc_info:
            CompilerPipeline.compile(src, env={"QUANTLAB_JDK_HOME": str(jdk)})

        assert "QUANTLAB_JDK_HOME" in str(exc_info.value)

    def test_non_executable_javac_no_artifacts(
        self, tmp_path, make_java_source, make_jdk
    ):
        src = make_java_source()
        jdk = make_jdk(javac_script=None)

        with pytest.raises(CompilerConfigError):
            CompilerPipeline.compile(src, env={"QUANTLAB_JDK_HOME": str(jdk)})

        assert list(tmp_path.rglob("*.jfx")) == []
        assert list(tmp_path.rglob("*.class")) == []


class TestResolveJavac:
    """Selector-level unit tests for the JDK resolver."""

    def test_resolves_executable_javac(self, jdk_ok):
        resolved = resolve_javac(jdk_home=jdk_ok)

        assert resolved is not None
        assert resolved.name == "javac"
        assert Path(resolved).is_absolute()
        assert os.access(resolved, os.X_OK)

    def test_returns_none_when_jdk_missing(self, tmp_path):
        assert resolve_javac(jdk_home=tmp_path / "nope") is None

    def test_returns_none_when_javac_not_executable(self, make_jdk):
        jdk = make_jdk(javac_script=None)
        assert resolve_javac(jdk_home=jdk) is None

    def test_reads_jdk_from_env(self, jdk_ok):
        resolved = resolve_javac(
            jdk_home=None, env={"QUANTLAB_JDK_HOME": str(jdk_ok)}
        )
        assert resolved is not None
        assert resolved == (jdk_ok / "bin" / "javac").resolve()

    def test_no_env_no_home_returns_none(self):
        assert resolve_javac(jdk_home=None, env={}) is None
