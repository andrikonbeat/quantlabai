"""WU-7 RED tests: SymbolRegistry + SQX naming helpers (REQ-12).

Covers ``resolve_symbol``/``u_symbol`` naming (``EURUSD_M1_dukas`` style,
dukascopy → ``_dukas`` suffix, round-trip), symbol validation (threat-matrix
boundary 1), and the SQLite registry (record/get/has/list_all, persistence
across instances).

Strict TDD: written first — FAIL (RED) until symbol_registry.py exists.
"""

from __future__ import annotations

import pytest

from quantlab.data import NotSupportedError


# ── resolve_symbol / u_symbol naming ────────────────────────────────────────


class TestNaming:
    def test_resolve_symbol_dukascopy_sqx_name(self) -> None:
        """GIVEN a Dukascopy FX symbol on M1
        WHEN resolve_symbol is called
        THEN the SQX name is EURUSD_M1_dukas (REQ-12).
        """
        from quantlab.data.symbol_registry import resolve_symbol

        assert resolve_symbol("EURUSD", "M1", "dukascopy") == "EURUSD_M1_dukas"

    def test_resolve_symbol_timeframe_variants(self) -> None:
        """GIVEN M5/H1 timeframes (launch scope, D5)
        WHEN resolve_symbol is called
        THEN the SQX name carries the timeframe.
        """
        from quantlab.data.symbol_registry import resolve_symbol

        assert resolve_symbol("GBPJPY", "M5", "dukascopy") == "GBPJPY_M5_dukas"
        assert resolve_symbol("XAUUSD", "H1", "dukascopy") == "XAUUSD_H1_dukas"

    def test_resolve_symbol_with_suffix(self) -> None:
        """GIVEN a symbol with an uppercase suffix (regex allows _[A-Z]+\d*)
        WHEN resolve_symbol is called
        THEN the SQX name preserves the suffix.
        """
        from quantlab.data.symbol_registry import resolve_symbol

        assert resolve_symbol("EURUSD_CONT", "M1", "dukascopy") == "EURUSD_CONT_M1_dukas"

    def test_resolve_symbol_rejects_deferred_datasource(self) -> None:
        """GIVEN a deferred datasource (crypto, D5)
        WHEN resolve_symbol is called
        THEN NotSupportedError is raised.
        """
        from quantlab.data.symbol_registry import resolve_symbol

        with pytest.raises(NotSupportedError, match="crypto"):
            resolve_symbol("BTCUSD", "M1", "crypto")

    def test_resolve_symbol_rejects_metacharacters(self) -> None:
        """GIVEN a symbol with shell metacharacters (boundary 1)
        WHEN resolve_symbol is called
        THEN ValueError is raised.
        """
        from quantlab.data.symbol_registry import resolve_symbol

        with pytest.raises(ValueError, match="symbol"):
            resolve_symbol("EURUSD;ls", "M1", "dukascopy")

    def test_resolve_symbol_rejects_lowercase(self) -> None:
        """GIVEN a lowercase symbol
        WHEN resolve_symbol is called
        THEN ValueError is raised (regex is ^[A-Z]{6}).
        """
        from quantlab.data.symbol_registry import resolve_symbol

        with pytest.raises(ValueError):
            resolve_symbol("eurusd", "M1", "dukascopy")

    def test_u_symbol_round_trip(self) -> None:
        """GIVEN an SQX name produced by resolve_symbol
        WHEN u_symbol is called
        THEN the original symbol/timeframe/datasource are recovered.
        """
        from quantlab.data.symbol_registry import resolve_symbol, u_symbol

        name = resolve_symbol("EURUSD", "M1", "dukascopy")
        assert u_symbol(name) == {
            "symbol": "EURUSD",
            "timeframe": "M1",
            "datasource": "dukascopy",
        }

    def test_u_symbol_with_suffix_round_trip(self) -> None:
        """GIVEN an SQX name with a symbol suffix
        WHEN u_symbol is called
        THEN symbol/timeframe/datasource are recovered (greedy symbol).
        """
        from quantlab.data.symbol_registry import resolve_symbol, u_symbol

        name = resolve_symbol("EURUSD_CONT", "H1", "dukascopy")
        assert u_symbol(name) == {
            "symbol": "EURUSD_CONT",
            "timeframe": "H1",
            "datasource": "dukascopy",
        }

    def test_u_symbol_rejects_invalid_name(self) -> None:
        """GIVEN a name without the datasource suffix
        WHEN u_symbol is called
        THEN ValueError is raised.
        """
        from quantlab.data.symbol_registry import u_symbol

        with pytest.raises(ValueError):
            u_symbol("EURUSD_M1")


