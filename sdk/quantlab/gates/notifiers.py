"""Pluggable notification adapters for human gates.

Provides email, Slack webhook, generic webhook, and console notifiers.
All ``send()`` methods are async. Failures are logged but never raised
to the caller — a notification failure must NEVER block a gate.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)


class Notifier(ABC):
    """Abstract notification channel."""

    @abstractmethod
    async def send(self, message: str, **kwargs: Any) -> None:
        """Send a notification message.

        Args:
            message: Human-readable notification body.
            **kwargs: Extra payload fields injected by the caller
                      (e.g. gate_id, campaign_id).
        """


class ConsoleNotifier(Notifier):
    """Logs notifications to the application log stream."""

    async def send(self, message: str, **kwargs: Any) -> None:  # noqa: ARG002
        logger.info("[GATE NOTIFICATION] %s", message)


class WebhookNotifier(Notifier):
    """Posts JSON payload to a generic HTTP webhook endpoint."""

    def __init__(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout

    async def send(self, message: str, **kwargs: Any) -> None:
        payload: dict[str, Any] = {"text": message}
        payload.update(kwargs)
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.url,
                    json=payload,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ):
                    logger.info("Webhook notification sent to %s", self.url)
        except ImportError:
            logger.info("[WEBHOOK NOTIFICATION] url=%s payload=%s", self.url, payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Webhook notification to %s failed: %s", self.url, exc)


class EmailNotifier(Notifier):
    """Sends email via SMTP using ``aiosmtplib`` when available."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        from_addr: str,
        to_addrs: list[str],
        *,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.username = username
        self.password = password

    async def send(
        self,
        message: str,
        *,
        subject: str = "Gate Notification",
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        try:
            import aiosmtplib
            from email.message import EmailMessage

            msg = EmailMessage()
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)
            msg["Subject"] = subject
            msg.set_content(message)
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.username,
                password=self.password,
            )
            logger.info("Email notification sent to %s", self.to_addrs)
        except ImportError:
            logger.info(
                "[EMAIL NOTIFICATION] to=%s subject=%s body=%s",
                self.to_addrs,
                subject,
                message,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Email notification failed: %s", exc)


class SlackNotifier(Notifier):
    """Posts a message to a Slack incoming webhook."""

    def __init__(self, webhook_url: str, *, timeout: float = 10.0) -> None:
        self.webhook_url = webhook_url
        self.timeout = timeout

    async def send(self, message: str, **kwargs: Any) -> None:
        payload: dict[str, Any] = {"text": message}
        payload.update(kwargs)
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ):
                    logger.info("Slack notification posted to %s", self.webhook_url)
        except ImportError:
            logger.info("[SLACK NOTIFICATION] %s", payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Slack notification to %s failed: %s", self.webhook_url, exc)


class MobilePushNotifier(Notifier):
    """Mobile push channel registered in ``NotifierDispatcher`` (REQ-35).

    Delivers alerts to a mobile push endpoint. An async ``transport`` may be
    injected for deterministic tests; the default transport posts the JSON
    payload to the endpoint via ``aiohttp``. Delivery failures are logged at
    ``WARNING`` and never raised — a push failure must NOT break the alert
    pipeline (REQ-35 scenario 2).
    """

    def __init__(
        self,
        endpoint: str,
        *,
        transport: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.endpoint = endpoint
        self.headers = headers or {}
        self.timeout = timeout
        self._transport = transport

    async def send(self, message: str, **kwargs: Any) -> None:
        payload: dict[str, Any] = {"text": message}
        payload.update(kwargs)
        try:
            if self._transport is not None:
                await self._transport(self.endpoint, payload)
                logger.info("Mobile push notification sent to %s", self.endpoint)
                return
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    json=payload,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ):
                    logger.info("Mobile push notification sent to %s", self.endpoint)
        except ImportError:
            logger.info(
                "[MOBILE PUSH NOTIFICATION] endpoint=%s payload=%s",
                self.endpoint,
                payload,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Mobile push notification to %s failed: %s", self.endpoint, exc
            )
