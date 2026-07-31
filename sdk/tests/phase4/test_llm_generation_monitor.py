"""Unit tests for the LLM Generation Monitor (Phase 1 core module).

Covers: ``parse_verdict`` (valid/fenced/invalid/missing/bad confidence),
``build_prompt`` (counts + baseline + JSON schema), confidence gate,
``ActionExecutor`` (stop vs continue), circuit-open degradation, and
constructor defaults.
"""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, Mock

import pytest

from quantlab.dsl.models import LLMConfig
from quantlab.robustness.llm_circuit_breaker import LLMCircuitBreaker
from quantlab.sqx.llm_generation_monitor import (
    ActionExecutor,
    LLMGenerationMonitor,
    MonitorSnapshot,
    Verdict,
    build_prompt,
    parse_verdict,
)


def make_snapshot(**overrides: object) -> MonitorSnapshot:
    """Build a realistic MonitorSnapshot for tests."""
    base = dict(
        status_text="Strategies generated  10\nGeneration: 3\nIn databank 1",
        generated_count=10,
        databank_counts={"Results": 2, "Strategies": 2},
        elapsed_s=123.4,
        baseline={
            "generations": 80,
            "population": 200,
            "walk_forward": True,
            "monte_carlo": True,
            "criteria": [{"metric": "profit_factor", "operator": ">", "value": 1.3}],
        },
    )
    base.update(overrides)
    return MonitorSnapshot(**base)


def verdict_payload(
    action: str = "continue",
    confidence: float = 0.9,
    **overrides: object,
) -> dict[str, object]:
    """Build a valid verdict dict, overridable per test."""
    payload = {
        "assessment": "Campaign generating but databank count not growing",
        "severity": "warning",
        "detected_issues": ["zero acceptance"],
        "recommended_action": action,
        "confidence": confidence,
        "reasoning": "counts stagnant across polls",
    }
    payload.update(overrides)
    return payload


class TestParseVerdict:
    """Task 1.2: parse_verdict strips fences and validates via pydantic."""

    def test_valid_verdict(self) -> None:
        """GIVEN a well-formed verdict dict as JSON
        WHEN parse_verdict is called
        THEN a Verdict with all fields is returned.
        """
        raw = json.dumps(verdict_payload())
        verdict = parse_verdict(raw)

        assert isinstance(verdict, Verdict)
        assert verdict.assessment == "Campaign generating but databank count not growing"
        assert verdict.severity == "warning"
        assert verdict.detected_issues == ["zero acceptance"]
        assert verdict.recommended_action == "continue"
        assert verdict.confidence == 0.9
        assert verdict.reasoning == "counts stagnant across polls"

    def test_stop_action_accepted(self) -> None:
        """GIVEN a verdict with recommended_action stop
        WHEN parse_verdict is called
        THEN a stop Verdict is returned (Phase 1 accepts continue|stop).
        """
        verdict = parse_verdict(json.dumps(verdict_payload(action="stop")))

        assert verdict is not None
        assert verdict.recommended_action == "stop"

    def test_fenced_json_block(self) -> None:
        """GIVEN a ```json-fenced block
        WHEN parse_verdict is called
        THEN the fences are stripped and the Verdict is returned.
        """
        raw = f"```json\n{json.dumps(verdict_payload())}\n```"
        verdict = parse_verdict(raw)

        assert verdict is not None
        assert verdict.recommended_action == "continue"

    def test_fenced_with_language_hint_case_insensitive(self) -> None:
        """GIVEN a ```JSON block (uppercase hint)
        WHEN parse_verdict is called
        THEN the fence is stripped case-insensitively.
        """
        raw = f"```JSON\n{json.dumps(verdict_payload(action='stop'))}\n```"
        verdict = parse_verdict(raw)

        assert verdict is not None
        assert verdict.recommended_action == "stop"

    def test_invalid_json_returns_none_and_warns(self, caplog) -> None:
        """GIVEN text that is not valid JSON
        WHEN parse_verdict is called
        THEN None is returned and a warning is logged (treated as continue).
        """
        with caplog.at_level(logging.WARNING, logger="quantlab.sqx.llm_generation_monitor"):
            verdict = parse_verdict("not json at all {{{")

        assert verdict is None
        assert any("continue" in r.message.lower() for r in caplog.records)

    def test_missing_fields_returns_none_and_warns(self, caplog) -> None:
        """GIVEN JSON missing required verdict fields
        WHEN parse_verdict is called
        THEN None is returned and a warning is logged (treated as continue).
        """
        with caplog.at_level(logging.WARNING, logger="quantlab.sqx.llm_generation_monitor"):
            verdict = parse_verdict(json.dumps({"assessment": "only this"}))

        assert verdict is None
        assert any("continue" in r.message.lower() for r in caplog.records)

    def test_bad_confidence_returns_none_and_warns(self, caplog) -> None:
        """GIVEN a verdict with confidence outside 0..1
        WHEN parse_verdict is called
        THEN None is returned and a warning is logged (treated as continue).
        """
        payload = verdict_payload(confidence=1.5)
        with caplog.at_level(logging.WARNING, logger="quantlab.sqx.llm_generation_monitor"):
            verdict = parse_verdict(json.dumps(payload))

        assert verdict is None
        assert any("continue" in r.message.lower() for r in caplog.records)

    def test_empty_text_returns_none(self) -> None:
        """GIVEN an empty or None response
        WHEN parse_verdict is called
        THEN None is returned (treated as continue).
        """
        assert parse_verdict("") is None
        assert parse_verdict(None) is None

    def test_unknown_action_returns_none(self) -> None:
        """GIVEN a recommended_action outside continue|stop
        WHEN parse_verdict is called
        THEN None is returned (Phase 1 schema rejects unknown actions).
        """
        verdict = parse_verdict(json.dumps(verdict_payload(action="abort")))

        assert verdict is None


