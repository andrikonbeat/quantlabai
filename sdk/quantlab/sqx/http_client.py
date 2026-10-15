"""SQX HTTP API client — typed wrapper over the ``sqcli`` HTTP API.

The SQX daemon exposes every ``sqcli`` subcommand over HTTP::

    GET http://127.0.0.1:5050/call?cmd=<url-encoded command>

This module replaces the subprocess shelling in ``cli_wrapper.py`` /
``cli/runner.py`` with a typed async client: one namespace per command
category (``project``, ``databank``, ``symbol``, …), Pydantic response
models, a structured error hierarchy, and retry with exponential backoff.

Wire format mirrors ``cli_wrapper._send_http`` byte-for-byte
(``urllib.parse.quote(command, safe="=")``) so responses are identical
to the CLI path.
"""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from typing import Any

import httpx
from pydantic import BaseModel, Field

from .settings import sqx_base_url, sqx_max_retries, sqx_timeout

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = sqx_base_url()
_COMMAND_ENDPOINT = "/call?cmd="


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class SQXError(Exception):
    """Base error for all SQX HTTP client failures."""


class SQXCommandError(SQXError):
    """The daemon answered, but the command failed (``Error: ...``)."""

    def __init__(self, command: str, response: str) -> None:
        self.command = command
        self.response = response
        super().__init__(f"SQX command failed [{command}]: {response[:200]}")


class SQXTimeout(SQXError):
    """The HTTP request timed out (transient — safe to retry)."""

    def __init__(self, command: str, timeout: float) -> None:
        self.command = command
        self.timeout = timeout
        super().__init__(f"SQX command timed out after {timeout:g}s: {command}")


class SQXNotReady(SQXError):
    """The daemon is still loading (``CLI not ready`` — transient)."""

    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__(f"SQX daemon not ready for: {command}")


class SQXParseError(SQXError):
    """The daemon answered, but the response could not be parsed."""

    def __init__(self, command: str, response: str, detail: str = "") -> None:
        self.command = command
        self.response = response
        suffix = f" ({detail})" if detail else ""
        super().__init__(f"Cannot parse SQX response for [{command}]{suffix}")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class CommandResult(BaseModel):
    """Raw result of any command — ``raw`` is always preserved."""

    raw: str = ""
    ok: bool = True


class ProjectList(BaseModel):
    """``-project action=list``."""

    projects: list[str] = Field(default_factory=list)
    raw: str = ""


class ProjectStatus(BaseModel):
    """``-project action=status``."""

    name: str = ""
    running: bool = False
    completed: bool = False
    raw: str = ""


class DatabankInfo(BaseModel):
    """One databank with its loaded strategy count."""

    name: str = ""
    strategy_count: int = 0


class DatabankList(BaseModel):
    """``-databank action=list``."""

    project: str = ""
    databanks: list[DatabankInfo] = Field(default_factory=list)
    raw: str = ""


class DatabankCount(BaseModel):
    """``-databank action=count``."""

    project: str = ""
    name: str = ""
    count: int = 0
    raw: str = ""


class SymbolInfo(BaseModel):
    """One symbol entry."""

    name: str = ""
    raw: str = ""


class SymbolList(BaseModel):
    """``-symbol action=list``."""

    symbols: list[SymbolInfo] = Field(default_factory=list)
    raw: str = ""


class InstrumentInfo(BaseModel):
    """One instrument entry."""

    name: str = ""
    raw: str = ""


class InstrumentList(BaseModel):
    """``-instrument action=list``."""

    instruments: list[InstrumentInfo] = Field(default_factory=list)
    raw: str = ""


class SessionEntry(BaseModel):
    """One trading session (``-session action=list`` CSV row)."""

    name: str = ""
    broker: str = ""
    timezone: str = ""
    elements: int = 0


class SessionList(BaseModel):
    """``-session action=list``."""

    sessions: list[SessionEntry] = Field(default_factory=list)
    raw: str = ""


class TimezoneList(BaseModel):
    """``-data action=timezones``."""

    timezones: list[str] = Field(default_factory=list)
    raw: str = ""


