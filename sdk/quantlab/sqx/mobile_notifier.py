"""Mobile Notifier — sends campaign events to mobile devices via webhook/ntfy/Telegram (C6).

This module provides a unified notification interface for sending campaign
events (WARNING/CRITICAL) to mobile devices. Supports multiple backends:

- ntfy.sh (self-hosted or cloud)
- Telegram Bot API
- Generic webhook (for custom integrations)
- Pushover (optional)

Features:
- Deduplication: same event fingerprint within window only notifies once
- Quiet hours: respects user-defined quiet hours
- Severity filtering: only notify on WARNING/CRITICAL
- Template-based message formatting
- Graceful degradation (never crashes monitor)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from typing import Any, Literal, Optional

import httpx

from quantlab.sqx.campaign_monitor import WatcherEvent

logger = logging.getLogger(__name__)


# ── Data Models ─────────────────────────────────────────────────────────────


@dataclass
class NotificationConfig:
    """Configuration for a notification backend."""

    # Backend type
    backend: Literal["ntfy", "telegram", "webhook", "pushover"] = "ntfy"

    # Backend-specific config
    ntfy_topic: str = ""          # ntfy topic name
    ntfy_server: str = "https://ntfy.sh"  # ntfy server URL

    telegram_bot_token: str = ""  # Telegram bot token
    telegram_chat_id: str = ""    # Telegram chat ID

    webhook_url: str = ""         # Generic webhook URL
    webhook_headers: dict[str, str] = field(default_factory=dict)

    pushover_user_key: str = ""   # Pushover user key
    pushover_api_token: str = ""  # Pushover app token

    # Filtering
    min_severity: Literal["INFO", "WARNING", "CRITICAL"] = "WARNING"
    enabled_event_types: list[str] | None = None  # None = all

    # Deduplication
    dedup_window_sec: int = 300   # Seconds to dedupe same fingerprint
    dedup_max_entries: int = 1000 # Max entries in dedup cache

    # Quiet hours
    quiet_hours_start: time = time(22, 0)  # 22:00
    quiet_hours_end: time = time(7, 0)     # 07:00
    quiet_hours_timezone: str = "UTC"      # Timezone for quiet hours

    # Template
    template: str = (
        "[{severity}] {campaign_id} {event_type}: {details_summary}"
    )

    def is_quiet_hour(self, dt: datetime | None = None) -> bool:
        """Check if current time is within quiet hours."""
        if dt is None:
            dt = datetime.now(UTC)
        # Convert to target timezone if needed
        # For simplicity, assume UTC; extend with pytz/zoneinfo if needed
        current = dt.time()
        if self.quiet_hours_start <= self.quiet_hours_end:
            return self.quiet_hours_start <= current <= self.quiet_hours_end
        else:
            # Overnight quiet hours (e.g., 22:00 - 07:00)
            return current >= self.quiet_hours_start or current <= self.quiet_hours_end


@dataclass
class NotificationPayload:
    """Payload for a single notification."""

    campaign_id: str
    event_type: str
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    details: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def fingerprint(self) -> str:
        """Generate deduplication fingerprint."""
        # Hash of campaign_id + event_type + severity + key details
        key_parts = [
            self.campaign_id,
            self.event_type,
            self.severity,
            str(sorted(self.details.items())),
        ]
        return hashlib.sha256("|".join(key_parts).encode()).hexdigest()[:16]

    def format_message(self, template: str) -> str:
        """Format notification message using template."""
        details_summary = ", ".join(
            f"{k}: {v}" for k, v in list(self.details.items())[:3]
        )
        return template.format(
            severity=self.severity,
            campaign_id=self.campaign_id,
            event_type=self.event_type,
            details_summary=details_summary,
            timestamp=self.timestamp,
        )


# ── Abstract Notifier Interface ───────────────────────────────────────────


class BaseNotifier(ABC):
    """Abstract base class for notification backends."""

    @abstractmethod
    async def send(
        self,
        payload: NotificationPayload,
        config: NotificationConfig,
    ) -> bool:
        """Send a notification.

        Args:
            payload: The notification payload
            config: Backend configuration

        Returns:
            True if sent successfully, False otherwise
        """
        ...

    def should_notify(
        self,
        payload: NotificationPayload,
        config: NotificationConfig,
    ) -> bool:
        """Check if notification should be sent based on filters."""
        # Severity filter
        severity_order = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}
        if severity_order.get(payload.severity, 0) < severity_order.get(config.min_severity, 1):
            return False

        # Event type filter
        if config.enabled_event_types and payload.event_type not in config.enabled_event_types:
            return False

        return True

    def format_message(self, payload: NotificationPayload, config: NotificationConfig) -> str:
        """Format notification message using config template."""
        return payload.format_message(config.template)


# ── Concrete Notifier Implementations ─────────────────────────────────────


class NtfyNotifier(BaseNotifier):
    """ntfy.sh notifier (self-hosted or cloud)."""

    async def send(
        self,
        payload: NotificationPayload,
        config: NotificationConfig,
    ) -> bool:
        if not self.should_notify(payload, config):
            return False

        if config.is_quiet_hour():
            logger.debug("ntfy: quiet hours, skipping notification")
            return False

        if not config.ntfy_topic:
            logger.warning("ntfy: no topic configured")
            return False

        url = f"{config.ntfy_server.rstrip('/')}/{config.ntfy_topic}"
        headers = {
            "Title": f"QuantLab: {payload.severity} - {payload.event_type}",
            "Priority": "high" if payload.severity == "CRITICAL" else "default",
            "Tags": "warning" if payload.severity == "WARNING" else "rotating_light",
        }

        message = self.format_message(payload, config)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    content=message,
                    headers=headers,
                )
                resp.raise_for_status()
                return True
        except Exception as exc:
            logger.warning("ntfy send failed: %s", exc)
            return False


class TelegramNotifier(BaseNotifier):
    """Telegram Bot API notifier."""

    async def send(
        self,
        payload: NotificationPayload,
        config: NotificationConfig,
    ) -> bool:
        if not self.should_notify(payload, config):
            return False

        if config.is_quiet_hour():
            logger.debug("telegram: quiet hours, skipping notification")
            return False

        if not config.telegram_bot_token or not config.telegram_chat_id:
            logger.warning("telegram: missing bot token or chat ID")
            return False

        url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
        message = self.format_message(payload, config)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    json={
                        "chat_id": config.telegram_chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
                resp.raise_for_status()
                return True
        except Exception as exc:
            logger.warning("telegram send failed: %s", exc)
            return False


class WebhookNotifier(BaseNotifier):
    """Generic webhook notifier (for custom integrations)."""

    async def send(
        self,
        payload: NotificationPayload,
        config: NotificationConfig,
    ) -> bool:
        if not self.should_notify(payload, config):
            return False

        if config.is_quiet_hour():
            logger.debug("webhook: quiet hours, skipping notification")
            return False

        if not config.webhook_url:
            logger.warning("webhook: no URL configured")
            return False

        message = self.format_message(payload, config)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    config.webhook_url,
                    json={
                        "campaign_id": payload.campaign_id,
                        "event_type": payload.event_type,
                        "severity": payload.severity,
                        "details": payload.details,
                        "timestamp": payload.timestamp,
                        "message": self.format_message(payload, config),
                    },
                    headers=config.webhook_headers,
                    timeout=10.0,
                )
                resp.raise_for_status()
                return True
        except Exception as exc:
            logger.warning("webhook send failed: %s", exc)
            return False


class PushoverNotifier(BaseNotifier):
    """Pushover notifier (fallback)."""

    async def send(
        self,
        payload: NotificationPayload,
        config: NotificationConfig,
    ) -> bool:
        if not self.should_notify(payload, config):
            return False

        if config.is_quiet_hour():
            logger.debug("pushover: quiet hours, skipping notification")
            return False

        if not config.pushover_user_key or not config.pushover_api_token:
            logger.warning("pushover: missing user key or API token")
            return False

        url = "https://api.pushover.net/1/messages.json"
        message = self.format_message(payload, config)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    data={
                        "user": config.pushover_user_key,
                        "token": config.pushover_api_token,
                        "message": message,
                        "title": f"QuantLab: {payload.severity} - {payload.event_type}",
                        "priority": 1 if payload.severity == "CRITICAL" else 0,
                    },
                )
                resp.raise_for_status()
                return True
        except Exception as exc:
            logger.warning("pushover send failed: %s", exc)
            return False


# ── Notifier Registry & Manager ───────────────────────────────────────────


class NotifierRegistry:
    """Registry of available notifier backends."""

    _backends: dict[str, type[BaseNotifier]] = {
        "ntfy": NtfyNotifier,
        "telegram": TelegramNotifier,
        "webhook": WebhookNotifier,
        "pushover": PushoverNotifier,
    }

    @classmethod
    def register(cls, name: str, notifier_class: type[BaseNotifier]) -> None:
        cls._backends[name] = notifier_class

    @classmethod
    def create(cls, backend: str) -> BaseNotifier:
        if backend not in cls._backends:
            raise ValueError(f"Unknown notifier backend: {backend}")
        return cls._backends[backend]()

    @classmethod
    def available(cls) -> list[str]:
        return list(cls._backends.keys())


class NotificationManager:
    """Manages multiple notification backends with deduplication and quiet hours."""

    def __init__(self, configs: list[NotificationConfig] | None = None):
        self.configs = configs or []
        self._notifiers: list[BaseNotifier] = []
        self._dedup_cache: dict[str, float] = {}  # fingerprint -> timestamp
        self._dedup_max_entries: int = 1000
        self._dedup_window_sec: int = 300

        for config in self.configs:
            try:
                notifier = NotifierRegistry.create(config.backend)
                self._notifiers.append((notifier, config))
            except ValueError as exc:
                logger.warning("Unknown notifier backend: %s", exc)

    def add_config(self, config: NotificationConfig) -> None:
        """Add a notification config."""
        self.configs.append(config)
        try:
            notifier = NotifierRegistry.create(config.backend)
            self._notifiers.append((notifier, config))
        except ValueError as exc:
            logger.warning("Unknown notifier backend: %s", exc)

    def send(
        self,
        campaign_id: str,
        event_type: str,
        severity: Literal["INFO", "WARNING", "CRITICAL"],
        details: dict[str, Any],
    ) -> None:
        """Send a notification through all configured backends.

        Handles deduplication and quiet hours automatically.
        """
        payload = NotificationPayload(
            campaign_id=campaign_id,
            event_type=event_type,
            severity=severity,
            details=details,
        )

        fingerprint = payload.fingerprint()
        now = datetime.now().timestamp()

        # Deduplication check
        if fingerprint in self._dedup_cache:
            last_sent = self._dedup_cache[fingerprint]
            if now - last_sent < 300:  # Default 5 min dedup window
                logger.debug("Notification deduplicated: %s", fingerprint)
                return

        # Update dedup cache
        self._dedup_cache[fingerprint] = now
        # Prune old entries
        if len(self._dedup_cache) > 1000:
            cutoff = now - 3600
            self._dedup_cache = {
                k: v for k, v in self._dedup_cache.items() if v > cutoff
            }

        # Send to all notifiers
        for notifier, config in self._notifiers:
            if not notifier.should_notify(payload, config):
                continue
            if config.is_quiet_hour():
                logger.debug("Quiet hours for %s, skipping", config.backend)
                continue

            try:
                asyncio.create_task(self._send_async(notifier, payload, config))
            except Exception as exc:
                logger.warning("Failed to schedule notification: %s", exc)

    async def _send_async(
        self,
        notifier: BaseNotifier,
        payload: NotificationPayload,
        config: NotificationConfig,
    ) -> None:
        try:
            success = await notifier.send(payload, config)
            if success:
                logger.info("Notification sent via %s: %s %s",
                           type(notifier).__name__, severity, event_type)
            else:
                logger.warning("Notification failed via %s", type(notifier).__name__)
        except Exception as exc:
            logger.warning("Notifier %s failed: %s", type(notifier).__name__, exc)


# ── Convenience Functions ─────────────────────────────────────────────────


def create_notification_manager(
    ntfy_topic: str | None = None,
    telegram_bot_token: str | None = None,
    telegram_chat_id: str | None = None,
    webhook_url: str | None = None,
    webhook_headers: dict[str, str] | None = None,
) -> NotificationManager:
    """Create a NotificationManager with common backends configured."""
    configs = []

    if ntfy_topic:
        configs.append(NotificationConfig(
            backend="ntfy",
            ntfy_topic=ntfy_topic,
        ))

    if telegram_bot_token and telegram_chat_id:
        configs.append(NotificationConfig(
            backend="telegram",
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
        ))

    if webhook_url:
        configs.append(NotificationConfig(
            backend="webhook",
            webhook_url=webhook_url,
            webhook_headers=webhook_headers or {},
        ))

    return NotificationManager(configs)


# ── Integration with CampaignMonitor ──────────────────────────────────────

def attach_mobile_notifier(
    monitor: Any,  # CampaignMonitor or LLMGenerationMonitor
    notification_manager: NotificationManager,
) -> None:
    """Attach a notification manager to a monitor.

    The monitor must have a `_fanout_notify` method that accepts a WatcherEvent.
    """
    original_fanout = getattr(monitor, '_fanout_notify', None)

    def wrapped_fanout(event):
        # Call original fanout if exists
        if original_fanout:
            try:
                original_fanout(event)
            except Exception as exc:
                logger.warning("Original fanout failed: %s", exc)

        # Send to mobile
        notification_manager.send(
            campaign_id=event.campaign_id,
            event_type=event.event_type,
            severity=event.severity,
            details=event.details,
        )

    monitor._fanout_notify = wrapped_fanout
    logger.info("Mobile notifier attached to %s", type(monitor).__name__)


# ── Verdict Classification for Mobile (Dedup + Quiet Hours) ──────────────


@dataclass
class VerdictClassification:
    """Classification result for a verdict/notification."""

    should_notify: bool
    reason: str
    category: Literal["new", "duplicate", "quiet_hours", "severity_filter"]


class VerdictClassifier:
    """Classifies verdicts/notifications to avoid spam and respect quiet hours."""

    def __init__(
        self,
        dedup_window_sec: int = 300,
        quiet_hours_start: time = time(22, 0),
        quiet_hours_end: time = time(7, 0),
        severity_threshold: Literal["INFO", "WARNING", "CRITICAL"] = "WARNING",
    ):
        self.dedup_window_sec = dedup_window_sec
        self.quiet_hours_start = quiet_hours_start
        self.quiet_hours_end = quiet_hours_end
        self.severity_threshold = severity_threshold
        self._dedup_cache: dict[str, float] = {}

    def _is_quiet_hour(self) -> bool:
        now = datetime.now(UTC).time()
        if self.quiet_hours_start <= self.quiet_hours_end:
            return self.quiet_hours_start <= now <= self.quiet_hours_end
        else:
            return now >= self.quiet_hours_start or now <= self.quiet_hours_end

    def _get_fingerprint(self, event_type: str, severity: str, details: dict) -> str:
        key = f"{event_type}:{severity}:{sorted(details.items())}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def classify(
        self,
        event_type: str,
        severity: Literal["INFO", "WARNING", "CRITICAL"],
        details: dict[str, Any],
    ) -> VerdictClassification:
        """Classify a verdict/notification for mobile delivery."""
        # Severity filter
        severity_order = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}
        if severity_order.get(severity, 0) < severity_order.get(self.severity_threshold, 1):
            return VerdictClassification(
                should_notify=False,
                reason=f"Severity {severity} below threshold {self.severity_threshold}",
                category="severity_filter",
            )

        # Quiet hours check
        if self._is_quiet_hour():
            return VerdictClassification(
                should_notify=False,
                reason="Within quiet hours",
                category="quiet_hours",
            )

        # Deduplication
        fingerprint = self._get_fingerprint(event_type, severity, {})
        now = datetime.now().timestamp()
        last_sent = self._dedup_cache.get(fingerprint, 0)
        if now - last_sent < self.dedup_window_sec:
            return VerdictClassification(
                should_notify=False,
                reason=f"Duplicate within {self.dedup_window_sec}s window",
                category="duplicate",
            )

        # Update dedup cache
        self._dedup_cache[event_type] = now
        # Cleanup old entries
        cutoff = datetime.now().timestamp() - 3600
        self._dedup_cache = {k: v for k, v in self._dedup_cache.items() if v > cutoff}

        return VerdictClassification(
            should_notify=True,
            reason="New unique event",
            category="new",
        )

    def _get_fingerprint(self, event_type: str, severity: str, details: dict) -> str:
        """Generate fingerprint for deduplication."""
        key_parts = [
            event_type,
            severity,
            str(sorted(details.items())) if details else "",
        ]
        return hashlib.sha256("|".join(key_parts).encode()).hexdigest()[:16]


# ── Convenience: Attach to CampaignMonitor / LLMGenerationMonitor ───────────


def setup_mobile_notifications(
    monitor: Any,
    ntfy_topic: str | None = None,
    telegram_bot_token: str | None = None,
    telegram_chat_id: str | None = None,
    webhook_url: str | None = None,
    webhook_headers: dict[str, str] | None = None,
) -> NotificationManager:
    """Convenience function to attach mobile notifications to a monitor."""
    nm = create_notification_manager(
        ntfy_topic=ntfy_topic,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        webhook_url=webhook_url,
        webhook_headers=webhook_headers,
    )
    attach_mobile_notifier(monitor, nm)
    return nm