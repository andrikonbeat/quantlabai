"""SQX CLI integration for QuantLab AI.

Provides the real CLI wrapper for dispatching CFX campaigns to a live
SQX daemon via its HTTP command API.
"""

from quantlab.sqx.cli_wrapper import dispatch_campaign

__all__ = ["dispatch_campaign"]
