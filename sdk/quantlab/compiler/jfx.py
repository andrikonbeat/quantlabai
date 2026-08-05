"""Packaging compiled classes into a ``.jfx`` archive (REQ-29).

Layout: JAR-with-classes — the ``.jfx`` is a ZIP whose entries are the
compiled ``.class`` files, preserving their package-relative paths. This
layout is provisional pending JForex 4 verification (design open question:
"JAR-with-classes vs SQX-native layout").
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from quantlab.compiler.errors import CompileError


@dataclass
class JfxArtifact:
    """A packaged ``.jfx`` archive (REQ-29)."""

    path: Path
    source: Path
    class_name: str


def package_classes(
    classes_dir: str | Path,
    source: str | Path,
    *,
    class_name: Optional[str] = None,
    output: Optional[str | Path] = None,
) -> JfxArtifact:
    """Package compiled classes into a ``.jfx`` ZIP archive.

    Default output is ``{ClassName}.jfx`` next to *source* (REQ-29 scenario 1:
    "a .jfx archive is produced next to the source").

    Raises:
        CompileError: no compiled ``.class`` files found — fail-closed, no
            partial ``.jfx`` is produced.
    """
    classes_dir = Path(classes_dir)
    source = Path(source)
    class_name = class_name or source.stem
    output = Path(output) if output is not None else source.with_suffix(".jfx")

    class_files = sorted(p for p in classes_dir.rglob("*.class") if p.is_file())
    if not class_files:
        raise CompileError(
            f"no compiled classes found under {classes_dir} — cannot package"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for class_file in class_files:
            zf.write(class_file, class_file.relative_to(classes_dir).as_posix())

    return JfxArtifact(path=output, source=source, class_name=class_name)
