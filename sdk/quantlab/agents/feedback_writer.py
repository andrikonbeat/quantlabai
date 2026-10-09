"""KnowledgeLakeFeedbackWriter — persists hypothesis feedback to Knowledge Lake."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

from quantlab.knowledge.models import HypothesisFeedbackRecord

logger = logging.getLogger(__name__)


class KnowledgeLakeFeedbackWriter:
    """Writes hypothesis feedback to Knowledge Lake metadata files.

    Appends feedback records to `structured/{campaign_id}/metadata.yaml`
    under the `feedback:` key. The writer is async; actual I/O is offloaded.
    """

    def __init__(self, lake_root: Path | str | None = None, auto_adjust: bool = False) -> None:
        self._lake_root = Path(lake_root) if lake_root is not None else Path("knowledge")
        self.auto_adjust = bool(auto_adjust)

    async def write_feedback(
        self, record: HypothesisFeedbackRecord, reindex: bool = True
    ) -> None:
        """Persist feedback record to the campaign's metadata.yaml file.

        Args:
            record: Feedback record to append.
            reindex: When True (default), refresh the lake index afterwards
                so the updated metadata is visible to queries. Best-effort
                and never raises.
        """
        await self._write_feedback_sync(record)
        if reindex:
            try:
                from quantlab.knowledge.store import KnowledgeStore

                KnowledgeStore(self._lake_root).rebuild_index()
            except Exception as exc:
                logger.debug("Feedback reindex skipped: %s", exc)

    async def _write_feedback_sync(self, record: HypothesisFeedbackRecord) -> None:
        campaign_dir = self._lake_root / "structured" / record.campaign_id
        campaign_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = campaign_dir / "metadata.yaml"

        data: dict[str, Any] = {}
        if metadata_path.exists():
            try:
                if yaml is not None:
                    loaded = yaml.safe_load(metadata_path.read_text()) or {}
                    if isinstance(loaded, dict):
                        data = loaded
            except Exception:
                data = {}

        feedback = data.get("feedback") if isinstance(data.get("feedback"), list) else []
        feedback.append(record.to_dict())
        data["feedback"] = feedback

        if yaml is not None:
            try:
                metadata_path.write_text(yaml.safe_dump(data, sort_keys=False))
                return
            except Exception:
                pass

        # Fallback: simple YAML-like write
        lines = []
        for k, v in data.items():
            if k == "feedback" and isinstance(v, list):
                lines.append("feedback:")
                for item in v:
                    lines.append("  -")
                    for ik, iv in item.items():
                        if isinstance(iv, str):
                            # Basic quoting
                            escaped = iv.replace('"', '\\"')
                            lines.append(f'    {ik}: "{escaped}"')
                        else:
                            lines.append(f"    {ik}: {iv}")
            else:
                lines.append(f"{k}: {v}")
        metadata_path.write_text("\n".join(lines) + "\n")