class TestBuildPrompt:
    """Task 1.3: build_prompt includes status, counts, baseline, and schema."""

    def test_includes_status_and_counts(self) -> None:
        """GIVEN a snapshot
        WHEN build_prompt is called
        THEN status text, generated count, and databank counts are present.
        """
        prompt = build_prompt(make_snapshot())

        assert "Strategies generated  10" in prompt
        assert "Generation: 3" in prompt
        assert "Results" in prompt
        assert "Strategies" in prompt

    def test_includes_baseline_values(self) -> None:
        """GIVEN a snapshot with a baseline dict
        WHEN build_prompt is called
        THEN baseline generations/population/WF/MC/criteria are present.
        """
        prompt = build_prompt(make_snapshot())

        assert "80" in prompt
        assert "200" in prompt
        assert "walk_forward" in prompt
        assert "monte_carlo" in prompt
        assert "profit_factor" in prompt
        assert "1.3" in prompt

    def test_includes_json_schema_instructions(self) -> None:
        """GIVEN any snapshot
        WHEN build_prompt is called
        THEN the strict verdict JSON schema is embedded in the prompt.
        """
        prompt = build_prompt(make_snapshot())

        assert "assessment" in prompt
        assert "severity" in prompt
        assert "detected_issues" in prompt
        assert "recommended_action" in prompt
        assert '"continue"' in prompt or "continue" in prompt
        assert '"stop"' in prompt or "stop" in prompt
        assert "confidence" in prompt
        assert "reasoning" in prompt

    def test_unknown_databank_counts_rendered(self) -> None:
        """GIVEN databank_counts is None (parse failed)
        WHEN build_prompt is called
        THEN the prompt still renders with an explicit unknown marker.
        """
        prompt = build_prompt(make_snapshot(databank_counts=None))

        assert "unknown" in prompt.lower()


