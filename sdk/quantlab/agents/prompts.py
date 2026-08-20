"""Prompt templates for LLM-powered research agent.

Each template is a format string with structured placeholders for the
relevant data context. Templates are organised by analysis type:

- ``fundamental``: Company financial metrics (PE, PB, ROE, revenue, debt)
- ``technical``:  Price action and indicators (close, volume, RSI, SMA)
- ``macro``:      Macroeconomic indicators (GDP, CPI, rates, unemployment)
- ``news``:       News articles and sentiment for a given query

Usage::

    prompt = PROMPT_TEMPLATES["fundamental"].format(
        ticker="AAPL", pe=25.5, pb=8.2, roe=0.35, ...,
    )
"""

from __future__ import annotations

PROMPT_TEMPLATES: dict[str, str] = {
    "fundamental": (
        "You are a financial research analyst. Analyze the following fundamental "
        "data for {ticker} and generate trading hypotheses.\n\n"
        "Fundamental Metrics:\n"
        "- P/E Ratio: {pe}\n"
        "- P/B Ratio: {pb}\n"
        "- ROE: {roe}\n"
        "- Revenue: {revenue}\n"
        "- Total Debt: {debt}\n\n"
        "Based on these fundamentals, identify potential catalysts, valuation "
        "gaps, and risk factors. Suggest specific entry/exit conditions."
    ),
    "technical": (
        "You are a technical analysis specialist. Review the following price "
        "action data for {ticker} and generate trading hypotheses.\n\n"
        "Technical Data:\n"
        "- Latest Close: {close}\n"
        "- Volume: {volume}\n"
        "- RSI(14): {rsi}\n"
        "- SMA(50): {sma}\n\n"
        "Based on price action and indicators, identify chart patterns, "
        "support/resistance levels, and potential breakout or reversal setups."
    ),
    "macro": (
        "You are a macroeconomist. Analyze the following macroeconomic "
        "indicators and generate trading hypotheses.\n\n"
        "Macroeconomic Context:\n"
        "- GDP Growth: {gdp}\n"
        "- CPI Inflation: {cpi}\n"
        "- Interest Rate: {rate}\n"
        "- Unemployment: {unemployment}\n\n"
        "Based on these macro conditions, identify asset classes or sectors "
        "likely to outperform, and suggest directional trading strategies."
    ),
    "news": (
        "You are a news analyst. Review the following news articles for "
        "query '{query}' and generate trading hypotheses.\n\n"
        "News Articles:\n"
        "{articles}\n\n"
        "Each article may include its source URL in parentheses. When you "
        "base a hypothesis on an article, cite that URL in the hypothesis "
        "source_urls. Based on news sentiment and content, identify "
        "market-moving events, catalysts, and potential trading opportunities."
    ),
}

TOOL_KNOWLEDGE_TEMPLATES: dict[str, str] = {
    # Official tool-knowledge surfaces (REQ-LMR-01). Populated via retrieval
    # or curated cheat-sheets only — full corpora are never injected. Each
    # template points the agent at the version-pinned KB cheat-sheet instead
    # of embedding corpus text.
    "sqx_block_snippet": (
        "SQX block-to-snippet mapping: every indicator block in StrategyQuant X "
        "maps to a Java snippet in the 931-entry snippet corpus "
        "(internal/autocomplete/Snippets/SQ/Blocks/). Consult the curated "
        "cheat-sheet 'block-to-snippet' for the block->snippet mapping before "
        "translating a block into JForex; never invent JForex API calls."
    ),
    "jforex_lifecycle": (
        "JForex strategy lifecycle: a strategy implements IStrategy with "
        "onStart(), onBar(), onTick() and onStop() callbacks. Annotate "
        "user-editable parameters with @Configurable so the generated JForex "
        "code stays tunable in the Dukascopy platform. See the curated "
        "cheat-sheet 'jforex-lifecycle' for the ABL->JForex translation rules."
    ),
    "sqx_http_api": (
        "SQX HTTP API: strategy operations are exposed over HTTP endpoints. "
        "Endpoint paths and payload schemas are version-pinned in the installed "
        "distribution's docs; consult the curated cheat-sheet 'sqx-http-api' "
        "or get_doc('api', ...) instead of guessing paths."
    ),
}
