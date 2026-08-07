"""Tests for the canonical data symbol written into Build-Task1.xml.

REQ: the chart symbol in the build task MUST reference an existing data
root. The data registry names symbols by their M1 root (``EURUSD_M1_dukas``);
H1/D1 are derived .dat files inside that root, never standalone symbols.
The legacy ``{symbol}_{timeframe}_dukas`` pattern (``EURUSD_H1_dukas``)
produces builds with no data → 0 strategies. These tests lock the chart
symbol to the registry-resolved M1 root.
"""

import re
import zipfile
from pathlib import Path

import pytest

from quantlab.data.symbol_registry import resolve_symbol
from quantlab.sqx.project_builder import create_project

REPO_ROOT = Path(__file__).resolve().parents[3]
HISTORY_DIR = REPO_ROOT / "assets" / "SQX_144_2953_linux_20260601" / "user" / "data" / "History"

CHART_RE = re.compile(r'<Chart symbol="[^"]*" timeframe="[^"]*" spread="\d+"')


def _build_cfx(tmp_path: Path, symbol: str, timeframe: str) -> str:
    """Create a project in tmp_path and return the generated project.cfx path."""
    cfx = create_project(
        sqx_install_path=str(tmp_path),
        campaign_id="symbol-test",
        symbol=symbol,
        timeframe=timeframe,
        walk_forward=False,
        monte_carlo=False,
    )
    return cfx


def _chart_symbols(cfx_path: str) -> list[str]:
    with zipfile.ZipFile(cfx_path) as zf:
        task_xml = zf.read("Build-Task1.xml").decode("utf-8")
    return CHART_RE.findall(task_xml)


class TestCanonicalChartSymbol:
    """GIVEN a market+timeframe WHEN the project is built THEN the chart
    symbol is the canonical M1 root that exists in the data registry."""

    @pytest.mark.parametrize(
        ("symbol", "timeframe"),
        [("EURUSD", "H1"), ("EURUSD", "M1"), ("GBPUSD", "H1"), ("USDJPY", "H1")],
    )
    def test_chart_symbol_is_registry_m1_root(self, tmp_path, symbol, timeframe) -> None:
        cfx = _build_cfx(tmp_path, symbol, timeframe)
        chart_lines = _chart_symbols(cfx)
        assert chart_lines, "no <Chart symbol=...> element found in build task"

        expected = resolve_symbol(symbol, "M1", "dukascopy")
        # The first <Chart> is the main data chart that create_project
        # rewrites; it must carry the canonical root symbol.
        assert f'symbol="{expected}"' in chart_lines[0], (
            f"main chart symbol {chart_lines[0]!r} != canonical root {expected!r}"
        )

    def test_no_derived_timeframe_in_symbol_name(self, tmp_path) -> None:
        """The buggy pattern {symbol}_{timeframe}_dukas must not appear."""
        cfx = _build_cfx(tmp_path, "EURUSD", "H1")
        task_xml = zipfile.ZipFile(cfx).read("Build-Task1.xml").decode("utf-8")
        assert 'symbol="EURUSD_H1_dukas"' not in task_xml
        assert 'symbol="EURUSD_M1_dukas"' in task_xml

    def test_chart_timeframe_attribute_preserved(self, tmp_path) -> None:
        """The timeframe attribute still selects the derived bars (H1)."""
        cfx = _build_cfx(tmp_path, "EURUSD", "H1")
        chart_lines = _chart_symbols(cfx)
        assert any('timeframe="H1"' in line for line in chart_lines)

    def test_built_symbol_matches_real_data_directory(self, tmp_path) -> None:
        """The written symbol must correspond to an existing History/ dir."""
        if not HISTORY_DIR.is_dir():
            pytest.skip(f"real data bundle not present: {HISTORY_DIR}")
        cfx = _build_cfx(tmp_path, "EURUSD", "H1")
        chart_lines = _chart_symbols(cfx)
        data_roots = {d.name for d in HISTORY_DIR.iterdir() if d.is_dir()}
        for line in chart_lines:
            m = re.search(r'symbol="([^"]+)"', line)
            assert m is not None
            assert m.group(1) in data_roots, (
                f"chart symbol {m.group(1)!r} not in data roots: {sorted(data_roots)}"
            )


class TestSymbolFallback:
    """Non-registry symbols fall back to the M1-root convention."""

    def test_lowercase_symbol_uppercased(self, tmp_path) -> None:
        cfx = _build_cfx(tmp_path, "eurusd", "H1")
        task_xml = zipfile.ZipFile(cfx).read("Build-Task1.xml").decode("utf-8")
        assert 'symbol="EURUSD_M1_dukas"' in task_xml
