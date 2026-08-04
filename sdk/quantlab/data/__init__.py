"""Data collection and processing package.

WU-7 (REQ-12/REQ-13): exports the rebuilt Dukascopy-only ``DataManager``
(the component ``BuilderAgent._ensure_data`` consumes in orchestrated mode),
the ``SymbolRegistry`` + SQX naming helpers, and the data exceptions.
"""

from quantlab.data.data_manager import DataManager
from quantlab.data.exceptions import DataManagerError, NotSupportedError
from quantlab.data.symbol_registry import SymbolRegistry, resolve_symbol, u_symbol


def get_data_manager(**kwargs) -> DataManager:
    """Factory returning a configured :class:`DataManager`.

    Keyword arguments are forwarded to ``DataManager`` (e.g.
    ``sqx_install_path``, ``sqcli_path``, ``registry_path``).
    """
    return DataManager(**kwargs)


__all__ = [
    "DataManager",
    "DataManagerError",
    "NotSupportedError",
    "SymbolRegistry",
    "get_data_manager",
    "resolve_symbol",
    "u_symbol",
]
