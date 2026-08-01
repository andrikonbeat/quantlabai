"""Unit tests for the LLM Generation Monitor (Phase 1 core module).

Covers: ``parse_verdict`` (valid/fenced/invalid/missing/bad confidence),
``build_prompt`` (counts + baseline + JSON schema), confidence gate,
``ActionExecutor`` (stop vs continue), circuit-open degradation,
constructor defaults, ``CampaignMonitor`` databank observability
(``parse_databank_counts`` + ``current_snapshot``), and the mock SQX
server rejection mode.
"""

import asyncio
import json
import logging
import re
import time
import urllib.parse
from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from quantlab.dsl.models import LLMConfig
from quantlab.robustness.llm_circuit_breaker import LLMCircuitBreaker
from quantlab.sqx.campaign_monitor import (
    BaselineConfig,
    CampaignMonitor,
    parse_databank_counts,
)
from quantlab.sqx.cli_wrapper import dispatch_campaign
from quantlab.sqx.llm_generation_monitor import (
    ActionExecutor,
    LLMGenerationMonitor,
    MonitorSnapshot,
    Verdict,
    build_prompt,
    parse_verdict,
)
from quantlab.sqx.campaign_monitor import extract_results_count


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


class TestParseDatabankCounts:
    """Task 2.1: parse_databank_counts tolerates formats; garbage → None."""

    MOCK_LIST_OUTPUT = (
        "List of available databanks\n"
        "--------------------------------------------------\n"
        "Results, Records: 3\n"
        "Initial population, Records: 0\n"
        "Last generation, Records: 0\n"
    )

    def test_mock_format_all_databanks(self) -> None:
        """GIVEN mock -databank action=list output
        WHEN parse_databank_counts is called
        THEN per-databank record counts are returned (banner skipped).
        """
        assert parse_databank_counts(self.MOCK_LIST_OUTPUT) == {
            "Results": 3,
            "Initial population": 0,
            "Last generation": 0,
        }

    def test_colonless_variant(self) -> None:
        """GIVEN 'Results, Records 3' (no colon separator)
        WHEN parse_databank_counts is called
        THEN the count is still parsed (colon is optional).
        """
        assert parse_databank_counts(
            "Results, Records 3\nStrategies, Records 5\n"
        ) == {
            "Results": 3,
            "Strategies": 5,
        }

    def test_single_databank_line(self) -> None:
        """GIVEN a single databank line
        WHEN parse_databank_counts is called
        THEN the single mapping is returned.
        """
        assert parse_databank_counts("Results, Records: 12\n") == {"Results": 12}

    def test_extract_results_count_space_variant(self) -> None:
        """GIVEN status text with 'Strategies generated  58' (space separator)
        WHEN extract_results_count is called
        THEN 58 is returned.
        """
        assert extract_results_count("Strategies generated  58\nAccepted: 0\n") == 58

    def test_extract_results_count_colon_variant(self) -> None:
        """GIVEN status text with 'Strategies generated: 58' (colon separator)
        WHEN extract_results_count is called
        THEN 58 is returned (spec: both variants accepted).
        """
        assert extract_results_count("Strategies generated: 58\nAccepted: 0\n") == 58

    def test_extract_results_count_unparseable_returns_zero(self) -> None:
        """GIVEN status text with no parseable count
        WHEN extract_results_count is called
        THEN 0 is returned without raising.
        """
        assert extract_results_count("Generation in progress\n") == 0
        assert extract_results_count("") == 0

    def test_case_insensitive_label(self) -> None:
        """GIVEN an uppercase label
        WHEN parse_databank_counts is called
        THEN the count is still parsed.
        """
        assert parse_databank_counts("RESULTS, RECORDS: 3\n") == {"RESULTS": 3}

    def test_partial_garbage_lines_skipped(self) -> None:
        """GIVEN a mix of parseable and unexpected lines
        WHEN parse_databank_counts is called
        THEN the parseable databanks are returned and the rest are skipped.
        """
        assert parse_databank_counts(
            "some unexpected output\nResults, Records: 7\n"
        ) == {"Results": 7}

    def test_garbage_returns_none_and_warns(self, caplog) -> None:
        """GIVEN databank output that cannot be parsed
        WHEN parse_databank_counts is called
        THEN None is returned and a warning is logged (counts unknown).
        """
        with caplog.at_level(
            logging.WARNING, logger="quantlab.sqx.campaign_monitor"
        ):
            result = parse_databank_counts("no databanks here\n")

        assert result is None
        assert any("unknown" in r.message.lower() for r in caplog.records)

    def test_empty_returns_none(self) -> None:
        """GIVEN empty or missing databank output
        WHEN parse_databank_counts is called
        THEN None is returned (counts treated as unknown).
        """
        assert parse_databank_counts("") is None
        assert parse_databank_counts(None) is None


