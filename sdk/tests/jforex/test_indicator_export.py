"""Tests for Ciclo 4 — LLM Indicator Export (REQ-05).

Covers the export round-trip (Java helper JSON schema <-> Python reader) and
the pipeline step that injects the helper into generated ``.jfx`` archives.
"""

from __future__ import annotations

import asyncio
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from quantlab.jforex.exporter import (
    INDICATOR_EXPORTER_SOURCE,
    IndicatorExport,
    IndicatorSnapshot,
    indicator_export_path,
    inject_indicator_exporter,
    read_indicator_export,
)
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.indicator_export_stage import IndicatorExportStage


def _sample_export() -> IndicatorExport:
    """Build a representative IndicatorExport with two indicators."""
    return IndicatorExport(
        strategy="BullEyes_M15",
        exported_at=datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc),
        indicators=[
            IndicatorSnapshot(
                name="RSI",
                value=41.7,
                timestamp=datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc),
            ),
            IndicatorSnapshot(
                name="EMA20",
                value=1.0802,
                timestamp=datetime(2026, 8, 13, 12, 1, 0, tzinfo=timezone.utc),
            ),
        ],
    )


def _make_jfx(tmp_path: Path, name: str = "BullEyes_M15") -> Path:
    """Create a minimal valid .jfx (ZIP) with one compiled class entry."""
    jfx = tmp_path / f"{name}.jfx"
    with zipfile.ZipFile(jfx, "w") as zf:
        zf.writestr(f"{name}.class", b"\xca\xfe\xba\xbe")
    return jfx


# ── T4.1: export path + Java helper contract ─────────────────────────────────


class TestIndicatorExportPath:
    """REQ-05: exports live under ~/JForex4/exports/quantlab-indicators-<strategy>.json."""

    def test_default_path_follows_req05_pattern(self):
        """Default export path matches ~/JForex4/exports/quantlab-indicators-<s>.json."""
        path = indicator_export_path("BullEyes_M15")
        assert path.parent == Path.home() / "JForex4" / "exports"
        assert path.name == "quantlab-indicators-BullEyes_M15.json"

    def test_explicit_export_dir_is_used(self, tmp_path: Path):
        """An explicit export dir overrides the home-based default."""
        out = tmp_path / "exports"
        path = indicator_export_path("TrendH1", export_dir=out)
        assert path == out / "quantlab-indicators-TrendH1.json"

    def test_java_helper_source_exists_with_class_and_pattern(self):
        """The shipped Java helper declares the class and the REQ-05 filename."""
        source = INDICATOR_EXPORTER_SOURCE.read_text(encoding="utf-8")
        assert "class IndicatorExporter" in source
        assert "quantlab-indicators-" in source
        assert source.count("export") >= 1


# ── T4.4: export round-trip ──────────────────────────────────────────────────


class TestExportRoundTrip:
    """JSON written by the helper must parse back into the same model."""

    def test_serialize_then_read_round_trips(self, tmp_path: Path):
        """write -> read returns the same IndicatorExport values."""
        payload = _sample_export().model_dump_json()
        path = tmp_path / "quantlab-indicators-BullEyes_M15.json"
        path.write_text(payload, encoding="utf-8")

        parsed = read_indicator_export(path)
        assert parsed.strategy == "BullEyes_M15"
        assert parsed.exported_at == _sample_export().exported_at
        assert [(i.name, i.value) for i in parsed.indicators] == [
            ("RSI", 41.7),
            ("EMA20", 1.0802),
        ]

    def test_read_rejects_corrupt_json(self, tmp_path: Path):
        """Corrupt JSON raises ValueError — fail loud at the reader boundary."""
        path = tmp_path / "quantlab-indicators-BullEyes_M15.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(ValueError):
            read_indicator_export(path)

    def test_read_rejects_missing_required_fields(self, tmp_path: Path):
        """A JSON body missing the strategy field is invalid."""
        path = tmp_path / "quantlab-indicators-BullEyes_M15.json"
        path.write_text(json.dumps({"indicators": []}), encoding="utf-8")
        with pytest.raises(ValueError):
            read_indicator_export(path)


