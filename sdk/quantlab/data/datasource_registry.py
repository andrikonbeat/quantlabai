"""Registry of DataManager datasource handlers (REQ-04).

Lets ``DataManager`` select a datasource by name (``datasource="jforex"``)
without breaking the existing ``dukascopy``/sqcli path (REQ-04 scenario 2).
Each handler owns the source-specific ensure/update operations; the shared
SQLite symbol cache and the public contract dicts stay in DataManager.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class DatasourceHandler(ABC):
    """Per-datasource operations consumed by DataManager.

    Subclasses implement the datasource-specific part of
    ``ensure_symbol``/``update_data``. The symbol name and the
    ensure/update semantics are owned by the handler so DataManager
    never hardcodes a datasource.
    """

    name: str = ""

    @abstractmethod
    def sqx_name(self, symbol: str, datatype: str) -> str:
        """Build the SQX symbol name, validating the symbol for this source."""

    @abstractmethod
    async def ensure(self, symbol: str, datatype: str, sqx_name: str) -> None:
        """Make historical data available; raise when the source cannot."""

    @abstractmethod
    async def update(self, symbol: str, datatype: str, sqx_name: str) -> None:
        """Refresh historical data; raise when the source cannot."""


class DatasourceRegistry:
    """Maps lowercase datasource names to :class:`DatasourceHandler` instances."""

    def __init__(self) -> None:
        self._handlers: dict[str, DatasourceHandler] = {}

    def register(self, handler: DatasourceHandler) -> None:
        """Register a handler under its lowercased name."""
        self._handlers[handler.name.lower()] = handler

    def get(self, name: str) -> DatasourceHandler | None:
        """Return the handler registered under *name*, or ``None``."""
        return self._handlers.get(name.lower())

    def names(self) -> list[str]:
        """Return every registered name, sorted."""
        return sorted(self._handlers)