class TestCurrentSnapshot:
    """Task 2.3: current_snapshot exposes status, counts, elapsed, baseline."""

    @staticmethod
    def _monitor(**kwargs: Any) -> CampaignMonitor:
        baseline = BaselineConfig(
            startup_grace_s=60.0,
            expected_gen_time_s=32.0,
            early_gen_multiplier=2.0,
            early_gen_count=3,
            stall_polls_threshold=21,
            rejection_warn_gens=3,
        )
        config = {
            "timeframe": "M1",
            "walk_forward": True,
            "monte_carlo": True,
            "generations": 80,
            "population": 200,
            "market": "EURUSD",
            "criteria": [{"metric": "profit_factor", "operator": ">", "value": 1.3}],
        }
        return CampaignMonitor(
            campaign_id="c1",
            base_url="http://127.0.0.1:5050",
            baseline=baseline,
            config=config,
            **kwargs,
        )

    def test_snapshot_fields(self) -> None:
        """GIVEN a monitor with observed state
        WHEN current_snapshot is called
        THEN a MonitorSnapshot with status/counts/elapsed/baseline is returned.
        """
        monitor = self._monitor()
        monitor._last_status_text = "Strategies generated  10\nGeneration: 3\n"
        monitor._last_count = 10
        monitor._databank_counts = {"Results": 2, "Strategies": 2}
        monitor._start_time = time.monotonic() - 5.0

        snap = monitor.current_snapshot()

        assert isinstance(snap, MonitorSnapshot)
        assert snap.status_text == "Strategies generated  10\nGeneration: 3\n"
        assert snap.generated_count == 10
        assert snap.databank_counts == {"Results": 2, "Strategies": 2}
        assert snap.elapsed_s == pytest.approx(5.0, abs=0.2)
        # Raw config values surface for the verdict prompt ...
        assert snap.baseline["generations"] == 80
        assert snap.baseline["population"] == 200
        assert snap.baseline["walk_forward"] is True
        assert snap.baseline["monte_carlo"] is True
        assert snap.baseline["market"] == "EURUSD"
        assert snap.baseline["timeframe"] == "M1"
        assert snap.baseline["criteria"][0]["metric"] == "profit_factor"
        # ... merged with the derived BaselineConfig timing parameters.
        assert snap.baseline["stall_polls_threshold"] == 21
        assert snap.baseline["startup_grace_s"] == 60.0

    def test_snapshot_before_run_defaults(self) -> None:
        """GIVEN a monitor that has not started polling
        WHEN current_snapshot is called
        THEN empty status, 0 generated, None counts, 0 elapsed are returned.
        """
        snap = self._monitor().current_snapshot()

        assert snap.status_text == ""
        assert snap.generated_count == 0
        assert snap.databank_counts is None
        assert snap.elapsed_s == 0.0

    def test_snapshot_without_config_uses_derived_baseline_only(self) -> None:
        """GIVEN a monitor constructed without a raw config
        WHEN current_snapshot is called
        THEN the baseline carries the derived BaselineConfig values alone.
        """
        baseline = BaselineConfig(
            startup_grace_s=60.0,
            expected_gen_time_s=32.0,
            early_gen_multiplier=2.0,
            early_gen_count=3,
            stall_polls_threshold=21,
            rejection_warn_gens=3,
        )
        monitor = CampaignMonitor(
            "c1", "http://127.0.0.1:5050", baseline
        )

        snap = monitor.current_snapshot()

        assert snap.baseline == baseline.to_dict()

    def test_poll_tick_stores_databank_counts(self) -> None:
        """GIVEN a poll tick with databank output
        WHEN _poll_tick runs
        THEN the parsed counts and status text are stored for the snapshot
        and no heuristic events fire for a healthy tick.
        """
        monitor = self._monitor()
        events = monitor._poll_tick(
            "Strategies generated                           10\n",
            elapsed=5.0,
            databank_text="Results, Records: 2\nStrategies, Records: 2\n",
        )

        assert monitor._databank_counts == {"Results": 2, "Strategies": 2}
        assert monitor._last_status_text.startswith("Strategies generated")
        assert events == []

    def test_poll_tick_failed_databank_sets_counts_unknown(self) -> None:
        """GIVEN a poll tick without databank output
        WHEN _poll_tick runs
        THEN databank counts are treated as unknown and heuristics still run.
        """
        monitor = self._monitor()
        events = monitor._poll_tick(
            "Strategies generated                           10\n", elapsed=5.0
        )

        assert monitor._databank_counts is None
        assert isinstance(events, list)


