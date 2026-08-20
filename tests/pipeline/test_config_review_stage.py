"""ConfigReviewStage G7 — reviewer-owned persisted teaching table.

parameter-educational-table delta scenarios driven through the stage:
- Review persists the table (path in verdict + ``PhaseResult.artifacts``).
- Parameter without KB entry yields a stable fallback row and the table is
  still persisted.
- Empty config yields the stable placeholder line and the stage completes
  without error.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from quantlab.campaign.delegation import PhaseDirective, execute_phase
from quantlab.knowledge.kb.models import KbParameter
from quantlab.knowledge.kb.store import KbStore
from quantlab.knowledge.kb.teaching import EMPTY_TABLE_NOTE
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.config_review_stage import (
    ConfigReviewStage,
    build_review_teaching_table,
)
from quantlab.sqx.project_builder import BuildConfig

TEACHING_REL = "structured/camp-1/review/teaching-table.md"


def _param(name: str, **overrides: object) -> KbParameter:
    """A minimal valid KB parameter for the review teaching table."""
    base: dict[str, object] = {
        "name": name,
        "sqx_name": name,
        "tab": "What to build",
        "section": f"3. {name} configuration",
        "type": "config",
        "default": "ATR-based",
        "range": None,
        "what_it_does": f"Sets the {name} rule used by the builder.",
        "how_it_works_in_sqx": f"The builder attaches {name} to generated strategies.",
        "quant_trading_role": f"{name} is a mandatory capital-survival control.",
        "why_choose": f"Protocol requires {name}.",
        "when_choose": "Always required.",
    }
    base.update(overrides)
    return KbParameter.model_validate(base)


def _seed(root: Path, *params: KbParameter) -> KbStore:
    store = KbStore(root=root)
    store.initialize()
    if params:
        store.seed(list(params))
    return store


def _ctx(
    root: Path,
    build_config: BuildConfig | None,
    campaign_id: str = "camp-1",
) -> PipelineContext:
    return PipelineContext(
        config={"campaign_id": campaign_id, "knowledge_root": str(root)},
        artifacts={"build_config": build_config},
    )


def _run(stage, ctx: PipelineContext) -> dict:
    return asyncio.run(stage.execute(ctx))


def _read(root: Path) -> str:
    return (root / TEACHING_REL).read_text(encoding="utf-8")


class TestTeachingTablePersistence:
    """parameter-educational-table scenarios on the stage execute path."""

    def test_review_persists_teaching_table_in_verdict_and_outcome(self, tmp_path: Path) -> None:
        _seed(tmp_path, _param("Stop Loss"), _param("Profit Target"))
        ctx = _ctx(
            tmp_path,
            BuildConfig(
                sl_required=True,
                sl_value_type="pips",
                pt_required=True,
                pt_value_type="pips",
            ),
        )

        outcome = _run(ConfigReviewStage(), ctx)

        assert (tmp_path / TEACHING_REL).is_file()
        assert outcome["teaching_table"] == TEACHING_REL
        verdict = ctx.artifacts["config_review_verdict"]
        assert verdict["teaching_table"] == TEACHING_REL
        assert verdict["action"] == "APPROVE"

    def test_teaching_table_renders_kb_rows(self, tmp_path: Path) -> None:
        _seed(tmp_path, _param("Stop Loss"))
        _run(ConfigReviewStage(), _ctx(tmp_path, BuildConfig(sl_required=True, min_sl_pips=20)))

        content = _read(tmp_path)
        assert "| Tab / Section | Parameter |" in content
        assert "| What to build / 3. Stop Loss configuration | Stop Loss |" in content
        assert "capital-survival control" in content

    def test_parameter_without_kb_entry_adds_stable_fallback_row(self, tmp_path: Path) -> None:
        _seed(tmp_path, _param("Stop Loss"))
        _run(
            ConfigReviewStage(),
            _ctx(
                tmp_path,
                BuildConfig(sl_required=True, pt_required=True, limit_slpt_rrr=True),
            ),
        )

        content = _read(tmp_path)
        assert "| Review | limit_slpt_rrr | No KB entry | — | — | — | — | — |" in content
        assert "| Review | pt_required | No KB entry | — | — | — | — | — |" in content

    def test_empty_config_persists_placeholder_table(self, tmp_path: Path) -> None:
        _seed(tmp_path, _param("Stop Loss"))
        ctx = _ctx(tmp_path, None)

        outcome = _run(ConfigReviewStage(), ctx)

        assert (tmp_path / TEACHING_REL).is_file()
        assert _read(tmp_path).strip() == EMPTY_TABLE_NOTE
        assert outcome["teaching_table"] == TEACHING_REL
        assert ctx.artifacts["config_review_verdict"]["action"] == "APPROVE"

    def test_all_none_config_persists_placeholder_table(self, tmp_path: Path) -> None:
        _seed(tmp_path, _param("Stop Loss"))
        outcome = _run(ConfigReviewStage(), _ctx(tmp_path, BuildConfig()))

        assert (tmp_path / TEACHING_REL).is_file()
        assert _read(tmp_path).strip() == EMPTY_TABLE_NOTE
        assert outcome["teaching_table"] == TEACHING_REL

    def test_no_kb_entries_still_persists_header_with_fallback_rows(self, tmp_path: Path) -> None:
        bc = BuildConfig(sl_required=True, pt_required=True)
        _run(ConfigReviewStage(), _ctx(tmp_path, bc))

        content = _read(tmp_path)
        assert "| Tab / Section | Parameter |" in content
        assert content.count("No KB entry") == 2

    def test_missing_campaign_context_degrades_no_persist(self, tmp_path: Path) -> None:
        ctx = PipelineContext(
            config={},
            artifacts={"build_config": BuildConfig(sl_required=True)},
        )

        outcome = _run(ConfigReviewStage(), ctx)

        assert outcome["teaching_table"] == ""
        assert ctx.artifacts["config_review_verdict"]["teaching_table"] == ""
        assert not (tmp_path / "structured").exists()


class TestBuildReviewTeachingTable:
    """Pure rendering contract of ``build_review_teaching_table``."""

    def test_placeholder_when_no_config(self) -> None:
        assert build_review_teaching_table(None, lambda _: []) == EMPTY_TABLE_NOTE

    def test_placeholder_when_no_configured_fields(self) -> None:
        assert build_review_teaching_table(BuildConfig(), lambda _: []) == EMPTY_TABLE_NOTE

    def test_fallback_rows_when_consult_empty(self) -> None:
        out = build_review_teaching_table(
            BuildConfig(sl_required=True, pt_required=True), lambda _: []
        )
        assert "| Tab / Section | Parameter |" in out
        assert "| Review | sl_required | No KB entry | — | — | — | — | — |" in out
        assert "| Review | pt_required | No KB entry | — | — | — | — | — |" in out

    def test_kb_hits_rendered_and_deduped(self) -> None:
        def consult(term: str) -> list[dict[str, object]]:
            if term == "Stop Loss":
                return [_param("Stop Loss").model_dump()]
            return []

        out = build_review_teaching_table(
            BuildConfig(sl_required=True, min_sl_pips=20, sl_atr=True),
            consult,
        )
        # Three configured fields map to the same KB term — one deduped row.
        assert out.count("| What to build / 3. Stop Loss configuration | Stop Loss |") == 1


class TestReviewPhaseEnvelope:
    """G7 spec: the teaching-table path lands in ``PhaseResult.artifacts``."""

    def test_review_phase_artifacts_include_teaching_table(self, tmp_path: Path) -> None:
        _seed(tmp_path, _param("Stop Loss"))
        payload = {
            "campaign_id": "camp-1",
            "knowledge_root": str(tmp_path),
            "artifacts": {
                "build_config": BuildConfig(sl_required=True, pt_required=True),
            },
        }

        result = asyncio.run(
            execute_phase(
                PhaseDirective(
                    phase_id="review",
                    scope="review-scope",
                    payload=payload,
                )
            )
        )

        assert result.status == "success"
        assert TEACHING_REL in result.artifacts
        assert (tmp_path / TEACHING_REL).is_file()