# Block -> Snippet cheat-sheet (SQX)

Curated, original summary. Written from public tool knowledge; NOT a copy of
the licensed SQX User Manual. The full 931-entry snippet corpus lives in the
installed distribution (`internal/autocomplete/Snippets/SQ/Blocks/`) and is
gitignored (REQ-KDI-01); this sheet only records the mapping shape.

## Purpose

Every indicator block in StrategyQuant X maps to a Java snippet in the snippet
corpus. When an LLM agent translates an SQX block into JForex code, it MUST
consult this mapping (or `get_doc("block", "<Block>", "<version>")`) and never
invent JForex API calls.

## Common block mapping shape

| SQX block | Typical parameters | JForex counterpart |
|-----------|--------------------|--------------------|
| RSI | period, applied price | `IIndicators.rsi(price, period)` |
| Bollinger Bands | period, deviation, applied price | `IIndicators.bollingerBands(price, period, deviation, ...)` |
| EMA / SMA | period, applied price | `IIndicators.ema/sma(price, period)` |
| ATR | period | `IIndicators.atr(instrument, period, ...)` |
| MACD | fast, slow, signal | `IIndicators.macd(price, fast, slow, signal)` |

## Rules

1. Resolve the block doc first: `get_doc("block", name, version)`.
2. Use the snippet reference (`DocRef.snippet`) to locate the exact Java source
   in the version-pinned corpus.
3. Translate parameters by semantic name; do not reorder arguments blindly.
4. When a block has no snippet reference, omit the implementation and log the
   gap — never fabricate a snippet path.

## Provenance

- Source: public StrategyQuant/JForex tool knowledge, curated by the project.
- License: project-authored summary; no licensed text reproduced.
- Version: SQX `144.2953`.