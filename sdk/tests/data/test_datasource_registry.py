"""Ciclo 3 RED tests: DataManager registry-based datasource switching (REQ-04).

Covers the datasource registry (register/get/names), DataManager routing
(datasource="jforex" -> JForexProvider, datasource="dukascopy" -> sqcli,
unknown -> NotSupportedError), cache separation across datasources,
fail-closed JForex behavior, and the backward-compatible dukascopy/sqcli
path (REQ-04 scenario 2).

Strict TDD: written first — FAIL (RED) until the datasource registry and
JForexProvider exist.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from quantlab.data.datasource_registry import DatasourceHandler, DatasourceRegistry


# ── Recording handler doubles (no mocks — real registry, real handler) ──────


class FakeHandler(DatasourceHandler):
    """A minimal DatasourceHandler that records every call."""

    def __init__(self, name: str, suffix: str = "X") -> None:
        self.name = name
        self._suffix = suffix
        self.ensures: list[tuple] = []
        self.updates: list[tuple] = []

    def sqx_name(self, symbol: str, datatype: str) -> str:
        return f"{symbol}_{datatype.upper()}_{self._suffix}"

    async def ensure(self, symbol: str, datatype: str, sqx_name: str) -> None:
        self.ensures.append((symbol, datatype, sqx_name))

    async def update(self, symbol: str, datatype: str, sqx_name: str) -> None:
        self.updates.append((symbol, datatype, sqx_name))


@pytest.fixture
def fake_sqcli(monkeypatch):
    """Patch the module-level sqcli runner so no subprocess ever spawns."""

    class Recording:
        def __init__(self) -> None:
            self.commands: list[list[str]] = []

        async def __call__(self, sqcli_path, args, timeout=60.0) -> str:
            self.commands.append([sqcli_path, *args])
            return "ok\n"

    fake = Recording()
    monkeypatch.setattr(
        "quantlab.data.data_manager._run_sqcli_command", fake
    )
    return fake


def write_history(state_dir, sqx_name: str, rows: list[dict]) -> None:
    """Write a JForex history JSON file into the state directory."""
    history = state_dir / "history"
    history.mkdir(parents=True, exist_ok=True)
    (history / f"{sqx_name}.json").write_text(
        json.dumps(rows), encoding="utf-8"
    )


# ── T3.1: DatasourceRegistry + DataManager routing ──────────────────────────


class TestDatasourceRegistry:
    def test_register_get_roundtrip_case_insensitive(self) -> None:
        reg = DatasourceRegistry()
        reg.register(FakeHandler("alpha"))
        assert reg.get("alpha") is not None
        assert reg.get("ALPHA") is not None
        assert reg.get("missing") is None

    def test_names_returns_sorted_registered(self) -> None:
        reg = DatasourceRegistry()
        reg.register(FakeHandler("beta"))
        reg.register(FakeHandler("alpha"))
        assert reg.names() == ["alpha", "beta"]


class TestDataManagerRouting:
    @pytest.fixture
    def dm(self):
        """DataManager wired to an injected registry with two handlers."""
        from quantlab.data import DataManager, SymbolRegistry

        reg = DatasourceRegistry()
        alpha = FakeHandler("alpha", suffix="alf")
        beta = FakeHandler("beta", suffix="bet")
        reg.register(alpha)
        reg.register(beta)
        return DataManager(
            datasources=reg,
            registry=SymbolRegistry(db_path=":memory:"),
        ), alpha, beta

    @pytest.mark.asyncio
    async def test_ensure_symbol_routes_to_registered_handler(self, dm) -> None:
        manager, alpha, beta = dm
        result = await manager.ensure_symbol("EURUSD", datasource="alpha", datatype="M1")

        assert result["status"] == "ok"
        assert result["sqx_name"] == "EURUSD_M1_alf"
        assert result["datasource"] == "alpha"
        assert alpha.ensures == [("EURUSD", "M1", "EURUSD_M1_alf")]
        assert beta.ensures == []

    @pytest.mark.asyncio
    async def test_update_data_routes_to_registered_handler(self, dm) -> None:
        manager, alpha, beta = dm
        result = await manager.update_data("GBPJPY", datasource="beta", datatype="H1")

        assert result["status"] == "ok"
        assert result["sqx_name"] == "GBPJPY_H1_bet"
        assert beta.updates == [("GBPJPY", "H1", "GBPJPY_H1_bet")]
        assert alpha.updates == []

    @pytest.mark.asyncio
    async def test_unknown_datasource_raises_not_supported(self, dm) -> None:
        manager, _, _ = dm
        from quantlab.data import NotSupportedError

        with pytest.raises(NotSupportedError, match="nope"):
            await manager.ensure_symbol("EURUSD", datasource="nope")

    @pytest.mark.asyncio
    async def test_cache_hit_avoids_repeating_handler_call(self, dm) -> None:
        manager, alpha, _ = dm
        await manager.ensure_symbol("EURUSD", datasource="alpha", datatype="M1")
        second = await manager.ensure_symbol("EURUSD", datasource="alpha", datatype="M1")

        assert second["cached"] is True
        assert len(alpha.ensures) == 1

    @pytest.mark.asyncio
    async def test_cache_is_separated_per_datasource(self, dm) -> None:
        manager, alpha, beta = dm
        await manager.ensure_symbol("EURUSD", datasource="alpha", datatype="M1")
        second = await manager.ensure_symbol("EURUSD", datasource="beta", datatype="M1")

        assert second["cached"] is False
        assert second["sqx_name"] == "EURUSD_M1_bet"
        assert len(alpha.ensures) == 1
        assert len(beta.ensures) == 1

    @pytest.mark.asyncio
    async def test_registered_handlers_visible_on_manager(self, dm) -> None:
        manager, _, _ = dm
        assert manager.datasources.names() == ["alpha", "beta"]


# ── T3.2: JForexProvider historical data ────────────────────────────────────


class TestJForexProvider:
    @pytest.fixture
    def provider(self):
        from quantlab.jforex.provider import JForexProvider

        return JForexProvider()

    def test_sqx_name_jforex_naming(self, provider) -> None:
        assert provider.sqx_name("EURUSD", "M1") == "EURUSD_M1_jforex"

    def test_sqx_name_validates_symbol_boundary(self, provider) -> None:
        with pytest.raises(ValueError, match="symbol"):
            provider.sqx_name("EURUSD;rm -rf /", "M1")

    @pytest.mark.asyncio
    async def test_ensure_fail_closed_when_state_unconfigured(self, provider) -> None:
        from quantlab.data import DataManagerError

        with pytest.raises(DataManagerError, match="not configured"):
            await provider.ensure("EURUSD", "M1", "EURUSD_M1_jforex")

    @pytest.mark.asyncio
    async def test_ensure_fail_closed_when_history_missing(self, tmp_path) -> None:
        from quantlab.jforex.provider import JForexProvider
        from quantlab.data import DataManagerError

        provider = JForexProvider(state_dir=tmp_path)
        with pytest.raises(DataManagerError, match="no local history"):
            await provider.ensure("EURUSD", "M1", "EURUSD_M1_jforex")

    def test_fetch_history_parses_valid_rows(self, tmp_path) -> None:
        from quantlab.jforex.provider import JForexProvider

        write_history(tmp_path, "EURUSD_M1_jforex", [
            {
                "timestamp": "2026-01-02T03:04:05Z",
                "open": 1.10, "high": 1.20, "low": 1.00,
                "close": 1.15, "volume": 1000.0,
            },
        ])
        bars = JForexProvider(state_dir=tmp_path).fetch_history("EURUSD", "M1")

        assert len(bars) == 1
        assert bars[0].close == 1.15
        assert bars[0].volume == 1000.0
        assert bars[0].timestamp == datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    def test_fetch_history_skips_malformed_rows(self, tmp_path) -> None:
        from quantlab.jforex.provider import JForexProvider

        write_history(tmp_path, "EURUSD_M1_jforex", [
            {"timestamp": "2026-01-02T03:04:05Z", "open": "bad", "high": 1.2,
             "low": 1.0, "close": 1.15, "volume": 1000.0},
            {"open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15, "volume": 1000.0},
            {"timestamp": "2026-01-02T03:05:00Z", "open": 1.11, "high": 1.21,
             "low": 1.01, "close": 1.16, "volume": 1100.0},
        ])
        bars = JForexProvider(state_dir=tmp_path).fetch_history("EURUSD", "M1")

        assert len(bars) == 1
        assert bars[0].close == 1.16

    def test_fetch_history_missing_file_returns_empty(self, tmp_path) -> None:
        from quantlab.jforex.provider import JForexProvider

        assert JForexProvider(state_dir=tmp_path).fetch_history("GBPJPY", "M1") == []

    def test_fetch_history_unconfigured_returns_empty(self, provider) -> None:
        assert provider.fetch_history("EURUSD", "M1") == []


# ── T3.3/T3.4: switching, fallback, dukascopy backward compatibility ────────


class TestDatasourceSwitching:
    @pytest.fixture
    def dm(self, tmp_path):
        """Default DataManager: dukascopy via sqcli + jforex via local state.

        sqcli_path points at a nonexistent binary — if jforex routing ever
        touched sqcli, the launch failure would surface as an error.
        """
        from quantlab.data import DataManager

        return DataManager(
            sqcli_path="/nonexistent/sqcli",
            jforex_state_dir=str(tmp_path),
        )

    @pytest.mark.asyncio
    async def test_jforex_ensure_routes_to_provider_no_sqcli(
        self, dm, tmp_path
    ) -> None:
        write_history(tmp_path, "EURUSD_M1_jforex", [
            {"timestamp": "2026-01-02T03:04:05Z", "open": 1.1, "high": 1.2,
             "low": 1.0, "close": 1.15, "volume": 1000.0},
        ])
        result = await dm.ensure_symbol("EURUSD", datasource="jforex", datatype="M1")

        assert result["status"] == "ok"
        assert result["sqx_name"] == "EURUSD_M1_jforex"
        assert result["cached"] is False
        assert result["datasource"] == "jforex"

    @pytest.mark.asyncio
    async def test_jforex_update_routes_to_provider(self, dm, tmp_path) -> None:
        write_history(tmp_path, "EURUSD_H1_jforex", [
            {"timestamp": "2026-01-02T03:04:05Z", "open": 1.1, "high": 1.2,
             "low": 1.0, "close": 1.15, "volume": 1000.0},
        ])
        result = await dm.update_data("EURUSD", datasource="jforex", datatype="H1")

        assert result["status"] == "ok"
        assert result["sqx_name"] == "EURUSD_H1_jforex"
        rows = await dm.list_symbols()
        assert rows[0]["datasource"] == "jforex"
        assert rows[0]["sqx_name"] == "EURUSD_H1_jforex"

    @pytest.mark.asyncio
    async def test_jforex_ensure_fail_closed_without_history(self, dm) -> None:
        from quantlab.data import DataManagerError

        with pytest.raises(DataManagerError, match="no local history"):
            await dm.ensure_symbol("EURUSD", datasource="jforex", datatype="M1")

    @pytest.mark.asyncio
    async def test_mixed_usage_jforex_then_dukascopy_fallback(
        self, dm, tmp_path, fake_sqcli
    ) -> None:
        """REQ-04 scenario 2: jforex and dukascopy coexist on one manager."""
        write_history(tmp_path, "EURUSD_M1_jforex", [
            {"timestamp": "2026-01-02T03:04:05Z", "open": 1.1, "high": 1.2,
             "low": 1.0, "close": 1.15, "volume": 1000.0},
        ])
        jf = await dm.ensure_symbol("EURUSD", datasource="jforex", datatype="M1")
        dk = await dm.ensure_symbol("EURUSD", datasource="dukascopy", datatype="M1")

        assert jf["sqx_name"] == "EURUSD_M1_jforex"
        assert dk["sqx_name"] == "EURUSD_M1_dukas"
        assert fake_sqcli.commands == [[
            "/nonexistent/sqcli", "-symbol", "action=add",
            "name=EURUSD_M1_dukas", "datasource=dukascopy", "datatype=M1",
        ]]

        rows = await dm.list_symbols()
        assert {r["sqx_name"] for r in rows} == {"EURUSD_M1_jforex", "EURUSD_M1_dukas"}

        # Second round: both datasources hit their own cache rows.
        jf2 = await dm.ensure_symbol("EURUSD", datasource="jforex", datatype="M1")
        dk2 = await dm.ensure_symbol("EURUSD", datasource="dukascopy", datatype="M1")
        assert jf2["cached"] is True
        assert dk2["cached"] is True
        assert len(fake_sqcli.commands) == 1

    @pytest.mark.asyncio
    async def test_dukascopy_still_rejects_deferred_sources(self, dm, fake_sqcli) -> None:
        from quantlab.data import NotSupportedError

        with pytest.raises(NotSupportedError, match="crypto"):
            await dm.ensure_symbol("BTCUSD", datasource="crypto")
        with pytest.raises(NotSupportedError, match="yahoo"):
            await dm.update_data("EURUSD", datasource="yahoo")
        assert fake_sqcli.commands == []
