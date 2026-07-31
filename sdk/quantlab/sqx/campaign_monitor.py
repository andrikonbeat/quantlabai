"""Campaign Monitor — background watcher for SQX daemon campaign progress.

Detects stalled or misconfigured campaigns by polling the SQX HTTP API at a
configurable interval, interpreting responses against config-aware baselines
(timeframe, WF/MC flags, expected generation output), and emitting structured
``WatcherEvent`` objects.

WARNING/CRITICAL events trigger either a registered callback or a
``rich.prompt.Confirm`` prompt. On user approval, the monitor dispatches
``-project action=stop`` via the existing HTTP API.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import time
import urllib.parse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Literal

import httpx

from quantlab.sqx.llm_generation_monitor import MonitorSnapshot

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────

_COMMAND_ENDPOINT = "/call?cmd="

# ── Data Models ─────────────────────────────────────────────────────────────


@dataclass
class WatcherEvent:
    """A structured event emitted by the CampaignMonitor.

    Attributes:
        timestamp: ISO 8601 UTC string of when the event was created.
        campaign_id: The campaign this event relates to.
        event_type: The category of event detected.
        severity: How serious the event is.
        details: Arbitrary key-value payload describing the event context.
    """

    timestamp: str
    campaign_id: str
    event_type: Literal[
        "startup_stall", "config_error", "zero_growth_stall",
        "campaign_complete", "excessive_rejection",
    ]
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    details: dict

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return asdict(self)


@dataclass
class BaselineConfig:
    """Computed baseline timing parameters for a campaign.

    All values are derived from the campaign config and are used by
    the poll-tick logic to detect stall patterns.
    """

    startup_grace_s: float
    expected_gen_time_s: float
    early_gen_multiplier: float
    early_gen_count: int = 3
    stall_polls_threshold: int = 9
    rejection_warn_gens: int = 3

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return asdict(self)


# ── Pure Helpers ────────────────────────────────────────────────────────────


def extract_results_count(status_text: str) -> int:
    """Parse the number of strategies generated from an SQX status response.

    Looks for a line containing *"Strategies generated"* followed by an
    integer. Returns 0 if the pattern is missing or unparseable.

    Args:
        status_text: Raw plain-text response from the SQX HTTP API.

    Returns:
        The strategy count found, or 0.
    """
    if not status_text:
        return 0

    m = re.search(r"Strategies\s+generated\s+(\d+)", status_text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except (ValueError, IndexError):
            return 0
    return 0


_DATABANK_RECORDS_RE = re.compile(
    r"^\s*(?P<name>.+?),\s*Records\s*:?\s*(?P<count>\d+)\s*$",
    re.IGNORECASE,
)


def parse_databank_counts(text: str | None) -> dict[str, int] | None:
    """Parse ``-databank action=list`` output into per-databank record counts.

    Tolerates both ``Results, Records: 3`` and ``Results, Records 3``
    (optional colon) line styles, any amount of surrounding whitespace, and
    unrelated header/footer lines (e.g. the mock's "List of available
    databanks" banner), which are skipped. When nothing parseable is found
    the counts are treated as unknown: this function logs a warning and
    returns ``None`` instead of raising.

    Args:
        text: Raw plain-text response from ``-databank action=list``.

    Returns:
        A mapping of databank name to record count, or ``None`` when the
        output is missing or unparseable.
    """
    if not text or not text.strip():
        logger.warning("Databank output missing/empty — counts treated as unknown")
        return None

    counts: dict[str, int] = {}
    for line in text.splitlines():
        m = _DATABANK_RECORDS_RE.match(line)
        if not m:
            continue
        try:
            counts[m.group("name").strip()] = int(m.group("count"))
        except (ValueError, IndexError):
            logger.warning(
                "Databank line unparseable (%r) — skipped", line.strip()
            )

    if not counts:
        logger.warning(
            "No databank record counts found in output — "
            "counts treated as unknown"
        )
        return None
    return counts


_KNOWN_ERROR_PATTERNS = [
    "Cannot start project",
    "config errors",
    "Error:",
    "Cannot get",
]


def extract_error_patterns(status_text: str) -> list[str]:
    """Scan an SQX status response for known error messages.

    Returns up to the first 3 lines that match any known error pattern.
    If no errors are found, returns an empty list.

    Args:
        status_text: Raw plain-text response from the SQX HTTP API.

    Returns:
        A list of matching error lines (at most 3).
    """
    if not status_text:
        return []

    errors: list[str] = []
    for line in status_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for pattern in _KNOWN_ERROR_PATTERNS:
            if pattern.lower() in stripped.lower():
                errors.append(stripped)
                break
        if len(errors) >= 3:
            break

    return errors


def _extract_generation_from_status(status_text: str) -> int:
    """Extract the current generation number from a status response.

    Tries, in order:
    1. ``Generation: N`` or ``In generation N``
    2. ``In databank N`` (proxy)
    Returns 0 if nothing matches.

    Args:
        status_text: Raw plain-text status response.

    Returns:
        Estimated generation number, or 0.
    """
    if not status_text:
        return 0

    # Try explicit generation line
    m = re.search(
        r"(?:Generation|In\s+generation)[:\s]+(\d+)",
        status_text,
        re.IGNORECASE,
    )
    if m:
        try:
            return int(m.group(1))
        except (ValueError, IndexError):
            pass

    # Fall back to "In databank N"
    m = re.search(r"In\s+databank\s+(\d+)", status_text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except (ValueError, IndexError):
            pass

    return 0


def _get_config_value(cfg: Any, key: str, default: Any = None) -> Any:
    """Extract a config value, handling dicts, objects, and enum types."""
    if isinstance(cfg, dict):
        val = cfg.get(key, default)
    else:
        val = getattr(cfg, key, default)
    if hasattr(val, "value"):
        return val.value
    return val


def compute_baseline(config: Any, poll_interval: float = 5.0) -> BaselineConfig:
    """Compute baseline timing parameters from campaign config.

    Args:
        config: A dict or object with keys/attrs for *timeframe*,
            *walk_forward*, *monte_carlo*, *generations*, and *population*.
        poll_interval: Seconds between status polls (default 5.0).

    Returns:
        A :class:`BaselineConfig` populated with derived values.
    """
    tf = str(_get_config_value(config, "timeframe", "H1"))
    wf = bool(_get_config_value(config, "walk_forward", True))
    mc = bool(_get_config_value(config, "monte_carlo", True))
    gens = int(_get_config_value(config, "generations", 80))
    pop = int(_get_config_value(config, "population", 200))

    # Startup grace: M1 gets 60s, others get 15s
    startup_grace = 60.0 if tf.upper() == "M1" else 15.0

    # Rough throughput: ~30s per gen baseline (pop * symbols / 500)
    # For simplicity we use pop * 2 / 500 scaling; if no WF/MC the
    # baseline is faster since fewer computations per generation.
    expected_gen = max(15.0, pop * gens / 500.0)

    # Early generations take longer when WF + MC are both enabled
    early_mult = 2.0 if (wf and mc) else 1.0

    # Stall threshold: ceil(gen_time / poll_interval) × 3
    stall_polls = max(3, math.ceil(expected_gen / poll_interval) * 3)

    # Rejection warning generations
    reject_gens = 3 if gens < 100 else 5

    return BaselineConfig(
        startup_grace_s=startup_grace,
        expected_gen_time_s=expected_gen,
        early_gen_multiplier=early_mult,
        early_gen_count=3,
        stall_polls_threshold=stall_polls,
        rejection_warn_gens=reject_gens,
    )


# ── CampaignMonitor ─────────────────────────────────────────────────────────


class CampaignMonitor:
    """Background watcher that polls an SQX daemon and detects stall patterns.

    Launch as an asyncio task alongside campaign execution. The monitor
    polls ``-project action=status`` at a configurable interval, analyses
    each response against config-aware baselines, and emits structured
    ``WatcherEvent`` objects.

    Args:
        campaign_id: The name/ID of the campaign being monitored.
        base_url: Base URL of the SQX HTTP API (e.g. ``http://127.0.0.1:5050``).
        baseline: Pre-computed :class:`BaselineConfig` for this campaign.
        poll_interval: Seconds between status polls (default 5.0).
        on_watcher_event: Optional callback invoked for every detected event.
            When ``None``, WARNING/CRITICAL events trigger a
            ``rich.prompt.Confirm`` prompt in CLI mode.
        http_timeout: HTTP request timeout in seconds (default 10.0).
        config: Optional raw campaign configuration (dict or object) used to
            build the baseline context for :meth:`current_snapshot`. May be
            ``None`` — the snapshot then carries only the derived baseline.
    """

    def __init__(
        self,
        campaign_id: str,
        base_url: str,
        baseline: BaselineConfig,
        poll_interval: float = 5.0,
        on_watcher_event: Callable[[WatcherEvent], None] | None = None,
        http_timeout: float = 10.0,
        config: Any | None = None,
    ) -> None:
        self._campaign_id = campaign_id
        self._base_url = base_url.rstrip("/")
        self._baseline = baseline
        self._poll_interval = poll_interval
        self._on_watcher_event = on_watcher_event
        self._http_timeout = http_timeout
        self._config = config

        # Internal state
        self._start_time: float = 0.0
        self._events: list[WatcherEvent] = []
        self._last_count: int = -1
        self._stall_polls: int = 0
        self._http_failures: int = 0
        self._stopped: bool = False
        self._client: httpx.AsyncClient | None = None
        self._emitted_excessive_rejection: bool = False
        # Databank observability state (surfaced via current_snapshot())
        self._last_status_text: str = ""
        self._databank_counts: dict[str, int] | None = None

    # ── Public API ──────────────────────────────────────────────────────

    async def run(self) -> list[WatcherEvent]:
        """Run the monitor loop until the campaign finishes or is cancelled.

        Returns:
            All :class:`WatcherEvent` objects collected during monitoring.
        """
        self._start_time = time.monotonic()
        self._events = []
        self._last_count = -1
        self._stall_polls = 0
        self._http_failures = 0
        self._stopped = False
        self._emitted_excessive_rejection = False
        self._last_status_text = ""
        self._databank_counts = None

        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            self._client = client
            try:
                await self._run_loop(client)
            except asyncio.CancelledError:
                logger.info(
                    "CampaignMonitor('%s') cancelled after %.1fs",
                    self._campaign_id,
                    time.monotonic() - self._start_time,
                )
            except Exception:
                logger.exception(
                    "CampaignMonitor('%s') failed", self._campaign_id,
                )
                raise
            finally:
                self._client = None

        return self._events

    async def cancel(self) -> None:
        """Signal the monitor loop to stop at the next poll cycle."""
        logger.info("CampaignMonitor('%s') cancel requested", self._campaign_id)
        self._stopped = True

    def current_snapshot(self) -> MonitorSnapshot:
        """Return a point-in-time observability snapshot for the LLM monitor.

        Provides the latest raw status text, the generated strategy count,
        per-databank record counts (``None`` when unknown or parse-failed),
        elapsed seconds, and the baseline context (raw config values merged
        with the derived :class:`BaselineConfig`). This is the snapshot
        provider consumed by
        :class:`~quantlab.sqx.llm_generation_monitor.LLMGenerationMonitor`.
        """
        return MonitorSnapshot(
            status_text=self._last_status_text or "",
            generated_count=max(0, self._last_count),
            databank_counts=self._databank_counts,
            elapsed_s=self._elapsed_s(),
            baseline=self._build_baseline_context(),
        )

    # ── Internal: Run Loop ──────────────────────────────────────────────

    async def _run_loop(self, client: httpx.AsyncClient) -> None:
        """Core poll loop — runs until the campaign finishes or is stopped."""
        while not self._stopped:
            status_text = await self._fetch_status(client)

            # ── Handle HTTP failures ──
            if status_text is None:
                self._http_failures += 1
                logger.warning(
                    "CampaignMonitor('%s') HTTP failure %d/3",
                    self._campaign_id,
                    self._http_failures,
                )
                if self._http_failures >= 3:
                    ev = self._make_event(
                        "config_error",
                        "WARNING",
                        {
                            "errors": ["3 consecutive HTTP failures"],
                            "elapsed_s": round(
                                time.monotonic() - self._start_time, 1
                            ),
                        },
                    )
                    await self._dispatch_event(ev)

                    # After 3 failures the daemon may be dead — self-cancel
                    logger.warning(
                        "CampaignMonitor('%s') daemon appears dead — cancelling",
                        self._campaign_id,
                    )
                    break
                await asyncio.sleep(self._poll_interval)
                continue

            # Reset failure counter on success
            self._http_failures = 0

            # ── Check terminal state ──
            if self._is_campaign_done(status_text):
                ev = self._make_event(
                    "campaign_complete",
                    "INFO",
                    {
                        "elapsed_s": round(
                            time.monotonic() - self._start_time, 1
                        ),
                    },
                )
                await self._dispatch_event(ev)
                break

            # ── Databank observability (fetch failure is tolerated) ──
            databank_text = await self._fetch_databank(client)

            # ── Process one poll tick ──
            elapsed = time.monotonic() - self._start_time
            events = self._poll_tick(status_text, elapsed, databank_text)
            for ev in events:
                await self._dispatch_event(ev)

            await asyncio.sleep(self._poll_interval)

    # ── Internal: Status Fetching ───────────────────────────────────────

    async def _fetch_status(
        self, client: httpx.AsyncClient
    ) -> str | None:
        """Fetch the campaign status from the SQX daemon.

        Returns the response text on success, or ``None`` on HTTP/connection
        failure.
        """
        try:
            encoded = urllib.parse.quote(
                f"-project action=status name={self._campaign_id}",
                safe="=",
            )
            url = f"{self._base_url}{_COMMAND_ENDPOINT}{encoded}"
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except httpx.TimeoutException:
            logger.debug(
                "CampaignMonitor('%s') status timeout", self._campaign_id,
            )
            return None
        except httpx.RequestError as exc:
            logger.debug(
                "CampaignMonitor('%s') status request failed: %s",
                self._campaign_id,
                exc,
            )
            return None
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "CampaignMonitor('%s') status HTTP error: %s",
                self._campaign_id,
                exc,
            )
            return None

    async def _fetch_databank(
        self, client: httpx.AsyncClient
    ) -> str | None:
        """Fetch the databank record counts from the SQX daemon.

        Returns the response text on success, or ``None`` on HTTP/connection
        failure. Failures are logged and tolerated — the caller treats the
        counts as unknown and heuristic polling is unaffected.

        Args:
            client: The shared ``httpx.AsyncClient`` from :meth:`run`.

        Returns:
            Raw ``-databank action=list`` response text, or ``None``.
        """
        try:
            encoded = urllib.parse.quote("-databank action=list", safe="=")
            url = f"{self._base_url}{_COMMAND_ENDPOINT}{encoded}"
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except httpx.TimeoutException:
            logger.debug(
                "CampaignMonitor('%s') databank timeout", self._campaign_id,
            )
            return None
        except httpx.RequestError as exc:
            logger.debug(
                "CampaignMonitor('%s') databank request failed: %s",
                self._campaign_id,
                exc,
            )
            return None
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "CampaignMonitor('%s') databank HTTP error: %s",
                self._campaign_id,
                exc,
            )
            return None

    # ── Internal: Poll Tick ─────────────────────────────────────────────

    def _poll_tick(
        self,
        status_text: str,
        elapsed: float,
        databank_text: str | None = None,
    ) -> list[WatcherEvent]:
        """Analyse one status response and return any events it triggers.

        Also records the raw status text and parses/stores the databank
        record counts for :meth:`current_snapshot`. Databank parse failures
        never raise: the counts are treated as unknown (``None``).

        Args:
            status_text: Raw status text from the SQX daemon.
            elapsed: Seconds since the monitor started.
            databank_text: Optional raw ``-databank action=list`` output.
                When ``None`` (fetch failed) the counts are treated as
                unknown.

        Returns:
            A (possibly empty) list of WatcherEvent instances.
        """
        self._last_status_text = status_text
        if databank_text is None:
            self._databank_counts = None
        else:
            self._databank_counts = parse_databank_counts(databank_text)

        events: list[WatcherEvent] = []
        count = extract_results_count(status_text)
        errors = extract_error_patterns(status_text)

        # 1. Config errors → immediate CRITICAL
        if errors:
            events.append(
                self._make_event(
                    "config_error",
                    "CRITICAL",
                    {
                        "errors": errors,
                        "elapsed_s": round(elapsed, 1),
                    },
                )
            )

        # 2. Startup phase (0 strategies so far) — no errors
        if count == 0 and not errors:
            if elapsed > self._baseline.startup_grace_s + self._baseline.expected_gen_time_s:
                events.append(
                    self._make_event(
                        "startup_stall",
                        "WARNING",
                        {"elapsed_s": round(elapsed, 1), "count": 0},
                    )
                )
            return events

        # If errors were found, return early (no stall analysis)
        if errors:
            return events

        # 3. Zero-growth stall (established throughput then stopped)
        if count == self._last_count:
            self._stall_polls += 1
            if self._stall_polls >= self._baseline.stall_polls_threshold:
                events.append(
                    self._make_event(
                        "zero_growth_stall",
                        "WARNING",
                        {
                            "count": count,
                            "elapsed_s": round(elapsed, 1),
                            "stalled_polls": self._stall_polls,
                        },
                    )
                )
        else:
            self._stall_polls = 0

        # 4. Excessive rejection — after rejection_warn_gens of no growth
        generation = _extract_generation_from_status(status_text)
        if (
            not self._emitted_excessive_rejection
            and self._last_count >= 0
            and count == self._last_count
            and self._stall_polls >= self._baseline.rejection_warn_gens
        ):
            events.append(
                self._make_event(
                    "excessive_rejection",
                    "INFO",
                    {
                        "generation": generation,
                        "rejection_rate": 1.0,
                        "stalled_polls": self._stall_polls,
                    },
                )
            )
            self._emitted_excessive_rejection = True

        self._last_count = count
        return events

    # ── Internal: Event Dispatch ────────────────────────────────────────

    async def _dispatch_event(self, event: WatcherEvent) -> None:
        """Record an event and notify the user via callback or CLI prompt.

        WARNING/CRITICAL events in CLI mode trigger a ``rich.prompt.Confirm``.
        On approval, the campaign is stopped via the HTTP API.
        """
        self._events.append(event)

        if self._on_watcher_event is not None:
            self._on_watcher_event(event)
            return

        # CLI mode — prompt only for WARNING/CRITICAL
        if event.severity in ("WARNING", "CRITICAL"):
            from rich.prompt import Confirm

            confirmed = Confirm.ask(
                f"Campaign seems stalled. Stop?\n"
                f"  Type: {event.event_type}\n"
                f"  Details: {event.details}",
                default=False,
            )
            if confirmed:
                await self._stop_campaign()

    async def _stop_campaign(self) -> None:
        """Dispatch ``-project action=stop`` via the HTTP API."""
        if self._client is None:
            logger.warning("No HTTP client available to stop campaign")
            return

        try:
            encoded = urllib.parse.quote(
                f"-project action=stop name={self._campaign_id}",
                safe="=",
            )
            url = f"{self._base_url}{_COMMAND_ENDPOINT}{encoded}"
            resp = await self._client.get(url)
            resp.raise_for_status()
            logger.info(
                "CampaignMonitor('%s') stop dispatched successfully",
                self._campaign_id,
            )
        except Exception as exc:
            logger.error(
                "CampaignMonitor('%s') stop failed: %s",
                self._campaign_id,
                exc,
            )

    # ── Internal: Helpers ───────────────────────────────────────────────

    def _elapsed_s(self) -> float:
        """Seconds since monitoring started (0.0 before :meth:`run`)."""
        if not self._start_time:
            return 0.0
        return round(max(0.0, time.monotonic() - self._start_time), 2)

    def _build_baseline_context(self) -> dict[str, Any]:
        """Assemble the baseline context for the LLM verdict prompt.

        Merges raw campaign config values (timeframe, WF/MC flags,
        generations, population, criteria, market) with the derived
        ``BaselineConfig`` timing parameters. Config values are read
        defensively via ``_get_config_value``; a missing raw config yields
        the derived baseline alone.
        """
        context: dict[str, Any] = {}
        if self._config is not None:
            for key in (
                "timeframe",
                "walk_forward",
                "monte_carlo",
                "generations",
                "population",
                "criteria",
                "market",
            ):
                value = _get_config_value(self._config, key, None)
                if value is not None:
                    context[key] = value
        context.update(self._baseline.to_dict())
        return context

    def _make_event(
        self,
        event_type: str,
        severity: str,
        details: dict,
    ) -> WatcherEvent:
        """Create a WatcherEvent with the current timestamp."""
        return WatcherEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            campaign_id=self._campaign_id,
            event_type=event_type,  # type: ignore[arg-type]
            severity=severity,  # type: ignore[arg-type]
            details=details,
        )

    @staticmethod
    def _is_campaign_done(status_text: str) -> bool:
        """Check if the status text indicates campaign completion or failure."""
        text = status_text.lower()
        return (
            "Project execution stopped" in status_text
            or any(
                term in text
                for term in ("completed", "finished", "done", "success", "failed")
            )
        )
