"""Phase-boundary memory capture service (REQ-102/103).

``MemoryCaptureService`` wraps :class:`AgentMemoryManager` (D1) and captures
the campaign.md Result Contract envelope (``status``, ``executive_summary``,
``artifacts``, ``next_recommended``, ``risks``) plus the phase config at every
phase boundary. Capture is **config-disabled** by default (D1) and is
**non-blocking**: any persistence failure is logged as a warning and the
campaign flow continues (REQ-102).

Engram complementarity (REQ-103): each decision is written to BOTH Engram
(topic ``agent/{agent}/{campaign}``) and the Knowledge Lake
``agent-memory/{agent}/{campaign}/memory.yaml``. Neither replaces the other.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from quantlab.agents.memory import AgentMemoryManager

logger = logging.getLogger(__name__)

# campaign.md Result Contract envelope fields (D2). Missing fields default to
# null so the record stays complete and persistable (REQ-102).
RESULT_CONTRACT_FIELDS: tuple[str, ...] = (
    "status",
    "executive_summary",
    "artifacts",
    "next_recommended",
    "risks",
)

# Environment variable that enables capture when no config dict is provided.
CAPTURE_ENV_VAR = "QUANTLAB_MEMORY_CAPTURE"

_ENABLED_VALUES = frozenset({"1", "true", "yes", "on"})
_DISABLED_VALUES = frozenset({"0", "false", "no", "off"})


def is_capture_enabled(capture_config: dict[str, Any] | None = None) -> bool:
    """Return True when phase-boundary capture is active (D1, config-disabled).

    An explicit ``capture_config["enabled"]`` value wins; otherwise the
    ``QUANTLAB_MEMORY_CAPTURE`` environment variable is honored
    (``"1"/"true"/"yes"/"on"`` enables). With no signal at all, capture is
    disabled — the default is off so existing flows are untouched.
    """
    if isinstance(capture_config, dict) and "enabled" in capture_config:
        return bool(capture_config["enabled"])
    raw = os.environ.get(CAPTURE_ENV_VAR, "").strip().lower()
    if raw in _ENABLED_VALUES:
        return True
    if raw in _DISABLED_VALUES:
        return False
    return False


class MemoryCaptureService:
    """Captures Result Contract envelopes at phase boundaries (REQ-102).

    Args:
        knowledge_root: Knowledge Lake root for ``agent-memory/`` writes.
        engram_save_fn: Optional async Engram persistence function.
        capture_config: Optional dict controlling capture enablement
            (``{"enabled": bool}``). When absent, the
            ``QUANTLAB_MEMORY_CAPTURE`` env var is honored; default off.
    """

    def __init__(
        self,
        knowledge_root: str | os.PathLike[str] = "knowledge",
        engram_save_fn: Any = None,
        capture_config: dict[str, Any] | None = None,
    ) -> None:
        self._knowledge_root = knowledge_root
        self._engram_save_fn = engram_save_fn
        self._capture_config = capture_config

    async def capture_phase(
        self,
        agent: str,
        campaign: str,
        phase: str,
        envelope: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> None:
        """Capture a phase-boundary Result Contract envelope, non-blocking.

        Args:
            agent: Agent name (e.g. ``"research-director"``).
            campaign: Campaign identifier.
            phase: Phase name (e.g. ``"config"``).
            envelope: Result Contract dict; missing fields default to null.
            config: Optional phase config persisted alongside the envelope.

        Never raises: persistence failures are logged as warnings so the
        campaign flow continues (REQ-102). When capture is disabled (D1),
        this is a no-op.
        """
        if not is_capture_enabled(self._capture_config):
            logger.debug("memory capture disabled; skipping phase '%s'", phase)
            return

        decision = self._build_decision(envelope)
        try:
            manager = AgentMemoryManager(
                knowledge_root=self._knowledge_root,
                engram_save_fn=self._engram_save_fn,
            )
            await manager.save_decision(
                agent, campaign, decision, phase=phase, config=config
            )
        except Exception as exc:  # noqa: BLE001 — non-blocking by contract
            logger.warning(
                "memory capture failed for phase '%s' (non-blocking): %s",
                phase,
                exc,
            )

    @staticmethod
    def _build_decision(envelope: dict[str, Any] | None) -> dict[str, Any]:
        """Normalize an envelope to the Result Contract with null defaults (D2).

        Non-dict input yields a record whose contract fields are all null —
        the record is still persisted (REQ-102 missing-fields default).
        """
        source = envelope if isinstance(envelope, dict) else {}
        return {field: source.get(field) for field in RESULT_CONTRACT_FIELDS}
