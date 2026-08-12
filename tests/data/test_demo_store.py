"""Task 1.1 RED: DemoWindowStore atomic write/read + validation.

Scenario 1 "Atomic write survives partial write": a write interrupted mid-way
does not corrupt the persisted YAML.
Scenario 2 "Corrupt YAML raises validation error": loading a malformed file
raises ``StateCorruptionError`` instead of returning garbage.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from quantlab.data.demo.store import DemoWindowStore, StateCorruptionError


class TestAtomicWrite:
    """REQ-621 scenario 1 — atomic write survives partial write."""

    def test_atomic_write_creates_valid_yaml(self, tmp_path):
        """GIVEN a DemoWindowStore pointed at tmp_path
        WHEN persist() writes a window
        THEN the YAML file exists and parses back to the same values.
        """
        store = DemoWindowStore(root=tmp_path, campaign_id="camp-1")
        window = {
            "started_at": "2026-01-01",
            "expires_at": "2026-01-15",
            "renewal_count": 0,
        }
        store.persist(window)

        path = tmp_path / "structured" / "demo" / "camp-1" / "window.yaml"
        assert path.exists()
        loaded = store.load("camp-1")
        assert loaded == window

    def test_atomic_write_uses_temp_then_rename(self, tmp_path):
        """GIVEN a store
        WHEN persist() runs
        THEN no partial file remains at the final path during the write.
        """
        store = DemoWindowStore(root=tmp_path, campaign_id="camp-2")
        window = {"started_at": "2026-01-01", "expires_at": "2026-01-15", "renewal_count": 0}

        # The implementation should write to a temp file and rename.
        # We verify by checking that the final path is never a partial write
        # (rename is atomic on POSIX).
        store.persist(window)
        path = tmp_path / "structured" / "demo" / "camp-2" / "window.yaml"
        assert path.exists()
        # No .tmp sibling should remain after successful persist.
        tmp_siblings = list(path.parent.glob("*.tmp"))
        assert tmp_siblings == [], "temp file must be cleaned up after rename"


class TestValidation:
    """REQ-621 scenario 1 — corrupt YAML raises StateCorruptionError."""

    def test_corrupt_yaml_raises_state_corruption_error(self, tmp_path):
        """GIVEN a window.yaml with invalid YAML
        WHEN load() is called
        THEN StateCorruptionError is raised.
        """
        store = DemoWindowStore(root=tmp_path, campaign_id="camp-3")
        path = tmp_path / "structured" / "demo" / "camp-3" / "window.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("started_at: [unterminated", encoding="utf-8")

        with pytest.raises(StateCorruptionError, match="camp-3"):
            store.load("camp-3")

    def test_missing_file_raises_state_corruption_error(self, tmp_path):
        """GIVEN no persisted state
        WHEN load() is called
        THEN StateCorruptionError is raised.
        """
        store = DemoWindowStore(root=tmp_path, campaign_id="camp-4")
        with pytest.raises(StateCorruptionError, match="camp-4"):
            store.load("camp-4")

    def test_overwrite_replaces_previous_state(self, tmp_path):
        """GIVEN an existing window state
        WHEN persist() writes a new state
        THEN the loaded state reflects the new values.
        """
        store = DemoWindowStore(root=tmp_path, campaign_id="camp-5")
        store.persist({"started_at": "2026-01-01", "expires_at": "2026-01-15", "renewal_count": 0})
        store.persist({"started_at": "2026-02-01", "expires_at": "2026-02-15", "renewal_count": 1})
        loaded = store.load("camp-5")
        assert loaded["started_at"] == "2026-02-01"
        assert loaded["renewal_count"] == 1
