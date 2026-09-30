#!/usr/bin/env python3
"""Shared deterministic, idempotent sync driver for repo-canonical artifacts.

Both ``sync_prompts.py`` and ``sync_skills.py`` instantiate ``SyncDriver``
with their own repo/live dirs, managed-name callable, and retired-name tuple.
The driver guarantees byte-equality, idempotency, and active retirement of
stale live copies.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def _read_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


class SyncDriver:
    """Deterministic, idempotent sync from a repo dir to a live dir.

    Args:
        repo_dir: Source of truth directory.
        live_dir: Target directory that mirrors the repo.
        managed_names: Callable ``(repo_dir) -> list[str]`` returning the
            sorted allowlist of filenames that must stay byte-equal.
        retired_names: Filenames that must be removed from ``live_dir`` if
            present; they are versioned in repo only.
    """

    def __init__(
        self,
        repo_dir: Path,
        live_dir: Path,
        managed_names: callable,  # Callable[[Path], list[str]]
        retired_names: tuple[str, ...],
    ) -> None:
        self.repo_dir = repo_dir
        self.live_dir = live_dir
        self.managed_names = managed_names
        self.retired_names = retired_names

    def sync(self, *, dry_run: bool = False) -> list[str]:
        """Copy managed artifacts from repo to live, byte-for-byte.

        Returns the sorted list of managed names that were (or, with
        ``dry_run=True``, would be) written. Idempotent: a name whose live
        bytes already equal the repo bytes is skipped. Retired files are
        actively removed from live before managed copies are refreshed.
        """
        self.live_dir.mkdir(parents=True, exist_ok=True)
        changed: list[str] = []

        # Active retirement: remove stale live copies of retired artifacts.
        retired_removed = self._cleanup_retired(dry_run=dry_run)
        changed.extend(retired_removed)

        managed = self.managed_names(self.repo_dir)
        for name in managed:
            src = self.repo_dir / name
            dst = self.live_dir / name
            if not src.is_file():
                continue  # allowlist entry absent in repo: nothing to sync
            if _read_bytes(dst) == src.read_bytes():
                continue  # identical bytes -> no-op
            changed.append(name)
            if not dry_run:
                shutil.copyfile(src, dst)

        return sorted(changed)

    def check(self) -> list[str]:
        """Return sorted managed names whose live copy differs from the repo.

        Empty list means parity holds byte-for-byte.
        """
        drifted: list[str] = []
        for name in self.managed_names(self.repo_dir):
            src = self.repo_dir / name
            dst = self.live_dir / name
            if not src.is_file():
                continue
            if _read_bytes(dst) != src.read_bytes():
                drifted.append(name)
        return sorted(drifted)

    def _cleanup_retired(self, *, dry_run: bool = False) -> list[str]:
        """Remove retired files from the live directory.

        Returns the sorted list of retired names that were (or, with
        ``dry_run=True``, would be) removed.
        """
        removed: list[str] = []
        for name in self.retired_names:
            target = self.live_dir / name
            if target.is_file():
                removed.append(name)
                if not dry_run:
                    target.unlink()
        return sorted(removed)
