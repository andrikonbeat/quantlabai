# Design: Research Real Analysis Frame

## Technical Approach

Add a perception-layer stage between `StatisticsStage` and `ReviewStage` that enriches pipeline context with live market context. It normalizes OHLCV bars, computes contextual technical zones via a thin `ta` wrapper, classifies market regime with 3-bar smoothing, scores sentiment from news, and aggregates everything into a serializable Pydantic `Frame`. No entry/exit signals are produced. Frame serialization primes SDD 5 guardian-orchestrator consumption without coupling.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Custom indicators vs `ta` wrapper | Maintenance burden vs version drift | Thin `ta` wrapper; pin `ta>=0.11.0` |
| Fail-fast vs graceful degradation | Safety vs pipeline continuity | Degrade gracefully; always emit Frame |
| Rule-based vs LLM sentiment | Cost/determinism vs accuracy | Rule-based first; LLM deferred |
| dataclasses vs Pydantic v2 for Frame | Lightweight vs validation/serialization | Pydantic v2 (project standard) |
| ABC in `agent_stages.py` only vs split file | Simplicity vs file size | Follow existing DeployStage pattern: ABC in `agent_stages.py`, concrete in `market_analysis_stage.py` |

## Data Flow

    Yahoo/Dukascopy OHLCV
            │
            ▼
    MarketDataProvider ──→ list[Bar]
            │
            ▼
    IndicatorEngine ──→ list[IndicatorResult]  (zones only)
            │
            ▼
    RegimeClassifier ──→ RegimeResult(regime, confidence, triggers)
            │
            ▼
    SentimentScorer ──→ SentimentResult(score, rationale, source_count)
            │
            ▼
    Frame aggregator ──→ Frame
            │
            ▼
    MarketAnalysisStage ──→ ctx.artifacts["market_analysis"] + ctx.artifacts["frame"]
            │
            ▼
    ReviewStage (existing) + Future Guardian (SDD 5)

**Error boundaries**: Any component failure degrades to empty/default result. Stage never blocks pipeline; writes partial Frame with `data_quality: degraded`.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/data/market/__init__.py` | Create | Package init |
| `sdk/quantlab/data/market/models.py` | Create | `Bar` (timestamp, OHLCV) + `MarketDataConfig` |
| `sdk/quantlab/data/market/providers.py` | Create | `MarketDataProvider` normalizing Yahoo/Dukascopy into `list[Bar]` |
| `sdk/quantlab/analysis/__init__.py` | Create | Package init |
| `sdk/quantlab/analysis/indicators.py` | Create | `IndicatorEngine` (ta wrapper) + `IndicatorResult` |
| `sdk/quantlab/analysis/regime.py` | Create | `RegimeClassifier` with 3-bar persistence smoothing |
| `sdk/quantlab/analysis/sentiment.py` | Create | `SentimentScorer` rule-based on `NewsItem` |
| `sdk/quantlab/analysis/frame.py` | Create | `Frame` Pydantic model + JSON/YAML serialization |
| `sdk/quantlab/pipeline/stages/agent_stages.py` | Modify | Add `MarketAnalysisStage` ABC |
| `sdk/quantlab/pipeline/stages/market_analysis_stage.py` | Create | Concrete `MarketAnalysisStage` |
| `sdk/quantlab/agents/analysis_agent.py` | Modify | EXTEND to optionally consume Frame (additive) |
| `sdk/quantlab/pipeline/registry.py` | Modify | Register `market_analysis` stage |
| `sdk/pyproject.toml` | Modify | Add `ta>=0.11.0` dependency |

## Interfaces / Contracts

```python
# sdk/quantlab/data/market/models.py
@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

class MarketDataConfig:
    source: Literal["yahoo", "dukascopy"]
    symbol: str
    timeframe: str
    start: datetime | None
    end: datetime | None

