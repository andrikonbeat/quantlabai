"""QuantLab multi-agent gate system.

Provides human approval gates with async callback protocol,
configurable timeouts, fallback policies, notification hooks,
and Engram audit logging.
"""

from quantlab.gates.models import (
    DEFAULT_GATE_POLICIES,
    HUMAN_GATE_IDS,
    FallbackPolicy,
    GateContext,
    GateDecision,
    GateDecisionAction,
    GatePolicyConfig,
)
from quantlab.gates.notifiers import (
    ConsoleNotifier,
    EmailNotifier,
    Notifier,
    SlackNotifier,
    WebhookNotifier,
)
from quantlab.gates.orchestrator import HumanGateOrchestrator

__all__ = [
    "DEFAULT_GATE_POLICIES",
    "HUMAN_GATE_IDS",
    "ConsoleNotifier",
    "EmailNotifier",
    "FallbackPolicy",
    "GateContext",
    "GateDecision",
    "GateDecisionAction",
    "GatePolicyConfig",
    "HumanGateOrchestrator",
    "Notifier",
    "SlackNotifier",
    "WebhookNotifier",
]
