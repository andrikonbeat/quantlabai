"""RED tests for the G3 Dukascopy market context block in the research prompt.

Spec: llm-research "Dukascopy Market Context (G3)" + dukascopy-research-data
"Indicator Zones in Research Prompt" + "Dataset Sample Caching".

Strict TDD: written first — FAIL until ``_market_context`` and the
``build_prompt`` market block exist.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from quantlab.agents.llm_research_agent import LLMResearchAgent
from quantlab.data.market.models import Bar


# ── Helpers ────────────────────────────────────────────────────────────────────


def _rising_bars(count: int = 40) -> list[Bar]:
    """Strong upward series: RSI overbought, ADX trending."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Bar(
            timestamp=base + timedelta(hours=i),
            open=1.10 + i * 0.02,
            high=1.11 + i * 0.02,
            low=1.09 + i * 0.02,
            close=1.10 + i * 0.02,
            volume=1000.0,
        )
        for i in range(count)
    ]


def _volatile_bars() -> list[Bar]:
    """High-volatility session: last bars spike so ATR zone is 'high'."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars: list[Bar] = []
    for i in range(40):
        if i < 37:
            close = 1.10
            high = close + 0.0005
            low = close - 0.0005
        else:
            close = 1.10 + (i - 37) * 0.10
            high = close + 0.50
            low = close - 0.50
        bars.append(
            Bar(
                timestamp=base + timedelta(hours=i),
                open=close,
                high=high,
                low=low,
                close=close,
                volume=1000.0,
            )
        )
    return bars


def _few_bars() -> list[Bar]:
    """5 bars — too few for RSI(14); zones must read insufficient_data."""
    return _rising_bars(count=5)


class _FakeDukascopyProvider:
    """Hermetic provider seam injected via the module-level import."""

    def __init__(self, bars_by_symbol: dict[str, list[Bar]]) -> None:
        self.bars_by_symbol = bars_by_symbol
        self.requests: list[tuple[str, str]] = []

    def fetch_bars(self, symbol: str, timeframe: str) -> list[Bar]:
        self.requests.append((symbol, timeframe))
        return self.bars_by_symbol.get(f"{symbol}:{timeframe}", [])


def _agent_with_provider(
    bars_by_symbol: dict[str, list[Bar]], monkeypatch: pytest.MonkeyPatch
) -> LLMResearchAgent:
    provider = _FakeDukascopyProvider(bars_by_symbol)
    monkeypatch.setattr(
        "quantlab.agents.llm_research_agent.DukascopyProvider",
        lambda: provider,
    )
    agent = LLMResearchAgent()
    return agent


def _data(ticker: str = "EURUSD", **extra: object) -> dict[str, object]:
    data: dict[str, object] = {
        "fundamental": {"ticker": ticker},
        "macro": {},
        "news": [],
    }
    data.update(extra)
    return data


# ── TestDukascopyMarketBlock (task 4.2 / 4.4) ─────────────────────────────────


class TestDukascopyMarketBlock:
    """build_prompt renders the market block with zones + source; gaps omit."""

    def test_build_prompt_includes_market_block_with_timeframe_and_zones(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agent = _agent_with_provider({"EURUSD:H1": _rising_bars()}, monkeypatch)

        prompt = agent.build_prompt("momentum on EURUSD", _data())

        assert "Market Context" in prompt
        assert "EURUSD" in prompt
        assert "H1" in prompt
        assert "- RSI: overbought" in prompt
        assert "- ADX: trending" in prompt

    def test_build_prompt_cites_data_source(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agent = _agent_with_provider({"EURUSD:H1": _rising_bars()}, monkeypatch)

        prompt = agent.build_prompt("momentum on EURUSD", _data())

        assert "Dukascopy" in prompt

    def test_build_prompt_omits_raw_series_values(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agent = _agent_with_provider({"EURUSD:H1": _rising_bars()}, monkeypatch)

        prompt = agent.build_prompt("momentum on EURUSD", _data())

        # Zone labels only — no raw OHLCV series or bar dumps in the block.
        assert "- RSI: overbought" in prompt
        assert "1.10" not in prompt

    def test_build_prompt_uses_timeframe_from_data(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agent = _agent_with_provider({"EURUSD:M5": _rising_bars()}, monkeypatch)

        prompt = agent.build_prompt("momentum on EURUSD", _data(timeframe="M5"))

        assert "Market Context" in prompt
        assert "M5" in prompt

    def test_build_prompt_provider_gap_omits_block_and_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agent = _agent_with_provider({}, monkeypatch)

        prompt = agent.build_prompt("momentum on EURUSD", _data())

        assert "Market Context" not in prompt
        assert "Research Objective" in prompt

    def test_build_prompt_insufficient_bars_still_renders_block_with_insufficient_data(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agent = _agent_with_provider({"EURUSD:H1": _few_bars()}, monkeypatch)

        prompt = agent.build_prompt("momentum on EURUSD", _data())

        assert "Market Context" in prompt
        assert "insufficient_data" in prompt

    def test_build_prompt_high_volatility_reflects_zones(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agent = _agent_with_provider({"EURUSD:H1": _volatile_bars()}, monkeypatch)

        prompt = agent.build_prompt("volatile session", _data())

        assert "Market Context" in prompt
        assert "- ATR: high" in prompt

    def test_build_prompt_no_ticker_omits_block(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agent = _agent_with_provider({"EURUSD:H1": _rising_bars()}, monkeypatch)

        prompt = agent.build_prompt("research", _data(ticker=""))

        assert "Market Context" not in prompt
        assert "Research Objective" in prompt

    def test_build_prompt_provider_unavailable_omits_block(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "quantlab.agents.llm_research_agent.DukascopyProvider",
            lambda: (_ for _ in ()).throw(RuntimeError("unavailable")),
        )
        agent = LLMResearchAgent()

        prompt = agent.build_prompt("momentum on EURUSD", _data())

        assert "Market Context" not in prompt
        assert "Research Objective" in prompt


# ── TestDukascopyMarketCache (task 4.5) ───────────────────────────────────────


class TestDukascopyMarketCache:
    """cache_market_bars caches fetched samples + rebuild_index (knowledge-store)."""

    @pytest.mark.asyncio
    async def test_cache_market_bars_writes_dataset_and_records_index(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agent = _agent_with_provider({"EURUSD:H1": _rising_bars()}, monkeypatch)
        bars = _rising_bars()

        rel = await agent.cache_market_bars(
            "EURUSD", "H1", bars, knowledge_root=tmp_path
        )

        assert rel == "datasets/EURUSD/H1.csv"
        csv_path = tmp_path / "datasets" / "EURUSD" / "H1.csv"
        assert csv_path.is_file()
        lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
        assert lines[0] == "timestamp,open,high,low,close,volume"
        assert len(lines) == len(bars) + 1
        index = yaml.safe_load((tmp_path / "index.yaml").read_text(encoding="utf-8"))
        assert index["_version"] == "5"
        assert "datasets/EURUSD/H1.csv" in index["directories"]["datasets"]

    @pytest.mark.asyncio
    async def test_cache_market_bars_empty_bars_returns_none(
        self, tmp_path: Path
    ) -> None:
        agent = LLMResearchAgent()

        rel = await agent.cache_market_bars("EURUSD", "H1", [], knowledge_root=tmp_path)

        assert rel is None
        assert not (tmp_path / "datasets" / "EURUSD" / "H1.csv").exists()

    @pytest.mark.asyncio
    async def test_cache_market_bars_refetches_when_bars_omitted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        agent = _agent_with_provider({"EURUSD:H1": _rising_bars()}, monkeypatch)

        rel = await agent.cache_market_bars("EURUSD", "H1", knowledge_root=tmp_path)

        assert rel == "datasets/EURUSD/H1.csv"
        assert (tmp_path / "datasets" / "EURUSD" / "H1.csv").is_file()

    @pytest.mark.asyncio
    async def test_generate_config_caches_market_bars(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quantlab.dsl.models import LLMConfig

        agent = _agent_with_provider({"EURUSD:H1": _rising_bars()}, monkeypatch)

        response = (
            '{"campaign":"c","market":"EURUSD","timeframe":"H1",'
            '"hypotheses":[{"name":"h1","description":"d",'
            '"parameters":{"rsi_period":14},"expected_outcome":"x",'
            '"confidence":0.5,"source_urls":["https://example.com"]}]}'
        )
        monkeypatch.setattr(
            "quantlab.agents.llm_research_agent.LLMCircuitBreaker.call",
            lambda self, coro: coro,
        )
        monkeypatch.setattr(
            agent,
            "call_llm",
            lambda prompt, llm_config: response,  # type: ignore[method-assign]
        )

        config = await agent.generate_config(
            objectives=["momentum on EURUSD"],
            market_context={"market": "EURUSD", "timeframe": "H1"},
            llm_config=LLMConfig(provider="opencode"),
            knowledge_root=tmp_path,
        )

        assert config.market == "EURUSD"
        assert (tmp_path / "datasets" / "EURUSD" / "H1.csv").is_file()