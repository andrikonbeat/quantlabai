"""E8: Prior Observations Recall.

Production call site for `compose_prior_context`: reads prior decisions,
risks and lessons from the memory lake and returns them as a structured
list of observations for the exploration decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PriorObservation:
    """One prior observation relevant to the current exploration."""

    text: str
    source: str  # e.g. "memory-lake", "similar-campaign"
    campaign_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source": self.source,
            "campaign_id": self.campaign_id,
        }


class PriorObservationsRecall:
    """Recalls prior observations and learnings (E8).

    This is the production call site for
    `quantlab.knowledge.context.compose_prior_context`, which previously
    had zero production call sites (definition + tests only).
    """

    def __init__(
        self,
        knowledge_root: str | Path = "knowledge",
        limit: int = 10,
        agent: str | None = None,
    ) -> None:
        self.knowledge_root = knowledge_root
        self.limit = limit
        self.agent = agent

    def recall(
        self,
        campaign_id: str,
        phase: str = "research",
    ) -> list[PriorObservation]:
        """Compose prior context and parse it into observations."""
        from quantlab.knowledge.context import compose_prior_context

        # Production call site (REQ-104/501).
        block = compose_prior_context(
            campaign_id,
            phase,
            limit=self.limit,
            root=self.knowledge_root,
            agent=self.agent,
        )
        return self._parse(block)

    def recall_texts(
        self,
        campaign_id: str,
        phase: str = "research",
    ) -> list[str]:
        """Convenience: prior observations as plain strings."""
        return [o.text for o in self.recall(campaign_id, phase)]

    @staticmethod
    def _parse(block: str) -> list[PriorObservation]:
        """Parse the markdown context block into observations."""
        observations: list[PriorObservation] = []
        if not block or "no prior memory" in block.lower():
            return observations
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("- ") and len(stripped) > 2:
                observations.append(PriorObservation(
                    text=stripped[2:].strip(),
                    source="memory-lake",
                ))
        return observations
