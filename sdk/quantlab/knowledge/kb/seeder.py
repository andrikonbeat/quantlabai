"""SQX Parameter KB seeder (REQ-203, D7).

Extracts the documented builder parameters from ``doc_dev/SQX Builder Config.md``
into one YAML per parameter with ``status: seeded`` and an ``evidence_ref``
pointing back at the doc. The extraction is CURATED: ``SEED_SPEC`` holds the
meaningful documented subset per tab (the full builder surface — 339 signals
blocks, all indicator combinations — is deferred). Every entry carries
``doc_keys``: distinctive fragments that MUST appear in that tab's section of
the doc. An entry whose keys are not found is downgraded to
``status: needs_review`` — the seeder NEVER invents parameter semantics.

Doc gaps (ATM experimental tab, Optimizer block, Portfolio Master vs
Portfolio Composer, Cross Checks vs Retester, Data-range-parts OOS) become
explicit ``needs_review`` entries with a "Not documented" marker instead of
fabricated content (REQ-203).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from quantlab.knowledge.kb.models import KbParameter
from quantlab.knowledge.kb.store import KbStore

# Default source document (relative to the project root).
DEFAULT_DOC_PATH = "doc_dev/SQX Builder Config.md"

# Marker used for doc-gap entries: no invented semantics (REQ-203).
GAP_WHAT_IT_DOES = "Not documented — doc gap; semantics pending review (no invented content)"
GAP_HOW_IT_WORKS = "Not documented — doc gap; pending review"
GAP_TRADING_ROLE = "Not documented — doc gap; pending review"

# Distinctive heading fragments used to split the doc into per-tab sections.
TAB_HEADING_MARKERS: dict[str, str] = {
    "What to build": "**what to build**",
    "Genetic options": "**genetic options**",
    "Data": "**data**",
    "Trading options": "**trading options**",
    "Building blocks": "building blocks",
    "Money management": "**money management**",
    "Cross checks": "cross checks",
    "Ranking": "**ranking**",
}


@dataclass
class SeedResult:
    """Outcome of a seed run."""

    total: int = 0
    seeded: int = 0
    needs_review: int = 0
    parameters: list[KbParameter] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"SeedResult(total={self.total}, seeded={self.seeded}, "
            f"needs_review={self.needs_review})"
        )


# ── Curated documented subset per tab (source: doc_dev/SQX Builder Config.md) ──
# Each entry maps 1:1 to the KbParameter schema plus ``doc_keys`` (distinctive
# substrings that must appear in the tab's section for the entry to be seeded).

SEED_SPEC: list[dict[str, object]] = [
    # ── What to build ────────────────────────────────────────────────────────
    {
        "name": "Strategy type", "sqx_name": "Strategy type", "tab": "What to build",
        "section": "1. Output config & strategy type", "type": "enum",
        "default": "Simple strategy", "range": None,
        "what_it_does": "Selects the generation mode; Simple strategy builds a strategy for a single symbol and timeframe.",
        "how_it_works_in_sqx": "Builder output mode: Simple strategy [default] produces one strategy per symbol/timeframe.",
        "quant_trading_role": "One symbol/timeframe per portfolio slot keeps generated scope tight.",
        "why_choose": "Slot-filling campaigns run one market per slot.", "when_choose": "Default per protocol.",
        "doc_keys": ["strategy type"],
    },
    {
        "name": "Trading directions", "sqx_name": "Trading directions", "tab": "What to build",
        "section": "2. Additional build config", "type": "enum",
        "default": "Both (Long & Short)", "range": "Long only | Short only | Both",
        "what_it_does": "Sets allowed trade direction(s); Entry Symmetry and Exit Symmetry apply when Both is selected.",
        "how_it_works_in_sqx": "Filters generated logic to the selected direction(s) and symmetry.",
        "quant_trading_role": "Keeps long/short behavior balanced for the slot.",
        "why_choose": "Set per the empty slot's need.", "when_choose": "Default Both unless the hypothesis is directional.",
        "doc_keys": ["trading directions"],
    },
    {
        "name": "Strategy style", "sqx_name": "Strategy style", "tab": "What to build",
        "section": "2. Additional build config", "type": "enum",
        "default": "SQX Signals Style", "range": "SQX Signals Style | Fuzzy Logic | SQ3 (legacy)",
        "what_it_does": "Chooses the rule-generation style; SQX Signals Style is used — not Fuzzy Logic, not legacy SQ3.",
        "how_it_works_in_sqx": "Determines the block language the builder uses to express rules.",
        "quant_trading_role": "Signals style produces block rules that translate to Java JForex.",
        "why_choose": "Fuzzy logic / SQ3 generation is out of protocol.", "when_choose": "Always per protocol.",
        "doc_keys": ["strategy style"],
    },
    {
        "name": "Build mode", "sqx_name": "Build mode", "tab": "What to build",
        "section": "2. Additional build config", "type": "enum",
        "default": "Genetic evolution",
        "range": "max 100 generations; 4 islands x 100 strategies; initial population used; restart on finish",
        "what_it_does": "Sets the build engine; Genetic evolution with generation/island/population limits and restart policy.",
        "how_it_works_in_sqx": "Drives the evolutionary search parameters of the builder.",
        "quant_trading_role": "Core generation engine that finds candidate strategies.",
        "why_choose": "Genetic search over the block space.", "when_choose": "Default build mode.",
        "doc_keys": ["build mode"],
    },
    {
        "name": "Conditions in entry rule", "sqx_name": "Conditions in entry rule", "tab": "What to build",
        "section": "2. Additional build config", "type": "range",
        "default": None, "range": "1 - 2",
        "what_it_does": "Min/max number of conditions allowed inside the entry rule.",
        "how_it_works_in_sqx": "Bounds how many blocks can compose one entry condition.",
        "quant_trading_role": "Fewer conditions reduce overfitting on small accounts.",
        "why_choose": "Simple entry logic survives nano-account costs.", "when_choose": "Default 1-2 per protocol.",
        "doc_keys": ["conditions in entry rule"],
    },
    {
        "name": "Conditions in exit rule", "sqx_name": "Conditions in exit rule", "tab": "What to build",
        "section": "2. Additional build config", "type": "range",
        "default": None, "range": "1 - 2 (if enabled)",
        "what_it_does": "Min/max number of conditions allowed inside the exit rule.",
        "how_it_works_in_sqx": "Bounds exit-condition composition when exit rules are enabled.",
        "quant_trading_role": "Keeps exit logic simple and robust.",
        "doc_keys": ["conditions in exit rule"],
    },
    {
        "name": "Global Indicators period", "sqx_name": "Global Indicators period", "tab": "What to build",
        "section": "2. Additional build config", "type": "range",
        "default": None, "range": "5 - 50",
        "what_it_does": "Allowed range for indicator periods used across generated rules.",
        "how_it_works_in_sqx": "Constrains the periods the builder may assign to indicator blocks.",
        "quant_trading_role": "Avoids absurdly long/short indicator lookbacks.",
        "doc_keys": ["global indicators period"],
    },
    {
        "name": "Global Lookback period (Shift)", "sqx_name": "Global Lookback period (Shift)", "tab": "What to build",
        "section": "2. Additional build config", "type": "range",
        "default": None, "range": "max 3",
        "what_it_does": "Maximum lookback shift allowed for indicator references.",
        "how_it_works_in_sqx": "Limits how far back in bars a rule may look.",
        "quant_trading_role": "Keeps rules aligned to current market state.",
        "doc_keys": ["global lookback period"],
    },
    {
        "name": "Number of Exit Types (SL/PT/etc...)", "sqx_name": "Number of Exit Types (SL/PT/etc...)", "tab": "What to build",
        "section": "2. Additional build config", "type": "range",
        "default": None, "range": "max 3",
        "what_it_does": "Maximum number of distinct exit types (SL, PT, trailing, ...) a strategy may combine.",
        "how_it_works_in_sqx": "Caps exit-type variety per generated strategy.",
        "quant_trading_role": "Bounds exit complexity per strategy.",
        "doc_keys": ["number of exit types"],
    },
    {
        "name": "Stop Loss", "sqx_name": "Stop Loss", "tab": "What to build",
        "section": "3. Stop Loss configuration", "type": "config",
        "default": "ATR-based",
        "range": "ATR Multiple 1.2 - 1.8; ATR Period 14 - 20 (Fixed pips 15-25 and Percent 1.5%-2.5% disabled)",
        "what_it_does": "Required stop-loss rule; ATR-based mode active (Multiple 1.2-1.8, Period 14-20).",
        "how_it_works_in_sqx": "Builder must attach an SL; ATR-based stops scale with volatility on M15.",
        "quant_trading_role": "Mandatory capital-survival control for a $100 account.",
        "small_account_recommendation": {
            "recommended_value": "ATR-based (Multiple 1.2-1.8, Period 14-20)",
            "default_value": "ATR-based",
            "reason": "ATR-based SL adapts to volatility; fixed pips/percent risk mis-calibrate on nano capital.",
        },
        "why_choose": "Required by protocol; ATR adapts to market conditions.", "when_choose": "Always required.",
        "related_parameters": ["Profit Target"],
        "doc_keys": ["stop loss", "atr multiple"],
    },
    {
        "name": "Profit Target", "sqx_name": "Profit Target", "tab": "What to build",
        "section": "4. Profit Target configuration", "type": "config",
        "default": "ATR-based",
        "range": "ATR Multiple 1.2 - 2.2; ATR Period 14 - 20 (Fixed pips 15-50 and Percent 1.5%-5% disabled)",
        "what_it_does": "Required profit-target rule; ATR-based mode active; Limit Risk-Reward (SL vs PT) ratio disabled.",
        "how_it_works_in_sqx": "Builder attaches a PT with ranges independent from the SL.",
        "quant_trading_role": "Defines the reward side; flexible risk-reward keeps edges viable.",
        "why_choose": "Required; separate SL/PT ranges let risk-reward breathe.", "when_choose": "Always required.",
        "related_parameters": ["Stop Loss"],
        "doc_keys": ["profit target", "atr multiple"],
    },
    # ── Genetic options ──────────────────────────────────────────────────────
    {
        "name": "Max # of Generations", "sqx_name": "Max # of Generations", "tab": "Genetic options",
        "section": "1. Genetic options", "type": "int", "default": 100, "range": None,
        "what_it_does": "Maximum number of evolutionary cycles the builder runs (100).",
        "how_it_works_in_sqx": "Evolution stops after this many generations unless restarted.",
        "quant_trading_role": "Budget for the search; 100 per protocol.",
        "doc_keys": ["of generations"],
    },
    {
        "name": "Population Size (per island)", "sqx_name": "Population Size (per island)", "tab": "Genetic options",
        "section": "1. Genetic options", "type": "int", "default": 100, "range": None,
        "what_it_does": "Strategies coexisting in each island per generation (100).",
        "how_it_works_in_sqx": "Per-island population pool for the genetic search.",
        "quant_trading_role": "Diversity pool per island.",
        "doc_keys": ["population size"],
    },
    {
        "name": "Crossover Probability", "sqx_name": "Crossover Probability", "tab": "Genetic options",
        "section": "1. Genetic options", "type": "int", "default": 93, "range": "0 - 100 (%)",
        "what_it_does": "Chance two parent strategies exchange logic parts to create a child (93%).",
        "how_it_works_in_sqx": "Crossover rate of the genetic algorithm.",
        "quant_trading_role": "Exploration intensity of the search.",
        "doc_keys": ["crossover probability"],
    },
    {
        "name": "Mutation Probability", "sqx_name": "Mutation Probability", "tab": "Genetic options",
        "section": "1. Genetic options", "type": "int", "default": 30, "range": "0 - 100 (%)",
        "what_it_does": "Chance of random rule changes per strategy to introduce variability (30%).",
        "how_it_works_in_sqx": "Mutation rate of the genetic algorithm.",
        "quant_trading_role": "Injects novelty into the population.",
        "doc_keys": ["mutation probability"],
    },
    {
        "name": "Islands (separate evolution)", "sqx_name": "Islands (separate evolution)", "tab": "Genetic options",
        "section": "2. Islands options", "type": "int", "default": 4, "range": None,
        "what_it_does": "Independent evolution environments used to foster diversity (4).",
        "how_it_works_in_sqx": "Island-model evolution with separate gene pools.",
        "quant_trading_role": "Keeps divergent lineages alive.",
        "doc_keys": ["separate evolution"],
    },
    {
        "name": "Migrate every Xth generation, X =", "sqx_name": "Migrate every Xth generation, X =", "tab": "Genetic options",
        "section": "2. Islands options", "type": "int", "default": 87, "range": None,
        "what_it_does": "Best strategies migrate between islands every X generations (87).",
        "how_it_works_in_sqx": "Periodic island migration of elite individuals.",
        "quant_trading_role": "Shares progress across islands.",
        "doc_keys": ["migrate every xth"],
    },
    {
        "name": "Population migration rate", "sqx_name": "Population migration rate", "tab": "Genetic options",
        "section": "2. Islands options", "type": "int", "default": 6, "range": "0 - 100 (%)",
        "what_it_does": "Share of the population moved between islands during migration (6%).",
        "how_it_works_in_sqx": "Migration volume per event.",
        "quant_trading_role": "Balances diversity vs convergence.",
        "doc_keys": ["population migration rate"],
    },
    {
        "name": "Initial population size required", "sqx_name": "Initial population size required", "tab": "Genetic options",
        "section": "3. Initial population generation", "type": "int", "default": 400, "range": None,
        "what_it_does": "Total strategies required to start evolution (400 = 100 x 4 islands).",
        "how_it_works_in_sqx": "Seeds the first generation pool.",
        "quant_trading_role": "Startup pool for the search.",
        "doc_keys": ["initial population size required"],
    },
    {
        "name": "Use strategies from Initial population databank as evolution start",
        "sqx_name": "Use strategies from Initial population databank as evolution start", "tab": "Genetic options",
        "section": "3. Initial population generation", "type": "bool", "default": True, "range": None,
        "what_it_does": "Start evolution from pre-existing databank strategies when available (on).",
        "how_it_works_in_sqx": "Reuses prior good strategies as seed individuals.",
        "quant_trading_role": "Warms up the search with proven logic.",
        "doc_keys": ["initial population databank"],
    },
    {
        "name": "Generated decimation coefficient", "sqx_name": "Generated decimation coefficient", "tab": "Genetic options",
        "section": "3. Initial population generation", "type": "int", "default": 1, "range": None,
        "what_it_does": "Over-generation factor filtered before evolution starts (1 = none).",
        "how_it_works_in_sqx": "Controls how many extra candidates are generated then decimated.",
        "quant_trading_role": "Quality pre-filtering of the start pool.",
        "doc_keys": ["decimation coefficient"],
    },
    {
        "name": "Profit factor > 1 (initial population filter)", "sqx_name": "Profit factor > 1", "tab": "Genetic options",
        "section": "4. Filter generated initial population", "type": "filter",
        "default": "> 1", "range": None,
        "what_it_does": "Only strategies with profit factor above 1 enter the initial population.",
        "how_it_works_in_sqx": "Initial-population acceptance filter.",
        "quant_trading_role": "Excludes outright losers from the start.",
        "doc_keys": ["profit factor"],
    },
    {
        "name": "Detect same strategies in population and replace them with newly generated ones",
        "sqx_name": "Detect same strategies in population and replace them with newly generated ones", "tab": "Genetic options",
        "section": "5. Fresh blood", "type": "bool", "default": True, "range": None,
        "what_it_does": "Detect identical strategies and replace duplicates with fresh ones (on).",
        "how_it_works_in_sqx": "Deduplicates the population to keep genetic diversity.",
        "quant_trading_role": "Prevents wasted generations on clones.",
        "doc_keys": ["detect same strategies"],
    },
    {
        "name": "Replace % of weakest strategies with newly generated",
        "sqx_name": "Replace % of weakest strategies with newly generated", "tab": "Genetic options",
        "section": "5. Fresh blood", "type": "int", "default": 10, "range": "0 - 100 (%)",
        "what_it_does": "Replace the weakest 10% of strategies with brand-new ones.",
        "how_it_works_in_sqx": "Periodic culling of the worst individuals.",
        "quant_trading_role": "Refreshes the gene pool.",
        "doc_keys": ["weakest strategies"],
    },
    {
        "name": "Every generation(s)", "sqx_name": "Every generation(s)", "tab": "Genetic options",
        "section": "5. Fresh blood", "type": "int", "default": 2, "range": None,
        "what_it_does": "Weakest-replacement runs every N generations (2).",
        "how_it_works_in_sqx": "Cadence of the fresh-blood culling.",
        "quant_trading_role": "Cadence control for diversity refresh.",
        "doc_keys": ["every generation"],
    },
    {
        "name": "Start again when finished (continuous repeating evolution)",
        "sqx_name": "Start again when finished (continuous repeating evolution)", "tab": "Genetic options",
        "section": "6. Evolution management", "type": "bool", "default": True, "range": None,
        "what_it_does": "Restart evolution automatically after the generation budget is reached (on).",
        "how_it_works_in_sqx": "Continuous evolution loop.",
        "quant_trading_role": "Keeps searching for better candidates.",
        "doc_keys": ["start again when finished"],
    },
    {
        "name": "Restart evolution if fitness stagnates for X generation(s)",
        "sqx_name": "Restart evolution if fitness stagnates for X generation(s)", "tab": "Genetic options",
        "section": "6. Evolution management", "type": "int", "default": 30, "range": None,
        "what_it_does": "Restart evolution if fitness does not improve for 30 consecutive generations.",
        "how_it_works_in_sqx": "Stagnation watchdog of the search.",
        "quant_trading_role": "Escapes local optima.",
        "doc_keys": ["stagnates"],
    },
    # ── Data ─────────────────────────────────────────────────────────────────
    {
        "name": "Engine", "sqx_name": "Engine", "tab": "Data",
        "section": "1. Trading engine", "type": "enum", "default": "JForex", "range": None,
        "what_it_does": "Selects the trading engine; JForex because final execution is JForex 4 / Dukascopy.",
        "how_it_works_in_sqx": "Chooses the backtest/execution engine family.",
        "quant_trading_role": "Aligns simulation with the live platform.",
        "doc_keys": ["engine", "jforex"],
    },
    {
        "name": "Symbol", "sqx_name": "Symbol", "tab": "Data",
        "section": "2. Backtest data settings", "type": "str",
        "default": "EURUSD_M1_dukas", "range": None,
        "what_it_does": "Backtest symbol (e.g. EURUSD_M1_dukas); alternates per portfolio slot.",
        "how_it_works_in_sqx": "Data feed used for generation and backtests.",
        "quant_trading_role": "The market the strategy must trade.",
        "doc_keys": ["symbol", "dukas"],
    },
    {
        "name": "Timeframe", "sqx_name": "Timeframe", "tab": "Data",
        "section": "2. Backtest data settings", "type": "enum", "default": "M15", "range": None,
        "what_it_does": "Base timeframe (M15) chosen to allow solid technical stops on small accounts.",
        "how_it_works_in_sqx": "Bars used for rule evaluation and backtests.",
        "quant_trading_role": "M15 balances signal quality with trade frequency.",
        "doc_keys": ["timeframe", "m15"],
    },
    {
        "name": "Start day", "sqx_name": "Start day", "tab": "Data",
        "section": "2. Backtest data settings", "type": "date", "default": "2003.05.05", "range": None,
        "what_it_does": "Start of the backtest history (2003.05.05).",
        "how_it_works_in_sqx": "Data window start for generation.",
        "quant_trading_role": "Historical depth for statistical relevance.",
        "doc_keys": ["start day"],
    },
    {
        "name": "End day", "sqx_name": "End day", "tab": "Data",
        "section": "2. Backtest data settings", "type": "date", "default": "2025.12.19", "range": None,
        "what_it_does": "End of the backtest history (2025.12.19).",
        "how_it_works_in_sqx": "Data window end for generation.",
        "quant_trading_role": "Recent regime coverage.",
        "doc_keys": ["end day"],
    },
    {
        "name": "Precision", "sqx_name": "Precision", "tab": "Data",
        "section": "3. Test parameters", "type": "enum",
        "default": "Selected timeframe only (fastest)", "range": "Selected timeframe only | 1 minute data tick simulation",
        "what_it_does": "Backtest precision; fastest mode speeds initial generation; 1-minute tick simulation builds candles more realistically and makes strategies fail more often.",
        "how_it_works_in_sqx": "Controls simulation granularity.",
        "quant_trading_role": "Fastest mode during generation; tick simulation for validation.",
        "why_choose": "Switching this alone can flip generation from producing to producing nothing.", "when_choose": "Fastest for search, tick for confirmation.",
        "doc_keys": ["selected timeframe only"],
    },
    {
        "name": "Commissions & swap", "sqx_name": "Commissions & swap", "tab": "Data",
        "section": "3. Test parameters", "type": "str",
        "default": "$7 per full lot; EUR/USD swap long -0.707, short 0.37", "range": None,
        "what_it_does": "Execution costs modeled in backtests ($7/full lot; EUR/USD swap values).",
        "how_it_works_in_sqx": "Cost model applied per trade.",
        "quant_trading_role": "Costs are decisive on nano accounts.",
        "doc_keys": ["commissions"],
    },
    {
        "name": "Spread", "sqx_name": "Spread", "tab": "Data",
        "section": "3. Test parameters", "type": "float", "default": 1.0, "range": "pips",
        "what_it_does": "Conservative 1-pip spread to keep strategies viable under liquidity shifts.",
        "how_it_works_in_sqx": "Spread model in backtests.",
        "quant_trading_role": "Conservative cost buffer.",
        "doc_keys": ["spread", "pip"],
    },
    {
        "name": "Slippage", "sqx_name": "Slippage", "tab": "Data",
        "section": "3. Test parameters", "type": "float", "default": 0.5, "range": "pips",
        "what_it_does": "Simulated price gap between order and execution (0.5 pips).",
        "how_it_works_in_sqx": "Execution realism model.",
        "quant_trading_role": "Prevents phantom fill quality.",
        "doc_keys": ["slippage"],
    },
    {
        "name": "Min. distance", "sqx_name": "Min. distance", "tab": "Data",
        "section": "3. Test parameters", "type": "float", "default": 0.0, "range": "pips",
        "what_it_does": "Minimum distance enforced for orders (0 pips).",
        "how_it_works_in_sqx": "Order-placement constraint.",
        "quant_trading_role": "Keeps orders executable.",
        "doc_keys": ["min. distance"],
    },
    # ── Trading options ──────────────────────────────────────────────────────
    {
        "name": "Don't trade on weekends", "sqx_name": "Don't trade on weekends", "tab": "Trading options",
        "section": "1. Trading options", "type": "bool", "default": False, "range": None,
        "what_it_does": "Weekend trading enabled/disabled (off).",
        "how_it_works_in_sqx": "Time-gates market entry.",
        "quant_trading_role": "Avoids thin-market execution.",
        "doc_keys": ["weekends"],
    },
    {
        "name": "Friday Close Time", "sqx_name": "Friday Close Time", "tab": "Trading options",
        "section": "1. Trading options", "type": "time", "default": "00:38", "range": None,
        "what_it_does": "Weekly trading closes Friday at 00:38.",
        "how_it_works_in_sqx": "Week close time gate.",
        "quant_trading_role": "Weekend exposure control.",
        "doc_keys": ["friday close time"],
    },
    {
        "name": "Sunday Open Time", "sqx_name": "Sunday Open Time", "tab": "Trading options",
        "section": "1. Trading options", "type": "time", "default": "00:38", "range": None,
        "what_it_does": "Weekly trading reopens Sunday at 00:38.",
        "how_it_works_in_sqx": "Week open time gate.",
        "quant_trading_role": "Defines when exposure resumes.",
        "doc_keys": ["sunday open time"],
    },
    {
        "name": "Exit At End Of Day", "sqx_name": "Exit At End Of Day", "tab": "Trading options",
        "section": "1. Trading options", "type": "bool", "default": False, "range": None,
        "what_it_does": "Positions may be held overnight during the week (off).",
        "how_it_works_in_sqx": "Daily exit gate.",
        "quant_trading_role": "Allows intra-week swing holding.",
        "doc_keys": ["exit at end of day"],
    },
    {
        "name": "End Of Day Exit Time", "sqx_name": "End Of Day Exit Time", "tab": "Trading options",
        "section": "1. Trading options", "type": "time", "default": "23:04", "range": None,
        "what_it_does": "Daily exit time when End Of Day exit is active (23:04).",
        "how_it_works_in_sqx": "Daily close time gate.",
        "quant_trading_role": "Overnight risk control.",
        "doc_keys": ["end of day exit time"],
    },
    {
        "name": "Exit On Friday", "sqx_name": "Exit On Friday", "tab": "Trading options",
        "section": "1. Trading options", "type": "bool", "default": True, "range": None,
        "what_it_does": "Close all positions Friday at 20:40 — a $100 account lacks margin for a weekend gap.",
        "how_it_works_in_sqx": "Friday forced-flat gate.",
        "quant_trading_role": "Protects nano capital from weekend gap risk.",
        "small_account_recommendation": {
            "recommended_value": True, "default_value": False,
            "reason": "A $100 account cannot absorb an adverse weekend gap; flatten before the close.",
        },
        "why_choose": "Weekend gap protection on nano capital.", "when_choose": "Always for small accounts.",
        "doc_keys": ["exit on friday"],
    },
    {
        "name": "Limit Time Range", "sqx_name": "Limit Time Range", "tab": "Trading options",
        "section": "1. Trading options", "type": "bool", "default": False,
        "range": "From 08:00 / To 16:00 (when enabled)",
        "what_it_does": "Restrict trading to a daily time window (off; window 08:00-16:00 when enabled).",
        "how_it_works_in_sqx": "Daily time-range gate.",
        "quant_trading_role": "Optional liquidity alignment.",
        "doc_keys": ["limit time range"],
    },
    {
        "name": "Order Types To Close", "sqx_name": "Order Types To Close", "tab": "Trading options",
        "section": "1. Trading options", "type": "enum", "default": "All", "range": None,
        "what_it_does": "Which order types are closed at the end of the allowed range (All).",
        "how_it_works_in_sqx": "Close-order selection at range end.",
        "quant_trading_role": "Guarantees flat state at range end.",
        "doc_keys": ["order types to close"],
    },
    {
        "name": "Max distance from market", "sqx_name": "Max distance from market", "tab": "Trading options",
        "section": "1. Trading options", "type": "bool", "default": False,
        "range": "Max distance percent 6 (when enabled)",
        "what_it_does": "Cap on how far pending orders may sit from market (off; 6% when enabled).",
        "how_it_works_in_sqx": "Pending-order distance guard.",
        "quant_trading_role": "Avoids stale pending orders.",
        "doc_keys": ["max distance from market"],
    },
    {
        "name": "Maximum Trades Per Day", "sqx_name": "Maximum Trades Per Day", "tab": "Trading options",
        "section": "1. Trading options", "type": "int", "default": 0, "range": "0 = no limit",
        "what_it_does": "Daily trade cap; 0 means no limit in the general config.",
        "how_it_works_in_sqx": "Caps entries per trading day.",
        "quant_trading_role": "Prevents overtrading and excess commissions on a small account.",
        "small_account_recommendation": {
            "recommended_value": 1, "default_value": 0,
            "reason": "Protocol recommends 1 per day to avoid overtrading and excess commissions on a $100 account.",
        },
        "why_choose": "Generation protocol recommends 1 for small accounts.", "when_choose": "Small-account campaigns.",
        "doc_keys": ["maximum trades per day"],
    },
    {
        "name": "Minimum / Maximum SL", "sqx_name": "Minimum / Maximum SL", "tab": "Trading options",
        "section": "1. Trading options", "type": "range", "default": "0 / 0", "range": None,
        "what_it_does": "No extra SL bounds here; SL is controlled in the What to build tab (0/0).",
        "how_it_works_in_sqx": "Builder-level SL constraint override.",
        "quant_trading_role": "Avoids double constraint conflicts.",
        "doc_keys": ["minimum / maximum sl"],
    },
    {
        "name": "Minimum / Maximum PT", "sqx_name": "Minimum / Maximum PT", "tab": "Trading options",
        "section": "1. Trading options", "type": "range", "default": "0 / 0", "range": None,
        "what_it_does": "No extra PT bounds here; PT is controlled in the What to build tab (0/0).",
        "how_it_works_in_sqx": "Builder-level PT constraint override.",
        "quant_trading_role": "Avoids double constraint conflicts.",
        "doc_keys": ["minimum / maximum pt"],
    },
    {
        "name": "Realistic Gaps Handling", "sqx_name": "Realistic Gaps Handling", "tab": "Trading options",
        "section": "1. Trading options", "type": "bool", "default": True, "range": None,
        "what_it_does": "Backtest accounts for price gaps realistically (on).",
        "how_it_works_in_sqx": "Gap-aware simulation model.",
        "quant_trading_role": "Improves robustness of results.",
        "doc_keys": ["realistic gaps handling"],
    },
    {
        "name": "Store Chart Data", "sqx_name": "Store Chart Data", "tab": "Trading options",
        "section": "2. Build options", "type": "bool", "default": False, "range": None,
        "what_it_does": "Persist chart data during builds (off to save space and speed processing).",
        "how_it_works_in_sqx": "Chart storage toggle in builds.",
        "quant_trading_role": "Storage/perf tradeoff.",
        "doc_keys": ["store chart data"],
    },
    # ── Building blocks ──────────────────────────────────────────────────────
    {
        "name": "Signals (Predefined conditions)", "sqx_name": "Signals (Predefined conditions)", "tab": "Building blocks",
        "section": "1. Signals", "type": "selection",
        "default": "188 of 339 blocks selected", "range": None,
        "what_it_does": "Predefined complete conditions combining indicators with comparisons; 188 of 339 selected (ADX, ATR, Awesome Oscillator, Bollinger Bands, CCI, Directional Index, Ichimoku, MACD, RSI, Stochastic, Bar And Time).",
        "how_it_works_in_sqx": "Ready-to-use condition blocks for rules.",
        "quant_trading_role": "Core rule material for hypotheses.",
        "doc_keys": ["188 blocks"],
    },
    {
        "name": "Indicators", "sqx_name": "Indicators", "tab": "Building blocks",
        "section": "2. Indicators", "type": "selection",
        "default": "69 of 106 blocks selected",
        "range": "Excludes {Indicator Crosses Above MA, Indicator Crosses Below MA, Indicator Below MA, Indicator Above MA}",
        "what_it_does": "Indicator blocks combined with operators; 69 of 106 selected; MA-cross family excluded (no Java JForex conversion).",
        "how_it_works_in_sqx": "Indicator/price/operator composition blocks.",
        "quant_trading_role": "Avoids blocks that cannot translate to JForex Java.",
        "doc_keys": ["69 blocks"],
    },
    {
        "name": "Stop/Limit entry blocks", "sqx_name": "Stop/Limit entry blocks", "tab": "Building blocks",
        "section": "3. Stop/Limit entry blocks", "type": "selection",
        "default": "41 of 58 blocks selected",
        "range": "Formula: Price level +/- Multiplicator * Price Range",
        "what_it_does": "Blocks defining entry price for Stop/Limit orders (41 of 58 selected); base formula Price level +/- Multiplicator * Price Range.",
        "how_it_works_in_sqx": "Entry-price construction blocks (levels like Bollinger/Ichimoku/MAs; ranges like ATR/BarRange/Fixed pips).",
        "quant_trading_role": "Determines order-entry precision.",
        "doc_keys": ["stop/limit entry"],
    },
    {
        "name": "Order types", "sqx_name": "Order types", "tab": "Building blocks",
        "section": "4. Order types", "type": "selection",
        "default": "All selected",
        "range": "(MKT) Enter at market; (MKT) Enter/reverse at market; (STOP) Enter at stop; (LMT) Enter at limit",
        "what_it_does": "Order types enabled for generation (all selected).",
        "how_it_works_in_sqx": "Order-entry blocks available to rules.",
        "quant_trading_role": "Entry-style variety.",
        "doc_keys": ["enter at market"],
    },
    {
        "name": "Exit types", "sqx_name": "Exit types", "tab": "Building blocks",
        "section": "5. Exit types", "type": "selection",
        "default": "All selected",
        "range": "Required: Profit Target, Stop Loss; others: Exit After Bars, Move SL 2 BE, Trailing Stop, ExitRule",
        "what_it_does": "Exit blocks enabled; Profit Target and Stop Loss are always required for capital survival.",
        "how_it_works_in_sqx": "Exit-rule blocks available to strategies.",
        "quant_trading_role": "Guarantees every strategy has risk controls.",
        "doc_keys": ["exit types", "trailing stop"],
    },
    {
        "name": "Calibrate indicators", "sqx_name": "Calibrate indicators", "tab": "Building blocks",
        "section": "6. Calibration", "type": "enum",
        "default": "On (calibrate before start)", "range": "On | Off",
        "what_it_does": "Calibrate indicator parameters before generation starts (on) so blocks fit the selected market.",
        "how_it_works_in_sqx": "Pre-generation indicator calibration.",
        "quant_trading_role": "Adapts indicators to the market.",
        "doc_keys": ["calibrate indicators"],
    },
    # ── Money management ─────────────────────────────────────────────────────
    {
        "name": "Initial capital", "sqx_name": "Initial capital", "tab": "Money management",
        "section": "1. Initial capital", "type": "int", "default": 100, "range": "USD",
        "what_it_does": "Base account capital for simulations and survival metrics ($100).",
        "how_it_works_in_sqx": "Account model for the simulation.",
        "quant_trading_role": "Nano-capital anchor for all sizing.",
        "doc_keys": ["initial capital"],
    },
    {
        "name": "Choose Money Management method", "sqx_name": "Choose Money Management method", "tab": "Money management",
        "section": "2. Money management method", "type": "enum",
        "default": "Fixed size",
        "range": "Fixed size | Risk fixed % balance | (other SQX methods)",
        "what_it_does": "Money management method; Fixed size selected because percentage risk distorts results on nano capital.",
        "how_it_works_in_sqx": "Determines how order size is derived per trade.",
        "quant_trading_role": "Fixed lots keep nano-account results undistorted.",
        "small_account_recommendation": {
            "recommended_value": "Fixed size", "default_value": "Fixed size",
            "reason": "Percent-based risk distorts generation results on $100 accounts.",
        },
        "why_choose": "Doc explicitly rejects Risk fixed % balance for nano capital.", "when_choose": "Always for small accounts.",
        "doc_keys": ["money management method", "fixed size"],
    },
    {
        "name": "Order size", "sqx_name": "Order size", "tab": "Money management",
        "section": "3. Order size", "type": "float", "default": 0.01, "range": "lots (0.01 = 1,000 units)",
        "what_it_does": "Fixed order volume of 0.01 lots (1,000 units) keeping per-trade risk at $1.50-$2.50.",
        "how_it_works_in_sqx": "Lot size applied per trade under Fixed size.",
        "quant_trading_role": "Minimum tradable unit; risk-per-trade stays in the $1.50-$2.50 band.",
        "small_account_recommendation": {
            "recommended_value": 0.01, "default_value": 0.01,
            "reason": "Minimum allowed lot keeps per-trade risk within the $1.50-$2.50 band on $100.",
        },
        "doc_keys": ["order size"],
    },
    # ── Cross checks ─────────────────────────────────────────────────────────
    {
        "name": "What If simulations", "sqx_name": "What If simulations", "tab": "Cross checks",
        "section": "1. BASIC (FAST)", "type": "config",
        "default": "15 simulations, 3 filter conditions",
        "range": "Filters: Profit factor > 1.3 AND Ret/DD Ratio > 4",
        "what_it_does": "Scenario tests (e.g. selected days only, exclude best/worst trades) to check profit dependence on isolated events.",
        "how_it_works_in_sqx": "What-If robustness simulations.",
        "quant_trading_role": "Detects event-dependent profitability.",
        "doc_keys": ["what if simulations"],
    },
    {
        "name": "Monte Carlo trades manipulation", "sqx_name": "Monte Carlo trades manipulation", "tab": "Cross checks",
        "section": "1. BASIC (FAST)", "type": "config",
        "default": "2 tests, 30 simulations, 2 conditions",
        "range": "Net profit >= 60% of original at 80% confidence",
        "what_it_does": "Resamples trade sequence and randomly omits 10% of trades to verify equity-curve stability.",
        "how_it_works_in_sqx": "Monte Carlo order/selection perturbation.",
        "quant_trading_role": "Stability of results under trade noise.",
        "doc_keys": ["monte carlo trades manipulation"],
    },
    {
        "name": "Higher backtest precision", "sqx_name": "Higher backtest precision", "tab": "Cross checks",
        "section": "1. BASIC (FAST)", "type": "config",
        "default": "1-minute tick simulation, 3 conditions", "range": "Spread 3 pips",
        "what_it_does": "Slower, precise backtest with wider spread (3 pips) to confirm viability under costlier conditions.",
        "how_it_works_in_sqx": "High-precision re-simulation.",
        "quant_trading_role": "Net profit and trade count must stay >= 80% of the original.",
        "doc_keys": ["higher backtest precision"],
    },
    {
        "name": "Backtests on additional markets", "sqx_name": "Backtests on additional markets", "tab": "Cross checks",
        "section": "2. STANDARD (SLOW)", "type": "config",
        "default": "GBPUSD_M1_dukas", "range": "Spread 0.6; commission $7 per lot",
        "what_it_does": "Retests on a similar symbol to confirm the logic captures a general pattern, not pair-specific noise.",
        "how_it_works_in_sqx": "Cross-market retest.",
        "quant_trading_role": "Generality of the edge across correlated pairs.",
        "doc_keys": ["backtests on additional markets"],
    },
    {
        "name": "Monte Carlo retest methods", "sqx_name": "Monte Carlo retest methods", "tab": "Cross checks",
        "section": "2. STANDARD (SLOW)", "type": "config",
        "default": "6 tests, 10 simulations, 2 conditions",
        "range": "Net Profit >= 50% of original; Max DD % <= 200% of original (80% confidence)",
        "what_it_does": "Hardest test: varies historical data, spread, slippage and strategy parameters simultaneously.",
        "how_it_works_in_sqx": "Joint Monte Carlo perturbation.",
        "quant_trading_role": "Stress-tests the edge under combined shocks.",
        "doc_keys": ["monte carlo retest methods"],
    },
    {
        "name": "Sequential Optimization", "sqx_name": "Sequential Optimization", "tab": "Cross checks",
        "section": "2. STANDARD (SLOW)", "type": "config",
        "default": "Up/Down 50%, 50 steps",
        "range": ">= 80% of parameters must pass stability",
        "what_it_does": "Optimizes parameters sequentially to find stability ranges.",
        "how_it_works_in_sqx": "Per-parameter stability scan.",
        "quant_trading_role": "Rejects spike-dependent parameters.",
        "doc_keys": ["sequential optimization"],
    },
    {
        "name": "Opt. Profile / Sys. Param. Permutation", "sqx_name": "Opt. Profile / Sys. Param. Permutation", "tab": "Cross checks",
        "section": "3. EXTENSIVE (SLOWEST)", "type": "config",
        "default": "Max 1,000 optimizations, 4 conditions", "range": None,
        "what_it_does": "Analyzes the optimization profile to ensure chosen parameters sit in a broad profitable zone, not isolated peaks.",
        "how_it_works_in_sqx": "Optimization-surface analysis.",
        "quant_trading_role": "Robustness of the parameter neighborhood.",
        "doc_keys": ["opt. profile"],
    },
    {
        "name": "Walk-Forward Optimization", "sqx_name": "Walk-Forward Optimization", "tab": "Cross checks",
        "section": "3. EXTENSIVE (SLOWEST)", "type": "config",
        "default": "10 runs, 20% Out of sample",
        "range": "Robustness score >= 50%",
        "what_it_does": "Simulates periodic re-optimization over rolling OOS windows.",
        "how_it_works_in_sqx": "Walk-forward validation loop.",
        "quant_trading_role": "Simulates live re-optimization behavior.",
        "doc_keys": ["walk-forward optimization"],
    },
    {
        "name": "Walk-Forward Matrix", "sqx_name": "Walk-Forward Matrix", "tab": "Cross checks",
        "section": "3. EXTENSIVE (SLOWEST)", "type": "config",
        "default": "OOS 10% - 40%, 5 - 20 runs",
        "range": ">= 1 2x2 zone at 80% robustness; WF Net Profit (OOS) > 0",
        "what_it_does": "Matrix of walk-forward tests hunting the ideal optimization/test period combination.",
        "how_it_works_in_sqx": "Grid of walk-forward runs.",
        "quant_trading_role": "Finds stable optimization windows.",
        "doc_keys": ["walk-forward matrix"],
    },
    # ── Ranking ──────────────────────────────────────────────────────────────
    {
        "name": "Maximum strategies to store in databank", "sqx_name": "Maximum strategies to store in databank", "tab": "Ranking",
        "section": "1. Capacity & stop", "type": "int", "default": 100, "range": None,
        "what_it_does": "Keep only the best strategies passing all filters; 100 slots for the target portfolio slot.",
        "how_it_works_in_sqx": "Databank capacity cap.",
        "quant_trading_role": "Focuses the search on slot-filling quality.",
        "doc_keys": ["maximum strategies to store"],
    },
    {
        "name": "Stop generation when", "sqx_name": "Stop generation when", "tab": "Ranking",
        "section": "1. Capacity & stop", "type": "enum",
        "default": "Databank is full (reached maximum capacity)", "range": None,
        "what_it_does": "Generation stops automatically when the databank reaches its quality/capacity threshold.",
        "how_it_works_in_sqx": "Stop condition of the generation loop.",
        "quant_trading_role": "Avoids endless generation once the slot is filled.",
        "doc_keys": ["stop generation when"],
    },
    {
        "name": "Use", "sqx_name": "Use", "tab": "Ranking",
        "section": "2. Strategy Quality ranking", "type": "enum", "default": "Main data backtest", "range": None,
        "what_it_does": "Data source used for fitness computation (main data backtest).",
        "how_it_works_in_sqx": "Selects the dataset for quality ranking.",
        "quant_trading_role": "Bases selection on the primary backtest.",
        "doc_keys": ["main data backtest"],
    },
    {
        "name": "Compute from", "sqx_name": "Compute from", "tab": "Ranking",
        "section": "2. Strategy Quality ranking", "type": "enum",
        "default": "Weighted Fitness (multiple goals)", "range": None,
        "what_it_does": "Fitness formula; weighted multiple-goal fitness.",
        "how_it_works_in_sqx": "Combines ranking criteria into one fitness score.",
        "quant_trading_role": "Multi-objective selection driver.",
        "doc_keys": ["weighted fitness"],
    },
    {
        "name": "Ranking Criterium", "sqx_name": "Ranking Criterium", "tab": "Ranking",
        "section": "2. Strategy Quality ranking", "type": "config",
        "default": "Ret/DD Ratio Maximize (40); Max DD % Minimize (25); Profit factor Maximize (15); R Expectancy Maximize (10); Ambiguous Trades % Minimize (5); Complexity Minimize (5)",
        "range": "Weights sum to 100",
        "what_it_does": "Fitness goals and weights: Ret/DD 40, Max DD 25, Profit factor 15, R Expectancy 10, Ambiguous 5, Complexity 5.",
        "how_it_works_in_sqx": "Weighted multi-goal ranking.",
        "quant_trading_role": "Prioritizes risk-adjusted return over raw profit; penalizes complexity.",
        "why_choose": "Ret/DD is the dominant quality signal for survival.", "when_choose": "Default protocol weights.",
        "doc_keys": ["ranking criterium"],
    },
    {
        "name": "Custom filters", "sqx_name": "Custom filters", "tab": "Ranking",
        "section": "3. Custom filters", "type": "config",
        "default": "PF(IST) > 1.2; PF(OOS1) > 1.1; PF(ISV) > 1.01; Ret/DD > 3; Avg Trades/Month > 5; Expectancy > 5; Max Consec Losses < 10",
        "range": None,
        "what_it_does": "Mandatory minimum thresholds a strategy must pass to be stored.",
        "how_it_works_in_sqx": "Hard acceptance filters after fitness ranking.",
        "quant_trading_role": "Guarantees statistical and risk floors for stored strategies.",
        "doc_keys": ["custom filters", "profit factor (ist)"],
    },
    {
        "name": "Dismiss strategies with these problems", "sqx_name": "Dismiss strategies with these problems", "tab": "Ranking",
        "section": "4. Automatic filters", "type": "config",
        "default": "No trades / Too little trades; Zero PL trades / Zero duration trades; Too many ambiguous trades; Outlier trade",
        "range": None,
        "what_it_does": "Automatically discard strategies with operational problems.",
        "how_it_works_in_sqx": "Automatic dismissal filters.",
        "quant_trading_role": "Removes untradeable or outlier-dependent logic.",
        "doc_keys": ["dismiss strategies"],
    },
    {
        "name": "Fit to existing portfolio filter", "sqx_name": "Fit to existing portfolio filter", "tab": "Ranking",
        "section": "5. Fit to existing portfolio filter", "type": "config",
        "default": "Existing portfolio databank: Grove; filter out correlation > 0.3",
        "range": "Correlation by Day (or Hour) of Profit/Loss",
        "what_it_does": "Rejects candidates too correlated with strategies already in the portfolio (correlation > 0.3).",
        "how_it_works_in_sqx": "Portfolio correlation gate.",
        "quant_trading_role": "Keeps the portfolio genuinely diversified.",
        "doc_keys": ["existing portfolio"],
    },
]

# Doc gaps: mentioned but unexplained in the doc → needs_review, no invented
# content (REQ-203).
GAP_SPEC: list[dict[str, object]] = [
    {
        "name": "ATM tab", "sqx_name": "ATM tab", "tab": "Building blocks",
        "section": "7. ATM tab (experimental)", "type": "unknown", "status": "needs_review",
        "what_it_does": GAP_WHAT_IT_DOES,
        "how_it_works_in_sqx": GAP_HOW_IT_WORKS,
        "quant_trading_role": GAP_TRADING_ROLE,
    },
    {
        "name": "Data range parts (OOS)", "sqx_name": "Data range parts", "tab": "Data",
        "section": "4. Data range parts", "type": "config", "status": "needs_review",
        "default": "ISV1-ISV10 (~3% each); OOS1 final 30% (2019.03.02 → 2025.12.19)",
        "what_it_does": "Not documented — doc gap; whether generation should include OOS data at all is the author's open question.",
        "how_it_works_in_sqx": GAP_HOW_IT_WORKS,
        "quant_trading_role": GAP_TRADING_ROLE,
    },
    {
        "name": "Cross Checks vs Retester", "sqx_name": "Cross checks vs Retester", "tab": "Cross checks",
        "section": "Intro — Retester block vs builder cross checks", "type": "unknown", "status": "needs_review",
        "what_it_does": GAP_WHAT_IT_DOES,
        "how_it_works_in_sqx": GAP_HOW_IT_WORKS,
        "quant_trading_role": GAP_TRADING_ROLE,
    },
    {
        "name": "Optimizer block", "sqx_name": "Optimizer block", "tab": "Ranking",
        "section": "6. Optimizer block (undeveloped)", "type": "unknown", "status": "needs_review",
        "what_it_does": GAP_WHAT_IT_DOES,
        "how_it_works_in_sqx": GAP_HOW_IT_WORKS,
        "quant_trading_role": GAP_TRADING_ROLE,
    },
    {
        "name": "Portfolio Master vs Portfolio Composer", "sqx_name": "Portfolio Master / Portfolio Composer", "tab": "Ranking",
        "section": "7. Portfolio Master vs Portfolio Composer", "type": "unknown", "status": "needs_review",
        "what_it_does": GAP_WHAT_IT_DOES,
        "how_it_works_in_sqx": GAP_HOW_IT_WORKS,
        "quant_trading_role": GAP_TRADING_ROLE,
    },
]


# ── Doc parsing ───────────────────────────────────────────────────────────────


def parse_doc(doc_path: str | Path) -> dict[str, str]:
    """Split ``doc_dev/SQX Builder Config.md`` into per-tab sections.

    Returns a mapping tab → normalized (lowercased) section text. Tabs are
    detected by their heading markers; the section accumulates every line
    until the next tab heading.
    """
    text = Path(doc_path).read_text(encoding="utf-8")
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if line.startswith("#"):
            matched = next(
                (tab for tab, marker in TAB_HEADING_MARKERS.items() if marker in lower),
                None,
            )
            if matched is not None:
                current = matched
                sections.setdefault(current, [])
                continue
        if current is not None and line:
            sections[current].append(lower)
    return {tab: "\n".join(lines) for tab, lines in sections.items()}


def _doc_keys_found(doc_text: str, doc_keys: list[str]) -> bool:
    return all(key.lower() in doc_text for key in doc_keys)


def _build_parameter(
    entry: dict[str, object],
    doc_text: str | None,
    doc_path: str,
) -> KbParameter:
    """Build a KbParameter from a SEED_SPEC/GAP_SPEC entry.

    Seed entries whose ``doc_keys`` are not confirmed in the doc are
    downgraded to ``needs_review``; GAP_SPEC entries are always
    ``needs_review``. Nothing is invented: absent doc evidence only ever
    lowers the status.
    """
    doc_keys = [str(k) for k in (entry.get("doc_keys") or [])]
    documented = doc_text is not None and _doc_keys_found(doc_text, doc_keys)
    # Explicit status (GAP_SPEC entries) wins; otherwise derive from evidence.
    status = str(entry["status"]) if "status" in entry else (
        "seeded" if documented else "needs_review"
    )

    fields = {k: v for k, v in entry.items() if k != "doc_keys"}
    fields["status"] = status
    if doc_text is not None:
        fields["evidence_ref"] = f"{doc_path}#{fields['tab']}"
    return KbParameter.model_validate(fields)


# ── Public API ────────────────────────────────────────────────────────────────


def seed_from_doc(
    store: KbStore,
    doc_path: str | Path = DEFAULT_DOC_PATH,
    sqx_version: str | None = None,
) -> SeedResult:
    """Seed the KB from ``doc_dev/SQX Builder Config.md`` (REQ-203).

    Writes one YAML per curated documented parameter (status ``seeded``,
    evidence_ref to the doc) plus explicit doc-gap entries (status
    ``needs_review``). Missing or unreadable doc → empty result (nothing is
    invented without a source). ``sqx_version`` optionally overrides the
    target version bucket for every entry.
    """
    doc = Path(doc_path)
    if not doc.is_file():
        return SeedResult()

    sections = parse_doc(doc)
    parameters: list[KbParameter] = []
    for entry in SEED_SPEC:
        tab = str(entry["tab"])
        parameters.append(_build_parameter(entry, sections.get(tab), str(doc)))
    for entry in GAP_SPEC:
        tab = str(entry["tab"])
        parameters.append(_build_parameter(entry, sections.get(tab), str(doc)))

    store.seed(parameters, sqx_version=sqx_version)
    return SeedResult(
        total=len(parameters),
        seeded=sum(1 for p in parameters if p.status == "seeded"),
        needs_review=sum(1 for p in parameters if p.status == "needs_review"),
        parameters=parameters,
    )


def iter_seed_entries() -> Iterable[dict[str, object]]:
    """Yield every curated seed and gap entry (for inspection/tests)."""
    yield from SEED_SPEC
    yield from GAP_SPEC