# sdk/quantlab/analysis/indicators.py
class IndicatorResult(TypedDict):
    indicator_name: str
    value: float
    zone: Literal[
        "overbought", "oversold", "neutral",
        "high", "normal", "low",
        "trending", "range",
        "insufficient_data",
    ]
    metadata: dict[str, Any]

class IndicatorEngine:
    def __init__(self, min_ta_version: str = "0.11.0") -> None: ...
    def compute(self, bars: list[Bar], indicators: list[str]) -> list[IndicatorResult]: ...

# sdk/quantlab/analysis/regime.py
@dataclass(frozen=True)
class RegimeResult:
    regime: Literal["trending", "range-bound", "volatile", "quiet", "unknown"]
    confidence: float
    triggers: list[str]

class RegimeClassifier:
    def classify(self, bars: list[Bar], lookback: int = 20) -> RegimeResult: ...

# sdk/quantlab/analysis/sentiment.py
@dataclass(frozen=True)
class SentimentResult:
    score: float
    rationale: str
    source_count: int

class SentimentScorer:
    def score(self, news: list[NewsItem]) -> SentimentResult: ...

# sdk/quantlab/analysis/frame.py
class Frame(BaseModel):
    schema_version: str = "1.0"
    regime: str | None = None
    regime_confidence: float | None = None
    sentiment: float | None = None
    technical_context: list[IndicatorResult] | None = None
    risk: dict[str, Any] | None = None
    capital: dict[str, Any] | None = None
    timeframe: str | None = None
    edge: str | None = None
    instruments: list[str] | None = None
    guardian_hints: dict[str, Any] | None = None
    data_quality: str = "full"

    def to_json(self) -> str: ...
    @classmethod
    def from_json(cls, raw: str) -> Frame: ...
```

## Pipeline Integration

- **Placement**: `StatisticsStage` → `MarketAnalysisStage` → `ReviewStage`
- **Requires**: `export_paths` (from StatisticsStage), `market_context` (from ResearchConfig via `ctx.config`)
- **Provides**: `market_analysis` (dict), `frame` (JSON string + dict)
- **Failure mode**: Missing `market_data` or `market_context` raises `ValueError` with descriptive message (REQ-306). Missing indicators/sentiment degrade to partial Frame.
- **Downstream**: ReviewStage receives existing inputs plus optional `market_analysis`/`frame`. AnalysisAgent extended to read Frame if present.

## SDD 5 Priming

Frame serializes to JSON with `schema_version="1.0"`. `guardian_hints` structure:

```json
{
  "regime_shift": {"detected": true, "confidence": 0.8, "recommended_action": "reduce_exposure"},
  "sentiment_shift": {"detected": false, "confidence": 0.0, "recommended_action": null},
  "volatility_expansion": {"detected": true, "confidence": 0.9, "recommended_action": " tighten_stops"}
}
```

SDD 5 guardian-orchestrator consumes Frame read-only. This change owns Frame schema; SDD 5 only consumes.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | IndicatorEngine zone mapping | Known OHLCV series → expected zones; mock `ta` version |
| Unit | RegimeClassifier smoothing | Synthetic trending/range/volatile series; 3-bar persistence |
| Unit | SentimentScorer rules | Bullish/bearish/neutral `NewsItem` lists |
| Unit | Frame round-trip | JSON/YAML serialize/deserialize; schema_version immutability |
| Integration | MarketAnalysisStage | Pipeline with synthetic data; verify artifact I/O and graceful degradation |
| Contract | ta version pinning | Init fails below minimum version |
| Contract | Frame schema versioning | Reject mismatched `schema_version` on load |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required. Frame is additive. Removing it does not affect existing pipeline outputs. AnalysisAgent/ReviewerAgent remain untouched unless they opt in to read Frame.

## Open Questions

- [ ] Confirm `ta` minimum version with security review (`ta>=0.11.0`).
- [ ] Verify Dukascopy provider interface for OHLCV normalization (reuse `DataManager` or new adapter).
- [ ] Confirm `market_context` artifact key name and structure from ResearchStage.
