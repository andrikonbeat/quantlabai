"""AgentMemoryManager — Engram-backed persistence and cross-agent query for agent decisions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AgentMemoryManager:
    """Persists and queries agent memory via Engram and Knowledge Lake.

    Args:
        knowledge_root: Root path for Knowledge Lake agent-memory directories.
        engram_save_fn: Optional async function for Engram persistence.
        engram_search_fn: Optional async function for Engram search.
        retention_days: Retention period per agent topic (default 90 days).
    """

    def __init__(
        self,
        knowledge_root: str | Path = "knowledge",
        engram_save_fn: Any = None,
        engram_search_fn: Any = None,
        retention_days: int = 90,
    ) -> None:
        self._knowledge_root = Path(knowledge_root)
        self._engram_save_fn = engram_save_fn
        self._engram_search_fn = engram_search_fn
        self._retention_days = retention_days

    # ── Path helpers ─────────────────────────────────────────────────────────────

    def _agent_memory_path(self, agent_name: str, campaign_id: str) -> Path:
        return self._knowledge_root / "agent-memory" / agent_name / campaign_id

    def _topic_key(self, agent_name: str, campaign_id: str) -> str:
        return f"agent/{agent_name}/{campaign_id}"

    # ── Public API ───────────────────────────────────────────────────────────────

    async def save_decision(
        self,
        agent: str,
        campaign: str,
        decision: dict[str, Any],
        *,
        phase: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Persist a single agent decision to Engram and Knowledge Lake.

        Args:
            agent: Agent name (e.g. ``"research-agent"``).
            campaign: Campaign identifier.
            decision: Decision dict to persist. Missing timestamp/agent_name/campaign_id
                are injected automatically.
            phase: Optional phase name recorded on the decision (REQ-102).
            config: Optional phase config recorded on the decision (REQ-102).

        The decision is privacy-scrubbed (REQ-107) before EITHER store: the
        lake record and the Engram content both carry only scrubbed values.
        """
        decision.setdefault(
            "timestamp", datetime.now(timezone.utc).isoformat()
        )
        decision.setdefault("agent_name", agent)
        decision.setdefault("campaign_id", campaign)
        if phase is not None:
            decision.setdefault("phase", phase)
        if config is not None:
            decision.setdefault("config", config)

        # REQ-107: field-scoped deny-list scrub before any persistence.
        from quantlab.knowledge.privacy import PrivacyScrubber

        decision = PrivacyScrubber().scrub(decision)

        # Engram persistence
        if self._engram_save_fn is not None:
            topic_key = self._topic_key(agent, campaign)
            content = (
                "**What**: Agent {agent} recorded a decision\n"
                "**When**: {timestamp}\n"
                "**Campaign**: {campaign}\n"
                "**Decision**: {decision}"
            ).format(
                agent=agent,
                timestamp=decision.get("timestamp"),
                campaign=campaign,
                decision=decision,
            )
            try:
                await self._engram_save_fn(
                    title=f"decision/{agent}/{campaign}",
                    type="decision",
                    scope="project",
                    topic_key=topic_key,
                    content=content,
                    capture_prompt=False,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("AgentMemoryManager Engram save failed: %s", exc)

        # Knowledge Lake persistence
        memory_path = self._agent_memory_path(agent, campaign)
        memory_path.mkdir(parents=True, exist_ok=True)
        memory_file = memory_path / "memory.yaml"
        import yaml  # noqa: F811
        existing: list[dict[str, Any]] = []
        if memory_file.exists():
            try:
                existing = yaml.safe_load(memory_file.read_text(encoding="utf-8")) or []
                if not isinstance(existing, list):
                    existing = [existing]
            except Exception:
                existing = []
        existing.append(decision)
        memory_file.write_text(
            yaml.dump(existing, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    async def load_memory(
        self,
        agent: str,
        campaign: str,
    ) -> list[dict[str, Any]]:
        """Load agent memory for a given agent and campaign.

        Tries Knowledge Lake first, then falls back to Engram search.

        Args:
            agent: Agent name.
            campaign: Campaign identifier.

        Returns:
            List of decision dicts.
        """
        # Knowledge Lake first
        memory_file = self._agent_memory_path(agent, campaign) / "memory.yaml"
        if memory_file.exists():
            import yaml

            try:
                data = yaml.safe_load(memory_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return [data]
            except Exception:
                pass

        # Fallback to Engram
        if self._engram_search_fn is not None:
            topic_key = self._topic_key(agent, campaign)
            try:
                results = await self._engram_search_fn(
                    topic_key=topic_key,
                    query="",
                )
                if isinstance(results, list):
                    return [r.get("content", "") for r in results]
            except Exception as exc:  # noqa: BLE001
                logger.warning("AgentMemoryManager Engram search failed: %s", exc)

        return []

    async def query_cross_agent(
        self,
        pattern: str,
        agent: str | None = None,
        campaign: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Query memories across agents by pattern.

        Args:
            pattern: Text pattern to search for (case-insensitive).
            agent: Optional agent name filter.
            campaign: Optional campaign filter.

        Returns:
            Dict mapping ``agent_name`` to list of matching decision dicts.
        """
        results: dict[str, list[dict[str, Any]]] = {}

        # Knowledge Lake agent-memory directories
        memory_root = self._knowledge_root / "agent-memory"
        if not memory_root.exists():
            return results

        agents_to_search = [agent] if agent else [
            d.name for d in memory_root.iterdir() if d.is_dir()
        ]

        search_lower = pattern.lower()
        for agent_name in agents_to_search:
            agent_dir = memory_root / agent_name
            if not agent_dir.is_dir():
                continue

            campaigns_to_search = [campaign] if campaign else [
                d.name for d in agent_dir.iterdir() if d.is_dir()
            ]

            for camp in campaigns_to_search:
                camp_dir = agent_dir / camp
                memory_file = camp_dir / "memory.yaml"
                if not memory_file.exists():
                    continue

                import yaml

                try:
                    decisions = yaml.safe_load(
                        memory_file.read_text(encoding="utf-8")
                    ) or []
                    if not isinstance(decisions, list):
                        decisions = [decisions]
                except Exception:
                    continue

                matched = []
                for dec in decisions:
                    if search_lower in str(dec).lower():
                        dec.setdefault("agent_name", agent_name)
                        dec.setdefault("campaign_id", camp)
                        matched.append(dec)

                if matched:
                    results[agent_name] = matched

        return results
