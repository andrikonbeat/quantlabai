"""Gitignore enforcement for knowledge raw corpus (REQ-KDI-01).

Verifies that files under ``knowledge/raw/`` are never tracked or staged
by git, even when present on disk.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


class TestGitignoreEnforcement:
    """Raw corpus under knowledge/raw/ must never appear in git status."""

    def test_raw_files_not_tracked(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.test"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)

        # Copy the repo .gitignore rule into the temp repo
        source_gitignore = Path("/home/ogzuz/Proyectos/QuantLab AI/.gitignore")
        (repo / ".gitignore").write_text(source_gitignore.read_text(encoding="utf-8"), encoding="utf-8")

        raw_dir = repo / "knowledge" / "raw" / "sqx" / "144.2953"
        raw_dir.mkdir(parents=True)
        (raw_dir / "licensed.json").write_text("fake", encoding="utf-8")

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "knowledge/raw/" not in result.stdout
        assert "licensed.json" not in result.stdout
