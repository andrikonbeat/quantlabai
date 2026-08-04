"""Exceptions for the data package (REQ-12, D5)."""

from __future__ import annotations


class DataManagerError(Exception):
    """A data manager operation failed (sqcli missing, command error, timeout).

    Deliberately NOT a ``RuntimeError``: ``BuilderAgent._ensure_data``
    catches generic exceptions and wraps them as
    ``RuntimeError("Data pre-flight failed (orchestrated) ...")`` in
    orchestrated mode (REQ-13), and logs a non-blocking warning in legacy
    mode (REQ-11).
    """


class NotSupportedError(ValueError):
    """A datasource/operation outside the launch scope was requested (D5).

    Crypto, CSV, and yahoo datasources are deferred and MUST raise this
    clear error instead of being partially supported (REQ-12 scenario).
    """
