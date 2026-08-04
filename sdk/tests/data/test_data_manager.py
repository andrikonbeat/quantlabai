"""WU-7 RED tests: DataManager rebuild — Dukascopy-only (REQ-12, REQ-13).

Covers the recovered ``.pyc`` contract (``ensure_symbol``, ``update_data``,
``import_csv``, ``list_symbols``, ``get_symbol_info``), SQX naming
``EURUSD_M1_dukas``, the deterministic SQLite registry cache (cache hits
avoid re-download), D5 deferred-datasource rejection (crypto/CSV/yahoo →
``NotSupportedError``), threat-matrix boundary 1 (symbol regex +
metacharacter rejection), and the orchestrated ``_ensure_data`` path
consuming the manager instead of hard-raising.

Strict TDD: written first — FAIL (RED) until data_manager.py exists.
"""

from __future__ import annotations

import pytest

from quantlab.agents.builder_agent import BuilderAgent
from quantlab.dsl.models import ResearchConfig


class FakeSqcli:
    """SQX_FORCE_MOCK-style sqcli subprocess stub.

    Records every invocation (so tests can assert the exact command line)
    and returns canned success output. Patched in as
    ``data_manager._run_sqcli_command``.
    """

    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    async def __call__(self, sqcli_path: str, args: list[str], timeout: float = 60.0) -> str:
        self.commands.append([sqcli_path, *args])
        return "ok\n"


@pytest.fixture
def fake_sqcli(monkeypatch) -> FakeSqcli:
    """Patch the sqcli runner with a recording stub and return it."""
    fake = FakeSqcli()
    monkeypatch.setattr(
        "quantlab.data.data_manager._run_sqcli_command", fake
    )
    return fake


@pytest.fixture
def dm(monkeypatch) -> object:
    """A DataManager pointed at an explicit sqcli binary path.

    The explicit path avoids any env-var discovery; the runner itself is
    stubbed by ``fake_sqcli`` so no real subprocess ever spawns.
    """
    monkeypatch.delenv("SQCLI_PATH", raising=False)
    monkeypatch.delenv("SQX_INSTALL_PATH", raising=False)
    from quantlab.data import DataManager

    return DataManager(sqcli_path="/opt/sqx/sqcli")


# ── ensure_symbol / -symbol action=add (REQ-12 scenario) ────────────────────


class TestEnsureSymbol:
    @pytest.mark.asyncio
    async def test_ensure_symbol_runs_symbol_add_with_sqx_naming(
        self, fake_sqcli, dm
    ) -> None:
        """GIVEN a Dukascopy FX symbol on M1
        WHEN ensure_symbol is called
        THEN `-symbol action=add` runs with SQX naming EURUSD_M1_dukas
        AND the result carries status ok.
        """
        result = await dm.ensure_symbol("EURUSD", datatype="M1")

        assert result["status"] == "ok"
        assert result["sqx_name"] == "EURUSD_M1_dukas"
        assert result["cached"] is False
        assert fake_sqcli.commands == [[
            "/opt/sqx/sqcli",
            "-symbol",
            "action=add",
            "name=EURUSD_M1_dukas",
            "datasource=dukascopy",
            "datatype=M1",
        ]]

    @pytest.mark.asyncio
    async def test_ensure_symbol_updates_registry(self, fake_sqcli, dm) -> None:
        """GIVEN an ensured symbol
        WHEN list_symbols is called
        THEN the symbol registry contains the row (REQ-12 registry update).
        """
        await dm.ensure_symbol("GBPJPY", datatype="H1")

        rows = await dm.list_symbols()
        assert len(rows) == 1
        assert rows[0]["sqx_name"] == "GBPJPY_H1_dukas"
        assert rows[0]["symbol"] == "GBPJPY"
        assert rows[0]["datasource"] == "dukascopy"
        assert rows[0]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_cache_hit_avoids_redownload(self, fake_sqcli, dm) -> None:
        """GIVEN a symbol already ensured
        WHEN ensure_symbol is called again
        THEN no sqcli command runs again (cache hit, cached=True).
        """
        first = await dm.ensure_symbol("EURUSD", datatype="M1")
        second = await dm.ensure_symbol("EURUSD", datatype="M1")

        assert first["cached"] is False
        assert second["cached"] is True
        # Exactly one sqcli invocation across both calls — no re-download.
        assert len(fake_sqcli.commands) == 1

    @pytest.mark.asyncio
    async def test_cache_miss_for_new_timeframe(self, fake_sqcli, dm) -> None:
        """GIVEN M1 cached
        WHEN ensure_symbol runs for the same symbol on H1
        THEN it is a cache miss and a new sqcli command runs (M1/M5/H1).
        """
        await dm.ensure_symbol("EURUSD", datatype="M1")
        await dm.ensure_symbol("EURUSD", datatype="H1")

        assert len(fake_sqcli.commands) == 2
        assert fake_sqcli.commands[0][2:] == [
            "action=add", "name=EURUSD_M1_dukas",
            "datasource=dukascopy", "datatype=M1",
        ]
        assert fake_sqcli.commands[1][2:] == [
            "action=add", "name=EURUSD_H1_dukas",
            "datasource=dukascopy", "datatype=H1",
        ]


