"""Task 3.2 spec scenarios: ``.jfx`` packaging layout (REQ-29).

The packaged archive is a ZIP of the compiled ``.class`` files (JAR-with-classes
layout), named ``{ClassName}.jfx`` next to the source. Layout is provisional
pending JForex 4 verification (design open question).
"""

from __future__ import annotations

from zipfile import ZipFile

import pytest

from quantlab.compiler.errors import CompilerError
from quantlab.compiler.jfx import JfxArtifact, package_classes


class TestPackageClasses:
    def test_creates_jfx_zip_next_to_source(self, tmp_path, make_java_source):
        src = make_java_source(name="Alpha")
        classes = tmp_path / "classes"
        classes.mkdir()
        (classes / "Alpha.class").write_bytes(b"\xca\xfe\xba\xbe")

        artifact = package_classes(classes, src)

        assert isinstance(artifact, JfxArtifact)
        assert artifact.path == tmp_path / "Alpha.jfx"
        assert artifact.path.exists()

    def test_zip_contains_class_files_preserving_paths(
        self, tmp_path, make_java_source
    ):
        src = make_java_source(name="Beta")
        classes = tmp_path / "classes"
        nested = classes / "jforex" / "beta"
        nested.mkdir(parents=True)
        (nested / "Beta.class").write_bytes(b"c1")
        (classes / "Beta$Inner.class").write_bytes(b"c2")

        artifact = package_classes(classes, src)

        with ZipFile(artifact.path) as zf:
            names = zf.namelist()
        assert "jforex/beta/Beta.class" in names
        assert "Beta$Inner.class" in names

    def test_package_accepts_explicit_output_path(self, tmp_path, make_java_source):
        src = make_java_source(name="Gamma")
        classes = tmp_path / "classes"
        classes.mkdir()
        (classes / "Gamma.class").write_bytes(b"c")
        out = tmp_path / "custom" / "Gamma.jfx"

        artifact = package_classes(classes, src, output=out)

        assert artifact.path == out
        assert out.exists()

    def test_no_classes_raises_fail_closed(self, tmp_path, make_java_source):
        src = make_java_source(name="Delta")
        empty = tmp_path / "classes"
        empty.mkdir()

        with pytest.raises(CompilerError):
            package_classes(empty, src)

        assert list(tmp_path.rglob("*.jfx")) == []

    def test_missing_classes_dir_raises_fail_closed(
        self, tmp_path, make_java_source
    ):
        src = make_java_source(name="Epsilon")

        with pytest.raises(CompilerError):
            package_classes(tmp_path / "no-such-dir", src)

        assert list(tmp_path.rglob("*.jfx")) == []
