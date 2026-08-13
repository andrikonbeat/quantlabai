"""Indicator export contract (REQ-05) — schema, paths, and .jfx injection.

The JForex4 strategy runtime writes indicator snapshots via the packaged
``IndicatorExporter.java`` helper. This module mirrors that schema in Python
(``IndicatorExport`` / ``IndicatorSnapshot``), resolves the canonical export
path (``~/JForex4/exports/quantlab-indicators-<strategy>.json``), reads
exports back into models, and injects the Java helper + manifest into
generated ``.jfx`` archives (Ciclo 4, T4.1/T4.3).
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

#: Package-relative path to the Java helper packaged into .jfx archives.
INDICATOR_EXPORTER_SOURCE: Path = Path(__file__).with_name("IndicatorExporter.java")

#: Canonical export directory below the user home (REQ-05).
JFOREX_EXPORTS_DIR = "JForex4/exports"
#: Export filename prefix (REQ-05): quantlab-indicators-<strategy>.json
INDICATOR_FILE_PREFIX = "quantlab-indicators-"


class IndicatorSnapshot(BaseModel):
    """One timestamped indicator value written by the strategy helper."""

    name: str = Field(..., description="Indicator name, e.g. RSI")
    value: float = Field(..., description="Indicator value at timestamp")
    timestamp: datetime = Field(..., description="Snapshot timestamp (UTC)")


class IndicatorExport(BaseModel):
    """JSON schema of a ``quantlab-indicators-<strategy>.json`` export."""

    strategy: str = Field(..., description="Strategy identifier")
    exported_at: datetime = Field(..., description="Export creation time (UTC)")
    indicators: list[IndicatorSnapshot] = Field(
        default_factory=list, description="Timestamped indicator values"
    )


def indicator_export_path(
    strategy: str,
    export_dir: Optional[str | Path] = None,
) -> Path:
    """Return the canonical export path for *strategy* (REQ-05).

    Defaults to ``~/JForex4/exports/quantlab-indicators-<strategy>.json``;
    pass *export_dir* to override the base directory (tests, custom setups).
    """
    base = Path(export_dir) if export_dir is not None else Path.home() / JFOREX_EXPORTS_DIR
    return base / f"{INDICATOR_FILE_PREFIX}{strategy}.json"


def read_indicator_export(path: str | Path) -> IndicatorExport:
    """Parse and validate an indicator export JSON file.

    Raises:
        ValueError: File is missing, is corrupt JSON, or does not match the
            :class:`IndicatorExport` schema. The caller decides how to degrade
            (the LLM agent fails closed on this).
    """
    export_path = Path(path)
    try:
        raw = json.loads(export_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"indicator export not found: {export_path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"indicator export corrupt: {export_path}: {exc}") from exc
    try:
        return IndicatorExport.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(
            f"indicator export schema mismatch: {export_path}: {exc}"
        ) from exc


def inject_indicator_exporter(
    jfx_path: str | Path,
    strategy: str,
    export_dir: Optional[str | Path] = None,
) -> Path:
    """Inject the Java helper and export manifest into a ``.jfx`` archive.

    The ``.jfx`` is a ZIP; this adds ``IndicatorExporter.java`` (source) and
    ``indicator_export.manifest.json`` (strategy + target export path) without
    disturbing existing entries. The strategy runtime then writes
    ``quantlab-indicators-<strategy>.json`` via the helper (REQ-05).

    Args:
        jfx_path: Existing ``.jfx`` archive to inject into (must exist).
        strategy: Strategy identifier used for the export filename.
        export_dir: Optional override of the export base directory.

    Returns:
        The modified ``.jfx`` path (same file, entries appended).

    Raises:
        FileNotFoundError: *jfx_path* does not exist — fail closed, no new
            archive is created.
    """
    jfx = Path(jfx_path)
    if not jfx.is_file():
        raise FileNotFoundError(f".jfx archive not found: {jfx}")

    export_path = indicator_export_path(strategy, export_dir=export_dir)
    manifest = {
        "strategy": strategy,
        "export_path": str(export_path),
        "schema": "quantlab.indicator-export.v1",
    }
    source = INDICATOR_EXPORTER_SOURCE.read_text(encoding="utf-8")

    with zipfile.ZipFile(jfx, "a") as zf:
        existing = set(zf.namelist())
        if "IndicatorExporter.java" not in existing:
            zf.writestr("IndicatorExporter.java", source)
        if "indicator_export.manifest.json" not in existing:
            zf.writestr(
                "indicator_export.manifest.json",
                json.dumps(manifest, indent=2),
            )
    return jfx
