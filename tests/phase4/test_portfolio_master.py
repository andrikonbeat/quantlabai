"""Tests for PortfolioMaster — CSV/XML result parsing and build flow."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from quantlab.phase4.portfolio_master import (
    PortfolioMaster,
    PortfolioMasterResult,
    SelectedStrategy,
)
from quantlab.phase4.errors import PortfolioMasterError


# ── XML samples ────────────────────────────────────────────────────────────

SIMPLE_XML = """<?xml version="1.0"?>
<PortfolioMasterResults>
  <SelectedStrategy id="strat_123" weight="0.3" rank="1" fitness="1.5"/>
  <SelectedStrategy id="strat_456" weight="0.7" rank="2" fitness="1.2"/>
</PortfolioMasterResults>"""

XML_NO_FITNESS = """<?xml version="1.0"?>
<PortfolioMasterResults>
  <SelectedStrategy id="strat_abc" weight="1.0" rank="1"/>
</PortfolioMasterResults>"""

XML_NO_WEIGHT = """<?xml version="1.0"?>
<PortfolioMasterResults>
  <SelectedStrategy id="strat_xyz" rank="1"/>
</PortfolioMasterResults>"""

XML_NAMESPACED = """<?xml version="1.0"?>
<ns:PortfolioMasterResults xmlns:ns="http://sqx.com/portfolio">
  <ns:SelectedStrategy ns:id="strat_ns_1" ns:weight="0.4" ns:rank="1" ns:fitness="2.0"/>
  <ns:SelectedStrategy ns:id="strat_ns_2" ns:weight="0.6" ns:rank="2" ns:fitness="1.8"/>
</ns:PortfolioMasterResults>"""

XML_SINGLE = """<?xml version="1.0"?>
<PortfolioMasterResults>
  <SelectedStrategy id="strat_only" weight="1.0" rank="1" fitness="3.0"/>
</PortfolioMasterResults>"""

XML_EMPTY = """<?xml version="1.0"?>
<PortfolioMasterResults/>"""

XML_NO_STRATEGIES = """<?xml version="1.0"?>
<PortfolioMasterResults>
  <OtherElement id="nope"/>
