"""Tests for HypothesisConfig embedding/feedback/semantic_context fields (T9 3.7)."""

from __future__ import annotations


def _base_kwargs() -> dict:
    return {
        "name": "h1",
        "description": "RSI mean reversion",
        "parameters": {"rsi_period": 14},
        "expected_outcome": "Sharpe > 1.5",
        "confidence": 0.6,
    }


class TestHypothesisConfigNewFields:
    def test_defaults_none(self) -> None:
        from quantlab.dsl.models import HypothesisConfig

        hyp = HypothesisConfig(**_base_kwargs())
        assert hyp.embedding is None
        assert hyp.feedback is None
        assert hyp.semantic_context is None

    def test_embedding_field(self) -> None:
        from quantlab.dsl.models import HypothesisConfig

        hyp = HypothesisConfig(**_base_kwargs(), embedding=[0.1, 0.2, 0.3])
        assert hyp.embedding == [0.1, 0.2, 0.3]

    def test_feedback_field(self) -> None:
        from quantlab.dsl.models import HypothesisConfig
        from quantlab.knowledge.models import HypothesisFeedbackRecord

        record = HypothesisFeedbackRecord(
            campaign_id="camp-1", hypothesis_id="h1", feedback_type="pass",
            notes="good sharpe",
        )
        hyp = HypothesisConfig(**_base_kwargs(), feedback=record)
        assert hyp.feedback is not None
        assert hyp.feedback.campaign_id == "camp-1"

    def test_semantic_context_field(self) -> None:
        from quantlab.dsl.models import HypothesisConfig

        hyp = HypothesisConfig(
            **_base_kwargs(), semantic_context="Similar: hyp_old (sharpe 1.8)"
        )
        assert "hyp_old" in (hyp.semantic_context or "")

    def test_serialization_round_trip(self) -> None:
        from quantlab.dsl.models import HypothesisConfig
        from quantlab.knowledge.models import HypothesisFeedbackRecord

        hyp = HypothesisConfig(
            **_base_kwargs(),
            embedding=[0.5],
            feedback=HypothesisFeedbackRecord(campaign_id="c", hypothesis_id="h"),
            semantic_context="ctx",
        )
        dumped = hyp.model_dump()
        assert dumped["embedding"] == [0.5]
        assert dumped["semantic_context"] == "ctx"
        assert dumped["feedback"]["campaign_id"] == "c"
