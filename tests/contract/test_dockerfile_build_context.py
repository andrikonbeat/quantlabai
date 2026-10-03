"""Dockerfile build-context contract.

The ``docker`` CI job builds the image from a *clean checkout*, so the build
can only ``COPY`` paths that git actually ships. Copying a git-ignored path
fails at solve time, before any layer runs:

    ERROR: failed to build: failed to solve: failed to compute cache key:
    failed to calculate checksum of ref ...: "/reports": not found

This happened for real: ``Dockerfile`` copied ``reports``, which is
git-ignored (``.gitignore``: ``reports/``) generated output holding zero
tracked files. The directory only ever existed on the maintainer's machine, so
every clean checkout broke the image build while local builds kept working.

These tests encode the invariant so the mistake cannot come back silently.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "Dockerfile"

_COPY_FLAGS = ("--from=", "--chown=", "--chmod=", "--link=", "--exclude=")
_FLAG_RE = re.compile(r"^--[a-z]+=")


def _git(*args: str) -> str:
    """Run git against the committed tree, so worktree state cannot skew results."""
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _parse_copy_sources(text: str) -> list[tuple[int, str]]:
    """Return ``(line_number, source)`` for every build-context COPY source.

    Skips copies that read from another build stage (``--from=``), since those
    paths come from that stage's filesystem rather than the build context.
    """
    sources: list[tuple[int, str]] = []
    lines = text.splitlines()

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped.upper().startswith("COPY "):
            i += 1
            continue

        start_line = i + 1
        # Join backslash continuations into a single logical instruction.
        parts = [lines[i].strip()]
        while parts[-1].endswith("\\") and i + 1 < len(lines):
            i += 1
            parts.append(lines[i].strip())
        statement = " ".join(p.rstrip("\\").strip() for p in parts)

        # JSON array form: COPY ["a", "b", "./dest"]
        if statement.startswith("COPY ["):
            _, _, tail = statement.partition("[")
            tokens = json.loads("[" + tail)
        else:
            tokens = statement.split()[1:]

        if any(str(tok).startswith(_COPY_FLAGS) for tok in tokens):
            i += 1
            continue

        # The final token is the destination; everything before it is a source.
        for src in tokens[:-1]:
            sources.append((start_line, str(src)))

        i += 1

    return sources


COPY_SOURCES = _parse_copy_sources(DOCKERFILE.read_text(encoding="utf-8"))


class TestDockerfileBuildContext:
    """Every COPY source must exist in a clean checkout."""

    def test_dockerfile_declares_copy_instructions(self) -> None:
        """Guard the parser itself: an empty result means it silently matched nothing."""
        assert COPY_SOURCES, "no COPY sources parsed from Dockerfile — parser is broken"

    @pytest.mark.parametrize(
        ("line", "source"), COPY_SOURCES, ids=[f"L{ln}:{s}" for ln, s in COPY_SOURCES]
    )
    def test_copy_source_is_tracked_in_git(self, line: int, source: str) -> None:
        """git must ship the path, otherwise a clean checkout cannot build."""
        tracked = _git("ls-tree", "-r", "--name-only", "HEAD", "--", source).split()
        assert tracked, (
            f"Dockerfile:{line} copies {source!r}, but git tracks no such path. "
            "A clean checkout (what CI builds) will not contain it. "
            "Create the directory with RUN mkdir -p instead, or track the files."
        )

    @pytest.mark.parametrize(
        ("line", "source"), COPY_SOURCES, ids=[f"L{ln}:{s}" for ln, s in COPY_SOURCES]
    )
    def test_copy_source_is_not_git_ignored(self, line: int, source: str) -> None:
        """A git-ignored COPY source is the exact failure mode we are guarding against."""
        result = subprocess.run(
            ["git", "check-ignore", "-q", source],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        )
        assert result.returncode != 0, (
            f"Dockerfile:{line} copies {source!r}, which is git-ignored. "
            "CI builds from a clean checkout and will fail with "
            '"failed to calculate checksum ...: not found".'
        )


class TestDockerfileHygiene:
    """The reports directory must be created, not copied."""

    def test_reports_directory_is_created_not_copied(self) -> None:
        """reports/ is generated output; the image only needs the directory to exist."""
        text = DOCKERFILE.read_text(encoding="utf-8")
        assert not re.search(r"^COPY\s+.*\breports\b", text, re.MULTILINE), (
            "Dockerfile must not COPY reports/ — it is git-ignored generated output."
        )
        assert re.search(r"^RUN\s+mkdir\s+-p\s+.*\breports\b", text, re.MULTILINE), (
            "Dockerfile should create the reports directory with RUN mkdir -p so the "
            "QUANTLAB_REPORTS_DIR default and the docker-compose bind mount both work."
        )
