"""Contract tests for external library version pinning (T-6.2).

Verifies that ``ta`` meets the minimum required version at import time.
"""

from __future__ import annotations

import re
from importlib.metadata import version

MIN_TA_VERSION = "0.11.0"


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse a semantic version string into a tuple of ints."""
    parts = re.split(r"[^0-9]+", v)
    return tuple(int(p) for p in parts if p)


def test_ta_minimum_version_at_import() -> None:
    """GIVEN the ``ta`` package is installed
    WHEN its version is inspected at import time
    THEN the version is >= MIN_TA_VERSION (0.11.0).
    """
    installed = version("ta")
    assert _parse_version(installed) >= _parse_version(MIN_TA_VERSION), (
        f"ta version {installed} is below minimum {MIN_TA_VERSION}"
    )
