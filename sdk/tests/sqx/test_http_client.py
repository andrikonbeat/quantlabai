"""Strict TDD — RED phase: SQXHttpClient tests.

Covers spec from:
- odd/tasks/sqx-mcp-poc.md (HTTP API verified: /call?cmd=<command>)
- odd/tasks/sqx-http-wrapper.md (Phase 1: wrapper, models, errors, retry)
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.asyncio


def _make_client(handler, **kwargs):
    """Build an SQXHttpClient backed by an httpx MockTransport."""
    from quantlab.sqx.http_client import SQXHttpClient

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="http://test")
    return SQXHttpClient(base_url="http://127.0.0.1:5050", client=http, **kwargs)


def _ok(text: str) -> httpx.Response:
    return httpx.Response(200, text=text)


class TestErrorHierarchy:
    """Error types — structured exceptions with context."""

    def test_base_error_exists(self):
        """GIVEN the http_client module WHEN imported THEN SQXError is an Exception."""
        from quantlab.sqx.http_client import SQXError

        assert issubclass(SQXError, Exception)

    def test_command_error_carries_context(self):
        """GIVEN a failed command WHEN SQXCommandError raised THEN command+response stored."""
        from quantlab.sqx.http_client import SQXCommandError, SQXError

        err = SQXCommandError("-project action=start", "Error: no such project")
        assert isinstance(err, SQXError)
        assert err.command == "-project action=start"
        assert err.response == "Error: no such project"
        assert "-project action=start" in str(err)

    def test_timeout_not_ready_parse_errors(self):
        """GIVEN subclasses WHEN raised THEN all inherit SQXError."""
        from quantlab.sqx.http_client import (
            SQXError,
            SQXNotReady,
            SQXParseError,
            SQXTimeout,
        )

        assert issubclass(SQXTimeout, SQXError)
        assert issubclass(SQXNotReady, SQXError)
        assert issubclass(SQXParseError, SQXError)


class TestClientInit:
    """Client construction — defaults, normalization, injection."""

    def test_default_base_url(self):
        """GIVEN no args WHEN instantiated THEN points at the SQX daemon port."""
        from quantlab.sqx.http_client import SQXHttpClient

        client = SQXHttpClient()
        assert client.base_url == "http://127.0.0.1:5050"

    def test_trailing_slash_stripped(self):
        """GIVEN base_url with trailing slash WHEN instantiated THEN normalized."""
        from quantlab.sqx.http_client import SQXHttpClient

        assert SQXHttpClient(base_url="http://x:5050/").base_url == "http://x:5050"

    def test_default_timeout_and_retries(self):
        """GIVEN no tuning args WHEN instantiated THEN sane defaults."""
        from quantlab.sqx.http_client import SQXHttpClient

        client = SQXHttpClient()
        assert client.timeout == 30.0
        assert client.max_retries == 3

    async def test_context_manager_closes_owned_client(self):
        """GIVEN async-with WHEN block exits THEN owned httpx client closed."""
        from quantlab.sqx.http_client import SQXHttpClient

        async with SQXHttpClient() as client:
            assert client.base_url == "http://127.0.0.1:5050"


class TestCommandEncoding:
    """Wire format — must match the daemon: /call?cmd=<quoted, safe='='>."""

    async def test_project_list_url_encoding(self):
        """GIVEN project.list WHEN sent THEN URL keeps '=' raw, spaces encoded."""
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return _ok("Projects listed.")

        client = _make_client(handler)
        await client.project.list()
        await client.aclose()
        assert len(seen) == 1
        assert seen[0].startswith("http://127.0.0.1:5050/call?cmd=")
        assert "cmd=-project%20action=list" in seen[0]

    async def test_run_raw_command_passthrough(self):
        """GIVEN a raw command WHEN run THEN sent verbatim (encoded)."""
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return _ok("ok")

        client = _make_client(handler)
        result = await client.run("-databank action=count project=Builder name=Results")
        await client.aclose()
        assert result.ok is True
        assert "cmd=-databank%20action=count%20project=Builder%20name=Results" in seen[0]


class TestProjectNamespace:
    """-project commands — lifecycle used by dispatch."""

    async def test_project_list_returns_names(self):
        """GIVEN list output WHEN parsed THEN project names extracted."""
        from quantlab.sqx.http_client import ProjectList

        def handler(request: httpx.Request) -> httpx.Response:
            return _ok("Available projects:\nBuilder\nRetester\nProjects listed.")

        client = _make_client(handler)
        result = await client.project.list()
        await client.aclose()
        assert isinstance(result, ProjectList)
        assert "Builder" in result.projects
        assert "Retester" in result.projects

    async def test_project_start_stop_status(self):
        """GIVEN lifecycle commands WHEN called THEN correct cmd strings sent."""
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return _ok("ok")

        client = _make_client(handler)
        await client.project.start("Builder")
        await client.project.stop("Builder")
        status = await client.project.status("Builder")
        await client.aclose()
        assert "name=Builder" in seen[0]
        assert "action=start" in seen[0]
        assert "action=stop" in seen[1]
        assert "action=status" in seen[2]
        assert status.name == "Builder"

    async def test_project_status_running_flag(self):
        """GIVEN status text WHEN 'Project execution stopped' present THEN not running."""

        def handler(request: httpx.Request) -> httpx.Response:
            return _ok("Project Builder: Project execution stopped.")

        client = _make_client(handler)
        status = await client.project.status("Builder")
        await client.aclose()
        assert status.running is False
        assert status.completed is True


class TestDatabankNamespace:
    """-databank commands — results management."""

    async def test_databank_list_counts(self):
        """GIVEN list output WHEN parsed THEN databank names + counts extracted."""

        def handler(request: httpx.Request) -> httpx.Response:
            return _ok(
                "Loaded 3 strategies to databank Results\n"
                "Loaded 0 strategies to databank Initial population\n"
                "Databanks listed."
            )

        client = _make_client(handler)
        result = await client.databank.list("Builder")
        await client.aclose()
        by_name = {d.name: d.strategy_count for d in result.databanks}
        assert by_name["Results"] == 3
        assert by_name["Initial population"] == 0

    async def test_databank_export_sends_file(self):
        """GIVEN export args WHEN called THEN file param encoded in cmd."""
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return _ok("Exported.")

        client = _make_client(handler)
        await client.databank.export("Builder", "Results", "/tmp/out.csv")
        await client.aclose()
        assert "action=export" in seen[0]
        assert "file=" in seen[0]


class TestSessionParsing:
    """-session action=list — CSV table parsing."""

    async def test_session_list_csv(self):
        """GIVEN CSV session table WHEN parsed THEN entries typed."""
        from quantlab.sqx.http_client import SessionList

        def handler(request: httpx.Request) -> httpx.Response:
            return _ok(
                "List of sessions\n"
                "--------------------------------------------------\n"
                "Name,Broker,TimeZone,Elements\n"
                "No Session,-1,,0\n"
                "AUDCAD_dukascopy,3,,6\n"
            )

        client = _make_client(handler)
        result = await client.session.list()
        await client.aclose()
        assert isinstance(result, SessionList)
        assert len(result.sessions) == 2
        assert result.sessions[1].name == "AUDCAD_dukascopy"
        assert result.sessions[1].broker == "3"
        assert result.sessions[1].elements == 6


class TestErrorPaths:
    """Server errors, not-ready, transport failures."""

    async def test_error_prefix_raises_command_error(self):
        """GIVEN 'Error:' response WHEN command run THEN SQXCommandError."""
        from quantlab.sqx.http_client import SQXCommandError

        def handler(request: httpx.Request) -> httpx.Response:
            return _ok("Error: Parameter 'type' is missing.")

        client = _make_client(handler)
        with pytest.raises(SQXCommandError) as exc_info:
            await client.instrument.list()
        await client.aclose()
        assert "type" in exc_info.value.response

    async def test_not_ready_raises_then_recovers(self):
        """GIVEN 'CLI not ready' then ok WHEN retried THEN second attempt wins."""
        from quantlab.sqx.http_client import SQXNotReady  # noqa: F401

        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return _ok("Error: CLI not ready.")
            return _ok("Projects listed.")

        client = _make_client(handler, backoff_base=0.0)
        result = await client.project.list()
        await client.aclose()
        assert calls["n"] == 2
        assert result.projects == []

    async def test_connect_error_retried(self):
        """GIVEN ConnectError then ok WHEN run THEN retried transparently."""
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.ConnectError("refused", request=request)
            return _ok("Projects listed.")

        client = _make_client(handler, backoff_base=0.0)
        result = await client.project.list()
        await client.aclose()
        assert calls["n"] == 2
        assert result.projects == []

    async def test_persistent_failure_gives_up(self):
        """GIVEN always-refused WHEN run THEN ConnectError propagates after retries."""
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            raise httpx.ConnectError("refused", request=request)

        client = _make_client(handler, max_retries=2, backoff_base=0.0)
        with pytest.raises(httpx.ConnectError):
            await client.project.list()
        await client.aclose()
        assert calls["n"] == 3  # 1 initial + 2 retries

    async def test_timeout_maps_to_sqxtimeout(self):
        """GIVEN httpx timeout WHEN run THEN SQXTimeout raised."""
        from quantlab.sqx.http_client import SQXTimeout

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("slow", request=request)

        client = _make_client(handler, max_retries=0)
        with pytest.raises(SQXTimeout):
            await client.project.list()
        await client.aclose()


class TestRemainingNamespaces:
    """Spot-check remaining 12 categories send the right verbs."""

    async def test_verbs(self):
        """GIVEN one call per namespace WHEN sent THEN cmd contains category+action."""
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return _ok("ok")

        client = _make_client(handler)
        await client.symbol.list()
        await client.data.update()
        await client.portfolio.merge("Builder", "Results")
        await client.ai.plugins()
        await client.stockgroup.list()
        await client.brokerprofile.list()
        await client.tools.orders_to_csv("Strategy 0.1487.sqx")
        await client.license_info()
        await client.data.timezones()
        await client.run_file("/tmp/cmds.txt")
        await client.delete_file("/tmp/x.log")
        await client.execute("/tmp/eval.sh")
        await client.exit()
        await client.aclose()

        joined = "\n".join(seen)
        for needle in (
            "-symbol%20action=list",
            "-data%20action=update",
            "-portfolio%20action=merge",
            "-ai%20action=plugins",
            "-stockgroup%20action=list",
            "-brokerprofile%20action=list",
            "-tools%20action=orderstocsv",
            "-license%20action=info",
            "-data%20action=timezones",
            "-run%20file=",
            "-deletefile%20file=",
            "-execute%20file=",
            "-exit",
        ):
            assert needle in joined, f"missing {needle}"
