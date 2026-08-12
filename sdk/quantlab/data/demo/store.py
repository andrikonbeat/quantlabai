"""DemoWindowStore — atomic YAML persistence for demo window state.

Writes ``window.yaml`` under ``<root>/structured/demo/<campaign_id>/`` using
an atomic temp-file-then-rename strategy so a partial write never corrupts
state. On load, the YAML is validated against the expected schema; any
corruption raises :class:`StateCorruptionError` so the pipeline fails closed.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

import yaml


class StateCorruptionError(Exception):
    """Raised when persisted demo window state cannot be loaded or validated."""


class DemoWindowStore:
    """Atomic reader/writer for ``window.yaml`` under Knowledge Lake.

    Attributes:
        root: Knowledge Lake root directory.
        campaign_id: Campaign identifier used in the persist path.
    """

    PERSIST_PATH_TEMPLATE = "{root}/structured/demo/{campaign_id}/window.yaml"

    def __init__(self, root: str | Path, campaign_id: str) -> None:
        self.root = Path(root)
        self.campaign_id = campaign_id
        self._path = Path(
            self.PERSIST_PATH_TEMPLATE.format(
                root=self.root, campaign_id=self.campaign_id
            )
        )

    def _ensure_parent(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def persist(self, window: dict[str, object]) -> None:
        """Write *window* atomically to ``window.yaml``.

        A temp file is written in the same directory and then renamed over
        the target path. On POSIX this is atomic; on Windows the rename
        replaces the target if it exists.
        """
        self._ensure_parent()
        parent = self._path.parent
        fd, tmp = tempfile.mkstemp(dir=parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                yaml.safe_dump(window, fh, default_flow_style=False)
            os.replace(tmp, str(self._path))
        except Exception:
            # Clean up the temp file if anything goes wrong.
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise

    def load(self, campaign_id: str) -> dict[str, object]:
        """Load and validate the persisted window for *campaign_id*.

        Raises:
            StateCorruptionError: If the file is missing, unreadable, or
                fails schema validation.
        """
        path = Path(
            self.PERSIST_PATH_TEMPLATE.format(
                root=self.root, campaign_id=campaign_id
            )
        )
        if not path.exists():
            raise StateCorruptionError(
                f"Demo window state missing for campaign {campaign_id}: {path}"
            )
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise StateCorruptionError(
                f"Demo window state corrupt for campaign {campaign_id}: {exc}"
            ) from exc

        if not isinstance(raw, dict):
            raise StateCorruptionError(
                f"Demo window state is not a mapping for campaign {campaign_id}"
            )

        required = {"started_at", "expires_at", "renewal_count"}
        missing = required - raw.keys()
        if missing:
            raise StateCorruptionError(
                f"Demo window state missing fields for campaign "
                f"{campaign_id}: {', '.join(sorted(missing))}"
            )

        return dict(raw)