# ── SQLite registry persistence ─────────────────────────────────────────────


class TestSymbolRegistry:
    @pytest.mark.asyncio
    async def test_record_then_get(self, tmp_path) -> None:
        """GIVEN a recorded symbol
        WHEN get is called with symbol+timeframe
        THEN the stored row is returned.
        """
        from quantlab.data.symbol_registry import SymbolRegistry

        reg = SymbolRegistry(db_path=str(tmp_path / "symbols.db"))
        await reg.record("EURUSD_M1_dukas", "EURUSD", "M1", "dukascopy", status="ok")

        row = await reg.get("EURUSD", "M1")
        assert row is not None
        assert row["sqx_name"] == "EURUSD_M1_dukas"
        assert row["status"] == "ok"
        assert row["datasource"] == "dukascopy"

    @pytest.mark.asyncio
    async def test_has_true_and_false(self, tmp_path) -> None:
        """GIVEN a recorded symbol and an unrecorded one
        WHEN has is called
        THEN True/False reflect registry membership.
        """
        from quantlab.data.symbol_registry import SymbolRegistry

        reg = SymbolRegistry(db_path=str(tmp_path / "symbols.db"))
        await reg.record("GBPJPY_H1_dukas", "GBPJPY", "H1", "dukascopy", status="ok")

        assert await reg.has("GBPJPY", "H1") is True
        assert await reg.has("GBPJPY", "M1") is False
        assert await reg.has("EURUSD", "H1") is False

    @pytest.mark.asyncio
    async def test_record_updates_existing_entry(self, tmp_path) -> None:
        """GIVEN a symbol re-recorded
        WHEN get is called
        THEN the entry is updated in place (no duplicate rows).
        """
        from quantlab.data.symbol_registry import SymbolRegistry

        reg = SymbolRegistry(db_path=str(tmp_path / "symbols.db"))
        await reg.record("EURUSD_M1_dukas", "EURUSD", "M1", "dukascopy", status="ok")
        await reg.record("EURUSD_M1_dukas", "EURUSD", "M1", "dukascopy", status="ok")

        rows = await reg.list_all()
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_list_all_returns_all_rows(self, tmp_path) -> None:
        """GIVEN two recorded symbols
        WHEN list_all is called
        THEN both rows are returned.
        """
        from quantlab.data.symbol_registry import SymbolRegistry

        reg = SymbolRegistry(db_path=str(tmp_path / "symbols.db"))
        await reg.record("EURUSD_M1_dukas", "EURUSD", "M1", "dukascopy", status="ok")
        await reg.record("GBPJPY_H1_dukas", "GBPJPY", "H1", "dukascopy", status="ok")

        rows = await reg.list_all()
        assert {r["sqx_name"] for r in rows} == {"EURUSD_M1_dukas", "GBPJPY_H1_dukas"}

    @pytest.mark.asyncio
    async def test_persistence_across_instances(self, tmp_path) -> None:
        """GIVEN a registry written to a file
        WHEN a NEW registry instance opens the same file
        THEN the records persist (SQLite registry persistence, REQ-12).
        """
        from quantlab.data.symbol_registry import SymbolRegistry

        db = str(tmp_path / "symbols.db")
        reg1 = SymbolRegistry(db_path=db)
        await reg1.record("EURUSD_M1_dukas", "EURUSD", "M1", "dukascopy", status="ok")

        reg2 = SymbolRegistry(db_path=db)
        assert await reg2.has("EURUSD", "M1") is True
        row = await reg2.get("EURUSD", "M1")
        assert row["sqx_name"] == "EURUSD_M1_dukas"
