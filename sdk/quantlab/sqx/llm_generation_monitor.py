"""LLM Generation Monitor — LLM-powered campaign monitoring for SQX runs.

Runs as a sibling asyncio task to ``CampaignMonitor`` inside campaign
dispatch. Every N-th poll it builds a compact prompt from the shared
observability snapshot (status text + databank counts + baseline), asks
an LLM for a strict JSON verdict, gates the verdict on confidence, and
maps ``stop`` to the existing cancel path (HTTP ``-project action=stop``
+ ``monitor.cancel()``).

Safety rails:
- Confidence threshold (default 0.7): low-confidence verdicts never dispatch.
- Human confirmation required before executing a ``stop`` verdict.
- All failure paths (API error, timeout, open circuit breaker, parse
  failure) degrade to "log + treat as continue" — heuristics remain the
  always-on fallback and nothing crashes the dispatch loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from quantlab.dsl.models import LLMConfig
from quantlab.robustness.llm_circuit_breaker import LLMCircuitBreaker

logger = logging.getLogger(__name__)

_COMMAND_ENDPOINT = "/call?cmd="


# ── Data Models ─────────────────────────────────────────────────────────────


@dataclass
class MonitorSnapshot:
    """A point-in-time view of campaign observability.

    Attributes:
        status_text: Raw plain-text status response from the SQX HTTP API.
        generated_count: Number of strategies generated so far.
        databank_counts: Per-databank record counts, or ``None`` when the
            databank output could not be parsed.
        elapsed_s: Seconds since monitoring started.
        baseline: Raw campaign config values plus derived baseline context
            (generations, population, WF/MC, criteria).
    """

    status_text: str
    generated_count: int
    databank_counts: dict[str, int] | None = None
    elapsed_s: float = 0.0
    baseline: dict[str, Any] = field(default_factory=dict)


class Verdict(BaseModel):
    """Strict LLM verdict schema (Phase 1: continue|stop only).

    Attributes:
        assessment: Brief health assessment of the campaign.
        severity: Severity label (e.g. ``info``, ``warning``, ``critical``).
        detected_issues: List of issues the LLM spotted.
        recommended_action: ``continue`` or ``stop``.
        confidence: Model confidence in the recommendation, 0.0–1.0.
        reasoning: Explanation of the recommendation.
    """

    assessment: str
    severity: str
    detected_issues: list[str]
    recommended_action: Literal["continue", "stop"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


# ── Pure Helpers ────────────────────────────────────────────────────────────


def build_prompt(snapshot: MonitorSnapshot) -> str:
    """Build a compact LLM prompt from a monitor snapshot.

    Includes the live status text, databank record counts (or ``unknown``),
    the campaign baseline, and the strict JSON verdict schema.

    Args:
        snapshot: The current :class:`MonitorSnapshot`.

    Returns:
        A formatted prompt string ready for LLM consumption.
    """
    counts = (
        ", ".join(f"{k}: {v}" for k, v in snapshot.databank_counts.items())
        if snapshot.databank_counts
        else "unknown"
    )
    baseline_lines = "\n".join(
        f"  {key}: {value}" for key, value in snapshot.baseline.items()
    )

    return (
        "You are an operations assistant monitoring a live strategy "
        "generation campaign in StrategyQuant X. Decide whether the campaign "
        "should continue running or be stopped, based on the evidence below.\n"
        "\n"
        f"Campaign status:\n{snapshot.status_text}\n"
        "\n"
        f"Strategies generated: {snapshot.generated_count}\n"
        f"Databank record counts: {counts}\n"
        f"Elapsed seconds: {snapshot.elapsed_s:.1f}\n"
        "\n"
        "Campaign baseline (expected values):\n"
        f"{baseline_lines}\n"
        "\n"
        "Respond with STRICT JSON only (no markdown fences), matching "
        "exactly this schema:\n"
        "{\n"
        '  "assessment": "brief health assessment",\n'
        '  "severity": "info | warning | critical",\n'
        '  "detected_issues": ["issue 1", "issue 2"],\n'
        '  "recommended_action": "continue" | "stop",\n'
        '  "confidence": 0.0-1.0,\n'
        '  "reasoning": "why this recommendation"\n'
        "}\n"
        "Do not include any text outside the JSON object."
    )


def parse_verdict(text: str | None) -> Verdict | None:
    """Parse and validate an LLM verdict response.

    Strips ````` ```json ```` fences (case-insensitive), loads the JSON, and
    validates it against :class:`Verdict`. Any failure (empty text, invalid
    JSON, missing fields, out-of-range confidence, unknown action) is logged
    as a warning and returns ``None`` — the caller treats ``None`` as
    ``continue``.

    Args:
        text: The raw LLM response text.

    Returns:
        A validated :class:`Verdict`, or ``None`` when the response is
        invalid, missing, or malformed (treated as continue).
    """
    if not text or not text.strip():
        logger.warning("LLM verdict missing/empty — treated as continue")
        return None

    cleaned = re.sub(r"^\s*```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("LLM verdict invalid JSON (%s) — treated as continue", exc)
        return None

    try:
        return Verdict.model_validate(data)
    except ValidationError as exc:
        logger.warning(
            "LLM verdict failed validation (%s) — treated as continue", exc
        )
        return None


# ── Action Executor ─────────────────────────────────────────────────────────


class ActionExecutor:
    """Maps a verdict's recommended action to the campaign cancel path.

    ``stop`` dispatches the HTTP ``-project action=stop`` command and then
    signals ``monitor.cancel()`` (the same path used by ``CampaignMonitor``).
    ``continue`` is a no-op. No other campaign mutation occurs.
    """

    def __init__(
        self,
        campaign_id: str,
        base_url: str,
        monitor: Any | None = None,
        http_timeout: float = 10.0,
    ) -> None:
        """Args:
            campaign_id: Campaign/project identifier.
            base_url: Base URL of the SQX HTTP API.
            monitor: Optional monitor object exposing ``async cancel()``
                (e.g. ``CampaignMonitor``). Cancelled after a successful stop.
            http_timeout: HTTP request timeout in seconds.
        """
        self._campaign_id = campaign_id
        self._base_url = base_url.rstrip("/")
        self._monitor = monitor
        self._http_timeout = http_timeout

    async def execute(self, verdict: Verdict) -> bool:
        """Execute the verdict's recommended action.

        Args:
            verdict: The validated :class:`Verdict`.

        Returns:
            ``True`` when a stop was dispatched successfully, ``False`` for
            continue verdicts or failed stops.
        """
        if verdict.recommended_action != "stop":
            logger.info(
                "ActionExecutor('%s') continue verdict — no-op",
                self._campaign_id,
            )
            return False

        try:
            dispatched = await self._dispatch_http_stop()
        except Exception as exc:
            logger.error(
                "ActionExecutor('%s') stop failed: %s",
                self._campaign_id,
                exc,
            )
            return False
        if dispatched and self._monitor is not None:
            try:
                await self._monitor.cancel()
            except Exception as exc:
                logger.error(
                    "ActionExecutor('%s') monitor.cancel() failed: %s",
                    self._campaign_id,
                    exc,
                )
        return dispatched

    async def _dispatch_http_stop(self) -> bool:
        """Dispatch ``-project action=stop`` via the SQX HTTP API.

        Returns:
            ``True`` on a successful HTTP stop, ``False`` on failure.
        """
        try:
            encoded = urllib.parse.quote(
                f"-project action=stop name={self._campaign_id}",
                safe="=",
            )
            url = f"{self._base_url}{_COMMAND_ENDPOINT}{encoded}"
            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            logger.info(
                "ActionExecutor('%s') stop dispatched successfully",
                self._campaign_id,
            )
            return True
        except Exception as exc:
            logger.error(
                "ActionExecutor('%s') stop failed: %s",
                self._campaign_id,
                exc,
            )
            return False


# ── LLM Call ────────────────────────────────────────────────────────────────


async def _call_llm(prompt: str, llm_config: LLMConfig) -> str:
    """Call the LLM provider with the given prompt.

    Mirrors ``LLMResearchAgent.call_llm``: OpenAI/OpenCode via the async
    SDK, Anthropic unsupported, unknown providers rejected.

    Args:
        prompt: The formatted prompt string.
        llm_config: ``LLMConfig`` with provider, model, and parameters.

    Returns:
        The LLM response text as a string.

    Raises:
        ImportError: If the ``openai`` SDK is not installed.
        ValueError: If the provider is unsupported.
        Exception: On API errors (caught by the monitor's poll handler).
    """
    provider = llm_config.provider

    if provider in ("openai", "opencode"):
        try:
            import openai  # noqa: F401
        except ImportError:
            raise ImportError(
                "openai SDK is not installed. Install with: pip install openai"
            )

        try:
            from openai import AsyncOpenAI

            kwargs: dict[str, Any] = {
                "max_retries": 2,
                "timeout": llm_config.max_tokens,
            }
            if llm_config.base_url:
                kwargs["base_url"] = llm_config.base_url
            api_key = os.environ.get(llm_config.api_key_env)
            if api_key:
                kwargs["api_key"] = api_key

            client = AsyncOpenAI(**kwargs)
            response = await client.chat.completions.create(
                model=llm_config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception:
            raise

    elif provider == "anthropic":
        raise ValueError(
            "Anthropic provider is not yet supported. "
            "Use provider='openai' or 'opencode' instead."
        )
    else:
        raise ValueError(
            f"Unsupported LLM provider '{provider}'. "
            f"Supported: {', '.join(sorted(LLMConfig.VALID_PROVIDERS))}"
        )


# ── LLM Generation Monitor ──────────────────────────────────────────────────


async def _default_confirm_stop(verdict: Verdict) -> bool:
    """Default human-confirmation hook: a ``rich.prompt.Confirm`` prompt.

    Shown before any ``stop`` verdict is executed in CLI mode. Injectable
    callers (tests, orchestrator wiring) replace this via ``confirm_stop``.
    """
    from rich.prompt import Confirm

    return Confirm.ask(
        f"LLM monitor recommends stopping campaign.\n"
        f"  Severity: {verdict.severity}\n"
        f"  Assessment: {verdict.assessment}\n"
        f"  Issues: {', '.join(verdict.detected_issues) or 'none'}\n"
        f"  Confidence: {verdict.confidence:.2f}\n"
        "Stop the campaign?",
        default=False,
    )


class LLMGenerationMonitor:
    """LLM-capable monitor that reasons over live campaign observability.

    Polls a snapshot provider (typically ``CampaignMonitor.current_snapshot``)
    on its own cadence; every ``poll_every_n``-th tick it sends a compact
    prompt to the LLM through the circuit breaker, validates the verdict,
    gates on confidence, human-confirms ``stop``, and executes via
    :class:`ActionExecutor`. Every failure path degrades to "log + continue"
    so heuristic monitoring is never disrupted.
    """

    def __init__(
        self,
        campaign_id: str,
        base_url: str,
        snapshot_provider: Callable[[], MonitorSnapshot],
        llm_config: LLMConfig,
        llm_caller: Callable[[str, LLMConfig], Awaitable[str]] | None = None,
        circuit_breaker: LLMCircuitBreaker | None = None,
        confirm_stop: Callable[[Verdict], Awaitable[bool]] | None = None,
        confidence_threshold: float = 0.7,
        poll_every_n: int = 5,
        on_verdict: Callable[[Verdict], None] | None = None,
        monitor: Any | None = None,
        poll_interval: float = 10.0,
    ) -> None:
        """Args:
            campaign_id: Campaign/project identifier.
            base_url: Base URL of the SQX HTTP API.
            snapshot_provider: Sync callable returning the current
                :class:`MonitorSnapshot`.
            llm_config: ``LLMConfig`` for the LLM call.
            llm_caller: Async ``(prompt, llm_config) -> str`` caller.
                Defaults to :func:`_call_llm`.
            circuit_breaker: ``LLMCircuitBreaker`` protecting LLM calls.
                Defaults to a fresh instance.
            confirm_stop: Async ``(verdict) -> bool`` human-confirmation hook
                for stop verdicts. ``None`` skips confirmation.
            confidence_threshold: Minimum confidence for a verdict to dispatch
                an action (default 0.7).
            poll_every_n: Run the LLM poll every N-th tick (default 5).
            on_verdict: Optional sync hook invoked with every valid verdict.
            monitor: Optional monitor object exposing ``async cancel()``
                (e.g. ``CampaignMonitor``) used by the stop path.
            poll_interval: Seconds between monitor ticks (default 10.0).
        """
        self.campaign_id = campaign_id
        self.base_url = base_url.rstrip("/")
        self._snapshot_provider = snapshot_provider
        self._llm_config = llm_config
        self.llm_caller = llm_caller
        self.circuit_breaker = circuit_breaker or LLMCircuitBreaker()
        self.confirm_stop = confirm_stop or _default_confirm_stop
        self.confidence_threshold = confidence_threshold
        self.poll_every_n = poll_every_n
        self.on_verdict = on_verdict
        self._poll_interval = poll_interval
        self._stopped = False
        self._executor = ActionExecutor(
            campaign_id=campaign_id,
            base_url=base_url,
            monitor=monitor,
        )

    # ── Public API ──────────────────────────────────────────────────────

    async def run(self) -> None:
        """Run the poll loop until stopped.

        Heuristic monitoring (``CampaignMonitor``) continues independently;
        this loop only adds the LLM poll on a slow cadence.
        """
        self._stopped = False
        tick = 0
        while not self._stopped:
            tick += 1
            if tick % self.poll_every_n == 0:
                await self._poll_once()
            await asyncio.sleep(self._poll_interval)

    async def stop(self) -> None:
        """Signal the poll loop to stop at the next tick."""
        logger.info("LLMGenerationMonitor('%s') stop requested", self.campaign_id)
        self._stopped = True

    # ── Internal: Poll ──────────────────────────────────────────────────

    async def _poll_once(self) -> None:
        """Run a single LLM poll: snapshot → prompt → LLM → verdict → gate → act.

        Never raises: every failure path is logged and treated as continue.
        """
        try:
            snapshot = self._snapshot_provider()
        except Exception as exc:
            logger.warning(
                "LLMGenerationMonitor('%s') snapshot failed (%s) — treated as continue",
                self.campaign_id,
                exc,
            )
            return

        prompt = build_prompt(snapshot)
        caller = self.llm_caller or _call_llm

        try:
            response_text = await self.circuit_breaker.call(
                caller(prompt, self._llm_config)
            )
        except Exception as exc:
            logger.warning(
                "LLMGenerationMonitor('%s') LLM poll failed (%s) — treated as continue",
                self.campaign_id,
                exc,
            )
            return

        verdict = parse_verdict(response_text)
        if verdict is None:
            # parse_verdict already logged the warning; treated as continue
            return

        if self.on_verdict is not None:
            try:
                self.on_verdict(verdict)
            except Exception as exc:
                logger.warning(
                    "LLMGenerationMonitor('%s') on_verdict hook failed: %s",
                    self.campaign_id,
                    exc,
                )

        if verdict.recommended_action != "stop":
            logger.debug(
                "LLMGenerationMonitor('%s') verdict: continue",
                self.campaign_id,
            )
            return

        # ── Stop path: confidence gate → human confirm → execute ──
        if verdict.confidence < self.confidence_threshold:
            logger.info(
                "LLMGenerationMonitor('%s') stop verdict confidence %.2f "
                "below threshold %.2f — no action",
                self.campaign_id,
                verdict.confidence,
                self.confidence_threshold,
            )
            return

        confirmed = True
        if self.confirm_stop is not None:
            try:
                confirmed = await self.confirm_stop(verdict)
            except Exception as exc:
                logger.warning(
                    "LLMGenerationMonitor('%s') confirm_stop failed (%s) — "
                    "treated as continue",
                    self.campaign_id,
                    exc,
                )
                return
        if not confirmed:
            logger.info(
                "LLMGenerationMonitor('%s') stop declined by user — continuing",
                self.campaign_id,
            )
            return

        try:
            dispatched = await self._executor.execute(verdict)
        except Exception as exc:
            logger.error(
                "LLMGenerationMonitor('%s') action executor failed (%s) — "
                "treated as continue",
                self.campaign_id,
                exc,
            )
            return

        if dispatched:
            logger.info(
                "LLMGenerationMonitor('%s') stop executed — ending monitor loop",
                self.campaign_id,
            )
            self._stopped = True
