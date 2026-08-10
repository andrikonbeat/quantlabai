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
import csv
import io
import json
import logging
import math
import re
import time
import urllib.parse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

import httpx

from quantlab.gates.callbacks import sanitize_campaign_id
from quantlab.sqx.llm_generation_monitor import MonitorSnapshot

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────

_COMMAND_ENDPOINT = "/call?cmd="
_STRATEGIES_CSV_FILENAME = "strategies.csv"

# Persisted on-demand status snapshot (ADR-5/6, REQ-38): CampaignMonitor
# writes ``current_snapshot()`` here per poll tick, and ``campaign status
# --live`` / ``generation status`` read it. Path traversal is rejected via
# ``sanitize_campaign_id`` (threat matrix: snapshot path sanitization).
DEFAULT_SNAPSHOT_DIR: Path = Path("/tmp/sqx-status")

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


# ── On-Demand Status Snapshot (REQ-38, ADR-5/6) ──────────────────────────────


def snapshot_from_dict(data: dict[str, Any]) -> MonitorSnapshot:
    """Rebuild a :class:`MonitorSnapshot` from a persisted JSON dict.

    Unknown keys (added by future versions) are ignored so old snapshots
    keep reading; missing keys fall back to the dataclass defaults.
    """
    fields = MonitorSnapshot.__dataclass_fields__
    return MonitorSnapshot(**{k: v for k, v in data.items() if k in fields})


def load_snapshot(
    campaign_id: str,
    base_dir: str | Path | None = None,
) -> MonitorSnapshot:
    """Read the persisted live snapshot for *campaign_id* (REQ-38).

    The campaign id is sanitized via :func:`sanitize_campaign_id` BEFORE any
    path is built, so ``../`` traversal is rejected (threat matrix). The
    default base dir resolves at call time so tests can patch
    ``DEFAULT_SNAPSHOT_DIR``.

    Args:
        campaign_id: The campaign whose snapshot to read.
        base_dir: Snapshot root (default ``DEFAULT_SNAPSHOT_DIR``).

    Returns:
        The persisted :class:`MonitorSnapshot`.

    Raises:
        ValueError: If the campaign id is invalid (path traversal).
        FileNotFoundError: If no snapshot has been persisted yet.
    """
    if base_dir is None:
        base_dir = DEFAULT_SNAPSHOT_DIR
    safe = sanitize_campaign_id(campaign_id)
    path = Path(base_dir) / safe / "snapshot.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"No live snapshot for campaign '{campaign_id}' at {path} — "
            "start monitoring first (campaign run-flow / daemon)."
        )
    return snapshot_from_dict(json.loads(path.read_text(encoding="utf-8")))


def heuristic_recommendation(
    snapshot: MonitorSnapshot,
) -> Literal["continue", "stop", "reconfigure"]:
    """Recommend an action from a snapshot using rules only — zero LLM calls.

    Heuristics mirror the monitor's own detection vocabulary:

    - ``stop``: the status text shows config errors (the run cannot proceed),
      or zero strategies were generated past the startup grace + expected
      generation window (startup stall);
    - ``reconfigure``: zero strategies after the startup grace window but
      before a hard stall — the config may be wrong (e.g. bad databanks);
    - ``continue``: still inside the startup grace window, or the campaign is
      generating strategies.

    Args:
        snapshot: The current :class:`MonitorSnapshot`.

    Returns:
        ``"continue"``, ``"stop"``, or ``"reconfigure"``.
    """
    if extract_error_patterns(snapshot.status_text):
        return "stop"
    baseline = snapshot.baseline or {}
    grace = float(baseline.get("startup_grace_s", 0.0))
    expected = float(baseline.get("expected_gen_time_s", 0.0))
    if snapshot.generated_count == 0:
        if snapshot.elapsed_s > grace + expected:
            return "stop"
        if snapshot.elapsed_s > grace:
            return "reconfigure"
    return "continue"


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

    m = re.search(r"Strategies\s+generated\s*:?\s*(\d+)", status_text, re.IGNORECASE)
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


