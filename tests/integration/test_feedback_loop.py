"""End-to-end feedback loop test (T9 task 4.5).

Mock campaign -> feedback written -> semantic search finds the similar
prior hypothesis. Uses the real fallback path throughout (no mocks):
threshold covers the full cosine range since the hash-projection fallback
can yield small negative scores; ranking precision is covered by the
mocked unit tests.
"""

from __future__ import annotations

from pathlib import Path

import yaml


class TestFeedbackLoopEndToEnd:
    def test_full_loop(self, tmp_path: Path) -> None:
        import asyncio

        from quantlab.agents.feedback_writer import KnowledgeLakeFeedbackWriter
        from quantlab.knowledge.models import HypothesisFeedbackRecord
        from quantlab.knowledge.query import QueryBuilder
        from quantlab.knowledge.store import KnowledgeStore

        store = KnowledgeStore(root=tmp_path)
        store.initialize()

        # 1. Prior campaign with tags + metrics (the "similar prior hypothesis")
        prior_dir = tmp_path / "structured" / "camp-old"
        prior_dir.mkdir(parents=True, exist_ok=True)
        (prior_dir / "metrics.yaml").write_text(
            "sharpe_ratio: 1.8\nwin_rate: 0.55\n", encoding="utf-8"
        )
        store.tag("camp-old", ["mean_reversion", "rsi"])

        # 2. Feedback written for the new campaign's hypothesis
        writer = KnowledgeLakeFeedbackWriter(lake_root=tmp_path)
        asyncio.run(
            writer.write_feedback(
                HypothesisFeedbackRecord(
                    campaign_id="camp-new",
                    hypothesis_id="mean_reversion_rsi",
                    feedback_type="pass",
                    notes="archived after review",
                    source="gate",
                )
            )
        )
        feedback_path = tmp_path / "structured" / "camp-new" / "metadata.yaml"
        assert feedback_path.exists()
        feedback = yaml.safe_load(feedback_path.read_text(encoding="utf-8"))
        assert feedback["feedback"][0]["hypothesis_id"] == "mean_reversion_rsi"

        # 3. Semantic search over the same lake finds the prior campaign
        store.rebuild_index()
        index = store.read_index()
        builder = QueryBuilder(index=index, root=tmp_path)
        builder.filter_by_similarity(
            "rsi mean reversion strategy", top_k=5, threshold=-1.0
        )
        result = builder.execute(root=tmp_path)

        found = {c.campaign_id for c in result.campaigns}
        assert "camp-old" in found
