"""Default task XML loader.

Loads per-type default task XMLs shipped with SQX install.
The engine NEVER writes task XML from memory: every task starts as the exact
default the app itself seeds (internal/plugins/Task<Type>/task.xml).
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from quantlab.sqx.project_builder import _DEFAULT_TEMPLATE


# ── Install root resolution (lazy) ─────────────────────────────────────────────────

_INSTALL_ROOT: Path | None = None
_PLUGINS_DIR: Path | None = None


def _ensure_install_root() -> Path:
    """Find SQX install root by walking up from this file (lazy)."""
    global _INSTALL_ROOT, _PLUGINS_DIR
    if _INSTALL_ROOT is not None:
        return _INSTALL_ROOT
    
    current = Path(__file__).resolve()
    for _ in range(15):
        if (current / "internal" / "plugins" / "TaskBuild").exists():
            _INSTALL_ROOT = current
            _PLUGINS_DIR = current / "internal" / "plugins"
            return _INSTALL_ROOT
        if current.parent == current:
            break
        current = current.parent
    
    # Fallback: environment variable
    if env := os.environ.get("SQX_INSTALL_ROOT"):
        p = Path(env)
        if p.exists():
            _INSTALL_ROOT = p
            _PLUGINS_DIR = p / "internal" / "plugins"
            return _INSTALL_ROOT
    
    # Fallback: SQX 144 build path (for testing)
    fallback = Path("/mnt/Projects/05 - Develop/Proyectos/1- Active/quantlab-ai/SQX_144_2953_linux_20260601")
    if fallback.exists():
        _INSTALL_ROOT = fallback
        _PLUGINS_DIR = fallback / "internal" / "plugins"
        return _INSTALL_ROOT
    
    raise RuntimeError(
        "Could not locate SQX install root. Set SQX_INSTALL_ROOT "
        "or ensure this module lives inside an SQX install."
    )


def _get_plugins_dir() -> Path:
    _ensure_install_root()
    return _PLUGINS_DIR


# ── Cache ──────────────────────────────────────────────────────────────────────


_TEMPLATE_CACHE: dict[tuple[str, str | None], ET.Element] = {}
_SNIPPETS_CACHE: dict[tuple[str, str], frozenset[str]] = {}


# ── Public API ───────────────────────────────────────────────────────────────


def load_defaults(task_type: str, base: str | None = None) -> ET.Element:
    """
    Load the default task XML for a task type.
    
    Returns a FRESH deep copy of the parsed <Task><Settings> tree.
    The caller owns the returned tree and can mutate it freely.
    
    Args:
        task_type: "Build", "Retest", "Optimize", "Filtering", etc.
        base: For Build tasks: "forex", "futures", "stockpicker"
    
    Returns:
        Fresh ET.Element tree rooted at <Task><Settings>...
    
    Raises:
        FileNotFoundError: if default XML not found
        ValueError: if task_type unknown
    """
    cache_key = (task_type, base)
    if cache_key in _TEMPLATE_CACHE:
        # Deep copy for safe mutation
        return ET.fromstring(ET.tostring(_TEMPLATE_CACHE[cache_key], encoding="unicode"))
    
    # Determine XML file path
    if task_type == "Build" and base:
        xml_name = f"task_{base}.xml"  # task_forex.xml, task_futures.xml, task_stockpicker.xml
    else:
        xml_name = "task.xml"
    
    plugin_dir = _get_plugins_dir() / f"Task{task_type}"
    xml_path = plugin_dir / xml_name
    
    if not xml_path.exists():
        # Fallback: try the default template zip (for Build tasks)
        if task_type == "Build":
            with zipfile.ZipFile(_DEFAULT_TEMPLATE, "r") as z:
                data = z.read("Build-Task1.xml")
            root = ET.fromstring(data)
            _TEMPLATE_CACHE[cache_key] = root
            return ET.fromstring(ET.tostring(root, encoding="unicode"))
        raise FileNotFoundError(f"Default task XML not found: {xml_path}")
    
    # Parse and cache
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    # The default XML wraps settings in <Task><Settings>...
    # We return the <Settings> element for surgical editing
    settings = root.find("Settings")
    if settings is None:
        # Some task.xml may have <Settings> at root level
        if root.tag == "Settings":
            settings = root
        else:
            raise ValueError(f"Invalid task XML structure: no <Settings> in {xml_path}")
    
    _TEMPLATE_CACHE[cache_key] = settings
    return ET.fromstring(ET.tostring(settings, encoding="unicode"))


def available_types() -> list[str]:
    """Return list of available task types (directories under internal/plugins/)."""
    try:
        plugins_dir = _get_plugins_dir()
    except RuntimeError:
        return []
    types = []
    for p in plugins_dir.iterdir():
        if p.is_dir() and p.name.startswith("Task"):
            types.append(p.name[4:])  # strip "Task"
    return sorted(types)


def available_columns(task_type: str) -> list[str]:
    """Return available column names for a task type (from default XML)."""
    settings = load_defaults(task_type)
    cols = set()
    for elem in settings.iter():
        if elem.tag.endswith("Column") or elem.tag.endswith("Metric"):
            cols.add(elem.tag)
    return sorted(cols)


def snippet_names(task_type: str) -> list[str]:
    """Return available snippet names referenced in the default task XML."""
    cache_key = (task_type, "snippets")
    if cache_key in _SNIPPETS_CACHE:
        return list(_SNIPPETS_CACHE[cache_key])
    
    settings = load_defaults(task_type)
    names = set()
    for elem in settings.iter():
        # Look for snippet references in templateFile, strategyFile, etc.
        for attr in ("templateFile", "strategyFile", "customFile"):
            val = elem.get(attr)
            if val:
                names.add(val)
        # Also check <Snippet> elements
        if elem.tag == "Snippet":
            name = elem.get("name") or elem.text
            if name:
                names.add(name)
    
    _SNIPPETS_CACHE[cache_key] = frozenset(names)
    return list(names)


def get_install_root() -> Path:
    """Return the detected SQX install root."""
    return _ensure_install_root()


# ── CLI / testing ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    print("Install root:", get_install_root())
    print("Available task types:", available_types())
    
    for t in available_types():
        try:
            settings = load_defaults(t)
            print(f"\n{t}: {len(list(settings.iter()))} elements")
            # Print first few elements
            for i, elem in enumerate(settings.iter()):
                if i >= 5:
                    print("  ...")
                    break
                print(f"  {elem.tag}: {elem.attrib}")
        except Exception as e:
            print(f"{t}: ERROR - {e}")