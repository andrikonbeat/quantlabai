"""Integration tests — SQXHttpClient against a live SQX daemon.

These tests use the SQXProcessManager fixtures to manage the daemon lifecycle.

Run with::

    SQX_INTEGRATION=1 pytest -q -m integration

The fixtures automatically start/stop the SQX daemon.
"""

from __future__ import annotations

import pytest

from quantlab.sqx.http_client import (
    SQXHttpClient,
    SQXCommandError,
    ProjectList,
    SessionList,
    SessionEntry,
    DatabankList,
    DatabankInfo,
    AICatalog,
    SymbolList,
    TimezoneList,
    ProjectStatus,
)


# Use the process manager fixtures to manage SQX lifecycle
pytestmark = pytest.mark.usefixtures("sqx_session")


class TestSQXIntegration:
    """Integration tests using the session-scoped SQX fixture."""

    @pytest.mark.asyncio
    async def test_live_sqx_ready(self, sqx_session):
        """GIVEN session fixture WHEN daemon probed THEN -h returns help."""
        from quantlab.sqx.http_client import SQXHttpClient

        async with SQXHttpClient(base_url=sqx_session.base_url) as client:
            resp = await client.run("-h")
            assert "Usage" in resp.raw
            assert "not ready" not in resp.raw.lower()

    @pytest.mark.asyncio
    async def test_live_project_list(self, sqx_session):
        """GIVEN ready daemon WHEN project.list() THEN returns ProjectList."""
        async with SQXHttpClient(base_url=sqx_session.base_url) as client:
            result = await client.project.list()

        assert isinstance(result, ProjectList)
        assert isinstance(result.projects, list)
        assert isinstance(result.raw, str)
        assert len(result.raw) > 0

    @pytest.mark.asyncio
    async def test_live_session_list_parses_csv(self, sqx_session):
        """GIVEN ready daemon WHEN session.list() THEN parses CSV table."""
        async with SQXHttpClient(base_url=sqx_session.base_url) as client:
            result = await client.session.list()

        assert isinstance(result, SessionList)
        assert isinstance(result.sessions, list)
        # At least the "No Session" row should exist
        assert len(result.sessions) >= 1
        first = result.sessions[0]
        assert isinstance(first, SessionEntry)
        assert first.name in ("No Session", "") or "No Session" in first.name

    @pytest.mark.asyncio
    async def test_live_databank_list(self, sqx_session):
        """GIVEN ready daemon WHEN databank.list(project=Builder) THEN parses counts."""
        async with SQXHttpClient(base_url=sqx_session.base_url) as client:
            result = await client.databank.list("Builder")

        assert isinstance(result, DatabankList)
        assert result.project == "Builder"
        assert isinstance(result.databanks, list)
        for d in result.databanks:
            assert isinstance(d.name, str)
            assert isinstance(d.strategy_count, int)

    @pytest.mark.asyncio
    async def test_live_ai_catalog(self, sqx_session):
        """GIVEN ready daemon WHEN ai.list() THEN returns AICatalog with sections."""
        from quantlab.sqx.http_client import AICatalog

        async with SQXHttpClient(base_url=sqx_session.base_url) as client:
            result = await client.ai.list("all")

        assert isinstance(result, AICatalog)
        assert isinstance(result.skills, list)
        assert isinstance(result.commands, list)
        assert isinstance(result.agents, list)
        assert isinstance(result.rules, list)

    @pytest.mark.asyncio
    async def test_live_symbol_list(self, sqx_session):
        """GIVEN ready daemon WHEN symbol.list() THEN returns SymbolList."""
        async with SQXHttpClient(base_url=sqx_session.base_url) as client:
            result = await client.symbol.list()

        assert isinstance(result, SymbolList)
        assert isinstance(result.symbols, list)
        assert len(result.symbols) >= 0

    @pytest.mark.asyncio
    async def test_live_data_timezones(self, sqx_session):
        """GIVEN ready daemon WHEN data.timezones() THEN returns timezone list."""
        async with SQXHttpClient(base_url=sqx_session.base_url) as client:
            result = await client.data.timezones()

        assert isinstance(result, TimezoneList)
        assert isinstance(result.timezones, list)
        assert len(result.timezones) > 5

    @pytest.mark.asyncio
    async def test_live_error_handling(self, sqx_session):
        """GIVEN invalid command WHEN run THEN SQXCommandError raised."""
        from quantlab.sqx.http_client import SQXCommandError

        async with SQXHttpClient(base_url=sqx_session.base_url) as client:
            with pytest.raises(SQXCommandError) as exc_info:
                await client.instrument.list()  # missing required 'type' param

        assert "Parameter 'type' is missing" in exc_info.value.response
        assert exc_info.value.command == "-instrument action=list"

    @pytest.mark.asyncio
    async def test_live_project_status(self, sqx_session):
        """GIVEN a project WHEN status() THEN returns ProjectStatus with running flag."""
        async with SQXHttpClient(base_url=sqx_session.base_url) as client:
            projects = await client.project.list()
            if projects.projects:
                status = await client.project.status(projects.projects[0])
                assert isinstance(status, ProjectStatus)
                assert isinstance(status.running, bool)
                assert isinstance(status.completed, bool)
            else:
                pytest.skip("No projects to check")