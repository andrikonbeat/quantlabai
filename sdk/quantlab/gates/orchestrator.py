"""HumanGateOrchestrator — central async approval hub for all 5 human gates.

Responsibilities:
- Manage gate policies (timeout, fallback, escalation contacts).
- Dispatch notifications before gate opens and after decision.
- Invoke registered callbacks with configurable timeout.
- Apply fallback on timeout or callback failure.
- Persist every decision to Engram for audit.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict

from quantlab.gates.engram_logger import record_gate_decision
from quantlab.gates.models import (
    DEFAULT_GATE_POLICIES,
    FallbackPolicy,
    GateDecision,
    GateDecisionAction,
    GatePolicyConfig,
)
from quantlab.gates.notifiers import ConsoleNotifier, Notifier

logger = logging.getLogger(__name__)

# Gate-specific: async callback receives ``gate_context: dict[str, Any]`` and returns
# a ``GateDecision`` from ``quantlab.gates.models``.
GateCallback = Callable[[dict[str, Any]], Awaitable[GateDecision]]


class HumanGateOrchestrator:
    """Manages 5 human approval gates.

    Args:
        engram_save_fn: Optional async function for Engram persistence.
            Signature: ``async fn(title, type, scope, topic_key, content)``.
    """

    def __init__(self, engram_save_fn: Any = None) -> None:
        self._engram_save_fn = engram_save_fn
        self._callbacks: Dict[str, GateCallback] = {}
        self._notifiers: Dict[str, Notifier] = {}
        self._policies: Dict[str, GatePolicyConfig] = dict(DEFAULT_GATE_POLICIES)
        self._default_notifier = ConsoleNotifier()

    # ── Registration ────────────────────────────────────────────────────────────

    def register_callback(self, gate_id: str, callback: GateCallback) -> None:
        """Register an async callback that resolves a gate decision.

        Args:
            gate_id: One of the 5 ``HUMAN_*`` gate identifiers.
            callback: Async function receiving context dict, returning
                      ``GateDecision``.
        """
        self._callbacks[gate_id] = callback

    def register_notifier(self, channel: str, notifier: Notifier) -> None:
        """Override the notification channel for ``channel``.

        Args:
            channel: Channel name (e.g. ``"email"``, ``"slack"``).
            notifier: ``Notifier`` implementation.
        """
        self._notifiers[channel] = notifier

    def set_policy(self, gate_id: str, policy: GatePolicyConfig) -> None:
        """Override the policy for a single gate.

        Args:
            gate_id: Gate identifier.
            policy: New ``GatePolicyConfig`` for this gate.
        """
        self._policies[gate_id] = policy

    # ── Core protocol ───────────────────────────────────────────────────────────

    async def on_gate(self, gate_id: str, ctx: dict[str, Any]) -> GateDecision:
        """Invoke the human approval protocol for ``gate_id``.

        Flow:
        1. Notify configured channels that the gate is pending.
        2. Await the registered callback with the gate's timeout.
        3. Apply the configured fallback on timeout or callback error.
        4. Notify configured channels of the final decision.
        5. Persist the decision to Engram for audit.

        Args:
            gate_id: Gate identifier (e.g. ``"HUMAN_APPROVE_PORTFOLIO"``).
            ctx: Context dict describing the pipeline state, artifacts, and
                 campaign metadata.

        Returns:
            ``GateDecision`` — the resolved outcome of this gate.
        """
        policy = self._policies.get(gate_id, GatePolicyConfig(gate_id=gate_id))
        campaign_id = ctx.get("campaign_id", "")

        # Step 1: notify pending
        await self._notify_pending(gate_id, policy, campaign_id)

        # Step 2: resolve via callback or fallback
        callback = self._callbacks.get(gate_id)
        try:
            if callback is not None:
                decision = await asyncio.wait_for(
                    callback(ctx),
                    timeout=policy.timeout_hours * 3600,
                )
            else:
                # No callback registered — treat as immediate timeout
                raise asyncio.TimeoutError("No callback registered for gate")
        except asyncio.TimeoutError:
            logger.warning(
                "Gate '%s' timed out after %.1f h — applying fallback '%s'",
                gate_id,
                policy.timeout_hours,
                policy.fallback.value,
            )
            decision = self._apply_fallback(gate_id, policy)
        except Exception as exc:  # noqa: BLE001
            logger.error("Gate '%s' callback error: %s", gate_id, exc)
            decision = self._apply_fallback(gate_id, policy)

        # Step 3: notify decision
        await self._notify_decision(gate_id, decision, campaign_id)

        # Step 4: Engram audit
        if self._engram_save_fn is not None:
            await record_gate_decision(
                self._engram_save_fn,
                gate_id,
                decision.model_dump() if hasattr(decision, "model_dump") else decision.__dict__,
                campaign_id,
                ctx,
            )

        return decision

    # ── Fallback logic ──────────────────────────────────────────────────────────

    def _apply_fallback(self, gate_id: str, policy: GatePolicyConfig) -> GateDecision:
        """Compute the fallback ``GateDecision`` for a timed-out gate."""
        if policy.fallback == FallbackPolicy.ABORT:
            action = GateDecisionAction.FALLBACK
            reason = f"ABORT fallback — pipeline stopped for {gate_id}"
        elif policy.fallback == FallbackPolicy.ESCALATE:
            action = GateDecisionAction.ESCALATE
            reason = (
                f"ESCALATE fallback — escalated to {policy.escalate_to}"
                if policy.escalate_to
                else f"ESCALATE fallback — external escalation required for {gate_id}"
            )
        elif policy.fallback == FallbackPolicy.HOLD:
            action = GateDecisionAction.FALLBACK
            reason = f"HOLD fallback — deployment queued for {gate_id}"
        else:  # CONTINUE
            action = GateDecisionAction.APPROVE
            reason = f"CONTINUE fallback — proceeding as approved for {gate_id}"

        return GateDecision(
            gate_id=gate_id,
            action=action,
            reason=reason,
            decided_by="system",
        )

    # ── Notifications ───────────────────────────────────────────────────────────

    async def _notify_pending(
        self, gate_id: str, policy: GatePolicyConfig, campaign_id: str
    ) -> None:
        message = (
            f"Gate pending: {gate_id} | campaign={campaign_id} | "
            f"timeout={policy.timeout_hours}h | fallback={policy.fallback.value}"
        )
        await self._send_notifications(policy.notifications, message)

    async def _notify_decision(
        self, gate_id: str, decision: GateDecision, campaign_id: str
    ) -> None:
        policy = self._policies.get(gate_id)
        channels = policy.notifications if policy else []
        message = (
            f"Gate decision: {gate_id} | campaign={campaign_id} | "
            f"action={decision.action.value} | reason={decision.reason}"
        )
        await self._send_notifications(channels, message)

    async def _send_notifications(self, channels: list[str], message: str) -> None:
        for channel in channels:
            notifier = self._notifiers.get(channel, self._default_notifier)
            try:
                await notifier.send(message)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Notification channel '%s' failed: %s", channel, exc)
