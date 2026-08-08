"""WU5 consumption + prompts tests (REQ-104, REQ-105, REQ-203, REQ-204, REQ-205, REQ-501, REQ-502).

Covers the read/consumption side of the knowledge lake:

- REQ-104/501: ``compose_prior_context`` injects prior decisions, risks and
  lessons from the memory lake into a markdown block for the next phase's
  Result Contract envelope; an empty lake yields a placeholder, never an error.
- REQ-501: similar campaigns are ranked by embedding similarity when
  embeddings exist (``render_prior_context`` handles the ranking section).
- REQ-502: ``KbStore.consult`` looks parameters up by exact or fuzzy name with
  tab (category) and status filters, returning metadata dicts; unknown names
  return an empty list (the REQ-204 "missing entry blocks configuration" hook).
- REQ-205: ``build_teaching_table`` renders a per-parameter teaching table.
- REQ-104 wiring: ``ResearchDirector.compose_prior_context`` reads the lake at
  its own ``knowledge_root`` (read-side twin of the WU2 capture_phase).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from quantlab.agents.research_director import ResearchDirector
from quantlab.knowledge.context import (
    compose_prior_context,
    detect_self_correction,
    render_prior_context,
)
from quantlab.knowledge.kb.models import KbParameter
from quantlab.knowledge.kb.store import KbStore
from quantlab.knowledge.kb.teaching import build_teaching_table


# ── Fixtures / helpers ────────────────────────────────────────────────────────


def write_memory(root: Path, agent: str, campaign: str, decisions: list[dict]) -> Path:
    """Write agent-memory YAML in the exact AgentMemoryManager format."""
    camp_dir = root / "agent-memory" / agent / campaign
    camp_dir.mkdir(parents=True, exist_ok=True)
    memory_file = camp_dir / "memory.yaml"
    memory_file.write_text(
        yaml.dump(decisions, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return memory_file


def prior_decisions() -> list[dict]:
    """Two decisions from a prior campaign with risks and lessons."""
    return [
        {
            "status": "success",
            "executive_summary": "Config validated with ATR stop loss",
            "artifacts": ["build_config"],
            "next_recommended": "review",
            "risks": ["overfit on EURUSD M15"],
            "lessons": "Use ATR-based stops for volatility regimes",
            "phase": "config",
            "timestamp": "2026-01-01T00:00:00+00:00",
        },
        {
            "status": "failed",
            "executive_summary": "Dispatch failed: data gaps",
            "artifacts": [],
            "next_recommended": "halt",
            "risks": ["missing M1 data"],
            "lessons": "Verify data coverage before dispatch",
            "phase": "dispatch",
            "timestamp": "2026-01-02T00:00:00+00:00",
        },
    ]


def minimal_param(**overrides: object) -> dict:
    """Valid KbParameter payload (mirrors test_kb.py's minimal fixture)."""
    base: dict[str, object] = {
        "name": "Maximum Trades Per Day",
        "sqx_name": "Maximum Trades Per Day",
        "tab": "Trading options",
        "section": "1. Trading options",
        "type": "int",
        "default": 0,
        "range": None,
        "what_it_does": "Limits daily trade count; 0 means no limit.",
        "how_it_works_in_sqx": "Builder caps entries per day to the configured value.",
        "quant_trading_role": "Prevents overtrading on small accounts.",
    }
    base.update(overrides)
    return base


@pytest.fixture()
def kb_store(tmp_path: Path) -> KbStore:
    store = KbStore(root=tmp_path / "lake")
    store.initialize()
    return store


# ──────────────────────────────────────────────────────────────────────────────
# REQ-104/501: compose_prior_context
# ──────────────────────────────────────────────────────────────────────────────


class TestComposePriorContext:
    """REQ-104/501 scenarios for compose_prior_context."""

    def test_prior_decisions_risks_lessons_injected(self, tmp_path: Path) -> None:
        write_memory(tmp_path, "research-director", "campaign-1", prior_decisions())
        out = compose_prior_context(
            "campaign-2", "config", root=tmp_path
        )
        assert "## Prior Context" in out
        assert "campaign-1" in out
        assert "Config validated with ATR stop loss" in out
        assert "overfit on EURUSD M15" in out
        assert "Use ATR-based stops for volatility regimes" in out
        assert "Dispatch failed: data gaps" in out
        assert "missing M1 data" in out

    def test_empty_lake_returns_placeholder_no_error(self, tmp_path: Path) -> None:
        out = compose_prior_context("fresh-campaign", "research", root=tmp_path)
        assert "## Prior Context" in out
        assert "no prior memory" in out.lower()
        assert "fresh-campaign" not in out  # nothing self-referential in placeholder

    def test_current_campaign_records_excluded(self, tmp_path: Path) -> None:
        write_memory(tmp_path, "research-director", "campaign-1", prior_decisions())
        current = [
            {
                "status": "success",
                "executive_summary": "Current run summary must NOT leak",
                "risks": [],
                "timestamp": "2026-02-01T00:00:00+00:00",
            }
        ]
        write_memory(tmp_path, "research-director", "campaign-9", current)
        out = compose_prior_context("campaign-9", "config", root=tmp_path)
        assert "Config validated with ATR stop loss" in out  # prior campaign
        assert "Current run summary must NOT leak" not in out  # current excluded

    def test_limit_respected_newest_first(self, tmp_path: Path) -> None:
        for i, day in enumerate(("01", "02", "03"), start=1):
            write_memory(
                tmp_path,
                "research-director",
                f"campaign-{i}",
                [{
                    "status": "success",
                    "executive_summary": f"summary campaign-{i}",
                    "risks": [f"risk-{i}"],
                    "timestamp": f"2026-03-{day}T00:00:00+00:00",
                }],
            )
        out = compose_prior_context("campaign-9", "config", root=tmp_path, limit=1)
        # Newest (campaign-3) shown, older ones dropped by the limit.
        assert "summary campaign-3" in out
        assert "summary campaign-1" not in out

    def test_agent_filter(self, tmp_path: Path) -> None:
        write_memory(tmp_path, "research-director", "campaign-1", prior_decisions())
        write_memory(
            tmp_path,
            "builder-agent",
            "campaign-1",
            [{
                "status": "success",
                "executive_summary": "builder summary",
                "risks": ["builder risk"],
                "timestamp": "2026-01-01T00:00:00+00:00",
            }],
        )
        out = compose_prior_context(
            "campaign-2", "config", root=tmp_path, agent="research-director"
        )
        assert "Config validated with ATR stop loss" in out
        assert "builder summary" not in out


class TestRenderPriorContext:
    """REQ-501: similar campaigns ranked by embedding similarity."""

    def test_similar_campaigns_ranked_desc(self) -> None:
        decisions = prior_decisions()
        similar = [
            {"campaign_id": "campaign-9", "similarity_score": 0.91},
            {"campaign_id": "campaign-2", "similarity_score": 0.72},
        ]
        out = render_prior_context("config", decisions, similar)
        assert "Similar campaigns" in out
        assert "campaign-9 (0.91)" in out
        assert "campaign-2 (0.72)" in out
        # 0.91-ranked campaign must appear before the 0.72 one.
        assert out.index("campaign-9 (0.91)") < out.index("campaign-2 (0.72)")

    def test_no_similar_section_when_empty(self) -> None:
        out = render_prior_context("config", prior_decisions(), [])
        assert "Similar campaigns" not in out


# ──────────────────────────────────────────────────────────────────────────────
# REQ-104 wiring: ResearchDirector.compose_prior_context
# ──────────────────────────────────────────────────────────────────────────────


class TestResearchDirectorContextWiring:
    """REQ-104: the director composes prior context from its knowledge_root."""

    def test_director_compose_reads_lake(self, tmp_path: Path) -> None:
        write_memory(tmp_path, "research-director", "campaign-1", prior_decisions())
        director = ResearchDirector(knowledge_root=tmp_path)
        out = director.compose_prior_context("campaign-2", "config")
        assert "## Prior Context" in out
        assert "Config validated with ATR stop loss" in out
        assert "overfit on EURUSD M15" in out

    def test_director_empty_lake_placeholder(self, tmp_path: Path) -> None:
        director = ResearchDirector(knowledge_root=tmp_path)
        out = director.compose_prior_context("fresh", "research")
        assert "no prior memory" in out.lower()

    def test_director_agent_filter(self, tmp_path: Path) -> None:
        write_memory(tmp_path, "research-director", "campaign-1", prior_decisions())
        write_memory(
            tmp_path,
            "builder-agent",
            "campaign-1",
            [{
                "status": "success",
                "executive_summary": "builder only summary",
                "risks": ["builder risk"],
                "timestamp": "2026-01-01T00:00:00+00:00",
            }],
        )
        director = ResearchDirector(knowledge_root=tmp_path)
        out = director.compose_prior_context("campaign-2", "config", agent="research-director")
        assert "Config validated with ATR stop loss" in out
        assert "builder only summary" not in out


# ──────────────────────────────────────────────────────────────────────────────
# REQ-502: KbStore.consult
# ──────────────────────────────────────────────────────────────────────────────


class TestKbConsult:
    """REQ-502 / REQ-204 hook: exact + fuzzy name lookup with filters."""

    def _seed_two(self, kb_store: KbStore) -> None:
        params = [
            KbParameter.model_validate(
                minimal_param(status="verified", evidence_ref="cfx:campaign-1")
            ),
            KbParameter.model_validate(
                minimal_param(
                    name="Ranking Criterium",
                    sqx_name="Ranking Criterium",
                    tab="Ranking",
                    section="2. Strategy Quality ranking",
                    type="str",
                    what_it_does="Selects the ranking metric.",
                    how_it_works_in_sqx="Orders strategies by the metric.",
                    quant_trading_role="Defines strategy quality.",
                )
            ),
        ]
        kb_store.seed(params)

    def test_exact_name_returns_metadata(self, kb_store: KbStore) -> None:
        self._seed_two(kb_store)
        results = kb_store.consult("Maximum Trades Per Day", tab="Trading options")
        assert len(results) == 1
        entry = results[0]
        assert entry["name"] == "Maximum Trades Per Day"
        assert entry["tab"] == "Trading options"
        assert entry["what_it_does"] == "Limits daily trade count; 0 means no limit."
        assert entry["status"] == "verified"
        assert entry["evidence_ref"] == "cfx:campaign-1"

    def test_fuzzy_substring_matches(self, kb_store: KbStore) -> None:
        self._seed_two(kb_store)
        results = kb_store.consult("Trades")
        assert len(results) == 1
        assert results[0]["name"] == "Maximum Trades Per Day"

    def test_category_filter_excludes_other_tabs(self, kb_store: KbStore) -> None:
        self._seed_two(kb_store)
        # "Criterium" exists but in the Ranking tab; Trading options filter excludes it.
        assert kb_store.consult("Criterium", tab="Trading options") == []
        assert len(kb_store.consult("Criterium", tab="Ranking")) == 1

    def test_status_filter(self, kb_store: KbStore) -> None:
        params = [
            KbParameter.model_validate(minimal_param(status="verified")),
            KbParameter.model_validate(
                minimal_param(
                    name="Minimum Trades Per Day",
                    sqx_name="Minimum Trades Per Day",
                    status="needs_review",
                )
            ),
        ]
        kb_store.seed(params)
        assert len(kb_store.consult("Trades", status="verified")) == 1
        assert len(kb_store.consult("Trades", status="needs_review")) == 1

    def test_unknown_name_returns_empty(self, kb_store: KbStore) -> None:
        self._seed_two(kb_store)
        assert kb_store.consult("NoSuchParameter") == []


# ──────────────────────────────────────────────────────────────────────────────
# REQ-205: build_teaching_table
# ──────────────────────────────────────────────────────────────────────────────


class TestTeachingTable:
    """REQ-205: structured teaching table per configured parameter."""

    def _seeded(self, kb_store: KbStore) -> None:
        params = [
            KbParameter.model_validate(
                minimal_param(
                    small_account_recommendation={
                        "recommended_value": 1,
                        "default_value": 0,
                        "reason": "Prevents overtrading and excessive commissions.",
                    },
                    why_choose="Bounded daily entries protect small equity.",
                    when_choose="Trading on volatile FX pairs.",
                )
            ),
            KbParameter.model_validate(
                minimal_param(
                    name="Ranking Criterium",
                    sqx_name="Ranking Criterium",
                    tab="Ranking",
                    section="2. Strategy Quality ranking",
                    type="str",
                    what_it_does="Selects the ranking metric.",
                    how_it_works_in_sqx="Orders strategies by the metric.",
                    quant_trading_role="Defines strategy quality.",
                )
            ),
        ]
        kb_store.seed(params)
        return kb_store.list()

    def test_teaching_table_covers_every_parameter(self, kb_store: KbStore) -> None:
        params = self._seeded(kb_store)
        table = build_teaching_table(params)
        assert "| Tab / Section |" in table
        assert "| Parameter |" in table
        assert "Maximum Trades Per Day" in table
        assert "Ranking Criterium" in table
        assert "Limits daily trade count; 0 means no limit." in table
        assert "Prevents overtrading and excessive commissions." in table

    def test_empty_teaching_table_placeholder(self) -> None:
        out = build_teaching_table([])
        assert "No KB parameters to teach" in out


# ──────────────────────────────────────────────────────────────────────────────
# WU6 — REQ-105 self-correction + knowledge_root reconciliation
# ──────────────────────────────────────────────────────────────────────────────


class TestSelfCorrection:
    """REQ-105: detection-and-report of repeated failure signatures."""

    def failed(self, summary: str, phase: str = "dispatch", **extra):
        d = {
            "agent_name": "research-director",
            "campaign_id": "campaign-1",
            "phase": phase,
            "status": "failed",
            "executive_summary": summary,
            "risks": ["missing data"],
            "lessons": [],
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        d.update(extra)
        return d

    def test_two_prior_failures_same_signature_produce_recommendation(self) -> None:
        prior = [
            self.failed("dispatch failed: data gaps in M1"),
            self.failed("dispatch failed: data gaps in M1"),
        ]
        current = self.failed("dispatch failed: data gaps prevent execution")
        recs = detect_self_correction(current, prior)
        assert len(recs) == 1
        assert "dispatch" in recs[0]

    def test_success_produces_no_recommendation(self) -> None:
        prior = [
            self.failed("dispatch failed: data gaps in M1"),
            self.failed("dispatch failed: data gaps in M1"),
        ]
        current = self.failed("dispatch OK", status="success")
        assert detect_self_correction(current, prior) == []

    def test_first_failure_no_recommendation(self) -> None:
        prior = [self.failed("dispatch failed: data gaps in M1")]
        current = self.failed("dispatch failed: data gaps prevent execution")
        assert detect_self_correction(current, prior) == []

    def test_success_with_prior_failures_no_recommendation(self) -> None:
        prior = [
            self.failed("dispatch failed: data gaps in M1"),
            self.failed("dispatch failed: data gaps in M1"),
        ]
        current = {"status": "success", "executive_summary": "all good"}
        assert detect_self_correction(current, prior) == []

    def test_render_surfaces_self_correction_on_prior_record(self) -> None:
        records = prior_decisions()
        records[0]["self_correction"] = [
            "Repeated failure signature for phase 'config': review prior campaigns above."
        ]
        block = render_prior_context("review", records)
        assert "Self-correction" in block
        assert "review prior campaigns" in block


class TestKnowledgeRootReconcile:
    """WU6: canonical knowledge_root=knowledge with backwards-compat fallback."""

    def test_director_default_root_reads_knowledge_agent_memory(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        write_memory(
            tmp_path / "knowledge",
            "research-director",
            "campaign-1",
            [
                {
                    "agent_name": "research-director",
                    "campaign_id": "campaign-1",
                    "phase": "config",
                    "status": "success",
                    "executive_summary": "Config validated with ATR stop loss",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                }
            ],
        )
        director = ResearchDirector()
        block = director.compose_prior_context("campaign-3", "review")
        assert "Config validated with ATR stop loss" in block

    def test_legacy_structured_agent_memory_read_fallback(self, tmp_path) -> None:
        write_memory(
            tmp_path / "structured",
            "research-director",
            "campaign-1",
            [
                {
                    "agent_name": "research-director",
                    "campaign_id": "campaign-1",
                    "phase": "config",
                    "status": "success",
                    "executive_summary": "Config validated with ATR stop loss",
                    "timestamp": "2026-01-01T00:00:00+00:00",
                }
            ],
        )
        block = compose_prior_context("campaign-3", "review", root=tmp_path)
        assert "Config validated with ATR stop loss" in block

    def test_rollback_deletes_structured_campaign_dir(self, tmp_path) -> None:
        from quantlab.agents.research_director import CampaignRecord
        from quantlab.dsl.models import IterationConfig, ResearchConfig

        director = ResearchDirector(knowledge_root=tmp_path)
        campaign_dir = tmp_path / "structured" / "rollback-test"
        campaign_dir.mkdir(parents=True)
        director._campaigns["rollback-test"] = CampaignRecord(
            campaign_id="rollback-test",
            config=ResearchConfig(
                campaign="RollbackTest",
                market="EURUSD",
                timeframe="H1",
                iteration_config=IterationConfig(max_iterations=1),
            ),
        )
        director.rollback_campaign("rollback-test")
        assert not campaign_dir.exists()
