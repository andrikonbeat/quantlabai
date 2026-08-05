"""Shared fixtures for the compiler-pipeline test suite (PR-3, REQ-29/30/39).

The environment has NO JDK installed (verified: no ``java``, no ``javac``,
no ``QUANTLAB_JDK_HOME``), so every test SIMULATES javac with fake JDK trees:
a real ``jdk/bin/javac`` shell script that behaves like javac for the
``-d <classes> <src>`` invocation shape. Tests never depend on a JDK being
present — the missing-JDK and non-executable cases are exercised explicitly.

Factory fixtures (not module imports — ``tests/`` is not a package, so
cross-module ``from tests.compiler...`` imports fail; doubles live in conftest
per the PR-2 substrate convention).
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

_DEFAULT_BODIES = {
    # Mimics `javac -d <classes> <src>`: creates the output dir and writes a
    # fake class file derived from the source basename, then exits 0.
    "ok": """#!/bin/sh
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
name=$(basename "$src" .java)
printf 'fake class bytes' > "$classes/$name.class"
echo "compiled $src"
exit 0
""",
    # Fails like javac on a missing symbol, writing nothing.
    "fail": """#!/bin/sh
echo "MyStrategy.java:3: error: cannot find symbol" >&2
exit 1
""",
}


@pytest.fixture
def make_jdk(tmp_path):
    """Factory: create a fake JDK root at ``<tmp_path>/jdk``.

    ``javac_script="ok"`` → compiles any source (writes ``{Name}.class``);
    ``"fail"`` → always exits 1 with a parseable error line; ``"missing"`` →
    no javac binary at all; ``None`` → javac exists but is NOT executable;
    any other string is used verbatim as the script body.
    """

    def _make(javac_script: str | None = "ok") -> Path:
        jdk = tmp_path / "jdk"
        bin_dir = jdk / "bin"
        bin_dir.mkdir(parents=True)
        javac = bin_dir / "javac"

        if javac_script == "missing":
            return jdk

        if javac_script is None:
            # Present but NOT executable: an empty file without +x.
            javac.touch()
            return jdk

        body = (
            javac_script
            if javac_script not in ("ok", "fail")
            else _DEFAULT_BODIES[javac_script]
        )
        javac.write_text(body, encoding="utf-8")
        javac.chmod(javac.stat().st_mode | stat.S_IEXEC)
        return jdk

    return _make


@pytest.fixture
def jdk_ok(make_jdk) -> Path:
    """Fake JDK whose javac always compiles successfully."""
    return make_jdk("ok")


@pytest.fixture
def jdk_fail(make_jdk) -> Path:
    """Fake JDK whose javac always fails with a parseable error line."""
    return make_jdk("fail")


@pytest.fixture
def make_java_source(tmp_path):
    """Factory: write a minimal Java source file and return its path."""

    def _make(name: str = "MyStrategy") -> Path:
        src = tmp_path / f"{name}.java"
        src.write_text(
            f"public class {name} {{\n"
            "    public static void main(String[] args) {}\n"
            "}\n",
            encoding="utf-8",
        )
        return src

    return _make
