# Design: Hypothesis Builder

## Technical Approach

Dual-mode dispatch via Strategy pattern. LLM mode (primary) builds prompts from `llm_rationale` + `source_urls` + `data_sources`, calls the LLM provider, parses structured JSON into `BuildingBlock`/`Strategy`. Rule mode (fallback) maps `description` + `parameters` deterministically via keyword table (RB-4). Unifies output through a shared validator (RB-5). `HypothesisBuilderStage` wraps the builder as a pipeline stage inserted between research and builder.

## Architecture Decisions

| Decision | Options | Tradeoff | Choice |
|----------|---------|----------|--------|
| Mode dispatch | Strategy pattern vs if/elif | Strategy isolates each mode, simplifies testing and adding new modes | Strategy pattern |
| Fallback chain | Embed in builder vs raise-and-retry | Embed keeps sync simpler, raise has clearer error path | Embed: log warning, fallback to Rule (RB-6) |
| Stage placement | New stage vs modify BuilderStage | New stage leaves BuilderStage unchanged, follows existing `agent_stages.py` pattern | `HypothesisBuilderStage` |
| Registration | Inner class in registry.py (existing pattern) vs standalone | Existing pattern keeps consistency; one more inner wrapper | Inner class per `LLMResearchAgentStage` pattern |
| LLM reuse | Wrap `LLMResearchAgent.call_llm()` vs own provider | Reuse avoids duplicate provider code; own provider is more flexible | Reuse `call_llm()` with `LLMConfig` injection |

## Data Flow

```
ResearchStage ──→ HypothesisBuilderStage ──→ BuilderStage
    │                                            │
    └── hypotheses ──→ [LLM|Rule] ──→ building_blocks ──→ research_config.*
                     └── strategies ──→ (merged into config.blocks+strategies)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/hypothesis_builder.py` | Create | `HypothesisBuilder`, `LLMMode`, `RuleMode`, output validator |
| `sdk/quantlab/pipeline/stages/agent_stages.py` | Modify | Add `HypothesisBuilderStage` ABC |
| `sdk/quantlab/pipeline/registry.py` | Modify | Register `"hypothesis_builder"` + inner wrapper class |
| `sdk/quantlab/agents/research_director.py` | Modify | Insert stage in `build_pipeline()` after research |
| `sdk/quantlab/agents/builder_agent.py` | Modify | Insert stage in `generate_pipeline_config()` after research |

## Interfaces / Contracts

```python
# Core dispatcher
class HypothesisBuilder:
    def __init__(self, mode: Literal["llm", "rule"] = "rule",
                 llm_config: LLMConfig | None = None) -> None: ...
    async def build(self, hypotheses: list[HypothesisConfig],
                    market_context: dict[str, Any] | None = None
                    ) -> tuple[list[BuildingBlock], list[Strategy]]:
        # LLM → parse → validate → OK? return. Fail? log → Rule → return.

# LLM mode — builds prompt, calls LLM, parses JSON
class LLMMode:
    def __init__(self, llm_config: LLMConfig) -> None: ...
    async def build(self, hyp: HypothesisConfig) -> tuple[list[BuildingBlock], list[Strategy]]: ...
    def _build_prompt(self, hyp: HypothesisConfig) -> str: ...
    def _parse_response(self, text: str) -> tuple[list[BuildingBlock], list[Strategy]]: ...

# Rule mode — keyword-driven deterministic mapping
class RuleMode:
    _KEYWORD_MAP: dict[re.Pattern, list[BuildingBlock]] = { ... }  # RB-4 table
    def build(self, hyp: HypothesisConfig) -> tuple[list[BuildingBlock], list[Strategy]]: ...
    def _infer_direction(self, hyp: HypothesisConfig) -> StrategyDirection: ...

# Stage contract
class HypothesisBuilderStage(Stage, ABC):
    name = "hypothesis_builder"
    requires = ["research_config", "hypotheses", "objectives"]
    provides = ["building_blocks", "strategies"]
```

**Output validation** (RB-5): `_validate_blocks(blocks, strategies)` checks unique non-empty names, known indicator names, required param keys, non-empty condition strings, and cross-references from strategies to blocks.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | RuleMode keyword mapping (RB-4 rows) | Parametrize each keyword → expected `BuildingBlock` set |
| Unit | LLMMode prompt construction & JSON parse | Mock LLM, verify parse → `BuildingBlock`/`Strategy` |
| Unit | Output validation (RB-5) | Invalid indicator, missing params, duplicate, dangling refs |
| Unit | Fallback chain (RB-6) | Mock LLM throws → Rule returns valid |
| Unit | Stage registry | `StageRegistry.get_stage_class("hypothesis_builder")` returns class |
| Integration | Pipeline insertion | `build_pipeline()` order is `research → hypothesis_builder → builder` |
| Integration | Context contract | Stage reads hypotheses from ctx, writes building_blocks+strategies |
| Integration | Rule mode S-4 to S-6 | Full round-trip: hypothesis → blocks → validate |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

PR 1: `RuleMode` engine + tests (rule only, no LLM deps). PR 2: `LLMMode` + `HypothesisBuilder` orchestrator + tests. PR 3: stage wiring + pipeline integration + integration tests. No data migration, no feature flags.

## Open Questions

- [ ] Rule mode condition strings: emit ready-to-use strings per RB-4 or leave empty for BuilderAgent?
- [ ] `LLMMode` JSON schema — should we use Pydantic's `model_json_schema()` for the prompt or a hand-crafted template (existing `LLMResearchAgent` uses hand-crafted)?
