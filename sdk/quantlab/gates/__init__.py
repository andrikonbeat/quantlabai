"""QuantLab multi-agent gate system.

Provides human approval gates with async callback protocol,
configurable timeouts, fallback policies, notification hooks,
and Engram audit logging.
"""

from quantlab.gates.models import (
    DEFAULT_GATE_POLICIES,
    FallbackPolicy,
    GateContext,
    GateDecision,
    GateDecisionAction,
    GatePolicyConfig,
    HUMAN_GATE_IDS,
)
from quantlab.gates.orchestrator import HumanGateOrchestrator
from quantlab.gates.notifiers import (
    ConsoleNotifier,
    EmailNotifier,
    Notifier,
    SlackNotifier,
    WebhookNotifier,
)

__all__ = [
    "DEFAULT_GATE_POLICIES",
    "FallbackPolicy",
    "GateContext",
    "GateDecision",
    "GateDecisionAction",
    "GatePolicyConfig",
    "HUMAN_GATE_IDS",
    "HumanGateOrchestrator",
    "ConsoleNotifier",
    "EmailNotifier",
    "Notifier",
    "SlackNotifier",
    "WebhookNotifier",
]