</PortfolioMasterResults>"""

XML_MALFORMED = """<PortfolioMasterResults><broken>"""

# ── CSV samples ────────────────────────────────────────────────────────────

SIMPLE_CSV = """StrategyId,Weight,Rank,Fitness
strat_123,0.3,1,1.5
strat_456,0.7,2,1.2"""

CSV_UNDERSCORE_HEADERS = """strategy_id,weight,rank,fitness
strat_a,0.25,2,1.1
strat_b,0.75,1,1.9"""

CSV_SPACED_HEADERS = """Strategy Id, Weight , Rank , Fitness
strat_x,0.5,1,2.0
strat_y,0.5,2,1.5"""

CSV_NO_FITNESS = """StrategyId,Weight,Rank
strat_a,1.0,1"""

CSV_MINIMAL = """StrategyId
strat_abc
strat_def"""

CSV_EMPTY = ""
CSV_HEADER_ONLY = "StrategyId,Weight,Rank,Fitness"
CSV_MALFORMED_NUMBERS = """StrategyId,Weight
strat_bad,not_a_number"""

CSV_ORDERED = """Rank,StrategyId,Weight,Fitness
2,strat_z,0.3,1.2
1,strat_top,0.7,1.8"""  # Different column order


# ── Dataclass unit tests ──────────────────────────────────────────────────


class TestSelectedStrategy:
    """Tests for SelectedStrategy dataclass."""

    def test_creation(self):
        ss = SelectedStrategy("strat_1", 0.3, 1, fitness=1.5)
        assert ss.strategy_id == "strat_1"
        assert ss.weight == 0.3
        assert ss.rank == 1
        assert ss.fitness == 1.5

    def test_fitness_optional_defaults_none(self):
        ss = SelectedStrategy("strat_2", 0.5, 2)
        assert ss.fitness is None

    def test_immutable_like_attrs(self):
        ss = SelectedStrategy("abc", 0.1, 3)
        assert ss.strategy_id == "abc"
        assert ss.weight == 0.1
        assert ss.rank == 3


class TestPortfolioMasterResult:
    """Tests for PortfolioMasterResult dataclass."""

    def test_creation(self):
        strategies = [
            SelectedStrategy("a", 0.5, 1),
            SelectedStrategy("b", 0.5, 2),
        ]
        result = PortfolioMasterResult(
            strategies=strategies,
            total_count=2,
            source_format="csv",
        )
        assert len(result.strategies) == 2
        assert result.total_count == 2
        assert result.source_format == "csv"

    def test_defaults(self):
        result = PortfolioMasterResult()
        assert result.strategies == []
        assert result.total_count == 0
        assert result.source_format == ""


# ── parse_csv_results ─────────────────────────────────────────────────────


class TestParseCsvResults:
    """Tests for parse_csv_results method."""

    def test_simple_csv(self):
        result = PortfolioMaster.parse_csv_results( SIMPLE_CSV)
        assert isinstance(result, PortfolioMasterResult)
        assert result.source_format == "csv"
        assert result.total_count == 2

        # strat_456 weight=0.7 rank=2, strat_123 weight=0.3 rank=1
        # Sorted by rank asc: strat_123 (1), strat_456 (2)
        assert result.strategies[0].strategy_id == "strat_123"
        assert result.strategies[0].weight == 0.3
        assert result.strategies[0].rank == 1
        assert result.strategies[0].fitness == 1.5

        assert result.strategies[1].strategy_id == "strat_456"
        assert result.strategies[1].weight == 0.7
        assert result.strategies[1].rank == 2
        assert result.strategies[1].fitness == 1.2

    def test_underscore_headers(self):
        result = PortfolioMaster.parse_csv_results( CSV_UNDERSCORE_HEADERS)
        assert result.total_count == 2
        assert result.source_format == "csv"
        # Sorted: strat_b rank=1 then strat_a rank=2
        assert result.strategies[0].strategy_id == "strat_b"
        assert result.strategies[0].weight == 0.75
        assert result.strategies[1].strategy_id == "strat_a"
        assert result.strategies[1].weight == 0.25

    def test_spaced_headers(self):
        result = PortfolioMaster.parse_csv_results( CSV_SPACED_HEADERS)
        assert result.total_count == 2
        assert result.strategies[0].strategy_id == "strat_x"
        assert result.strategies[0].weight == 0.5
        assert result.strategies[1].strategy_id == "strat_y"
        assert result.strategies[1].weight == 0.5

    def test_no_fitness_column(self):
        """When no fitness column exists, fitness should default to None."""
        result = PortfolioMaster.parse_csv_results( CSV_NO_FITNESS)
        assert result.total_count == 1
        assert result.strategies[0].strategy_id == "strat_a"
        assert result.strategies[0].weight == 1.0
        assert result.strategies[0].rank == 1
        assert result.strategies[0].fitness is None

    def test_minimal_csv_id_only(self):
        """Only strategy ID column — weight/rank/fitness default."""
        result = PortfolioMaster.parse_csv_results( CSV_MINIMAL)
        assert result.total_count == 2
        ids = [s.strategy_id for s in result.strategies]
        assert ids == ["strat_abc", "strat_def"]
        for s in result.strategies:
            assert s.weight == 0.0
            assert s.rank == 0
            assert s.fitness is None

    def test_different_column_order(self):
        """Columns in different order should still match."""
        result = PortfolioMaster.parse_csv_results( CSV_ORDERED)
        assert result.total_count == 2
        # Sorted by rank: strat_top (1), strat_z (2)
        assert result.strategies[0].strategy_id == "strat_top"
        assert result.strategies[0].rank == 1
        assert result.strategies[0].weight == 0.7
        assert result.strategies[1].strategy_id == "strat_z"
        assert result.strategies[1].rank == 2

    def test_empty_csv_raises(self):
        with pytest.raises(PortfolioMasterError, match="empty"):
            PortfolioMaster.parse_csv_results( CSV_EMPTY)

    def test_header_only_raises(self):
        with pytest.raises(PortfolioMasterError, match="no strategy rows"):
            PortfolioMaster.parse_csv_results( CSV_HEADER_ONLY)

    def test_non_numeric_weight_raises(self):
        with pytest.raises(PortfolioMasterError, match="Non-numeric weight"):
            PortfolioMaster.parse_csv_results( CSV_MALFORMED_NUMBERS)

    def test_no_strategy_column_raises(self):
        csv = """Foo,Bar
