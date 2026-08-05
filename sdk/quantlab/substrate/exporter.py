"""Substrate per-phase export (REQ-26) — databank export routed into the
phase's checkpoint directory, with legacy-path collection parity (REQ-28).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_EXPORT_DIR_PATTERNS = [
    "user/projects/{campaign_id}/exports",
    "user/settings/Exports/{campaign_id}",
    "/tmp/sqx-exports/{campaign_id}",
    "/tmp/sqx-mock-exports/{campaign_id}",
]


def collect_exports(sqx_install_path: str | Path, campaign_id: str) -> list[str]:
    """Collect exported files from the standard SQX export directories.

    Identical pattern set to the legacy ``cli_wrapper._collect_exports`` so
    substrate output parity holds for the same inputs (REQ-28).
    """
    base = Path(sqx_install_path)
    export_paths: list[str] = []
    for pattern in _EXPORT_DIR_PATTERNS:
        export_dir = base / pattern.format(campaign_id=campaign_id)
        if not export_dir.is_dir():
            continue
        for f in export_dir.iterdir():
            if f.is_file():
                export_paths.append(str(f))
    return sorted(export_paths)


async def export_phase(
    client: Any,
    campaign_id: str,
    phase: Any,
    *,
    sqx_install_path: str | Path,
    export_dir: str | Path,
    databank: str = "Results",
) -> list[str]:
    """Export *databank* for *campaign_id* and stage artifacts under
    ``{export_dir}/{phase}/`` (each task's exports land in its phase
    checkpoint — REQ-27/REQ-26).

    Returns the staged file paths. The databank request is best-effort
    (export failures surface as warnings; collection is authoritative).
    """
    name = phase.value if hasattr(phase, "value") else str(phase)
    staging = Path(export_dir) / name
    staging.mkdir(parents=True, exist_ok=True)

    try:
        await client.send_command(
            f"-databank action=export project={campaign_id} "
            f"name={databank} file={staging / 'strategies.csv'}"
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Databank export failed for '%s': %s", campaign_id, exc)

    for src in collect_exports(sqx_install_path, campaign_id):
        try:
            shutil.copy2(src, staging / Path(src).name)
        except OSError as exc:  # pragma: no cover - defensive
            logger.warning("Failed to stage export %s: %s", src, exc)

    return sorted(str(p) for p in staging.iterdir() if p.is_file())
