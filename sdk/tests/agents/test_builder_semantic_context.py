"""Tests for semantic-context injection in HypothesisBuilder LLM mode (T9 3.6)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from quantlab.dsl.models import HypothesisConfig, LLMConfig


def _hyp(**overrides) -> HypothesisConfig:
    base = {
        "name": "mean_reversion_rsi",
        "description": "RSI(14) < 30 long entry",
        "parameters": {"rsi_period": 14},
        "expected_outcome": "Sharpe > 1.5",
        "confidence": 0.6,
    }
    base.update(overrides)
    return HypothesisConfig(**base)


_VALID_RESPONSE = json.dumps(
    {
        "building_blocks": [
            {
                "name": "RSI_14",
                "indicator": {"name": "RSI", "params": {"period": 14}},
                "entry": {"description": "oversold", "conditions": ["rsi(14) < 30"]},
                "exit": {"description": "overbought", "conditions": ["rsi(14) > 70"]},
            }
        ],
        "strategies": [
            {"name": "RsiStrategy", "direction": "LONG",
             "building_blocks": ["RSI_14"]}
        ],
    }
)


class TestLLMSemanticContext:
    def _mode(self):
        from quantlab.agents.hypothesis_builder.llm import LLMMode

        return LLMMode(LLMConfig(provider="openai"))

    def test_prompt_omits_section_when_none(self) -> None:
        mode = self._mode()
        prompt = mode._build_prompt(_hyp())
        assert "Semantic Context" not in prompt

    def test_prompt_renders_section_when_set(self) -> None:
        mode = self._mode()
        prompt = mode._build_prompt(
            _hyp(semantic_context="Similar: hyp_old (sharpe 1.8)")
        )
        assert "Semantic Context" in prompt
        assert "hyp_old" in prompt

    def test_build_forwards_hyp_context_to_prompt(self) -> None:
        import asyncio

        mode = self._mode()
        captured: dict[str, str] = {}

        async def fake_call_llm(prompt: str, cfg):  # type: ignore[no-untyped-def]
            captured["prompt"] = prompt
            return _VALID_RESPONSE

        with patch.object(mode._llm_agent, "call_llm", fake_call_llm):
            asyncio.run(
                mode.build(_hyp(semantic_context="Market: EURUSD H1"))
            )
        assert "Market: EURUSD H1" in captured["prompt"]


class TestBuilderThreadsMarketContext:
    def test_market_context_sets_semantic_context(self) -> None:
        import asyncio

        from quantlab.agents.hypothesis_builder import HypothesisBuilder

        builder = HypothesisBuilder(
            mode="llm", llm_config=LLMConfig(provider="openai")
        )
        hyp = _hyp()
        with patch(
            "quantlab.agents.hypothesis_builder.llm.LLMMode.build",
            AsyncMock(return_value=([], [])),
        ):
            # _build_with_llm stamps context before delegating to LLMMode
            asyncio.run(
                builder._build_with_llm(
                    [hyp], {"market": "EURUSD", "timeframe": "H1"}
                )
            )
        assert hyp.semantic_context is not None
        assert "EURUSD" in hyp.semantic_context

    def test_existing_semantic_context_preserved(self) -> None:
        import asyncio

        from quantlab.agents.hypothesis_builder import HypothesisBuilder

        builder = HypothesisBuilder(
            mode="llm", llm_config=LLMConfig(provider="openai")
        )
        hyp = _hyp(semantic_context="custom context")
        with patch(
            "quantlab.agents.hypothesis_builder.llm.LLMMode.build",
            AsyncMock(return_value=([], [])),
        ):
            asyncio.run(
                builder._build_with_llm(
                    [hyp], {"market": "EURUSD", "timeframe": "H1"}
                )
            )
        assert hyp.semantic_context == "custom context"

    def test_no_market_context_no_stamping(self) -> None:
        import asyncio

        from quantlab.agents.hypothesis_builder import HypothesisBuilder

        builder = HypothesisBuilder(
            mode="llm", llm_config=LLMConfig(provider="openai")
        )
        hyp = _hyp()
        with patch(
            "quantlab.agents.hypothesis_builder.llm.LLMMode.build",
            AsyncMock(return_value=([], [])),
        ):
            asyncio.run(builder._build_with_llm([hyp], None))
        assert hyp.semantic_context is None
