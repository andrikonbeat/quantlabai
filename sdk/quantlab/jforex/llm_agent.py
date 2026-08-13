"""LLMTechnicalAgent — reads exported strategy indicators and summarizes them.

Implements REQ-05 scenario "LLM agent reads indicators": given a
``quantlab-indicators-<strategy>.json`` export written by the packaged Java
helper, the agent builds a prompt from the timestamped indicator values and
asks an injectable LLM client for a technical analysis summary.

Failure mode (design): when the export is missing or corrupt the agent
returns an empty summary — it never crashes the pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from quantlab.jforex.exporter import (
    IndicatorExport,
    indicator_export_path,
    read_indicator_export,
)

logger = logging.getLogger(__name__)

#: Prefix of the fail-closed summary returned when no usable export exists.
EMPTY_SUMMARY_PREFIX = "No indicator data available"


class LLMTechnicalAgent:
    """Summarize exported JForex4 strategy indicators for an LLM.

    Args:
        llm_client: Async client exposing ``chat.completions.create(**kwargs)``
            (OpenAI-compatible). When omitted, the ``openai`` AsyncOpenAI
            client is constructed lazily on first use.
        model: Model identifier passed to the client.
        export_dir: Optional override of the export base directory.
    """

    def __init__(
        self,
        llm_client: Any | None = None,
        *,
        model: str = "gpt-4o-mini",
        export_dir: Optional[str | Path] = None,
    ) -> None:
        self._llm_client = llm_client
        self._model = model
        self._export_dir = export_dir

    @staticmethod
    def build_prompt(export: IndicatorExport) -> str:
        """Build the LLM prompt from an indicator export.

        Pure function — deterministic and directly testable (T4.4).

        Args:
            export: Parsed indicator export.

        Returns:
            Prompt text embedding strategy identity and each indicator
            name/value/timestamp line.
        """
        lines = [
            "You are a technical analysis assistant for QuantLab.",
            "",
            f"Strategy: {export.strategy}",
            f"Exported at: {export.exported_at.isoformat()}",
            "",
            "Latest indicator values:",
        ]
        for indicator in export.indicators:
            lines.append(
                f"- {indicator.name}: {indicator.value} "
                f"(at {indicator.timestamp.isoformat()})"
            )
        lines.extend(
            [
                "",
                "Provide a concise technical analysis summary of these "
                "indicator values, noting momentum, trend, and any "
                "divergences between indicators.",
            ]
        )
        return "\n".join(lines)

    async def analyze(self, strategy: str) -> str:
        """Analyze the exported indicators for *strategy*.

        Reads ``quantlab-indicators-<strategy>.json`` from the export
        directory, builds the prompt, and asks the LLM client for a summary.

        Fail-closed: a missing, corrupt, or schema-invalid export yields an
        empty summary (``EMPTY_SUMMARY_PREFIX ...``) and the LLM client is
        never invoked (design failure mode: "Indicator export missing → LLM
        agent receives empty summary, no crash").

        Returns:
            The LLM technical summary text, or the empty summary.
        """
        export_path = indicator_export_path(strategy, export_dir=self._export_dir)
        try:
            export = read_indicator_export(export_path)
        except ValueError as exc:
            logger.warning("LLMTechnicalAgent: %s", exc)
            return f"{EMPTY_SUMMARY_PREFIX} for strategy {strategy!r}"

        prompt = self.build_prompt(export)
        client = self._llm_client or self._default_client()
        response = await client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    def _default_client(self) -> Any:
        """Lazily construct the OpenAI async client (import deferred)."""
        from openai import AsyncOpenAI

        self._llm_client = AsyncOpenAI()
        return self._llm_client