class TestMockServerRejectionMode:
    """Task 4.1: rejection mode — growing generation count, static databank
    (0 records), campaign never completes until an explicit action=stop."""

    BASE_URL = "http://127.0.0.1:5050"

    @staticmethod
    def _cmd(command: str) -> str:
        return urllib.parse.quote(command, safe="=")

    @pytest.fixture(autouse=True)
    def _rejection_server(self) -> Any:
        from quantlab.sqx.mock_sqx_server import MockSQXHandler, MockSQXServer

        MockSQXServer.reset()
        server = MockSQXServer.instance(port=5050, mode="rejection")
        server.start()
        yield
        MockSQXServer.reset()
        MockSQXHandler._mode = "normal"

    async def _send(
        self, client: httpx.AsyncClient, command: str
    ) -> httpx.Response:
        return await client.get(f"{self.BASE_URL}/call?cmd={self._cmd(command)}")

    @pytest.mark.asyncio
    async def test_rejection_mode_never_completes_and_counts_grow(self) -> None:
        """GIVEN a rejection-mode campaign
        WHEN status is polled repeatedly past the normal completion time
        THEN the generated count grows, the databank stays at 0 records,
        the campaign never completes, and action=stop finally stops it.
        """
        async with httpx.AsyncClient(timeout=5.0) as client:
            await self._send(client, "-project action=start name=rej-camp")

            counts: list[int] = []
            for _ in range(3):
                resp = await self._send(
                    client, "-project action=status name=rej-camp"
                )
                match = re.search(
                    r"Strategies generated\s+(\d+)", resp.text
                )
                assert match is not None, f"no count in: {resp.text!r}"
                counts.append(int(match.group(1)))
                assert "Status: completed" not in resp.text
                await asyncio.sleep(0.05)

            # Generated count grows across status polls.
            assert counts == [10, 20, 30], counts

            # Databank record count stays at 0 (static rejection signal).
            db = await self._send(client, "-databank action=list")
            assert "Results, Records: 0" in db.text

            # Wait past the normal-mode completion duration (~2s) — in
            # rejection mode the campaign must still be running.
            await asyncio.sleep(2.5)
            status = await self._send(
                client, "-project action=status name=rej-camp"
            )
            assert "Status: completed" not in status.text
            assert "Strategies generated" in status.text

            # Explicit stop terminates the campaign.
            stop = await self._send(client, "-project action=stop name=rej-camp")
            assert "stopped" in stop.text.lower()
            after = await self._send(
                client, "-project action=status name=rej-camp"
            )
            assert "Strategies generated" in after.text

    @pytest.mark.asyncio
    async def test_normal_mode_still_completes(self) -> None:
        """GIVEN the default (normal) mode
        WHEN a campaign runs
        THEN the full lifecycle completes as before (regression guard).
        """
        from quantlab.sqx.mock_sqx_server import MockSQXServer

        MockSQXServer.reset()
        server = MockSQXServer.instance(port=5050, mode="normal")
        server.start()

        async with httpx.AsyncClient(timeout=5.0) as client:
            await self._send(client, "-project action=start name=normal-camp")
            # Normal simulation completes in ~2s.
            await asyncio.sleep(2.5)
            status = await self._send(
                client, "-project action=status name=normal-camp"
            )
            assert "completed" in status.text.lower()


# ═══════════════════════════════════════════════════════════════════════════
# 4.4: Integration — LLM monitor wired to a real (mock) SQX server
# ═══════════════════════════════════════════════════════════════════════════