# ── update_data / -data action=update ───────────────────────────────────────


class TestUpdateData:
    @pytest.mark.asyncio
    async def test_update_data_runs_data_update(self, fake_sqcli, dm) -> None:
        """GIVEN a Dukascopy symbol
        WHEN update_data is called
        THEN `-data action=update` runs with SQX naming.
        """
        result = await dm.update_data("EURUSD", datatype="M1")

        assert result["status"] == "ok"
        assert result["sqx_name"] == "EURUSD_M1_dukas"
        assert fake_sqcli.commands == [[
            "/opt/sqx/sqcli",
            "-data",
            "action=update",
            "name=EURUSD_M1_dukas",
        ]]


# ── import_csv (D5: CSV deferred) ───────────────────────────────────────────


class TestImportCsv:
    @pytest.mark.asyncio
    async def test_import_csv_csv_datasource_deferred_raises(self, fake_sqcli, dm) -> None:
        """GIVEN the CSV datasource (deferred at launch, D5)
        WHEN import_csv is requested
        THEN a clear NotSupported error is raised (REQ-12 scenario).
        """
        from quantlab.data import NotSupportedError

        with pytest.raises(NotSupportedError, match="CSV"):
            await dm.import_csv("EURUSD", csv_path="/tmp/data.csv")


# ── D5: deferred datasources rejected ───────────────────────────────────────


class TestDeferredDatasources:
    @pytest.mark.asyncio
    async def test_crypto_datasource_rejected(self, fake_sqcli, dm) -> None:
        """GIVEN a crypto datasource at launch
        WHEN ensure_symbol is requested
        THEN a clear NotSupported error is raised (REQ-12 scenario, D5).
        """
        from quantlab.data import NotSupportedError

        with pytest.raises(NotSupportedError, match="crypto"):
            await dm.ensure_symbol("BTCUSD", datasource="crypto")

    @pytest.mark.asyncio
    async def test_yahoo_datasource_rejected(self, fake_sqcli, dm) -> None:
        """GIVEN a yahoo datasource at launch
        WHEN update_data is requested
        THEN a clear NotSupported error is raised (D5).
        """
        from quantlab.data import NotSupportedError

        with pytest.raises(NotSupportedError, match="yahoo"):
            await dm.update_data("EURUSD", datasource="yahoo")

    @pytest.mark.asyncio
    async def test_deferred_datasource_never_touches_sqcli(self, fake_sqcli, dm) -> None:
        """GIVEN a rejected datasource
        WHEN the call raises
        THEN sqcli is never invoked (fail before any subprocess).
        """
        from quantlab.data import NotSupportedError

        with pytest.raises(NotSupportedError):
            await dm.ensure_symbol("BTCUSD", datasource="crypto")
        assert fake_sqcli.commands == []


# ── Threat-matrix boundary 1: symbol validation ─────────────────────────────


class TestSymbolValidation:
    @pytest.mark.asyncio
    async def test_metacharacter_symbol_rejected(self, fake_sqcli, dm) -> None:
        """GIVEN a symbol with shell metacharacters
        WHEN ensure_symbol is called
        THEN ValueError is raised (boundary 1 — no injection into sqcli args).
        """
        with pytest.raises(ValueError, match="symbol"):
            await dm.ensure_symbol("EURUSD; rm -rf /")

    @pytest.mark.asyncio
    async def test_lowercase_symbol_rejected(self, fake_sqcli, dm) -> None:
        """GIVEN a lowercase symbol (regex is ^[A-Z]{6}...)
        WHEN ensure_symbol is called
        THEN ValueError is raised.
        """
        with pytest.raises(ValueError, match="symbol"):
            await dm.ensure_symbol("eurusd")

    @pytest.mark.asyncio
    async def test_invalid_length_symbol_rejected(self, fake_sqcli, dm) -> None:
        """GIVEN a symbol that is not 6 uppercase letters
        WHEN ensure_symbol is called
        THEN ValueError is raised.
        """
        with pytest.raises(ValueError):
            await dm.ensure_symbol("US30")

    @pytest.mark.asyncio
    async def test_symbol_with_suffix_accepted(self, fake_sqcli, dm) -> None:
        """GIVEN a valid symbol with a suffix (e.g. EURUSD_CONT)
        WHEN ensure_symbol is called
        THEN the sqx name carries the suffix and the command runs.
        """
        result = await dm.ensure_symbol("EURUSD_CONT", datatype="M1")
        assert result["sqx_name"] == "EURUSD_CONT_M1_dukas"


# ── list_symbols / get_symbol_info ──────────────────────────────────────────


