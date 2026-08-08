"""Tests for SQXKnowledgeStoreStage canonical Knowledge Lake writes (W1).

REQ-101/REQ-402: campaign artifacts MUST be written under
``structured/{campaign_id}/`` and each write MUST pass conformance before
landing. The read side already tolerates both layouts; these tests pin the
WRITE-side canonical layout so pipeline writes can never silently drift
off-layout again.
"""

import yaml
import pytest

from pathlib import Path

from quantlab.knowledge.conformance import ConformanceError
from quantlab.phase4.stages import SQXKnowledgeStoreStage
from quantlab.pipeline.base import PipelineContext


def _make_context(
    tmp_path: Path,
    *,
    campaign_name: str = "MyCampaign",
    with_knowledge_root: bool = True,
) -> tuple[PipelineContext, Path, Path]:
    """Build a PipelineContext plus the expected lake root and export source."""
    lake = tmp_path / "lake"
    source = tmp_path / "src"
    source.mkdir()
    export_src = source / "backtest.csv"
    export_src.write_text("a,b\n1,2\n", encoding="utf-8")

    config: dict = {"campaign_name": campaign_name}
    if with_knowledge_root:
        config["knowledge_root"] = str(lake)

    ctx = PipelineContext(
        config=config,
        artifacts={
            "cfx_bytes": b"cfx-bytes",
            "export_paths": {"backtest": export_src},
            "statistics": {"total_trades": 3, "win_rate": 0.5},
        },
    )
    return ctx, lake, export_src


class TestSQXKnowledgeStoreStage:
    """SQXKnowledgeStoreStage writes the canonical Knowledge Lake layout."""

    @pytest.mark.asyncio
    async def test_cfx_written_under_structured_campaign_dir(self, tmp_path: Path) -> None:
        ctx, lake, _ = _make_context(tmp_path)
        await SQXKnowledgeStoreStage().execute(ctx)

        cfx = lake / "structured" / "MyCampaign" / "MyCampaign.cfx"
        assert cfx.is_file(), f"expected canonical CFX at {cfx}"
        assert cfx.read_bytes() == b"cfx-bytes"
        assert not (lake / "campaigns").exists(), "legacy campaigns/ layout must not be written"

    @pytest.mark.asyncio
    async def test_results_written_under_structured_campaign_results(self, tmp_path: Path) -> None:
        ctx, lake, export_src = _make_context(tmp_path)
        await SQXKnowledgeStoreStage().execute(ctx)

        dest = lake / "structured" / "MyCampaign" / "results" / "backtest.csv"
        assert dest.is_file(), f"expected canonical result at {dest}"
        assert dest.read_text(encoding="utf-8") == "a,b\n1,2\n"
        assert not (lake / "results").exists(), "legacy results/ layout must not be written"

    @pytest.mark.asyncio
    async def test_stats_written_to_structured_campaign_metrics_yaml(self, tmp_path: Path) -> None:
        ctx, lake, _ = _make_context(tmp_path)
        await SQXKnowledgeStoreStage().execute(ctx)

        metrics = lake / "structured" / "MyCampaign" / "metrics.yaml"
        assert metrics.is_file(), f"expected canonical metrics at {metrics}"
        stats = yaml.safe_load(metrics.read_text(encoding="utf-8"))
        assert stats["total_trades"] == 3
        assert stats["win_rate"] == 0.5
        assert not (lake / "stats").exists(), "legacy stats/ layout must not be written"

    @pytest.mark.asyncio
    async def test_conformance_checked_before_each_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Every write must go through assert_conformance with the right writer."""
        ctx, _, _ = _make_context(tmp_path)
        calls: list[tuple[str, str]] = []

        def _spy(writer: str, relative_path: str) -> None:
            calls.append((writer, relative_path))

        monkeypatch.setattr("quantlab.phase4.stages.assert_conformance", _spy)
        await SQXKnowledgeStoreStage().execute(ctx)

        assert ("config_writer", "structured/MyCampaign/MyCampaign.cfx") in calls
        assert ("config_writer", "structured/MyCampaign/results/backtest.csv") in calls
        assert ("metrics_writer", "structured/MyCampaign/metrics.yaml") in calls
        assert all(Path(call[1]).parts[0] == "structured" for call in calls)

    @pytest.mark.asyncio
    async def test_conformance_error_propagates_fail_closed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A rejected write MUST fail the stage, never be swallowed."""
        ctx, _, _ = _make_context(tmp_path)

        def _reject(writer: str, relative_path: str) -> None:
            raise ConformanceError(
                f"Off-layout write for writer {writer!r}: {relative_path!r}"
            )

        monkeypatch.setattr("quantlab.phase4.stages.assert_conformance", _reject)
        with pytest.raises(ConformanceError):
            await SQXKnowledgeStoreStage().execute(ctx)

    @pytest.mark.asyncio
    async def test_artifact_paths_shape(self, tmp_path: Path) -> None:
        ctx, _, _ = _make_context(tmp_path)
        result = await SQXKnowledgeStoreStage().execute(ctx)

        artifacts = result["artifact_paths"]
        assert set(artifacts) == {"cfx", "backtest", "statistics"}
        for key, value in artifacts.items():
            assert isinstance(value, Path), f"{key} artifact must be a Path"

    @pytest.mark.asyncio
    async def test_empty_knowledge_root_short_circuits(self, tmp_path: Path) -> None:
        ctx, _, _ = _make_context(tmp_path, with_knowledge_root=False)
        result = await SQXKnowledgeStoreStage().execute(ctx)
        assert result == {"artifact_paths": {}}

    @pytest.mark.asyncio
    async def test_campaign_name_with_special_chars_is_sanitized(self, tmp_path: Path) -> None:
        ctx, lake, _ = _make_context(tmp_path, campaign_name="My Campaign/Test: 2024!")
        await SQXKnowledgeStoreStage().execute(ctx)

        segment = "My_Campaign_Test__2024_"
        cfx = lake / "structured" / segment / f"{segment}.cfx"
        assert cfx.is_file(), f"expected sanitized CFX at {cfx}"
        assert (lake / "structured" / segment / "metrics.yaml").is_file()
        assert (lake / "structured" / segment / "results" / "backtest.csv").is_file()
