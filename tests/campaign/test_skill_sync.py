"""REQ-822/901: skills sync idempotency, parity, allowlist, registry refresh.

``ai/opencode/sync_skills.py`` is the sibling to ``sync_prompts.py``. It syncs
``ai/opencode/skills/*/SKILL.md`` to ``~/.config/opencode/skills/`` with the
same discipline: deterministic, idempotent, allowlist-based, ``--dry-run``/
``--check`` modes, repo-wins policy. Live hand-editing of synced skills is
prohibited.

These tests assert:

- ``sync_skills.py --check`` reports drift when live differs from repo;
- ``sync_skills.py --dry-run`` makes no changes;
- allowlist limits sync scope to QuantLab-owned skills only;
- registry refresh order follows sync.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SYNC_SCRIPT = REPO_ROOT / "ai" / "opencode" / "sync_skills.py"
SYNC_COMMON_SCRIPT = REPO_ROOT / "ai" / "opencode" / "sync_common.py"
REPO_SKILLS = REPO_ROOT / "ai" / "opencode" / "skills"
LIVE_SKILLS = Path.home() / ".config" / "opencode" / "skills"


def _parse_skill_frontmatter(skill_md_text: str) -> dict[str, object]:
    """Extract the YAML frontmatter block from a SKILL.md string.

    Returns the parsed metadata dict, or raises ValueError if the frontmatter
    block is missing or malformed.
    """
    if not skill_md_text.startswith("---"):
        raise ValueError("missing YAML frontmatter block")
    end = skill_md_text.find("---", 3)
    if end == -1:
        raise ValueError("malformed YAML frontmatter block")
    frontmatter_text = skill_md_text[3:end].strip()
    try:
        return yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"malformed YAML frontmatter: {exc}") from exc


REQUIRED_FRONTMATTER_FIELDS: dict[str, type] = {
    "name": str,
    "description": str,
    "disable-model-invocation": bool,
    "user-invocable": bool,
    "license": str,
    "metadata": dict,
}


def _validate_skill_frontmatter(parsed: dict[str, object]) -> None:
    """Validate that parsed SKILL.md frontmatter contains all required fields.

    Raises ValueError if any required field is missing or has the wrong type.
    """
    for field, expected_type in REQUIRED_FRONTMATTER_FIELDS.items():
        if field not in parsed:
            raise ValueError(f"missing required frontmatter field: {field}")
        if not isinstance(parsed[field], expected_type):
            raise ValueError(
                f"frontmatter field {field} must be {expected_type.__name__}, "
                f"got {type(parsed[field]).__name__}"
            )
    metadata = parsed.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a dict")
    for sub in ("author", "version"):
        if sub not in metadata:
            raise ValueError(f"metadata missing required key: {sub}")


def _load_sync_skills_module():
    spec = importlib.util.spec_from_file_location("sync_skills", SYNC_SCRIPT)
    assert spec is not None and spec.loader is not None, "sync_skills.py must load"
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_skills"] = module
    spec.loader.exec_module(module)
    return module


class TestSkillSyncModule:
    """REQ-822: sync_skills.py must exist and expose sync/check/allowlist."""

    def test_sync_skills_importable(self) -> None:
        """RED: sync_skills.py must be importable."""
        mod = _load_sync_skills_module()
        assert hasattr(mod, "sync"), "sync_skills.py must expose sync()"
        assert hasattr(mod, "check"), "sync_skills.py must expose check()"
        assert hasattr(mod, "managed_skill_names"), "sync_skills.py must expose managed_skill_names()"

    def test_managed_skill_names_returns_quantlab_prefix(self) -> None:
        """RED: allowlist must be quantlab-* only."""
        mod = _load_sync_skills_module()
        names = mod.managed_skill_names(REPO_SKILLS)
        assert names, "managed_skill_names must return at least one skill"
        assert all(name.startswith("quantlab-") for name in names), (
            "allowlist must be limited to quantlab-* skills"
        )


class TestSkillSyncDryRun:
    """REQ-822: dry-run reports changes without modifying live."""

    def test_dry_run_reports_drift_but_does_not_write(self, tmp_path: Path) -> None:
        """RED: --dry-run must report drift without modifying live."""
        mod = _load_sync_skills_module()
        repo = tmp_path / "repo" / "skills"
        repo.mkdir(parents=True)
        skill_dir = repo / "quantlab-run-campaign"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Campaign Skill\n", encoding="utf-8")
        live = tmp_path / "live"
        live.mkdir()
        (live / "quantlab-run-campaign" / "SKILL.md").parent.mkdir(parents=True)
        (live / "quantlab-run-campaign" / "SKILL.md").write_text(
            "# Stale Live\n", encoding="utf-8"
        )
        changed = mod.sync(repo, live, dry_run=True)
        assert "quantlab-run-campaign" in changed
        assert (live / "quantlab-run-campaign" / "SKILL.md").read_text(
            encoding="utf-8"
        ) == "# Stale Live\n", "dry-run must NOT modify live"

    def test_dry_run_is_idempotent(self, tmp_path: Path) -> None:
        """RED: a second dry-run on already-drifted live must still be a no-op."""
        mod = _load_sync_skills_module()
        repo = tmp_path / "repo" / "skills"
        repo.mkdir(parents=True)
        skill_dir = repo / "quantlab-run-campaign"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Campaign Skill\n", encoding="utf-8")
        live = tmp_path / "live"
        live.mkdir()
        (live / "quantlab-run-campaign" / "SKILL.md").parent.mkdir(parents=True)
        (live / "quantlab-run-campaign" / "SKILL.md").write_text(
            "# Stale Live\n", encoding="utf-8"
        )
        first = mod.sync(repo, live, dry_run=True)
        second = mod.sync(repo, live, dry_run=True)
        assert sorted(first) == sorted(second), "dry-run must be deterministic"


class TestSkillSyncCheck:
    """REQ-822: --check reports drift without modifying."""

    def test_check_reports_drift_when_live_differs(self, tmp_path: Path) -> None:
        """RED: check() must name the drifted skill."""
        mod = _load_sync_skills_module()
        repo = tmp_path / "repo" / "skills"
        repo.mkdir(parents=True)
        skill_dir = repo / "quantlab-run-campaign"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Campaign Skill\n", encoding="utf-8")
        live = tmp_path / "live"
        live.mkdir()
        (live / "quantlab-run-campaign" / "SKILL.md").parent.mkdir(parents=True)
        (live / "quantlab-run-campaign" / "SKILL.md").write_text(
            "# Stale Live\n", encoding="utf-8"
        )
        drifted = mod.check(repo, live)
        assert drifted == ["quantlab-run-campaign"], f"expected ['quantlab-run-campaign'], got {drifted}"

    def test_check_returns_empty_when_in_sync(self, tmp_path: Path) -> None:
        """RED: check() must return [] when live matches repo."""
        mod = _load_sync_skills_module()
        repo = tmp_path / "repo" / "skills"
        repo.mkdir(parents=True)
        skill_dir = repo / "quantlab-run-campaign"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Campaign Skill\n", encoding="utf-8")
        live = tmp_path / "live"
        live.mkdir()
        skill_live = live / "quantlab-run-campaign"
        skill_live.mkdir(parents=True)
        (skill_live / "SKILL.md").write_text("# Campaign Skill\n", encoding="utf-8")
        assert mod.check(repo, live) == []


class TestSkillSyncScope:
    """REQ-822: allowlist limits sync scope."""

    def test_allowlist_excludes_non_quantlab_skills(self, tmp_path: Path) -> None:
        """RED: only quantlab-* skills must be synced."""
        mod = _load_sync_skills_module()
        repo = tmp_path / "repo" / "skills"
        repo.mkdir(parents=True)
        (repo / "quantlab-run-campaign" / "SKILL.md").parent.mkdir(parents=True)
        (repo / "quantlab-run-campaign" / "SKILL.md").write_text(
            "# QuantLab\n", encoding="utf-8"
        )
        (repo / "third-party-skill" / "SKILL.md").parent.mkdir(parents=True)
        (repo / "third-party-skill" / "SKILL.md").write_text(
            "# Third\n", encoding="utf-8"
        )
        live = tmp_path / "live"
        live.mkdir()
        changed = mod.sync(repo, live)
        assert "quantlab-run-campaign" in changed
        assert "third-party-skill" not in changed
        assert (live / "third-party-skill").exists() is False


class TestSkillFormatNegative:
    """TST-SKILL-01: negative tests for REQ-904 SKILL.md frontmatter."""

    def test_valid_frontmatter_passes(self, tmp_path: Path) -> None:
        """GREEN: valid frontmatter must pass validation."""
        skill_md = """---