class TestActionExecutor:
    """Task 1.4: stop maps to HTTP stop + monitor.cancel(); continue is no-op."""

    @pytest.mark.asyncio
    async def test_stop_dispatches_http_and_cancels_monitor(self, monkeypatch) -> None:
        """GIVEN a stop verdict
        WHEN ActionExecutor.execute is called
        THEN the HTTP stop is dispatched once and monitor.cancel() is called once.
        """
        monitor = Mock()
        monitor.cancel = AsyncMock()
        executor = ActionExecutor(
            campaign_id="campaign-jforex-m1",
            base_url="http://127.0.0.1:5050",
            monitor=monitor,
        )
        dispatch = AsyncMock(return_value=True)
        monkeypatch.setattr(executor, "_dispatch_http_stop", dispatch)
        verdict = Verdict(**verdict_payload(action="stop"))

        result = await executor.execute(verdict)

        assert result is True
        dispatch.assert_awaited_once_with()
        monitor.cancel.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_continue_is_noop(self, monkeypatch) -> None:
        """GIVEN a continue verdict
        WHEN ActionExecutor.execute is called
        THEN neither HTTP stop nor monitor.cancel() is invoked.
        """
        monitor = Mock()
        monitor.cancel = AsyncMock()
        executor = ActionExecutor(
            campaign_id="c1",
            base_url="http://127.0.0.1:5050",
            monitor=monitor,
        )
        dispatch = AsyncMock(return_value=True)
        monkeypatch.setattr(executor, "_dispatch_http_stop", dispatch)
        verdict = Verdict(**verdict_payload(action="continue"))

        result = await executor.execute(verdict)

        assert result is False
        dispatch.assert_not_awaited()
        monitor.cancel.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_http_failure_logged_not_raised(self, monkeypatch, caplog) -> None:
        """GIVEN the HTTP stop request fails
        WHEN ActionExecutor.execute is called
        THEN the failure is logged and no exception propagates.
        """
        monitor = Mock()
        monitor.cancel = AsyncMock()
        executor = ActionExecutor(
            campaign_id="c1",
            base_url="http://127.0.0.1:5050",
            monitor=monitor,
        )
        async def failing_dispatch() -> bool:
            raise RuntimeError("connection refused")
        monkeypatch.setattr(executor, "_dispatch_http_stop", failing_dispatch)
        verdict = Verdict(**verdict_payload(action="stop"))

        with caplog.at_level(logging.ERROR, logger="quantlab.sqx.llm_generation_monitor"):
            result = await executor.execute(verdict)

        assert result is False
        assert any("failed" in r.message.lower() for r in caplog.records)


