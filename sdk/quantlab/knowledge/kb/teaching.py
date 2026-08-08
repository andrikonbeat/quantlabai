"""KB teaching-table rendering (REQ-205).

``build_teaching_table`` renders the structured teaching table
``config_reviewer`` must return per configured parameter (REQ-205): tab/
section, parameter, what-it-does and how-it-works-in-SQX, quant-trading role,
chosen config, why, and for-what. The same table is injected into campaign
prompts so agents see KB guidance alongside the prior-context block
(REQ-203/204).
"""

from __future__ import annotations

from typing import Sequence

from quantlab.knowledge.kb.models import KbParameter

# REQ-205 table columns: tab/section, parameter, what-it-does, how-it-works
# in SQX, quant-trading role, chosen config, why, and for-what.
TABLE_HEADERS: tuple[str, ...] = (
    "Tab / Section",
    "Parameter",
    "What it does",
    "How it works in SQX",
    "Quant trading role",
    "Chosen config",
    "Why",
    "For what",
)

EMPTY_TABLE_NOTE = "No KB parameters to teach."


def _cell(value: object) -> str:
    """Normalize a table cell, escaping pipes for markdown."""
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def build_teaching_table(parameters: Sequence[KbParameter]) -> str:
    """Render a markdown teaching table for the given KB parameters (REQ-205).

    Args:
        parameters: The KB entries for the configured parameters.

    Returns:
        A markdown table (header + separator + one row per parameter). When
        ``parameters`` is empty, a single placeholder line is returned — the
        reviewer's summary still emits a stable section.
    """
    if not parameters:
        return EMPTY_TABLE_NOTE

    lines = [
        "| " + " | ".join(TABLE_HEADERS) + " |",
        "|" + "---|" * len(TABLE_HEADERS),
    ]
    for param in parameters:
        rec = param.small_account_recommendation
        chosen = rec.recommended_value if rec is not None else param.default
        why = rec.reason if rec is not None else param.why_choose
        for_what = param.when_choose
        row = (
            f"{param.tab} / {param.section}",
            param.name,
            param.what_it_does,
            param.how_it_works_in_sqx,
            param.quant_trading_role,
            chosen,
            why,
            for_what,
        )
        lines.append("| " + " | ".join(_cell(value) for value in row) + " |")
    return "\n".join(lines)
