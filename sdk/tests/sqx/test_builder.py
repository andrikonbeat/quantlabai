"""Tests for builder (surgical XML edits)."""

import pytest
import tempfile
from pathlib import Path
from quantlab.sqx.templates import load_defaults
from quantlab.sqx.builder import apply_curated_keys, apply_spec_to_task, build_cfx_from_spec


class TestBuilder:
    """Builder tests."""

    def test_apply_curated_keys_simple(self):
        """Apply simple curated keys."""
        settings = load_defaults("Build", "forex")
        curated = {
            "session": "London",
            "sl_required": True,
            "min_sl_pips": 20,
        }
        applied = apply_curated_keys(settings, curated)
        assert "session" in applied
        assert "sl_required" in applied
        assert "min_sl_pips" in applied

    def test_apply_curated_keys_ignores_none(self):
        """None values should be ignored."""
        settings = load_defaults("Build", "forex")
        curated = {"session": "London", "unknown_key": None}
        applied = apply_curated_keys(settings, curated)
        assert "session" in applied
        assert "unknown_key" not in applied

    def test_apply_curated_keys_unknown_ignored(self):
        """Unknown keys should be silently ignored."""
        settings = load_defaults("Build", "forex")
        curated = {"unknown_key": "value"}
        applied = apply_curated_keys(settings, curated)
        assert len(applied) == 0

    def test_apply_spec_to_task_curated_only(self):
        """Apply spec with only curated keys."""
        settings = load_defaults("Build", "forex")
        task_spec = {
            "session": "Tokyo",
            "sl_required": True,
        }
        applied = apply_spec_to_task(settings, task_spec)
        assert "session" in applied
        assert "sl_required" in applied

    def test_apply_spec_to_task_with_special_sections(self):
        """Apply spec with special sections (delegated to sections.py)."""
        settings = load_defaults("Build", "forex")
        task_spec = {
            "task": "Build",
            "base": "forex",
            "engine": "JForex",
            "symbol": "EURUSD_M1_dukas",
            "timeframe": "M15",
            "range": {"from": "2010-01-01", "to": "2024-10-30"},
        }
        applied = apply_spec_to_task(settings, task_spec)
        assert len(applied) > 0

    def test_build_cfx_from_spec_creates_valid_cfx(self):
        """build_cfx_from_spec should create a valid .cfx file."""
        spec = {
            "edit": "TestBuilder",
            "tasks": [{
                "task": "Build",
                "base": "forex",
                "engine": "JForex",
                "symbol": "EURUSD_M1_dukas",
                "timeframe": "M15",
                "range": {"from": "2010-01-01", "to": "2024-10-30"},
            }]
        }
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            cfx_path = Path(tmp.name)
        try:
            build_cfx_from_spec({
                "edit": "TestBuilder",
                "tasks": [{
                    "task": "Build",
                    "base": "forex",
                    "engine": "JForex",
                    "symbol": "EURUSD_M1_dukas",
                    "timeframe": "M15",
                    "range": {"from": "2010-01-01", "to": "2024-10-30"},
                }]
            }, cfx_path)
            assert cfx_path.exists()
            assert cfx_path.stat().st_size > 0
        finally:
            cfx_path.unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