class TestLLMMonitorIntegration:
    """Task 4.4: fake llm_caller against the real mock server.

    - Stop verdict + confirm True → HTTP stop dispatched (campaign stopped).
    - Low confidence → no action, no confirm hook.
    - LLM raising → no exception; heuristics keep polling (databank
      observability still populated).
    """

    BASE_URL = "http://127.0.0.1:5050"

    @pytest.fixture(autouse=True)
    def _rejection_server(self) -> Any:
        from quantlab.sqx.mock_sqx_server import MockSQXHandler, MockSQXServer

        MockSQXServer.reset()
        server = MockSQXServer.instance(port=5050, mode="rejection")
        server.start()
        yield
        MockSQXServer.reset()
        MockSQXHandler._mode = "normal"

    @staticmethod
    def _cmd(command: str) -> str:
        return urllib.parse.quote(command, safe="=")

    def _baseline(self) -> BaselineConfig:
        return BaselineConfig(
            startup_grace_s=60.0,
            expected_gen_time_s=32.0,
            early_gen_multiplier=2.0,
            early_gen_count=3,
            stall_polls_threshold=21,
            rejection_warn_gens=3,
        )

    async def _start_campaign(self, name: str) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{self.BASE_URL}/call?cmd={self._cmd(f'-project action=start name={name}')}"
            )
            resp.raise_for_status()

    @staticmethod
    def _campaign_status(name: str) -> str:
        from quantlab.sqx.mock_sqx_server import MockSQXHandler

        return MockSQXHandler._campaigns.get(name, {}).get("status", "not found")

    async def _monitor_pair(
        self,
        campaign_id: str,
        llm_caller: Any,
        confirm_stop: Any,
    ) -> tuple[CampaignMonitor, LLMGenerationMonitor, asyncio.Task[Any]]:
        """Start a CampaignMonitor task and wire an LLMGenerationMonitor that
        reads its snapshot; returns (monitor, llm_monitor, monitor_task)."""
        monitor = CampaignMonitor(
            campaign_id=campaign_id,
            base_url=self.BASE_URL,
            baseline=self._baseline(),
            poll_interval=0.05,
            config={"timeframe": "M1", "generations": 80, "population": 200},
        )
        monitor_task = asyncio.create_task(monitor.run())
        await asyncio.sleep(0.2)  # let the monitor populate snapshot state
        llm_monitor = LLMGenerationMonitor(
            campaign_id=campaign_id,
            base_url=self.BASE_URL,
            snapshot_provider=monitor.current_snapshot,
            llm_config=LLMConfig(),
            llm_caller=llm_caller,
            confirm_stop=confirm_stop,
            confidence_threshold=0.7,
            poll_every_n=1,
            monitor=monitor,
        )
        return monitor, llm_monitor, monitor_task

    @pytest.mark.asyncio
    async def test_stop_verdict_confirmed_dispatches_http_stop(self) -> None:
        """GIVEN a stop verdict above the confidence threshold and a
        confirming human hook
        WHEN the monitor polls against the real mock server
        THEN the HTTP stop is dispatched (campaign state 'stopped') and the
        CampaignMonitor is cancelled (spec: stop uses the cancel path).
        """
        await self._start_campaign("rej-int-stop")
        confirm = AsyncMock(return_value=True)
        caller = AsyncMock(
            return_value=json.dumps(verdict_payload(action="stop", confidence=0.9))
        )
        monitor, llm_monitor, monitor_task = await self._monitor_pair(
            "rej-int-stop", caller, confirm
        )

        await llm_monitor._poll_once()

        assert self._campaign_status("rej-int-stop") == "stopped"
        confirm.assert_awaited_once()
        confirm.assert_awaited_with(
            Verdict(**verdict_payload(action="stop", confidence=0.9))
        )
        assert monitor._stopped is True

        await monitor.cancel()
        await asyncio.gather(monitor_task, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_low_confidence_never_dispatches(self) -> None:
        """GIVEN a stop verdict with confidence below the threshold
        WHEN the monitor polls against the real mock server
        THEN no HTTP stop is dispatched and the confirm hook never runs
        (spec: low-confidence verdicts never dispatch).
        """
        await self._start_campaign("rej-int-lowconf")
        confirm = AsyncMock(return_value=True)
        caller = AsyncMock(
            return_value=json.dumps(verdict_payload(action="stop", confidence=0.65))
        )
        monitor, llm_monitor, monitor_task = await self._monitor_pair(
            "rej-int-lowconf", caller, confirm
        )

        await llm_monitor._poll_once()

        assert self._campaign_status("rej-int-lowconf") == "running"
        confirm.assert_not_awaited()

        await monitor.cancel()
        await asyncio.gather(monitor_task, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_llm_raising_keeps_heuristics_running(self) -> None:
        """GIVEN the LLM caller raises (API error / circuit open)
        WHEN the monitor polls
        THEN no exception propagates and the CampaignMonitor heuristics
        continue polling normally — databank observability still updates
        (spec: LLM failure leaves heuristics running).
        """
        await self._start_campaign("rej-int-raise")

        async def failing_caller(prompt: str, cfg: LLMConfig) -> str:
            raise RuntimeError("LLM API down")

        monitor, llm_monitor, monitor_task = await self._monitor_pair(
            "rej-int-raise", failing_caller, AsyncMock(return_value=True)
        )

        await llm_monitor._poll_once()  # must not raise

        snapshot = monitor.current_snapshot()
        assert "Strategies generated" in snapshot.status_text
        assert snapshot.databank_counts == {
            "Results": 0,
            "Initial population": 0,
            "Last generation": 0,
        }

        await monitor.cancel()
        await asyncio.gather(monitor_task, return_exceptions=True)


# ═══════════════════════════════════════════════════════════════════════════
# 4.5: E2E — dispatch_campaign + LLM monitor
# ═══════════════════════════════════════════════════════════════════════════


class TestDispatchLLMMonitorE2E:
    """Task 4.5: dispatch_campaign(force_mock=True, llm_config=...) E2E.

    - Rejection-mode campaign + fake stop verdict + confirm True → the
      campaign is stopped before completion and dispatch returns promptly
      (not via timeout).
    - Without llm_config → zero LLM calls and an identical result shape
      (spec: "Hook not registered preserves behavior").
    """

    BASE_URL = "http://127.0.0.1:5050"
    RESULT_KEYS = {"status", "export_paths", "watcher_events"}

    @pytest.fixture(autouse=True)
    def _mock_server(self) -> Any:
        from quantlab.sqx.mock_sqx_server import MockSQXServer

        MockSQXServer.reset()
        yield
        MockSQXServer.reset()

    @staticmethod
    def _config() -> dict[str, Any]:
        return {
            "market": "EURUSD",
            "timeframe": "H1",
            "walk_forward": True,
            "monte_carlo": True,
        }

    @pytest.mark.asyncio
    async def test_e2e_llm_stop_before_completion(self) -> None:
        """GIVEN a rejection-mode campaign (never completes naturally), an
        llm_config, and a fake LLM caller returning a high-confidence stop
        verdict
        WHEN dispatch_campaign runs with confirm_stop=True
        THEN the campaign is stopped early, dispatch returns before the
        timeout, the verdict hook fires, and the result shape is unchanged.
        """
        from quantlab.sqx.mock_sqx_server import MockSQXHandler, MockSQXServer

        MockSQXServer.reset()
        server = MockSQXServer.instance(port=5050, mode="rejection")
        server.start()

        hook = Mock()
        confirm = AsyncMock(return_value=True)
        caller = AsyncMock(
            return_value=json.dumps(verdict_payload(action="stop", confidence=0.9))
        )

        result = await dispatch_campaign(
            cfx_bytes=b"dummy-cfx",
            campaign_id="e2e-llm-stop",
            config=self._config(),
            poll_interval=0.1,
            timeout=30.0,
            force_mock=True,
            on_watcher_event=Mock(),
            llm_config=LLMConfig(),
            on_llm_verdict=hook,
            llm_caller=caller,
            confirm_stop=confirm,
            poll_every_n=1,
        )

        # Prompt return, not timeout — the LLM stop path ended dispatch.
        assert result["status"] == "completed"
        assert set(result.keys()) == self.RESULT_KEYS
        # The campaign was stopped on the server (zero-acceptance stop).
        assert MockSQXHandler._campaigns["e2e-llm-stop"]["status"] == "stopped"
        # The verdict hook received the stop verdict.
        assert hook.call_count >= 1
        verdict = hook.call_args.args[0]
        assert isinstance(verdict, Verdict)
        assert verdict.recommended_action == "stop"

    @pytest.mark.asyncio
    async def test_e2e_no_llm_config_zero_llm_calls(self, monkeypatch) -> None:
        """Spec scenario "Hook not registered preserves behavior": dispatch
        without llm_config makes ZERO LLM calls and returns the same result
        shape as before this change."""
        import quantlab.sqx.llm_generation_monitor as llm_mod

        llm_call = Mock()
        monkeypatch.setattr(llm_mod, "_call_llm", llm_call)

        callback = Mock()
        result = await dispatch_campaign(
            cfx_bytes=b"dummy-cfx",
            campaign_id="e2e-no-llm",
            config=self._config(),
            poll_interval=0.2,
            timeout=30.0,
            force_mock=True,
            on_watcher_event=callback,
        )

        assert llm_call.call_count == 0
        assert set(result.keys()) == self.RESULT_KEYS
        assert result["status"] == "completed"
        # Heuristic monitoring still ran (normal-mode campaign completes).
        assert isinstance(result["watcher_events"], list)