class TestLLMGenerationMonitor:
    """Tasks 1.6/1.7: poll loop, confidence gate, circuit breaker, defaults."""

    def test_constructor_defaults(self) -> None:
        """GIVEN only required ctor args
        WHEN LLMGenerationMonitor is constructed
        THEN thresholds and cadence defaults are 0.7 / 5, hooks default
        safely, and a default stop-confirmation hook is installed (design D5:
        stop verdicts SHALL require human confirmation).
        """
        monitor = LLMGenerationMonitor(
            campaign_id="c1",
            base_url="http://127.0.0.1:5050",
            snapshot_provider=lambda: make_snapshot(),
            llm_config=LLMConfig(),
        )

        assert monitor.confidence_threshold == 0.7
        assert monitor.poll_every_n == 5
        assert monitor.on_verdict is None
        assert monitor.confirm_stop is not None
        assert callable(monitor.confirm_stop)
        assert monitor.llm_caller is None
        assert isinstance(monitor.circuit_breaker, LLMCircuitBreaker)

    @pytest.mark.asyncio
    async def test_low_confidence_stop_does_not_dispatch(self, monkeypatch) -> None:
        """GIVEN a stop verdict with confidence 0.65 < threshold 0.7
        WHEN the monitor polls
        THEN no confirm prompt and no executor dispatch occur.
        """
        confirm = AsyncMock(return_value=True)
        monitor = LLMGenerationMonitor(
            campaign_id="c1",
            base_url="http://127.0.0.1:5050",
            snapshot_provider=lambda: make_snapshot(),
            llm_config=LLMConfig(),
            llm_caller=AsyncMock(
                return_value=json.dumps(
                    verdict_payload(action="stop", confidence=0.65)
                )
            ),
            confirm_stop=confirm,
            confidence_threshold=0.7,
            poll_every_n=1,
            monitor=Mock(cancel=AsyncMock()),
        )
        dispatch = AsyncMock(return_value=True)
        monkeypatch.setattr(monitor._executor, "_dispatch_http_stop", dispatch)

        await monitor._poll_once()

        confirm.assert_not_awaited()
        dispatch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_high_confidence_stop_dispatches_after_confirm(self, monkeypatch) -> None:
        """GIVEN a stop verdict with confidence 0.9 >= threshold 0.7
        WHEN the monitor polls and the user confirms
        THEN the stop action is dispatched via the executor.
        """
        monitor = LLMGenerationMonitor(
            campaign_id="c1",
            base_url="http://127.0.0.1:5050",
            snapshot_provider=lambda: make_snapshot(),
            llm_config=LLMConfig(),
            llm_caller=AsyncMock(
                return_value=json.dumps(
                    verdict_payload(action="stop", confidence=0.9)
                )
            ),
            confirm_stop=AsyncMock(return_value=True),
            confidence_threshold=0.7,
            poll_every_n=1,
            monitor=Mock(cancel=AsyncMock()),
        )
        dispatch = AsyncMock(return_value=True)
        monkeypatch.setattr(monitor._executor, "_dispatch_http_stop", dispatch)

        await monitor._poll_once()

        dispatch.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_on_verdict_hook_receives_verdict(self) -> None:
        """GIVEN a registered on_verdict hook
        WHEN the monitor produces a verdict
        THEN the hook is invoked with the validated verdict.
        """
        hook = Mock()
        monitor = LLMGenerationMonitor(
            campaign_id="c1",
            base_url="http://127.0.0.1:5050",
            snapshot_provider=lambda: make_snapshot(),
            llm_config=LLMConfig(),
            llm_caller=AsyncMock(return_value=json.dumps(verdict_payload())),
            on_verdict=hook,
            confidence_threshold=0.7,
            poll_every_n=1,
            monitor=Mock(cancel=AsyncMock()),
        )

        await monitor._poll_once()

        hook.assert_called_once()
        called_verdict = hook.call_args.args[0]
        assert isinstance(called_verdict, Verdict)
        assert called_verdict.recommended_action == "continue"

    @pytest.mark.asyncio
    async def test_circuit_open_treated_as_continue(self, monkeypatch, caplog) -> None:
        """GIVEN the circuit breaker is OPEN
        WHEN the monitor polls
        THEN no exception propagates and no action is dispatched.
        """
        breaker = LLMCircuitBreaker(failure_threshold=1, recovery_timeout=30.0)
        # First poll: caller raises -> circuit records failure -> OPEN.
        async def failing_caller(prompt: str, cfg: LLMConfig) -> str:
            raise RuntimeError("LLM API down")

        monitor = LLMGenerationMonitor(
            campaign_id="c1",
            base_url="http://127.0.0.1:5050",
            snapshot_provider=lambda: make_snapshot(),
            llm_config=LLMConfig(),
            llm_caller=failing_caller,
            circuit_breaker=breaker,
            confirm_stop=AsyncMock(return_value=True),
            confidence_threshold=0.7,
            poll_every_n=1,
            monitor=Mock(cancel=AsyncMock()),
        )
        dispatch = AsyncMock(return_value=True)
        monkeypatch.setattr(monitor._executor, "_dispatch_http_stop", dispatch)

        # Trip the circuit (also must not propagate).
        with caplog.at_level(logging.WARNING, logger="quantlab.sqx.llm_generation_monitor"):
            await monitor._poll_once()
        assert breaker.state == "OPEN"

        # Second poll: CircuitOpenError must be swallowed as continue.
        with caplog.at_level(logging.WARNING, logger="quantlab.sqx.llm_generation_monitor"):
            await monitor._poll_once()

        dispatch.assert_not_awaited()
        assert any("continue" in r.message.lower() for r in caplog.records)