class AIPluginList(BaseModel):
    """``-ai action=plugins``."""

    plugins: list[str] = Field(default_factory=list)
    raw: str = ""


class AICatalog(BaseModel):
    """``-ai action=list`` — skills/commands/agents/rules."""

    skills: list[str] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)
    agents: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    raw: str = ""


class StockGroupList(BaseModel):
    """``-stockgroup action=list``."""

    groups: list[str] = Field(default_factory=list)
    raw: str = ""


class BrokerProfileList(BaseModel):
    """``-brokerprofile action=list``."""

    profiles: list[str] = Field(default_factory=list)
    raw: str = ""


class LicenseInfo(BaseModel):
    """``-license action=info``."""

    raw: str = ""
    ok: bool = True


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_SEPARATOR_CHARS = frozenset("-=~*#_")

_FOOTER_PHRASES = (
    "listed.",
    "saved.",
    "loaded.",
    "exported.",
    "synchronization finished.",
    "projects listed.",
    "databanks listed.",
    "data listed.",
    "strategies listed.",
)

_COMPLETION_TERMS = ("completed", "finished", "done", "success")


def _is_separator(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and all(ch in _SEPARATOR_CHARS for ch in stripped)


def _is_footer(line: str) -> bool:
    lowered = line.strip().lower()
    return any(phrase in lowered for phrase in _FOOTER_PHRASES)


def _clean_lines(raw: str) -> list[str]:
    """Drop separators, headers, footers and blanks — keep content lines."""
    out: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or _is_separator(stripped) or _is_footer(stripped):
            continue
        out.append(stripped)
    return out


def _parse_csv_table(raw: str) -> list[dict[str, str]]:
    """Parse the ``Header1,Header2`` + rows blocks SQX emits.

    Raises SQXParseError when no header row is found.
    """
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or _is_separator(stripped) or _is_footer(stripped):
            continue
        if "," not in stripped:
            continue
        cells = [c.strip() for c in stripped.split(",")]
        if header is None:
            header = cells
            continue
        rows.append({h: (cells[i] if i < len(cells) else "") for i, h in enumerate(header)})
    if header is None:
        raise SQXParseError("", raw, "no CSV header row found")
    return rows


def _is_completed_text(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in _COMPLETION_TERMS)


def _is_not_ready(text: str) -> bool:
    return "not ready" in text.lower()


def _is_error(text: str) -> bool:
    return text.lstrip().startswith("Error:")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class SQXHttpClient:
    """Typed async client for the SQX daemon HTTP API.

    Args:
        base_url: Daemon base URL (default ``http://127.0.0.1:5050``).
        timeout: Per-request timeout in seconds.
        max_retries: Retries for transient failures (transport errors and
            ``CLI not ready``). Server ``Error:`` answers are NOT retried.
        backoff_base: Base seconds for exponential backoff between retries.
        client: Optional injected ``httpx.AsyncClient`` (tests). When given,
            the client is NOT closed by :meth:`aclose`.
    """

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._client = client
        self._owns_client = client is None

        # Namespaces — one per sqcli command category.
        self.project = _ProjectNamespace(self)
        self.databank = _DatabankNamespace(self)
        self.portfolio = _PortfolioNamespace(self)
        self.symbol = _SymbolNamespace(self)
        self.instrument = _InstrumentNamespace(self)
        self.data = _DataNamespace(self)
        self.tools = _ToolsNamespace(self)
        self.ai = _AINamespace(self)
        self.stockgroup = _StockGroupNamespace(self)
        self.session = _SessionNamespace(self)
        self.brokerprofile = _BrokerProfileNamespace(self)

    # -- lifecycle ------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def aclose(self) -> None:
        """Close the owned httpx client (no-op for injected clients)."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> SQXHttpClient:
        await self._get_client()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    # -- core send ------------------------------------------------------

    async def run(self, command: str) -> CommandResult:
        """Send a raw sqcli command string; return the raw result."""
        raw = await self._send(command)
        return CommandResult(raw=raw, ok=True)

    async def _send(self, command: str) -> str:
        """Send one command with retry; raise on daemon errors."""
        encoded = urllib.parse.quote(command, safe="=")
        url = f"{self.base_url}{_COMMAND_ENDPOINT}{encoded}"
        logger.debug("SQX -> %s", command[:120])

        attempts = 1 + max(0, self.max_retries)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                client = await self._get_client()
                resp = await client.get(url)
                resp.raise_for_status()
                text = resp.text
                logger.debug("SQX <- %.200s", text.replace("\n", " | "))
                if _is_not_ready(text):
                    raise SQXNotReady(command)
                if _is_error(text):
                    raise SQXCommandError(command, text.strip())
                return text
            except SQXCommandError:
                raise
            except SQXNotReady as exc:
                last_error = exc
            except httpx.TimeoutException as exc:
                last_error = SQXTimeout(command, self.timeout)
                if self.max_retries == 0:
                    raise last_error from exc
            except (httpx.ConnectError, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                last_error = exc
            if attempt < attempts:
                delay = self.backoff_base * (2 ** (attempt - 1))
                logger.info(
                    "SQX retry %d/%d for [%s] after %s (backoff %.2fs)",
                    attempt,
                    attempts - 1,
                    command[:80],
                    type(last_error).__name__,
                    delay,
                )
                if delay > 0:
                    await asyncio.sleep(delay)
        assert last_error is not None
        if isinstance(last_error, SQXError):
            raise last_error
        raise last_error

    # -- utility commands (no namespace) --------------------------------

    async def run_file(self, file: str) -> CommandResult:
        """``-run file=...`` — run commands from a file."""
        return CommandResult(raw=await self._send(f"-run file={file}"))

    async def delete_file(self, file: str) -> CommandResult:
        """``-deletefile file=...``."""
        return CommandResult(raw=await self._send(f"-deletefile file={file}"))

    async def wait_for_user(self) -> CommandResult:
        """``-waitfor action=user``."""
        return CommandResult(raw=await self._send("-waitfor action=user"))

    async def wait_for_file(self, file: str) -> CommandResult:
        """``-waitfor action=file file=...``."""
        return CommandResult(raw=await self._send(f"-waitfor action=file file={file}"))

    async def execute(self, file: str) -> CommandResult:
        """``-execute file=...`` — call an external script."""
        return CommandResult(raw=await self._send(f"-execute file={file}"))

    async def license_info(self) -> LicenseInfo:
        """``-license action=info``."""
        return LicenseInfo(raw=await self._send("-license action=info"))

    async def license_update(self, code: str) -> CommandResult:
        """``-license action=update code=...``."""
        return CommandResult(raw=await self._send(f"-license action=update code={code}"))

    async def exit(self) -> CommandResult:
        """``-exit`` — stop the daemon."""
        return CommandResult(raw=await self._send("-exit"))


# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------


class _ProjectNamespace:
    """``-project`` — project lifecycle."""

    def __init__(self, client: SQXHttpClient) -> None:
        self._c = client

    async def list(self) -> ProjectList:
        raw = await self._c._send("-project action=list")
        return ProjectList(projects=_clean_lines(raw), raw=raw)

    async def start(self, name: str) -> CommandResult:
        return CommandResult(raw=await self._c._send(f"-project action=start name={name}"))

    async def start_only_task(self, name: str, task: int) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(f"-project action=startOnlyTask name={name} task={task}")
        )

    async def start_from_task(self, name: str, task: int) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(
                f"-project action=startFromTask name={name} task={task}"
            )
        )

    async def stop(self, name: str) -> CommandResult:
        return CommandResult(raw=await self._c._send(f"-project action=stop name={name}"))

    async def pause(self, name: str) -> CommandResult:
        return CommandResult(raw=await self._c._send(f"-project action=pause name={name}"))

    async def resume(self, name: str) -> CommandResult:
        return CommandResult(raw=await self._c._send(f"-project action=resume name={name}"))

    async def remove(self, name: str) -> CommandResult:
        return CommandResult(raw=await self._c._send(f"-project action=remove name={name}"))

    async def status(self, name: str) -> ProjectStatus:
        raw = await self._c._send(f"-project action=status name={name}")
        stopped = "Project execution stopped" in raw
        return ProjectStatus(
            name=name,
            running=not stopped,
            completed=stopped or _is_completed_text(raw),
            raw=raw,
        )

    async def loadconfig(self, name: str, file: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(f"-project action=loadconfig name={name} file={file}")
        )

    async def saveconfig(self, name: str, file: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(f"-project action=saveconfig name={name} file={file}")
        )


class _DatabankNamespace:
    """``-databank`` — results management."""

    def __init__(self, client: SQXHttpClient) -> None:
        self._c = client

    async def list(self, project: str) -> DatabankList:
        raw = await self._c._send(f"-databank action=list project={project}")
        databanks: list[DatabankInfo] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped.startswith("Loaded "):
                continue
            # "Loaded 3 strategies to databank Results"
            parts = stripped.split(" to databank ", 1)
            if len(parts) != 2:
                continue
            try:
                count = int(parts[0].split()[1])
            except (IndexError, ValueError):
                continue
            databanks.append(DatabankInfo(name=parts[1], strategy_count=count))
        return DatabankList(project=project, databanks=databanks, raw=raw)

    async def count(self, project: str, name: str) -> DatabankCount:
        raw = await self._c._send(f"-databank action=count project={project} name={name}")
        count = 0
        for token in raw.replace(",", " ").split():
            if token.isdigit():
                count = int(token)
                break
        return DatabankCount(project=project, name=name, count=count, raw=raw)

    async def save(
        self, project: str, name: str, folder: str, strategies: str | None = None
    ) -> CommandResult:
        cmd = f"-databank action=save project={project} name={name} folder={folder}"
        if strategies:
            cmd += f' strategies="{strategies}"'
        return CommandResult(raw=await self._c._send(cmd))

    async def load(
        self, project: str, name: str, folder: str, strategies: str | None = None
    ) -> CommandResult:
        cmd = f"-databank action=load project={project} name={name} folder={folder}"
        if strategies:
            cmd += f' strategies="{strategies}"'
        return CommandResult(raw=await self._c._send(cmd))

    async def delete(self, project: str, name: str, strategies: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(
                f'-databank action=delete project={project} name={name} strategies="{strategies}"'
            )
        )

    async def clear(self, project: str, name: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(f"-databank action=clear project={project} name={name}")
        )

    async def create(self, project: str, name: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(f"-databank action=create project={project} name={name}")
        )

    async def remove(self, project: str, name: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(f"-databank action=remove project={project} name={name}")
        )

    async def sync_to_files(self, project: str, name: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(
                f"-databank action=synctofiles project={project} name={name}"
            )
        )

    async def sync_from_files(self, project: str, name: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(
                f"-databank action=syncfromfiles project={project} name={name}"
            )
        )

    async def copy(
        self, project: str, name: str, destproject: str, destdatabank: str
    ) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(
                f"-databank action=copy project={project} name={name} "
                f"destproject={destproject} destdatabank={destdatabank}"
            )
        )

    async def move(
        self, project: str, name: str, destproject: str, destdatabank: str
    ) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(
                f"-databank action=move project={project} name={name} "
                f"destproject={destproject} destdatabank={destdatabank}"
            )
        )

    async def export(
        self, project: str, name: str, file: str, view: str | None = None
    ) -> CommandResult:
        cmd = f"-databank action=export project={project} name={name} file={file}"
        if view:
            cmd += f" view={view}"
        return CommandResult(raw=await self._c._send(cmd))


class _PortfolioNamespace:
    """``-portfolio`` — merge/split portfolio strategies."""

    def __init__(self, client: SQXHttpClient) -> None:
        self._c = client

    async def merge(
        self,
        project: str,
        databank: str,
        strategies: str = "all",
        name: str = "Portfolio",
        target: str | None = None,
        type: str = "simulated",
        capital: str = "first",
        signalspct: int = 70,
        signalsstrategy: str | None = None,
    ) -> CommandResult:
        cmd = (
            f"-portfolio action=merge project={project} databank={databank} "
            f'strategies="{strategies}" name={name} type={type} capital={capital}'
        )
        if target:
            cmd += f" target={target}"
        if type == "signals":
            cmd += f" signalspct={signalspct}"
            if signalsstrategy:
                cmd += f' signalsstrategy="{signalsstrategy}"'
        return CommandResult(raw=await self._c._send(cmd))

    async def split(self, project: str, databank: str, strategies: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(
                f"-portfolio action=split project={project} databank={databank} "
                f"strategies={strategies}"
            )
        )


class _SymbolNamespace:
    """``-symbol`` — symbol universe."""

    def __init__(self, client: SQXHttpClient) -> None:
        self._c = client

    async def list(self) -> SymbolList:
        raw = await self._c._send("-symbol action=list")
        return SymbolList(
            symbols=[SymbolInfo(name=n) for n in _clean_lines(raw)], raw=raw
        )

    async def add(
        self,
        symbols: str,
        datasource: str = "dukascopy",
        datatype: str = "M1",
        **kwargs: str,
    ) -> CommandResult:
        cmd = f"-symbol action=add symbols={symbols} datasource={datasource} datatype={datatype}"
        for key, value in kwargs.items():
            cmd += f" {key}={value}"
        return CommandResult(raw=await self._c._send(cmd))

    async def edit(self, symbol: str, name: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(f"-symbol action=edit symbol={symbol} name={name}")
        )

    async def delete(self, symbols: str) -> CommandResult:
        return CommandResult(raw=await self._c._send(f"-symbol action=delete symbols={symbols}"))

    async def clear(self, symbols: str) -> CommandResult:
        return CommandResult(raw=await self._c._send(f"-symbol action=clear symbols={symbols}"))

    async def mt5symbols(self, path: str) -> CommandResult:
        return CommandResult(raw=await self._c._send(f"-symbol action=mt5symbols path={path}"))


class _InstrumentNamespace:
    """``-instrument`` — instrument specs."""

    def __init__(self, client: SQXHttpClient) -> None:
        self._c = client

    async def list(self, datatype: str = "forex") -> InstrumentList:
        raw = await self._c._send(f"-instrument action=list datatype={datatype}")
        return InstrumentList(
            instruments=[InstrumentInfo(name=n) for n in _clean_lines(raw)], raw=raw
        )

    async def add(self, instrument: str, **kwargs: str) -> CommandResult:
        cmd = f"-instrument action=add instrument={instrument}"
        for key, value in kwargs.items():
            cmd += f" {key}={value}"
        return CommandResult(raw=await self._c._send(cmd))

    async def edit(self, instrument: str, **kwargs: str) -> CommandResult:
        cmd = f"-instrument action=edit instrument={instrument}"
        for key, value in kwargs.items():
            cmd += f" {key}={value}"
        return CommandResult(raw=await self._c._send(cmd))

    async def delete(self, instruments: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(f"-instrument action=delete instruments={instruments}")
        )


class _DataNamespace:
    """``-data`` — data pipeline."""

    def __init__(self, client: SQXHttpClient) -> None:
        self._c = client

    async def update(self, symbols: str | None = None) -> CommandResult:
        cmd = "-data action=update"
        if symbols:
            cmd += f" symbols={symbols}"
        return CommandResult(raw=await self._c._send(cmd))

    async def import_data(self, symbol: str, filepath: str, **kwargs: str) -> CommandResult:
        cmd = f"-data action=import symbol={symbol} filepath={filepath}"
        for key, value in kwargs.items():
            cmd += f" {key}={value}"
        return CommandResult(raw=await self._c._send(cmd))

    async def export(
        self,
        symbols: str,
        timeframe: str,
        datefrom: str,
        dateto: str,
        outputdir: str,
        **kwargs: str,
    ) -> CommandResult:
        cmd = (
            f"-data action=export symbols={symbols} timeframe={timeframe} "
            f"datefrom={datefrom} dateto={dateto} outputdir={outputdir}"
        )
        for key, value in kwargs.items():
            cmd += f" {key}={value}"
        return CommandResult(raw=await self._c._send(cmd))

    async def export_to_mt4(self, symbol: str, timeframe: str, **kwargs: str) -> CommandResult:
        cmd = f"-data action=exportToMT4 symbol={symbol} timeframe={timeframe}"
        for key, value in kwargs.items():
            cmd += f" {key}={value}"
        return CommandResult(raw=await self._c._send(cmd))

    async def export_to_mt5(self, symbol: str, timeframe: str, **kwargs: str) -> CommandResult:
        cmd = f"-data action=exportToMT5 symbol={symbol} timeframe={timeframe}"
        for key, value in kwargs.items():
            cmd += f" {key}={value}"
        return CommandResult(raw=await self._c._send(cmd))

    async def clone(self, symbols: str, hours: int) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(f"-data action=clone symbols={symbols} hours={hours}")
        )

    async def timezones(self) -> TimezoneList:
        raw = await self._c._send("-data action=timezones")
        return TimezoneList(timezones=_clean_lines(raw), raw=raw)


class _ToolsNamespace:
    """``-tools`` — trade export utilities."""

    def __init__(self, client: SQXHttpClient) -> None:
        self._c = client

    async def orders_to_csv(
        self,
        file: str,
        output: str | None = None,
        usecomma: bool = False,
        data: str = "main",
    ) -> CommandResult:
        cmd = f'-tools action=orderstocsv file="{file}"'
        if output:
            cmd += f" output={output}"
        if usecomma:
            cmd += " usecomma=true"
        cmd += f" data={data}"
        return CommandResult(raw=await self._c._send(cmd))

    async def orders_to_xlsx(
        self,
        file: str,
        output: str | None = None,
        usecomma: bool = False,
        data: str = "main",
    ) -> CommandResult:
        cmd = f'-tools action=orderstoxlsx file="{file}"'
        if output:
            cmd += f" output={output}"
        if usecomma:
            cmd += " usecomma=true"
        cmd += f" data={data}"
        return CommandResult(raw=await self._c._send(cmd))


class _AINamespace:
    """``-ai`` — AI plugin wiring."""

    def __init__(self, client: SQXHttpClient) -> None:
        self._c = client

    async def sync(self) -> CommandResult:
        return CommandResult(raw=await self._c._send("-ai action=sync"))

    async def plugins(self) -> AIPluginList:
        raw = await self._c._send("-ai action=plugins")
        return AIPluginList(plugins=_clean_lines(raw), raw=raw)

    async def list(self, type: str = "all") -> AICatalog:
        raw = await self._c._send(f"-ai action=list type={type}")
        catalog = AICatalog(raw=raw)
        section: str | None = None
        for line in _clean_lines(raw):
            lowered = line.lower()
            if "skill" in lowered and ":" not in line:
                section = "skills"
                continue
            if "command" in lowered and ":" not in line:
                section = "commands"
                continue
            if "agent" in lowered and ":" not in line:
                section = "agents"
                continue
            if "rule" in lowered and ":" not in line:
                section = "rules"
                continue
            if section == "skills":
                catalog.skills.append(line)
            elif section == "commands":
                catalog.commands.append(line)
            elif section == "agents":
                catalog.agents.append(line)
            elif section == "rules":
                catalog.rules.append(line)
        return catalog


class _StockGroupNamespace:
    """``-stockgroup`` — stock group management."""

    def __init__(self, client: SQXHttpClient) -> None:
        self._c = client

    async def list(self) -> StockGroupList:
        raw = await self._c._send("-stockgroup action=list")
        return StockGroupList(groups=_clean_lines(raw), raw=raw)

    async def update_all(self) -> CommandResult:
        return CommandResult(raw=await self._c._send("-stockgroup action=updateAll"))

    async def update(self, id: str) -> CommandResult:
        return CommandResult(raw=await self._c._send(f"-stockgroup action=update id={id}"))

    async def import_stocks(self, id: str, filepath: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(f"-stockgroup action=importstocks id={id} filepath={filepath}")
        )

    async def export_stocks(self, id: str, filepath: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(f"-stockgroup action=exportstocks id={id} filepath={filepath}")
        )

    async def import_group(self, filepath: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(f"-stockgroup action=import filepath={filepath}")
        )

    async def export_group(self, id: str, filepath: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(f"-stockgroup action=export id={id} filepath={filepath}")
        )


class _SessionNamespace:
    """``-session`` — trading sessions."""

    def __init__(self, client: SQXHttpClient) -> None:
        self._c = client

    async def list(self) -> SessionList:
        raw = await self._c._send("-session action=list")
        rows = _parse_csv_table(raw)
        sessions = [
            SessionEntry(
                name=r.get("Name", ""),
                broker=r.get("Broker", ""),
                timezone=r.get("TimeZone", ""),
                elements=int(r.get("Elements", "0") or 0),
            )
            for r in rows
        ]
        return SessionList(sessions=sessions, raw=raw)

    async def list_templates(self) -> CommandResult:
        return CommandResult(raw=await self._c._send("-session action=listtemplates"))

    async def import_templates(
        self, path: str | None = None, overwrite: bool = False
    ) -> CommandResult:
        cmd = "-session action=import"
        if path:
            cmd += f" path={path}"
        if overwrite:
            cmd += " overwrite=true"
        return CommandResult(raw=await self._c._send(cmd))


class _BrokerProfileNamespace:
    """``-brokerprofile`` — broker profiles."""

    def __init__(self, client: SQXHttpClient) -> None:
        self._c = client

    async def list(self) -> BrokerProfileList:
        raw = await self._c._send("-brokerprofile action=list")
        return BrokerProfileList(profiles=_clean_lines(raw), raw=raw)

    async def update_all(self) -> CommandResult:
        return CommandResult(raw=await self._c._send("-brokerprofile action=updateAll"))

    async def update(self, id: str) -> CommandResult:
        return CommandResult(raw=await self._c._send(f"-brokerprofile action=update id={id}"))

    async def import_stocks(self, id: str, filepath: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(
                f"-brokerprofile action=importstocks id={id} filepath={filepath}"
            )
        )

    async def export_stocks(self, id: str, filepath: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(
                f"-brokerprofile action=exportstocks id={id} filepath={filepath}"
            )
        )

    async def import_profile(self, filepath: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(f"-brokerprofile action=import filepath={filepath}")
        )

    async def export_profile(self, id: str, filepath: str) -> CommandResult:
        return CommandResult(
            raw=await self._c._send(f"-brokerprofile action=export id={id} filepath={filepath}")
        )


# ---------------------------------------------------------------------------
# Parsing helpers (at bottom for readability)
# ---------------------------------------------------------------------------

_SEPARATOR_CHARS = frozenset("-=~*#_")

_FOOTER_PHRASES = (
    "listed.",
    "saved.",
    "loaded.",
    "exported.",
    "synchronization finished.",
    "projects listed.",
    "databanks listed.",
    "data listed.",
    "strategies listed.",
)

_COMPLETION_TERMS = ("completed", "finished", "done", "success")


def _is_separator(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and all(ch in _SEPARATOR_CHARS for ch in stripped)


def _is_footer(line: str) -> bool:
    lowered = line.strip().lower()
    return any(phrase in lowered for phrase in _FOOTER_PHRASES)


def _clean_lines(raw: str) -> list[str]:
    """Drop separators, headers, footers and blanks — keep content lines."""
    out: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or _is_separator(stripped) or _is_footer(stripped):
            continue
        out.append(stripped)
    return out


def _parse_csv_table(raw: str) -> list[dict[str, str]]:
    """Parse the ``Header1,Header2`` + rows blocks SQX emits.

    Raises SQXParseError when no header row is found.
    """
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or _is_separator(stripped) or _is_footer(stripped):
            continue
        if "," not in stripped:
            continue
        cells = [c.strip() for c in stripped.split(",")]
        if header is None:
            header = cells
            continue
        rows.append({h: (cells[i] if i < len(cells) else "") for i, h in enumerate(header)})
    if header is None:
        raise SQXParseError("", raw, "no CSV header row found")
    return rows


def _is_completed_text(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in _COMPLETION_TERMS)


def _is_not_ready(text: str) -> bool:
    return "not ready" in text.lower()


def _is_error(text: str) -> bool:
    return text.lstrip().startswith("Error:")