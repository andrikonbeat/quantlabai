"""LLMResearchAgent — AI-powered research agent using LLM providers.

Generates structured ``ResearchConfig`` with hypotheses by fetching data
from YahooFinance, FRED, and News providers, building a structured prompt,
calling an LLM (OpenAI or Anthropic), and parsing the structured response.

If the LLM call fails (timeout, API error, parse error, or missing SDK),
the agent falls back transparently to the classic ``ResearchAgent``.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from typing import Any

from quantlab.agents.prompts import PROMPT_TEMPLATES
from quantlab.agents.research_agent import ResearchAgent
from quantlab.data.fundamental.fred import FredProvider
from quantlab.data.fundamental.yahoo import YahooFinanceProvider
from quantlab.dsl.models import (
    HypothesisConfig,
    LLMConfig,
    Market,
    ResearchConfig,
    Timeframe,
)
from quantlab.robustness.llm_circuit_breaker import LLMCircuitBreaker

try:
    from quantlab.data.news.web_search import WebSearchProvider
except ImportError:  # pragma: no cover
    WebSearchProvider = None  # type: ignore[assignment]

try:
    from quantlab.data.news.rss import RSSNewsProvider
except ImportError:  # pragma: no cover
    RSSNewsProvider = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Timeout for a single `opencode run` CLI invocation. The runtime boots
# fully (agents, skills, plugins), so allow generous headroom.
_OPENCODE_CLI_TIMEOUT: float = 300.0


class LLMResearchAgent:
    """AI-powered research agent that queries providers and LLMs.

    Generates ``ResearchConfig`` from natural-language objectives by:
    1. Fetching fundamental, macro, and news data from providers.
    2. Building a structured prompt with the collected data.
    3. Calling an LLM (OpenAI or Anthropic) for analysis.
    4. Parsing the structured LLM response into ``ResearchConfig``.
    5. Validating the output (source URLs, ticker correctness).
    6. Falling back to classic ``ResearchAgent`` on any failure.

    Args:
        research_agent_cls: Optional ``ResearchAgent`` class override for
            testing or custom fallback logic.
    """

    def __init__(
        self,
        research_agent_cls: type[ResearchAgent] | None = None,
        circuit_breaker: LLMCircuitBreaker | None = None,
    ) -> None:
        self._fallback_cls = research_agent_cls or ResearchAgent
        self._circuit_breaker = circuit_breaker or LLMCircuitBreaker()
        self._yahoo: YahooFinanceProvider | None = None
        self._fred: FredProvider | None = None
        self._web_search: Any = None
        self._rss_news: Any = None

    # ── Provider lazy init ─────────────────────────────────────────────────────

    def _get_yahoo(self) -> YahooFinanceProvider:
        if self._yahoo is None:
            self._yahoo = YahooFinanceProvider()
        return self._yahoo

    def _get_fred(self) -> FredProvider:
        if self._fred is None:
            self._fred = FredProvider()
        return self._fred

    def _get_web_search(self) -> Any | None:
        """Lazily initialize the WebSearchProvider singleton.

        Returns ``None`` when the provider is unavailable (missing
        dependency), matching the guarded-provider contract (NWS-01).
        """
        if self._web_search is None:
            try:
                if WebSearchProvider is None:  # type: ignore[truthy-function]
                    return None
                self._web_search = WebSearchProvider()
            except ImportError:  # pragma: no cover
                self._web_search = None
        return self._web_search

    def _get_rss_news(self) -> Any | None:
        """Lazily initialize the RSSNewsProvider singleton.

        Returns ``None`` when the provider is unavailable (missing
        dependency), matching the guarded-provider contract (NWS-01).
        """
        if self._rss_news is None:
            try:
                if RSSNewsProvider is None:  # type: ignore[truthy-function]
                    return None
                self._rss_news = RSSNewsProvider()
            except ImportError:  # pragma: no cover
                self._rss_news = None
        return self._rss_news

    # ── Task 2.5: fetch_data ────────────────────────────────────────────────────

    async def fetch_data(
        self,
        objective: str,
        market_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fetch fundamental, macro, and news data for the given objective.

        Args:
            objective: Research objective string.
            market_context: Optional dict with ``market``, ``ticker`` keys.

        Returns:
            A dict with keys ``fundamental``, ``macro``, ``news``, ``ticker``.

        Raises:
            ConnectionError: If all providers fail.
        """
        context = market_context or {}
        ticker: str = context.get("ticker", "")

        # Infer ticker from market if not explicitly given
        if not ticker:
            market_str = context.get("market", "")
            known_equities = {
                Market.SP500: "SPY",
                Market.NASDAQ: "QQQ",
                Market.DOWJONES: "DIA",
            }
            try:
                market = Market(market_str.upper()) if market_str else None
                ticker = known_equities.get(market, market_str) if market else ""
            except ValueError:
                ticker = market_str if market_str else ""

        fundamental_data: dict[str, Any] = {"ticker": ticker}
        macro_data: dict[str, Any] = {}
        news_data: list[dict[str, Any]] = []

        # Fetch fundamental data from YahooFinance
        if ticker:
            try:
                yahoo = self._get_yahoo()
                raw = await yahoo.fetch(ticker)
                info = raw.get("info", {})
                fundamental_data = {
                    "ticker": ticker,
                    "pe": info.get("trailingPE"),
                    "pb": info.get("priceToBook"),
                    "roe": info.get("returnOnEquity"),
                    "revenue": info.get("totalRevenue"),
                    "debt": info.get("totalDebt"),
                    "market_cap": info.get("marketCap"),
                    "sector": info.get("sector"),
                    "industry": info.get("industry"),
                }
            except Exception as exc:
                logger.warning("YahooFinance fetch failed for %s: %s", ticker, exc)

        # Fetch macro data from FRED
        fred_series = [
            ("GDP", "gdp"),
            ("CPIAUCSL", "cpi"),
            ("FEDFUNDS", "rate"),
            ("UNRATE", "unemployment"),
        ]
        try:
            fred = self._get_fred()
            for series_id, key in fred_series:
                try:
                    raw = await fred.fetch(series_id)
                    latest = raw.get("latest", {})
                    macro_data[key] = latest.get("value")
                except Exception as exc:
                    logger.debug("FRED fetch failed for %s: %s", series_id, exc)
                    macro_data[key] = None
        except Exception as exc:
            logger.warning("FRED provider init failed: %s", exc)

        # Normalise macro values for prompt formatting
        macro_formatted: dict[str, str] = {}
        for key, val in macro_data.items():
            if val is not None:
                if key == "rate":
                    macro_formatted[key] = f"{val:.2f}%"
                elif key == "unemployment":
                    macro_formatted[key] = f"{val:.1f}%"
                elif val is not None:
                    macro_formatted[key] = str(val)
            else:
                macro_formatted[key] = "N/A"

        # News: web search (query = market or objective) + RSS (ticker-scoped)
        market_query: str = context.get("market") or objective
        web_provider = self._get_web_search()
        if web_provider is not None:
            try:
                web_results = await web_provider.search_web(market_query)
                for result in web_results:
                    news_data.append(
                        {
                            "title": getattr(result, "title", ""),
                            "url": getattr(result, "url", ""),
                            "summary": getattr(result, "snippet", ""),
                            "source": getattr(result, "source", ""),
                        }
                    )
            except Exception as exc:
                logger.warning("Web search fetch failed: %s", exc)

        if ticker:
            rss_provider = self._get_rss_news()
            if rss_provider is not None:
                try:
                    rss_items = await rss_provider.fetch_news(ticker)
                    for item in rss_items:
                        news_data.append(
                            {
                                "title": getattr(item, "title", ""),
                                "url": getattr(item, "url", ""),
                                "summary": getattr(item, "summary", ""),
                                "source": getattr(item, "source", ""),
                            }
                        )
                except Exception as exc:
                    logger.warning("RSS news fetch failed: %s", exc)

        return {
            "ticker": ticker,
            "fundamental": fundamental_data,
            "macro": macro_formatted,
            "news": news_data,
        }

    # ── Task 2.5: build_prompt ──────────────────────────────────────────────────

    def build_prompt(
        self,
        objective: str,
        data: dict[str, Any],
    ) -> str:
        """Build a structured prompt from fetched data using templates.

        Selects templates based on available data and combines them into
        a single coherent prompt for the LLM.

        Args:
            objective: The research objective string.
            data: Dict from ``fetch_data()`` with ``fundamental``, ``macro``,
                ``news``, and ``ticker`` keys.

        Returns:
            A formatted prompt string ready for LLM consumption.
        """
        sections: list[str] = [
            "You are a quantitative research analyst. Generate a structured "
            "research configuration based on the following data.\n",
            f"Research Objective: {objective}\n",
        ]

        # Fundamental section
        fund = data.get("fundamental", {})
        if fund.get("ticker"):
            ticker = fund["ticker"]
            sections.append(
                PROMPT_TEMPLATES["fundamental"].format(
                    ticker=ticker,
                    pe=fund.get("pe", "N/A"),
                    pb=fund.get("pb", "N/A"),
                    roe=fund.get("roe", "N/A"),
                    revenue=fund.get("revenue", "N/A"),
                    debt=fund.get("debt", "N/A"),
                )
            )

        # Technical section (if price data available)
        if fund.get("ticker"):
            sections.append(
                PROMPT_TEMPLATES["technical"].format(
                    ticker=fund["ticker"],
                    close=fund.get("close", "N/A"),
                    volume=fund.get("volume", "N/A"),
                    rsi=fund.get("rsi", "N/A"),
                    sma=fund.get("sma_50", "N/A"),
                )
            )

        # Macro section
        macro = data.get("macro", {})
        if macro:
            sections.append(
                PROMPT_TEMPLATES["macro"].format(
                    gdp=macro.get("gdp", "N/A"),
                    cpi=macro.get("cpi", "N/A"),
                    rate=macro.get("rate", "N/A"),
                    unemployment=macro.get("unemployment", "N/A"),
                )
            )

        # News section
        news = data.get("news", [])
        if news:
            article_lines: list[str] = []
            for a in news[:10]:
                line = f"- {a.get('title', '')}: {a.get('summary', '')}"
                url = a.get("url", "")
                if url:
                    line += f" ({url})"
                article_lines.append(line)
            articles_text = "\n".join(article_lines) or "No news articles available."
            sections.append(
                PROMPT_TEMPLATES["news"].format(
                    query=objective,
                    articles=articles_text,
                )
            )

        # Response format instruction
        sections.append(
            "\nReturn your response as valid JSON with the following structure:\n"
            "{\n"
            '  "campaign": "Campaign name",\n'
            '  "market": "Market symbol (e.g. SP500, EURUSD, AAPL)",\n'
            '  "timeframe": "D1|H4|H1|M30|M15|M5|M1",\n'
            '  "building_blocks": [{"name": "...", "indicator": {"name": "...", '
            '"params": {...}}}],\n'
            '  "strategies": [{"name": "...", "direction": "LONG|SHORT|BOTH", '
            '"building_blocks": ["..."]}],\n'
            '  "hypotheses": [\n'
            "    {\n"
            '      "name": "hypothesis_name",\n'
            '      "description": "What this hypothesis tests",\n'
            '      "parameters": {"key": "value"},\n'
            '      "expected_outcome": "Expected result",\n'
            '      "confidence": 0.75,\n'
            '      "llm_rationale": "Why this hypothesis was generated",\n'
            '      "source_urls": ["https://..."],\n'
            '      "data_sources": ["yahoo-finance", "fred"]\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "IMPORTANT: Each hypothesis MUST include source_urls and "
            "a data_sources array."
        )

        return "\n".join(sections)

    # ── Task 2.5: call_llm ─────────────────────────────────────────────────────

    async def call_llm(
        self,
        prompt: str,
        llm_config: LLMConfig,
    ) -> str:
        """Call the LLM provider with the given prompt.

        Tries to import the ``openai`` SDK. If not installed, raises
        ``ImportError``. When installed, calls the configured provider API
        and returns the response text.

        Args:
            prompt: The formatted prompt string.
            llm_config: ``LLMConfig`` with provider, model, and parameters.

        Returns:
            The LLM response text as a string.

        Raises:
            ImportError: If the ``openai`` SDK is not installed.
            ValueError: If the provider is unsupported.
            Exception: On API errors (caught by ``generate_config``).
        """
        provider = llm_config.provider

        if provider == "opencode":
            return await self._call_opencode_cli(prompt, llm_config)

        if provider == "openai":
            try:
                import openai  # noqa: F811
            except ImportError:
                raise ImportError(
                    "openai SDK is not installed. Install with: pip install openai"
                )

            # Lazy-import inside the try block to handle missing SDK
            try:
                from openai import AsyncOpenAI

                kwargs: dict[str, Any] = {
                    "max_retries": 2,
                    "timeout": llm_config.max_tokens,
                }
                if llm_config.base_url:
                    kwargs["base_url"] = llm_config.base_url
                api_key = os.environ.get(llm_config.api_key_env)
                if api_key:
                    kwargs["api_key"] = api_key

                client = AsyncOpenAI(**kwargs)
                response = await client.chat.completions.create(
                    model=llm_config.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=llm_config.temperature,
                    max_tokens=llm_config.max_tokens,
                )
                content = response.choices[0].message.content or ""
                return content
            except Exception:
                raise

        elif provider == "anthropic":
            raise ValueError(
                "Anthropic provider is not yet supported. "
                "Use provider='openai' or 'opencode' instead."
            )
        else:
            raise ValueError(
                f"Unsupported LLM provider '{provider}'. "
                f"Supported: {', '.join(sorted(LLMConfig.VALID_PROVIDERS))}"
            )

    async def _call_opencode_cli(
        self,
        prompt: str,
        llm_config: LLMConfig,
    ) -> str:
        """Call the local OpenCode CLI instead of the HTTP Zen API.

        OpenCode Zen's HTTP API rate-limits the free tier with HTTP 429
        (``FreeUsageLimitError``). Calling the user's local ``opencode``
        binary uses their already-authenticated login (OAuth), needs no
        ``OPENCODE_API_KEY``, and does not hit the Zen quota.

        Emits ``opencode run --format json -m <provider/model> "<prompt>"``
        and parses the NDJSON event stream: assistant text lives in
        ``type == "text"`` events under ``part.text``; the run ends with a
        ``step_finish`` event.

        Raises:
            RuntimeError: If the opencode binary is missing, the run fails,
                times out, or produces no text output.
        """
        binary = shutil.which("opencode")
        if binary is None:
            raise RuntimeError(
                "opencode CLI not found in PATH. Install opencode "
                "(https://opencode.ai) and sign in with `opencode auth login` "
                "to use provider='opencode'."
            )

        # The -m flag expects provider/model form; a bare model gets the
        # opencode provider prefix unless it already carries one.
        model = llm_config.model
        if "/" not in model:
            model = f"opencode/{model}"

        cmd = [
            binary,
            "run",
            "--format",
            "json",
            "-m",
            model,
            prompt,
        ]
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_OPENCODE_CLI_TIMEOUT,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"opencode run timed out after {_OPENCODE_CLI_TIMEOUT}s"
            ) from exc

        if completed.returncode != 0:
            raise RuntimeError(
                f"opencode run failed (exit {completed.returncode}): "
                f"{completed.stderr.strip() or completed.stdout.strip()}"
            )

        # Parse NDJSON events: accumulate assistant text, ignore others.
        parts: list[str] = []
        for line in completed.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "text":
                part = event.get("part") or {}
                if part.get("type") == "text" and part.get("text"):
                    parts.append(part["text"])

        content = "\n".join(parts).strip()
        if not content:
            raise RuntimeError(
                "opencode run produced no text output. "
                f"stdout: {(completed.stdout or '').strip()[:500]}"
            )
        return content

    # ── Task 2.3: parse_response ────────────────────────────────────────────────

    def parse_response(self, response_text: str | None) -> ResearchConfig:
        """Parse an LLM JSON response into a ``ResearchConfig``.

        Args:
            response_text: The raw JSON string from the LLM.

        Returns:
            A validated ``ResearchConfig`` instance.

        Raises:
            ValueError: If the response is empty, not valid JSON, or missing
                required fields.
        """
        if not response_text or not response_text.strip():
            raise ValueError("LLM response is empty")

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Failed to parse LLM response as JSON: {exc}"
            ) from exc

        # Validate required fields
        required = {"campaign", "market", "timeframe"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(
                f"LLM response missing required fields: {', '.join(sorted(missing))}"
            )

        # Parse market
        try:
            market = Market(data["market"].upper())
        except ValueError:
            # Allow non-enum markets (e.g., AAPL for stocks) — pass as str
            market = data["market"]

        # Parse timeframe
        try:
            timeframe = Timeframe(data["timeframe"].upper())
        except ValueError:
            timeframe = Timeframe.D1

        # Parse hypotheses
        hypotheses: list[HypothesisConfig] = []
        for h_data in data.get("hypotheses", []):
            hypotheses.append(
                HypothesisConfig(
                    name=h_data.get("name", "llm_hypothesis"),
                    description=h_data.get("description", ""),
                    parameters=h_data.get("parameters", {}),
                    expected_outcome=h_data.get("expected_outcome", ""),
                    confidence=h_data.get("confidence", 0.5),
                    llm_rationale=h_data.get("llm_rationale"),
                    source_urls=h_data.get("source_urls", []),
                    data_sources=h_data.get("data_sources", []),
                )
            )

        # Parse building blocks
        building_blocks = data.get("building_blocks", [])

        # Parse strategies
        strategies = data.get("strategies", [])

        # Build ResearchConfig
        config = ResearchConfig(
            campaign=data.get("campaign", "LLM Research"),
            market=market if isinstance(market, Market) else Market.SP500,
            timeframe=timeframe,
            building_blocks=building_blocks,
            strategies=strategies,
            criteria=data.get("criteria", []),
            hypotheses=hypotheses,
            iteration_config=data.get("iteration_config", None),
        )

        return config

    # ── Task 2.7: output validation ─────────────────────────────────────────────

    def validate_output(self, config: ResearchConfig) -> ResearchConfig:
        """Validate the output ``ResearchConfig`` before returning.

        Checks:
        - Each hypothesis has at least one ``source_url``.
        - If ticker references are present in parameters, they are valid
          ``Market`` enum values or reasonable ticker symbols.

        Args:
            config: The ``ResearchConfig`` to validate.

        Returns:
            The same ``ResearchConfig`` instance if validation passes.

        Raises:
            ValueError: If validation fails.
        """
        for hyp in config.hypotheses:
            if not hyp.source_urls:
                raise ValueError(
                    f"Hypothesis '{hyp.name}' has no source_urls. "
                    "Each hypothesis must cite at least one source URL."
                )

            # Validate ticker if present in parameters
            ticker = hyp.parameters.get("ticker", "")
            if ticker:
                # Check if it's a known Market enum value
                try:
                    Market(ticker.upper())
                except ValueError:
                    # Allow common ticker patterns (1-5 uppercase alphanumeric)
                    if not (
                        ticker.isupper()
                        and ticker.isascii()
                        and ticker.isalpha()
                        and 1 <= len(ticker) <= 5
                    ):
                        raise ValueError(
                            f"Invalid ticker '{ticker}' in hypothesis "
                            f"'{hyp.name}'. Use a valid Market enum or a "
                            "standard ticker symbol (1-5 uppercase letters)."
                        )

        return config

    # ── Task 2.5: generate_config ───────────────────────────────────────────────

    async def generate_config(
        self,
        objectives: list[str],
        market_context: dict[str, Any] | None = None,
        llm_config: LLMConfig | None = None,
    ) -> ResearchConfig:
        """Generate a ``ResearchConfig`` using LLM-powered analysis.

        Orchestrates the full pipeline:
        1. Fetch data from YahooFinance, FRED, and News providers.
        2. Build a structured prompt with the collected data.
        3. Call the LLM provider.
        4. Parse the LLM response into ``ResearchConfig``.
        5. Validate the output.
        6. On any failure, fall back to classic ``ResearchAgent``.

        Args:
            objectives: Research objective strings.
            market_context: Optional market context dict.
            llm_config: ``LLMConfig`` for the LLM call. If ``None``, falls
                back immediately to ``ResearchAgent``.

        Returns:
            A validated ``ResearchConfig`` instance.
        """
        # If no LLM config, fallback immediately to classic
        if llm_config is None:
            logger.info("No LLMConfig provided — falling back to classic ResearchAgent")
            return await self._fallback(objectives, market_context)

        try:
            # Step 1: Fetch data from providers
            logger.debug("Fetching data for LLM research agent")
            data = await self.fetch_data(
                objectives[0] if objectives else "",
                market_context,
            )

            # Step 2: Build prompt
            prompt = self.build_prompt(
                objectives[0] if objectives else "",
                data,
            )

            # Step 3: Call LLM through circuit breaker
            logger.debug(
                "Calling LLM provider '%s' model '%s'",
                llm_config.provider,
                llm_config.model,
            )
            response_text = await self._circuit_breaker.call(
                self.call_llm(prompt, llm_config)
            )

            # Step 4: Parse response
            config = self.parse_response(response_text)

            # Step 5: Validate output
            config = self.validate_output(config)

            logger.info(
                "LLMResearchAgent: generated config with %d hypotheses",
                len(config.hypotheses),
            )
            return config

        except ImportError as exc:
            logger.warning(
                "LLM SDK not available (%s) — falling back to classic ResearchAgent",
                exc,
            )
            return await self._fallback(objectives, market_context)

        except Exception as exc:
            logger.warning(
                "LLM research agent failed (%s: %s) — "
                "falling back to classic ResearchAgent",
                type(exc).__name__,
                exc,
            )
            return await self._fallback(objectives, market_context)

    # ── Fallback ────────────────────────────────────────────────────────────────

    async def _fallback(
        self,
        objectives: list[str],
        market_context: dict[str, Any] | None = None,
    ) -> ResearchConfig:
        """Fall back to the classic ``ResearchAgent``.

        Args:
            objectives: Research objective strings.
            market_context: Optional market context dict.

        Returns:
            A ``ResearchConfig`` from the classic agent.
        """
        logger.info("Falling back to classic ResearchAgent")
        fallback = self._fallback_cls()
        return fallback.generate_config(objectives, market_context)
