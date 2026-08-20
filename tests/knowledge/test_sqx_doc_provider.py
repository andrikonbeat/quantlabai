"""Tests for SQXDocProvider — YAML loading, fallback, version isolation."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from quantlab.knowledge.sqX_doc_provider import SQXDocProvider


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def knowledge_root(tmp_path: Path) -> Path:
    return tmp_path / "knowledge"


@pytest.fixture()
def provider(knowledge_root: Path) -> SQXDocProvider:
    return SQXDocProvider(knowledge_root=knowledge_root)


def _write_yaml(root: Path, version: str, tab: str, param: str, data: dict) -> Path:
    path = root / "structured" / "sqx-kb" / version / "parameters" / tab
    path.mkdir(parents=True, exist_ok=True)
    yaml_path = path / f"{param}.yaml"
    import yaml

    yaml_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return yaml_path


# ── Task T-004: YAML loading ──────────────────────────────────────────────────


class TestSQXDocProviderYamlLoading:
    """YAML-backed parameter lookups return documented values."""

    def test_get_valid_range_from_yaml(self, provider: SQXDocProvider, knowledge_root: Path) -> None:
        _write_yaml(
            knowledge_root,
            "144.2953",
            "Indicators",
            "RSI",
            {
                "name": "RSI",
                "type": "int",
                "range": [2, 200],
                "enum_values": None,
                "description": "Relative Strength Index",
                "default": 14,
            },
        )
        result = provider.get_valid_range("Indicators", "RSI", "144.2953")
        assert result == (2, 200)

    def test_get_enum_values_from_yaml(self, provider: SQXDocProvider, knowledge_root: Path) -> None:
        _write_yaml(
            knowledge_root,
            "144.2953",
            "Indicators",
            "MACD",
            {
                "name": "MACD",
                "type": "string",
                "range": None,
                "enum_values": ["fast", "slow", "signal"],
                "description": "MACD indicator",
                "default": "fast",
            },
        )
        result = provider.get_enum_values("Indicators", "MACD", "144.2953")
        assert result == ["fast", "slow", "signal"]

    def test_get_description_from_yaml(self, provider: SQXDocProvider, knowledge_root: Path) -> None:
        _write_yaml(
            knowledge_root,
            "144.2953",
            "Indicators",
            "BB",
            {
                "name": "BB",
                "type": "float",
                "range": [0.1, 5.0],
                "enum_values": None,
                "description": "Bollinger Bands",
                "default": 2.0,
            },
        )
        result = provider.get_description("Indicators", "BB", "144.2953")
        assert result == "Bollinger Bands"

    def test_missing_yaml_returns_none_range(self, provider: SQXDocProvider) -> None:
        result = provider.get_valid_range("Indicators", "UNKNOWN", "144.2953")
        assert result is None

    def test_missing_yaml_returns_none_enums(self, provider: SQXDocProvider) -> None:
        result = provider.get_enum_values("Indicators", "UNKNOWN", "144.2953")
        assert result is None

    def test_missing_yaml_returns_empty_description(self, provider: SQXDocProvider) -> None:
        result = provider.get_description("Indicators", "UNKNOWN", "144.2953")
        assert result == ""


# ── Task T-004: Fallback probing ──────────────────────────────────────────────


class TestSQXDocProviderFallback:
    """Missing YAML falls back to _BUILD_CONFIG_MAP probing."""

    def test_fallback_infers_type_and_range(
        self, provider: SQXDocProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import quantlab.sqx.project_builder as pb

        monkeypatch.setattr(
            pb,
            "_BUILD_CONFIG_MAP",
            {
                "max_trades_per_day": (
                    r"<MaxTradesPerDay>\d+</MaxTradesPerDay>",
                    r"<MaxTradesPerDay>{value}</MaxTradesPerDay>",
                    "int",
                ),
            },
        )
        result = provider.get_valid_range("Trading options", "max_trades_per_day", "144.2953")
        assert result == (0, 1000)

    def test_fallback_returns_empty_description(
        self, provider: SQXDocProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import quantlab.sqx.project_builder as pb

        monkeypatch.setattr(pb, "_BUILD_CONFIG_MAP", {})
        result = provider.get_description("Trading options", "unknown", "144.2953")
        assert result == ""

    def test_fallback_warns_on_missing_yaml(
        self, provider: SQXDocProvider, knowledge_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import quantlab.sqx.project_builder as pb

        monkeypatch.setattr(pb, "_BUILD_CONFIG_MAP", {})
        with pytest.warns(UserWarning, match="YAML missing"):
            provider.get_valid_range("Trading options", "missing", "144.2953")


# ── Task T-004: Version isolation ─────────────────────────────────────────────


class TestSQXDocProviderVersionIsolation:
    """Lookups are isolated by SQX version."""

    def test_version_isolation(self, provider: SQXDocProvider, knowledge_root: Path) -> None:
        _write_yaml(
            knowledge_root,
            "144.2953",
            "Indicators",
            "RSI",
            {
                "name": "RSI",
                "type": "int",
                "range": [2, 200],
                "enum_values": None,
                "description": "RSI v144",
                "default": 14,
            },
        )
        _write_yaml(
            knowledge_root,
            "145.0",
            "Indicators",
            "RSI",
            {
                "name": "RSI",
                "type": "int",
                "range": [2, 100],
                "enum_values": None,
                "description": "RSI v145",
                "default": 14,
            },
        )
        assert provider.get_description("Indicators", "RSI", "144.2953") == "RSI v144"
        assert provider.get_description("Indicators", "RSI", "145.0") == "RSI v145"
        assert provider.get_valid_range("Indicators", "RSI", "144.2953") == (2, 200)
        assert provider.get_valid_range("Indicators", "RSI", "145.0") == (2, 100)
