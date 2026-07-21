"""CFX archive error hierarchy.

All errors inherit from QuantLabError for catch-all handling
while allowing specific error types to be caught individually.
"""

from quantlab.tools.exceptions import QuantLabError


class CfxNotFoundError(QuantLabError):
    """Raised when the requested .cfx file does not exist."""


class CfxCorruptError(QuantLabError):
    """Raised when a .cfx archive is not a valid ZIP or contains corrupt XML."""


class CfxParseError(QuantLabError):
    """Raised when a .cfx file violates the expected schema."""


class VersionError(QuantLabError):
    """Raised when a .cfx archive uses an unsupported schema version."""