# ── T4.3: pipeline injection step ────────────────────────────────────────────


class TestIndicatorExportInjection:
    """The .jfx ZIP gains the helper source + manifest pointing at the export."""

    def test_inject_adds_helper_and_manifest(self, tmp_path: Path):
        """After injection the .jfx contains IndicatorExporter.java and a manifest."""
        jfx = _make_jfx(tmp_path)
        export_dir = tmp_path / "exports"

        result = inject_indicator_exporter(jfx, "BullEyes_M15", export_dir=export_dir)

        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
            assert "IndicatorExporter.java" in names
            manifest = json.loads(zf.read("indicator_export.manifest.json"))
            assert manifest["strategy"] == "BullEyes_M15"
            assert manifest["export_path"] == str(
                export_dir / "quantlab-indicators-BullEyes_M15.json"
            )

    def test_inject_preserves_existing_class_entries(self, tmp_path: Path):
        """The strategy class entry survives injection."""
        jfx = _make_jfx(tmp_path, name="BullEyes_M15")

        inject_indicator_exporter(jfx, "BullEyes_M15")

        with zipfile.ZipFile(jfx) as zf:
            assert "BullEyes_M15.class" in zf.namelist()

    def test_inject_missing_jfx_fails_closed(self, tmp_path: Path):
        """Injecting into a nonexistent .jfx raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            inject_indicator_exporter(
                tmp_path / "missing.jfx", "BullEyes_M15"
            )


class TestIndicatorExportStage:
    """Stage routes every compiled .jfx through injection and provides the exports."""

    def test_stage_injects_every_compiled_strategy(self, tmp_path: Path):
        """Dict input: each strategy .jfx gains the helper; exports provided."""
        jfx_a = _make_jfx(tmp_path, name="AlphaM15")
        jfx_b = _make_jfx(tmp_path, name="BetaH1")
        ctx = PipelineContext(
            config={},
            artifacts={
                "compiled_strategies": {
                    "AlphaM15": jfx_a,
                    "BetaH1": jfx_b,
                }
            },
        )
        stage = IndicatorExportStage(export_dir=tmp_path / "exports")

        result = asyncio.run(stage.execute(ctx))

        for sid in ("AlphaM15", "BetaH1"):
            with zipfile.ZipFile(ctx.artifacts["compiled_strategies"][sid]) as zf:
                assert "IndicatorExporter.java" in zf.namelist()
            assert result["indicator_export_paths"][sid] == (
                tmp_path / "exports" / f"quantlab-indicators-{sid}.json"
            )

    def test_stage_handles_list_input_and_unwraps_artifacts(self, tmp_path: Path):
        """List input with artifact objects: strategy names come from stems."""
        from quantlab.compiler.jfx import JfxArtifact

        jfx = _make_jfx(tmp_path, name="GammaM30")
        ctx = PipelineContext(
            config={},
            artifacts={"compiled_strategies": [JfxArtifact(path=jfx, source=jfx, class_name="GammaM30")]},
        )
        stage = IndicatorExportStage(export_dir=tmp_path / "exports")

        result = asyncio.run(stage.execute(ctx))

        assert list(result["indicator_export_paths"]) == ["GammaM30"]
        with zipfile.ZipFile(jfx) as zf:
            assert "IndicatorExporter.java" in zf.namelist()

    def test_stage_empty_compiled_provides_empty_exports(self):
        """No compiled strategies -> empty exports map, no crash."""
        ctx = PipelineContext(config={}, artifacts={"compiled_strategies": {}})
        stage = IndicatorExportStage()
        result = asyncio.run(stage.execute(ctx))
        assert result["indicator_export_paths"] == {}