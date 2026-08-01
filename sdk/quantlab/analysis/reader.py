"""AnalysisReader — path resolution + databank delegate for strategies CSV."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from quantlab.readers.databank import read_strategies
from quantlab.tools.exceptions import ParseError

if TYPE_CHECKING:
    from quantlab.readers.models import StrategySummary


class AnalysisReader:
    """Thin wrapper that resolves the strategies export path and delegates
    to ``read_strategies`` from ``quantlab.readers.databank``.

    Usage::

        reader = AnalysisReader()
        strategies = reader.parse("exports/strategies.csv")
    """

    def parse(self, path: str | Path) -> list[StrategySummary]:
        """Parse a strategies CSV into a list of ``StrategySummary`` models.

        Args:
            path: Path to the strategies CSV file.

        Returns:
            A list of ``StrategySummary`` models.

        Raises:
            ParseError: If the CSV is corrupted or cannot be read.
        """
        return read_strategies(path)
