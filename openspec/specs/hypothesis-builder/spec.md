# Hypothesis Builder Spec

## Overview

Transform qualitative ``HypothesisConfig`` instances (with LLM rationale, source URLs,
and data sources) into structured ``BuildingBlock`` and ``Strategy`` objects that the
``BuilderAgent`` can consume for CFX generation.

## Requirements

### RB-1 — Input / Output Contract

The ``HypothesisBuilder`` MUST accept a ``list[HypothesisConfig]`` plus an optional
``market_context`` dict and MUST return a tuple of ``(list[BuildingBlock], list[Strategy])``.

```python
async def build(
    self,
    hypotheses: list[HypothesisConfig],
    market_context: dict[str, Any] | None = None,
) -> tuple[list[BuildingBlock], list[Strategy]]:
    ...
```

### RB-2 — Dual Mode Operation

The builder MUST support two modes selected at construction time:

- **``"llm"``**: Uses an LLM (OpenAI/Anthropic) to generate building blocks from
  the hypothesis ``llm_rationale``, ``source_urls``, and ``data_sources``.
- **``"rule"``**: A deterministic engine that maps hypothesis ``description`` +
  ``parameters`` to known indicator configurations via keyword matching.

The mode MAY be overridden per-call via a ``mode`` parameter. Default is ``"rule"``
when no LLM config is available.

### RB-3 — LLM Mode

When mode is ``"llm"``:

1. Construct a structured prompt containing:
   - The hypothesis name, description, and expected outcome.
   - The ``llm_rationale`` text.
   - The ``source_urls`` and ``data_sources`` for context.
   - A JSON schema for the expected response (``building_blocks`` array with
     ``{name, indicator: {name, params}, entry, exit}`` and ``strategies`` array
     with ``{name, direction, building_blocks: [names]}``).
2. Call the configured LLM provider with the prompt.
3. Parse the JSON response into ``BuildingBlock`` and ``Strategy`` instances.
4. Validate the output (see RB-5).

### RB-4 — Rule Mode

When mode is ``"rule"``, the builder MUST map hypothesis text to building blocks
using an improved keyword engine. At minimum:

| Keyword / Pattern | Building Block(s) |
|------------------|-------------------|
| mean-reversion, mean reversion | RSI(14, 30, 70) + BB(20, 2) |
| breakout, break out | Donchian(20) + Volume filter |
| momentum, trend, trend-following | EMA(200) + MACD(12, 26, 9) |
| volatility, atr | ATR(14) |
| divergence | RSI(14) + MACD(12, 26, 9) |
| volume | Volume SMA(20) |
| pullback | EMA(50) + RSI(14, 30, 70) |
| support, resistance | BB(20, 2) + RSI(14) |

Each building block MUST include an ``IndicatorConfig`` with sensible defaults,
and SHOULD include ``EntryRule`` and/or ``ExitRule`` with ``conditions`` strings.

### RB-5 — Output Validation

The builder MUST validate every produced building block and strategy:

- ``BuildingBlock.name`` is non-empty and unique within the batch.
- ``BuildingBlock.indicator.name`` is a known indicator (RSI, BB, EMA, MACD, ATR,
  Donchian, Volume, etc.).
- ``BuildingBlock.indicator.params`` has the required keys for that indicator.
- ``EntryRule.conditions`` and ``ExitRule.conditions`` are syntactically valid
  condition strings (non-empty, reference known indicators).
- ``Strategy.building_blocks`` references only names that exist in the output
  building blocks list.

If LLM mode produces invalid output, it MUST fall back to Rule mode (RB-6).

### RB-6 — LLM Fallback

If LLM mode encounters any error (API timeout, parse failure, validation failure),
the builder MUST log a warning and retry in Rule mode. The caller MUST receive
a valid ``(list[BuildingBlock], list[Strategy])`` tuple regardless of mode.

## Scenarios

### S-1: LLM mode with detailed rationale
**Given** a ``HypothesisConfig`` with ``llm_rationale="Rising CPI and strong
employment suggest inflationary pressure, benefiting commodity currencies"``
and ``data_sources=["fred", "rss-news"]``
**When** ``HypothesisBuilder(mode="llm").build([hyp])`` is called
**Then** it returns a non-empty ``list[BuildingBlock]`` and ``list[Strategy]``
where each building block has an ``IndicatorConfig`` with valid params.

### S-2: No rationale → Rule mode
**Given** a ``HypothesisConfig`` with ``llm_rationale=None``
**When** ``build([hyp])`` is called (default mode)
**Then** it uses Rule mode keyword matching on the description.

### S-3: LLM produces invalid building blocks
**Given** LLM mode produced building blocks with an unknown indicator name
**When** validation fails
**Then** it falls back to Rule mode and returns valid results.

### S-4: Mean-reversion via Rule mode
**Given** hypothesis description contains ``"mean-reversion on EURUSD"``
**When** ``build([hyp], mode="rule")``
**Then** building blocks include RSI(14, 30, 70) and BB(20, 2).

### S-5: Breakout with volume
**Given** hypothesis description contains ``"breakout with volume confirmation"``
**When** ``build([hyp], mode="rule")``
**Then** building blocks include Donchian(20) and a volume indicator.

### S-6: Momentum trend-following
**Given** hypothesis description contains ``"momentum trend-following strategy"``
**When** ``build([hyp], mode="rule")``
**Then** building blocks include EMA(200) and MACD(12, 26, 9).

### S-7: Stage contract
**Given** ``HypothesisBuilderStage`` is registered in ``StageRegistry`` as
``"hypothesis_builder"``
**When** the stage is looked up by name
**Then** it returns a stage class with ``name="hypothesis_builder"``.

### S-8: Stage insertion
**Given** a pipeline config with a ``research`` or ``research_llm`` stage
**When** ``build_pipeline()`` is called
**Then** a ``hypothesis_builder`` stage is inserted between research and builder.

### S-9: Stage requires/provides
**Given** a ``HypothesisBuilderStage`` instance
**Then** its ``requires`` includes ``["research_config", "hypotheses", "objectives"]``
and its ``provides`` includes ``["building_blocks", "strategies"]``.