class TestIntrospection:
    @pytest.mark.asyncio
    async def test_list_symbols_returns_registry_rows(self, fake_sqcli, dm) -> None:
        """GIVEN two ensured symbols
        WHEN list_symbols is called
        THEN both registry rows are returned with contract fields.
        """
        await dm.ensure_symbol("EURUSD", datatype="M1")
        await dm.ensure_symbol("GBPJPY", datatype="M5")

        rows = await dm.list_symbols()
        assert len(rows) == 2
        names = {r["sqx_name"] for r in rows}
        assert names == {"EURUSD_M1_dukas", "GBPJPY_M5_dukas"}
        for row in rows:
            assert {"sqx_name", "symbol", "timeframe", "datasource", "status"} <= set(row)

    @pytest.mark.asyncio
    async def test_get_symbol_info_known(self, fake_sqcli, dm) -> None:
        """GIVEN an ensured symbol
        WHEN get_symbol_info is called
        THEN the registry row is returned.
        """
        await dm.ensure_symbol("EURUSD", datatype="M1")
        info = await dm.get_symbol_info("EURUSD")
        assert info["sqx_name"] == "EURUSD_M1_dukas"
        assert info["status"] == "ok"

    @pytest.mark.asyncio
    async def test_get_symbol_info_unknown(self, fake_sqcli, dm) -> None:
        """GIVEN a symbol never ensured
        WHEN get_symbol_info is called
        THEN status 'unknown' is returned (informational, no raise).
        """
        info = await dm.get_symbol_info("ZZZZZZ")
        assert info["status"] == "unknown"


# ── sqcli discovery + orchestrated _ensure_data consumption (REQ-13) ────────


class TestSqcliDiscovery:
    @pytest.mark.asyncio
    async def test_ensure_symbol_without_sqcli_raises(self, monkeypatch) -> None:
        """GIVEN no sqcli configured (no path, no SQCLI_PATH/SQX_INSTALL_PATH)
        WHEN ensure_symbol is called
        THEN a DataManagerError is raised — the orchestrated pre-flight
        must fail closed instead of silently skipping.
        """
        monkeypatch.delenv("SQCLI_PATH", raising=False)
        monkeypatch.delenv("SQX_INSTALL_PATH", raising=False)
        from quantlab.data import DataManager, DataManagerError

        dm = DataManager()
        with pytest.raises(DataManagerError, match="sqcli"):
            await dm.ensure_symbol("EURUSD", datatype="M1")


class TestOrchestratedEnsureData:
    @pytest.mark.asyncio
    async def test_ensure_data_consumes_manager_in_orchestrated_mode(
        self, monkeypatch
    ) -> None:
        """GIVEN orchestrated mode and a WORKING DataManager
        WHEN _ensure_data runs
        THEN the manager is consumed (ensure_symbol called with
        dukascopy) and the pre-flight passes (no raise) — the hard-raise
        is replaced by the real manager (REQ-13).
        """
        calls: list[tuple] = []

        class FakeManager:
            async def ensure_symbol(self, symbol, datasource="dukascopy", datatype="M1"):
                calls.append((symbol, datasource, datatype))
                return {"status": "ok", "sqx_name": f"{symbol}_M1_dukas"}

        monkeypatch.setattr("quantlab.data.DataManager", FakeManager)

        agent = BuilderAgent()
        config = ResearchConfig(campaign="DMTest", market="EURUSD", timeframe="H1")
        result = await agent._ensure_data(config, orchestrated=True)

        assert result is None  # pre-flight passed — no hard-raise
        assert calls == [("EURUSD", "dukascopy", "M1")]

    @pytest.mark.asyncio
    async def test_ensure_data_wraps_manager_failure_in_orchestrated_mode(
        self, monkeypatch
    ) -> None:
        """GIVEN orchestrated mode and a DataManager that raises
        (e.g. NotSupportedError for a deferred datasource)
        WHEN _ensure_data runs
        THEN RuntimeError aborts dispatch with the data error (REQ-13).
        """
        from quantlab.data import NotSupportedError

        class FailingManager:
            async def ensure_symbol(self, symbol, datasource="dukascopy", datatype="M1"):
                raise NotSupportedError(f"datasource '{datasource}' not supported")

        monkeypatch.setattr("quantlab.data.DataManager", FailingManager)

        agent = BuilderAgent()
        config = ResearchConfig(campaign="DMFail", market="EURUSD", timeframe="H1")
        with pytest.raises(RuntimeError, match="Data pre-flight failed"):
            await agent._ensure_data(config, orchestrated=True)

    @pytest.mark.asyncio
    async def test_ensure_data_legacy_still_best_effort(self, monkeypatch) -> None:
        """GIVEN legacy mode and a failing DataManager
        WHEN _ensure_data runs
        THEN it logs and returns None (REQ-11 unchanged — non-blocking).
        """
        from quantlab.data import NotSupportedError

        class FailingManager:
            async def ensure_symbol(self, symbol, datasource="dukascopy", datatype="M1"):
                raise NotSupportedError("nope")

        monkeypatch.setattr("quantlab.data.DataManager", FailingManager)

        agent = BuilderAgent()
        config = ResearchConfig(campaign="DMLegacy", market="EURUSD", timeframe="H1")
        result = await agent._ensure_data(config, orchestrated=False)
        assert result is None