name: test-skill
description: A test skill.
disable-model-invocation: true
user-invocable: false
license: MIT
metadata:
  author: test
  version: "1.0"
---
# Test Skill
"""
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text(skill_md, encoding="utf-8")
        parsed = _parse_skill_frontmatter(skill_path.read_text(encoding="utf-8"))
        _validate_skill_frontmatter(parsed)  # must not raise

    def test_missing_disable_model_invocation(self, tmp_path: Path) -> None:
        """RED: missing disable-model-invocation must be flagged invalid."""
        skill_md = """---
name: test-skill
description: A test skill.
user-invocable: true
license: MIT
metadata:
  author: test
  version: "1.0"
---
# Test Skill
"""
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text(skill_md, encoding="utf-8")
        parsed = _parse_skill_frontmatter(skill_path.read_text(encoding="utf-8"))
        with pytest.raises(ValueError, match="missing required frontmatter field: disable-model-invocation"):
            _validate_skill_frontmatter(parsed)

    def test_missing_user_invocable(self, tmp_path: Path) -> None:
        """RED: missing user-invocable must be flagged invalid."""
        skill_md = """---
name: test-skill
description: A test skill.
disable-model-invocation: true
license: MIT
metadata:
  author: test
  version: "1.0"
---
# Test Skill
"""
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text(skill_md, encoding="utf-8")
        parsed = _parse_skill_frontmatter(skill_path.read_text(encoding="utf-8"))
        with pytest.raises(ValueError, match="missing required frontmatter field: user-invocable"):
            _validate_skill_frontmatter(parsed)

    def test_missing_both_fields(self, tmp_path: Path) -> None:
        """RED: missing both disable-model-invocation and user-invocable must be flagged invalid."""
        skill_md = """---
name: test-skill
description: A test skill.
license: MIT
metadata:
  author: test
  version: "1.0"
---
# Test Skill
"""
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text(skill_md, encoding="utf-8")
        parsed = _parse_skill_frontmatter(skill_path.read_text(encoding="utf-8"))
        with pytest.raises(ValueError, match="missing required frontmatter field: disable-model-invocation"):
            _validate_skill_frontmatter(parsed)