def parse_strategy_counts_csv(text: str | None) -> dict[str, int]:
    """Parse exported ``strategies.csv`` rows into per-strategy counts (REQ-21).

    The export is written at ``/tmp/sqx-exports/{campaign_id}/strategies.csv``
    by the dispatch path. Missing/empty/garbage input is TOLERATED: the
    function returns ``{}`` instead of raising, so a campaign that has not
    exported yet (or exports a partial file mid-generation) degrades to
    "no artifact progress" rather than crashing the monitor. Rows without a
    ``Name`` value and rows whose header lacks a ``Name`` column are skipped
    (partial rows tolerated); duplicate names accumulate.

    Args:
        text: Raw contents of the exported ``strategies.csv``.

    Returns:
        A mapping of strategy name to row count (``{}`` when unparseable).
    """
    if not text or not text.strip():
        logger.warning("Strategies CSV missing/empty — artifact counts unknown")
        return {}

    try:
        reader = csv.DictReader(io.StringIO(text))
    except csv.Error as exc:
        logger.warning("Strategies CSV unparseable (%s) — counts unknown", exc)
        return {}

    if reader.fieldnames is None or "Name" not in reader.fieldnames:
        logger.warning(
            "Strategies CSV has no 'Name' column — artifact counts unknown"
        )
        return {}

    counts: dict[str, int] = {}
    for row in reader:
        name = row.get("Name")
        if not name or not name.strip():
            continue
        counts[name.strip()] = counts.get(name.strip(), 0) + 1

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
        export_dir: Optional directory containing the exported
            ``strategies.csv`` (REQ-21). When set, artifact-derived strategy
            counts are read each poll and feed the snapshot and stall
            detection. ``None`` disables the artifact signal entirely.
        gate_writer: Optional sync ``(event) -> None`` callback invoked for
            WARNING/CRITICAL events when ``on_watcher_event`` is ``None``
            (orchestrated mode writes a gate decision-file via this hook
            instead of prompting in the CLI).
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
        export_dir: str | Path | None = None,
        gate_writer: Callable[[WatcherEvent], None] | None = None,
    ) -> None:
        self._campaign_id = campaign_id
        self._base_url = base_url.rstrip("/")
        self._baseline = baseline
        self._poll_interval = poll_interval
        self._on_watcher_event = on_watcher_event
        self._http_timeout = http_timeout
        self._config = config
        self._export_dir = Path(export_dir) if export_dir else None
        self._gate_writer = gate_writer
        self._notifiers: list[Any] = []

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
        # Artifact observability state (REQ-14/REQ-21)
        self._strategy_counts: dict[str, int] = {}
        self._last_artifact_count: int = 0

    def add_notifier(self, notifier: Any) -> None:
        """Register an async notifier to fan out every emitted event (REQ-15).

        Args:
            notifier: An object exposing ``async send(message, **kwargs)``
                (e.g. ``quantlab.gates.notifiers.Notifier``). ``send()`` is
                scheduled on the running loop; failures never propagate.
        """
        self._notifiers.append(notifier)

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

    async def final_check(self) -> None:
        """One last status poll after cancel: emit a missed campaign_complete.

        The dispatch loop can observe campaign completion *before* the
        monitor's own done-check poll runs, then cancel the monitor — the
        ``campaign_complete`` event the loop saw is lost because the
        monitor never got to poll again. This method fetches the status
        once more after :meth:`cancel` and, when the campaign has already
        reached a terminal state, emits the missed ``campaign_complete``
        event (including the ``on_watcher_event`` callback).

        No-op when no HTTP client is available (monitor already exited),
        when the final fetch fails, or when the campaign has not reached a
        terminal state. Never raises.
        """
        if self._client is None:
            return
        if any(ev.event_type == "campaign_complete" for ev in self._events):
            return
        status_text = await self._fetch_status(self._client)
        if status_text is None:
            return
        if not self._is_campaign_done(status_text):
            return
        # Re-check after the await: the loop itself may have just emitted
        # the event while we were fetching.
        if any(ev.event_type == "campaign_complete" for ev in self._events):
            return
        ev = self._make_event(
            "campaign_complete",
            "INFO",
            {"elapsed_s": round(self._elapsed_s(), 1)},
        )
        await self._dispatch_event(ev)

    def current_snapshot(self) -> MonitorSnapshot:
        """Return a point-in-time observability snapshot for the LLM monitor.

        Provides the latest raw status text, the generated strategy count,
        per-databank record counts (``None`` when unknown or parse-failed),
        artifact-derived strategy counts (REQ-14), elapsed seconds, and the
        baseline context (raw config values merged with the derived
        :class:`BaselineConfig`). This is the snapshot provider consumed by
        :class:`~quantlab.sqx.llm_generation_monitor.LLMGenerationMonitor`.
        """
        return MonitorSnapshot(
            status_text=self._last_status_text or "",
            generated_count=max(0, self._last_count),
            databank_counts=self._databank_counts,
            elapsed_s=self._elapsed_s(),
            baseline=self._build_baseline_context(),
            strategy_counts=dict(self._strategy_counts),
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

            # ── Artifact observability (REQ-21): strategies.csv signal ──
            strategy_counts = self._read_strategy_counts()

            # ── Process one poll tick ──
            elapsed = time.monotonic() - self._start_time
            events = self._poll_tick(
                status_text, elapsed, databank_text, strategy_counts
            )
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
        strategy_counts: dict[str, int] | None = None,
    ) -> list[WatcherEvent]:
        """Analyse one status response and return any events it triggers.

        Also records the raw status text and parses/stores the databank
        record counts and artifact strategy counts for
        :meth:`current_snapshot`. Databank parse failures never raise: the
        counts are treated as unknown (``None``).

        Zero-growth stall detection considers artifact progress (REQ-21):
        when ``strategy_counts`` is provided and grew since the last tick,
        the stall counter is reset even though the status-text count is
        flat. When ``strategy_counts`` is ``None`` (artifact not enabled or
        unavailable) the legacy status-text-only behavior is preserved.

        Args:
            status_text: Raw status text from the SQX daemon.
            elapsed: Seconds since the monitor started.
            databank_text: Optional raw ``-databank action=list`` output.
                When ``None`` (fetch failed) the counts are treated as
                unknown.
            strategy_counts: Optional artifact-derived strategy counts
                (REQ-21). ``None`` disables the artifact stall signal.

        Returns:
            A (possibly empty) list of WatcherEvent instances.
        """
        self._last_status_text = status_text
        if databank_text is None:
            self._databank_counts = None
        else:
            self._databank_counts = parse_databank_counts(databank_text)

        # Artifact signal (REQ-21): growth resets the zero-growth stall.
        artifact_growth = False
        if strategy_counts is not None:
            self._strategy_counts = strategy_counts
            artifact_growth = len(strategy_counts) > self._last_artifact_count
            self._last_artifact_count = len(strategy_counts)

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
            # REQ-38: surface the point-in-time state for status --live.
            self._persist_snapshot(elapsed)
            return events

        # If errors were found, return early (no stall analysis)
        if errors:
            # REQ-38: surface the point-in-time state for status --live.
            self._persist_snapshot(elapsed)
            return events

        # 3. Zero-growth stall (established throughput then stopped).
        #    Artifact progress (REQ-21) resets the stall even when the
        #    status-text count is flat.
        if count == self._last_count and not artifact_growth:
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
        # REQ-38: persist the point-in-time state on every poll tick so the
        # on-demand status commands can read it without blocking the run.
        self._persist_snapshot(elapsed)

        return events

    # ── Internal: Event Dispatch ────────────────────────────────────────

    async def _dispatch_event(self, event: WatcherEvent) -> None:
        """Record an event and notify the user via callback, gate, or CLI prompt.

        WARNING/CRITICAL events in CLI mode trigger a ``rich.prompt.Confirm``.
        On approval, the campaign is stopped via the HTTP API. Orchestrated
        mode registers a gate writer instead of prompting (REQ-20).
        """
        self._events.append(event)

        if self._on_watcher_event is not None:
            self._on_watcher_event(event)
        elif self._gate_writer is not None:
            # Orchestrated mode: surface WARNING/CRITICAL events through the
            # gate decision-file channel instead of a CLI prompt.
            if event.severity in ("WARNING", "CRITICAL"):
                self._gate_writer(event)
        elif event.severity in ("WARNING", "CRITICAL"):
            # CLI mode — prompt only for WARNING/CRITICAL
            from rich.prompt import Confirm

            confirmed = Confirm.ask(
                f"Campaign seems stalled. Stop?\n"
                f"  Type: {event.event_type}\n"
                f"  Details: {event.details}",
                default=False,
            )
            if confirmed:
                await self._stop_campaign()

        self._fanout_notify(event)

    def _fanout_notify(self, event: WatcherEvent) -> None:
        """Schedule an async notification to every registered notifier.

        Never raises: notifier ``send()`` is fire-and-forget on the running
        loop and each notifier's ``send()`` already logs its own failures.
        """
        if not self._notifiers:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning(
                "CampaignMonitor('%s') no running loop — notifier skipped",
                self._campaign_id,
            )
            return
        message = (
            f"[{event.severity}] {event.campaign_id} {event.event_type}: "
            f"{event.details}"
        )
        for notifier in self._notifiers:
            try:
                loop.create_task(
                    notifier.send(
                        message,
                        campaign_id=event.campaign_id,
                        event_type=event.event_type,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "CampaignMonitor('%s') notifier send failed: %s",
                    self._campaign_id,
                    exc,
                )

    def _persist_snapshot(self, elapsed: float | None = None) -> None:
        """Persist ``current_snapshot()`` for the on-demand status commands.

        Writes ``{DEFAULT_SNAPSHOT_DIR}/{sanitize_campaign_id}/snapshot.json``
        (ADR-5/6, REQ-38). When *elapsed* is provided (the value the current
        poll tick computed), it overrides the wall-clock ``elapsed_s`` so the
        persisted snapshot matches the exact view the tick's stall/error logic
        used. Never raises: an invalid campaign id (path traversal) or an IO
        error logs a warning and skips persistence, so monitoring continues
        regardless.
        """
        try:
            safe = sanitize_campaign_id(self._campaign_id)
        except ValueError as exc:
            logger.warning(
                "CampaignMonitor('%s') snapshot skipped: %s",
                self._campaign_id,
                exc,
            )
            return
        snapshot = asdict(self.current_snapshot())
        if elapsed is not None:
            snapshot["elapsed_s"] = elapsed
        path = DEFAULT_SNAPSHOT_DIR / safe / "snapshot.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(snapshot, default=str),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning(
                "CampaignMonitor('%s') snapshot write failed: %s",
                self._campaign_id,
                exc,
            )

    def _read_strategy_counts(self) -> dict[str, int] | None:
        """Read and parse the exported ``strategies.csv`` (REQ-21).

        Returns ``None`` when ``export_dir`` is unset (artifact signal
        disabled). When the file is missing or unparseable, returns ``{}``
        — the artifact signal degrades to "no progress" but never raises.
        """
        if self._export_dir is None:
            return None
        path = self._export_dir / _STRATEGIES_CSV_FILENAME
        if not path.is_file():
            return {}
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(
                "CampaignMonitor('%s') strategies.csv read failed: %s",
                self._campaign_id,
                exc,
            )
            return {}
        return parse_strategy_counts_csv(text)

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
