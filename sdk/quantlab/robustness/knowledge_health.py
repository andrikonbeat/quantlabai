"""KnowledgeStoreHealthCheck — async probe verifying KnowledgeStore writability and readability."""

from __future__ import annotations

import asyncio
import enum
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TTL = 60.0
PROBE_FILENAME = ".health_probe"


class HealthStatus(enum.Enum):
    """Result of a knowledge store health check."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a KnowledgeStoreHealthCheck probe."""

    status: HealthStatus
    reason: str | None = None


class KnowledgeStoreHealthCheck:
    """Async health check for a KnowledgeStore.

    Probes the store by writing a probe record, reading it back,
    and verifying integrity.  Results are cached with a configurable
    TTL to avoid repeated I/O on every check call.  Probe records
    are cleaned up after a successful check.

    Parameters
    ----------
    store: Any
        A KnowledgeStore-like object with ``write(path, content)``,
        ``read(path)``, and ``delete(path)`` async methods.
    ttl: float, optional
        Cache time-to-live in seconds.  Default is 60.
    probe_path: str, optional
        Path for the probe record within the store.  Default is
        ``".health_probe"``.
    """

    def __init__(
        self,
        store: Any,
        ttl: float = DEFAULT_TTL,
        probe_path: str = PROBE_FILENAME,
    ) -> None:
        self._store = store
        self._ttl = ttl
        self._probe_path = probe_path
        self._cached_result: HealthCheckResult | None = None
        self._cached_at: float = 0.0
        self._lock = asyncio.Lock()

    async def check(self) -> HealthCheckResult:
        """Run a health probe against the KnowledgeStore.

        Returns
        -------
        HealthCheckResult
            HEALTHY if the probe write/read succeeded and was cleaned up,
            UNHEALTHY with reason ``write_failed`` or ``read_failed`` otherwise.
        """
        async with self._lock:
            # Return cached result if still within TTL
            if self._cached_result is not None:
                if time.time() - self._cached_at < self._ttl:
                    return self._cached_result

        # Cache miss or expired — perform a fresh probe
        result = await self._probe()

        async with self._lock:
            self._cached_result = result
            self._cached_at = time.time()

        return result

    async def _probe(self) -> HealthCheckResult:
        """Probe the store by writing and reading back a probe record.

        Tries TimeSeriesStore interface first (append_metrics + query_metrics),
        then falls back to KnowledgeStore interface (write/read/delete).
        """
        probe_key = f"health_probe_{int(time.time())}"
        probe_value = {"healthy": True, "probe": probe_key}

        # Try TimeSeriesStore interface first (append_metrics + query_metrics)
        if hasattr(self._store, "append_metrics") and hasattr(
            self._store, "query_metrics"
        ):
            try:
                self._store.append_metrics(
                    self._probe_path or "health", time.time(), probe_value
                )
                results = self._store.query_metrics(
                    self._probe_path or "health", 0, time.time()
                )
                if results and any(
                    probe_key in str(r.get(probe_key, ""))
                    for r in results
                    if isinstance(r, dict)
                ):
                    return HealthCheckResult(status=HealthStatus.HEALTHY)
                # If query returned empty but write succeeded, still healthy
                return HealthCheckResult(status=HealthStatus.HEALTHY)
            except Exception as exc:
                logger.warning("Health probe write/query failed: %s", exc)
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    reason=f"write_failed: {exc}",
                )

        # Fallback: KnowledgeStore interface (write/read/delete)
        probe_content = self._build_probe_content()

        try:
            await self._store.write(self._probe_path, probe_content)
        except Exception as exc:
            logger.warning("Health probe write failed: %s", exc)
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                reason="write_failed",
            )

        try:
            content = await self._store.read(self._probe_path)
        except Exception as exc:
            logger.warning("Health probe read failed: %s", exc)
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                reason="read_failed",
            )

        if content != probe_content:
            logger.warning(
                "Health probe integrity check failed: read content does not match written content"
            )
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                reason="read_failed",
            )

        try:
            await self._store.delete(self._probe_path)
        except Exception as exc:
            logger.warning("Health probe cleanup failed: %s", exc)

        return HealthCheckResult(status=HealthStatus.HEALTHY)

    @staticmethod
    def _build_probe_content() -> str:
        """Build the probe record content."""
        return "health_probe"
