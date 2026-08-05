"""Campaign orchestration primitives (REQ-01, REQ-37).

``flow`` owns the canonical 14-phase lifecycle constant and the
flow-integrity assertion enforced at campaign start and after any
harness change (REQ-37).
"""

from quantlab.campaign.flow import PHASES, FlowIntegrityError, assert_flow

__all__ = ["PHASES", "FlowIntegrityError", "assert_flow"]