1,2"""
        with pytest.raises(PortfolioMasterError, match="No strategy ID column"):
            PortfolioMaster.parse_csv_results( csv)

    def test_empty_lines_skipped(self):
        csv = """StrategyId,Weight
strat_ok,0.5

"""
        result = PortfolioMaster.parse_csv_results( csv)
        assert result.total_count == 1
        assert result.strategies[0].strategy_id == "strat_ok"

    def test_extra_whitespace_in_values(self):
        csv = """StrategyId,Weight,Rank
  strat_a , 0.5 , 1
  strat_b , 0.5 , 2"""
        result = PortfolioMaster.parse_csv_results( csv)
        assert result.total_count == 2
        assert result.strategies[0].strategy_id == "strat_a"

    def test_float_rank_accepted(self):
        csv = """StrategyId,Weight,Rank,Fitness
s1,0.5,1.0,1.2
s2,0.5,2.0,1.1"""
        result = PortfolioMaster.parse_csv_results( csv)
        assert result.total_count == 2
        assert result.strategies[0].rank == 1
        assert result.strategies[1].rank == 2


# ── parse_xml_results ─────────────────────────────────────────────────────


class TestParseXmlResults:
    """Tests for parse_xml_results method."""

    def test_simple_xml(self):
        result = PortfolioMaster.parse_xml_results( SIMPLE_XML)
        assert isinstance(result, PortfolioMasterResult)
        assert result.source_format == "xml"
        assert result.total_count == 2

        # Sorted by rank asc: strat_123 (1), strat_456 (2)
        assert result.strategies[0].strategy_id == "strat_123"
        assert result.strategies[0].weight == 0.3
        assert result.strategies[0].rank == 1
        assert result.strategies[0].fitness == 1.5

        assert result.strategies[1].strategy_id == "strat_456"
        assert result.strategies[1].weight == 0.7
        assert result.strategies[1].rank == 2
        assert result.strategies[1].fitness == 1.2

    def test_no_fitness_attr(self):
        result = PortfolioMaster.parse_xml_results( XML_NO_FITNESS)
        assert result.total_count == 1
        assert result.strategies[0].fitness is None

    def test_no_weight_attr_defaults_zero(self):
        result = PortfolioMaster.parse_xml_results( XML_NO_WEIGHT)
        assert result.total_count == 1
        assert result.strategies[0].weight == 0.0

    def test_single_strategy(self):
        result = PortfolioMaster.parse_xml_results( XML_SINGLE)
        assert result.total_count == 1
        assert result.strategies[0].strategy_id == "strat_only"
        assert result.strategies[0].fitness == 3.0

    def test_recognizes_standard_xml(self):
        """Standard XML without namespace should parse normally."""
        result = PortfolioMaster.parse_xml_results( SIMPLE_XML)
        assert result.total_count == 2

    def test_empty_xml_raises(self):
        with pytest.raises(PortfolioMasterError, match="Cannot parse empty"):
            PortfolioMaster.parse_xml_results( "")

    def test_empty_result_element_raises(self):
        with pytest.raises(
            PortfolioMasterError, match="No <SelectedStrategy>"
        ):
            PortfolioMaster.parse_xml_results( XML_EMPTY)

    def test_no_selected_strategies_raises(self):
        with pytest.raises(
            PortfolioMasterError, match="No <SelectedStrategy>"
        ):
            PortfolioMaster.parse_xml_results( XML_NO_STRATEGIES)

    def test_malformed_xml_raises(self):
        with pytest.raises(PortfolioMasterError, match="Malformed XML"):
            PortfolioMaster.parse_xml_results( XML_MALFORMED)

    def test_whitespace_only_xml_raises(self):
        with pytest.raises(PortfolioMasterError, match="Cannot parse empty"):
            PortfolioMaster.parse_xml_results( "   \n\n   ")

    def test_non_numeric_weight_raises(self):
        xml = """<Root><SelectedStrategy id="s1" weight="abc" rank="1"/></Root>"""
        with pytest.raises(PortfolioMasterError, match="Non-numeric weight"):
            PortfolioMaster.parse_xml_results( xml)

    def test_non_numeric_rank_raises(self):
        xml = """<Root><SelectedStrategy id="s1" weight="1.0" rank="bad"/></Root>"""
        with pytest.raises(PortfolioMasterError, match="Non-numeric rank"):
            PortfolioMaster.parse_xml_results( xml)

    def test_non_numeric_fitness_raises(self):
        xml = """<Root><SelectedStrategy id="s1" weight="1.0" rank="1" fitness="nope"/></Root>"""
        with pytest.raises(PortfolioMasterError, match="Non-numeric fitness"):
            PortfolioMaster.parse_xml_results( xml)

    def test_extra_whitespace_in_attrs(self):
        xml = """<Root><SelectedStrategy id="  strat_abc  " weight="  1.0  " rank="  1  "/></Root>"""
        result = PortfolioMaster.parse_xml_results( xml)
        assert result.total_count == 1
        # ElementTree strips leading/trailing whitespace from attribute values
        assert result.strategies[0].strategy_id == "strat_abc"


# ── _extract_selected_strategies ──────────────────────────────────────────


class TestExtractSelectedStrategies:
    """Tests for _extract_selected_strategies — auto-detect CSV vs XML."""

    def test_xml_detection(self):
        """Content starting with '<' should be parsed as XML."""
        result = PortfolioMaster._extract_selected_strategies( SIMPLE_XML)
        assert result.source_format == "xml"
        assert result.total_count == 2

    def test_csv_detection(self):
        """Content not starting with '<' should be parsed as CSV."""
        result = PortfolioMaster._extract_selected_strategies( SIMPLE_CSV)
        assert result.source_format == "csv"
        assert result.total_count == 2

    def test_empty_raises(self):
        with pytest.raises(PortfolioMasterError, match="Empty results"):
            PortfolioMaster._extract_selected_strategies( "")

    def test_whitespace_only_raises(self):
        with pytest.raises(PortfolioMasterError, match="Empty results"):
            PortfolioMaster._extract_selected_strategies( "   \n  ")

    def test_garbage_raises(self):
        """Content that is neither CSV nor XML should raise."""
        with pytest.raises(
            PortfolioMasterError, match="Could not parse results"
        ):
            PortfolioMaster._extract_selected_strategies( "not csv not xml")

    def test_csv_looking_like_xml_uses_xml_first(self):
        """Content starting with '<' should try XML first (and fail gracefully)."""
        # Starts with '<' but isn't valid XML or CSV — should fail
        with pytest.raises(
            PortfolioMasterError, match="Could not parse results"
        ):
            PortfolioMaster._extract_selected_strategies(
                "<<<<garbage>>>>"
            )


# ── Integration: build_portfolio (async, with mocking) ────────────────────


class TestBuildPortfolio:
    """Tests for build_portfolio async method with mocked dispatcher."""

    @pytest.mark.asyncio
    async def test_returns_portfolio_master_result(self):
        """build_portfolio should return a PortfolioMasterResult."""
        dispatcher = AsyncMock()
        dispatcher.load_config = AsyncMock()
        dispatcher.start_project = AsyncMock()
        dispatcher.get_status = AsyncMock(
            return_value=AsyncMock(is_complete=True, is_failed=False)
        )
        dispatcher.export_results = AsyncMock(return_value=SIMPLE_CSV)

        master = PortfolioMaster(
            sqx_install_path="/fake/path",
            dispatcher=dispatcher,
        )

        result = await master.build_portfolio(
            strategies=["strat_123", "strat_456"],
            campaign_name="test_campaign",
        )

        assert isinstance(result, PortfolioMasterResult)
        assert result.source_format == "csv"
        assert result.total_count == 2
        assert result.strategies[0].strategy_id == "strat_123"

    @pytest.mark.asyncio
    async def test_xml_results_from_dispatcher(self):
        """build_portfolio should parse XML results correctly."""
        dispatcher = AsyncMock()
        dispatcher.load_config = AsyncMock()
        dispatcher.start_project = AsyncMock()
        dispatcher.get_status = AsyncMock(
            return_value=AsyncMock(is_complete=True, is_failed=False)
        )
        dispatcher.export_results = AsyncMock(return_value=SIMPLE_XML)

        master = PortfolioMaster(
            sqx_install_path="/fake/path",
            dispatcher=dispatcher,
        )

        result = await master.build_portfolio(
            strategies=["strat_123", "strat_456"],
            campaign_name="test_campaign",
        )

        assert isinstance(result, PortfolioMasterResult)
        assert result.source_format == "xml"
        assert result.total_count == 2

    @pytest.mark.asyncio
    async def test_no_strategies_raises(self):
        dispatcher = AsyncMock()
        master = PortfolioMaster(
            sqx_install_path="/fake/path",
            dispatcher=dispatcher,
        )
        with pytest.raises(PortfolioMasterError, match="At least one strategy"):
            await master.build_portfolio(strategies=[])

    @pytest.mark.asyncio
    async def test_campaign_failed_raises(self):
        dispatcher = AsyncMock()
        dispatcher.load_config = AsyncMock()
        dispatcher.start_project = AsyncMock()
        dispatcher.get_status = AsyncMock(
            return_value=AsyncMock(
                is_complete=False,
                is_failed=True,
                error_message="Something broke",
            )
        )

        master = PortfolioMaster(
            sqx_install_path="/fake/path",
            dispatcher=dispatcher,
        )

        with pytest.raises(PortfolioMasterError, match="Campaign failed"):
            await master.build_portfolio(
                strategies=["s1"],
                campaign_name="fail_campaign",
            )

    @pytest.mark.asyncio
    async def test_export_failure_raises(self):
        """Export results returning unparseable content should raise."""
        dispatcher = AsyncMock()
        dispatcher.load_config = AsyncMock()
        dispatcher.start_project = AsyncMock()
        dispatcher.get_status = AsyncMock(
            return_value=AsyncMock(is_complete=True, is_failed=False)
        )
        dispatcher.export_results = AsyncMock(
            return_value="garbage not csv or xml"
        )

        master = PortfolioMaster(
            sqx_install_path="/fake/path",
            dispatcher=dispatcher,
        )

        with pytest.raises(PortfolioMasterError, match="Could not parse"):
            await master.build_portfolio(
                strategies=["s1"],
                campaign_name="garbage_campaign",
            )

    @pytest.mark.asyncio
    async def test_mixed_strategies_in_result(self):
        """Test with strategies having varying attributes."""
        dispatcher = AsyncMock()
        dispatcher.load_config = AsyncMock()
        dispatcher.start_project = AsyncMock()
        dispatcher.get_status = AsyncMock(
            return_value=AsyncMock(is_complete=True, is_failed=False)
        )

        csv_data = """StrategyId,Weight,Rank,Fitness
alpha,0.5,1,2.0
beta,0.3,2,1.5
gamma,0.2,3,1.0"""
        dispatcher.export_results = AsyncMock(return_value=csv_data)

        master = PortfolioMaster(
            sqx_install_path="/fake/path",
            dispatcher=dispatcher,
        )

        result = await master.build_portfolio(
            strategies=["alpha", "beta", "gamma"],
            campaign_name="multi_test",
        )

        assert result.total_count == 3
        assert [s.strategy_id for s in result.strategies] == [
            "alpha",
            "beta",
            "gamma",
        ]
        assert [s.rank for s in result.strategies] == [1, 2, 3]
