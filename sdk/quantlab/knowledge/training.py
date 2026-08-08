"""Curated training export from the knowledge lake (REQ-106/107).

``export_training_jsonl`` converts captured agent decisions into a
training-ready, privacy-scrubbed JSONL dataset under ``datasets/``:

- REQ-106 curation: only decisions from *verified* campaigns (a campaign with
  at least one successful phase outcome) are exported, and records are
  deduplicated by their phase-config hash.
- REQ-107 privacy: the export is deny-list-clean (``PrivacyScrubber`` with
  ``export=True``), campaign IDs appear as SHA-256 hashes, and every record
  carries a stable hashed ``id``.

The write destination conforms to the REQ-101 taxonomy (``datasets/**``).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from quantlab.knowledge.privacy import PrivacyScrubber

# Canonical export destination (relative to the lake root, REQ-101).
DATASETS_DIR = "datasets"
CURATED_FILE_NAME = "curated_decisions.jsonl"

_SUCCESS_STATUS = {"success"}
_NONE_CONFIG_HASH_INPUT = "__none__"


def _verified_campaigns(root: Path) -> set[str]:
    """Campaigns with at least one successful phase outcome (REQ-106).

    A campaign is *verified* when any of its captured decisions succeeded —
    that is the curation gate for training data.
    """
    verified: set[str] = set()
    memory_root = root / "agent-memory"
    if not memory_root.is_dir():
        return verified
    for memory_file in memory_root.glob("*/*/memory.yaml"):
        campaign = memory_file.parent.name
        try:
            records = yaml.safe_load(memory_file.read_text(encoding="utf-8")) or []
        except Exception:
            continue
        if not isinstance(records, list):
            records = [records]
        if any(
            isinstance(record, dict)
            and str(record.get("status", "")).strip().lower() in _SUCCESS_STATUS
            for record in records
        ):
            verified.add(campaign)
    return verified


def _config_hash(config: dict[str, Any] | None) -> str:
    """Stable SHA-256 of the canonical phase config (REQ-106 dedupe).

    ``None``/missing configs share one bucket so config-less records are
    deduplicated together.
    """
    if not config:
        canonical = _NONE_CONFIG_HASH_INPUT
    else:
        canonical = json.dumps(
            config, sort_keys=True, separators=(",", ":"), default=str
        )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _record_id(record: dict[str, Any]) -> str:
    """Stable SHA-256 hex id for a scrubbed record (REQ-106 identity).

    Computed over the already-scrubbed record so the digest never embeds
    raw secrets or raw campaign IDs.
    """
    canonical = json.dumps(
        record, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def export_training_jsonl(root: str | Path) -> tuple[Path, int]:
    """Export curated, privacy-scrubbed decisions to ``datasets/``.

    Args:
        root: Knowledge Lake root.

    Returns:
        ``(path, count)``: the JSONL file path and the number of exported
        records. When nothing qualifies, ``count`` is 0 and no file is
        written (the returned path does not exist).
    """
    root = Path(root)
    datasets_dir = root / DATASETS_DIR
    export_path = datasets_dir / CURATED_FILE_NAME

    verified = _verified_campaigns(root)
    if not verified:
        return export_path, 0

    memory_root = root / "agent-memory"
    scrubber = PrivacyScrubber()
    seen_configs: set[str] = set()
    records: list[dict[str, Any]] = []

    for memory_file in sorted(memory_root.glob("*/*/memory.yaml")):
        campaign = memory_file.parent.name
        if campaign not in verified:
            continue
        try:
            decoded = yaml.safe_load(memory_file.read_text(encoding="utf-8")) or []
        except Exception:
            continue
        if not isinstance(decoded, list):
            decoded = [decoded]
        for record in decoded:
            if not isinstance(record, dict):
                continue
            config = record.get("config") if isinstance(record.get("config"), dict) else None
            key = _config_hash(config)
            if key in seen_configs:
                continue
            seen_configs.add(key)

            # REQ-107: scrub first (export mode hashes campaign IDs), then add
            # the stable record id over the scrubbed content.
            record = dict(record)
            record.setdefault("campaign_id", str(campaign))
            export_record = scrubber.scrub(record, export=True)
            export_record["id"] = _record_id(export_record)
            records.append(export_record)

    if not records:
        return export_path, 0

    records.sort(key=lambda r: str(r.get("timestamp", "")))
    datasets_dir.mkdir(parents=True, exist_ok=True)
    export_path.write_text(
        "\n".join(
            json.dumps(record, ensure_ascii=False, default=str) for record in records
        )
        + "\n",
        encoding="utf-8",
    )
    return export_path, len(records)
