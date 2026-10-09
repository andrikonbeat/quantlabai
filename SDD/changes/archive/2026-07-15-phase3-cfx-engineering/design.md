# Design: Phase 3 — CFX Engineering & Builder Control

## Technical Approach

Bottom-up: Pydantic v2 models mirroring CFX XML 1:1 → CfxReader/CfxWriter for ZIP/XML round-trips → CfxPatcher for LLM-friendly instruction sequences → 8 domain methods for typed mutation. Replaces current translator's XML-string construction with model composition.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Single `models.py` vs `models/` | Single file OK for ~20 models; package if >40 | **Single `models.py`** |
| Etree vs lxml | lxml has better XPath; etree is stdlib | **etree (stdlib)** — zero deps |
| Patcher mutation semantics | In-place simpler; immutable prevents drift | **Internal ref, validate-all then mutate, return `self`** — caller's ref unchanged |
| Unknown section handling | Passthrough may produce invalid output if upstream model changes | **Raw XML passthrough** — limitation accepted |
| CFX type detection | ZIP contents + root element | **Single XML `<Task>` → Config; Multi `<Project>` → Project** |
| XML field mapping | Direct attrib mapping vs explicit transform | **`element.attrib` → Pydantic field by key name** |

## Data Flow

```
DSL Model ──→ CfxPatcher ──→ CfxArchive ──→ CfxWriter ──→ .cfx ZIP
                                              ↑
                                     CfxReader ─── Real .cfx

.cfx ZIP ──→ CommandDispatcher.load_config() ──→ sqcli -project action=loadconfig
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/cfx/__init__.py` | Create | Package exports |
| `sdk/quantlab/cfx/models.py` | Create | Pydantic v2 models — CfxArchive, BuildTask, CfxConfig, CfxProject, Section types, PatchInstruction union |
| `sdk/quantlab/cfx/errors.py` | Create | CfxNotFoundError, CfxCorruptError, CfxParseError, VersionError |
| `sdk/quantlab/cfx/reader.py` | Create | CfxReader — open CFX ZIP → typed CfxArchive; version gate, ZIP traversal defense |
| `sdk/quantlab/cfx/writer.py` | Create | CfxWriter — typed CfxArchive → ZIP, ZIP_DEFLATED + ZIP_UTF-8 for non-ASCII names |
| `sdk/quantlab/cfx/patcher.py` | Create | CfxPatcher — validate-then-apply instruction sequences |
| `sdk/quantlab/cfx/dom.py` | Create | 8 domain methods per spec |
| `sdk/quantlab/translate/cfx.py` | Modify | Rewrite CfxArchive.from_model() to use cfx-editor models |
| `sdk/quantlab/translate/translator.py` | Modify | Rewrite generate_cfx_xml() via CfxPatcher + CfxWriter |
| `tests/cfx/` | Create | Package + fixture-based test suite |

## Interfaces / Contracts

### CfxConfig and CfxProject

```python
class CfxConfig(BaseModel):
    """Single-file config: <Task> root, one BuildTask."""
    task: BuildTask
    schema_version: str

class CfxProject(BaseModel):
    """Multi-file project: <Project> root, task routing."""
    config: ProjectConfig
    tasks: dict[str, BuildTask]        # "Build-Task1.xml" → model
    schema_version: str

class CfxArchive(BaseModel):
    config: CfxConfig | CfxProject
    task_files: dict[str, BuildTask]   # flattened lookup
```

### Section Types

```python
class SettingsSection(BaseModel):
    """Simple key-value section (Options, Data, Rankings, etc.)."""
    name: str
    settings: dict[str, str]           # element.attrib → field mapping

class RawXmlSection(BaseModel):
    """Byte-for-byte passthrough for unrecognized sections."""
    name: str
    raw_xml: str

# Complex sections (Blocks, ATMs, Resources, DataBanks) get specific typed models.
class BuildTask(BaseModel):
    options, what_to_build, risk_money_mgmt, data: SettingsSection | None
    rankings, parts_to_improve, cross_checks, notes: SettingsSection | None
    blocks: BlockConfig | None         # typed model
    atms: AtmConfig | None
    databanks: DataBankConfig | None
    resources: ResourceConfig | None
    unknown_sections: list[RawXmlSection]
```

### CfxReader

```python
class CfxReader:
    @staticmethod def read(path: Path) -> CfxArchive:
        # 1. ZIP traversal defense: reject entries with '..' or absolute paths
        # 2. CFX type detection:
        #    - Single XML in ZIP + <Task> root → CfxConfig
        #    - Multiple files + <Project> root → CfxProject
        # 3. Version gate before full parse
```

### CfxPatcher — Mutation Semantics

```python
class CfxPatcher:
    def __init__(self, archive: CfxArchive) -> None:
        # Holds internal reference (same object, not a copy)
    def apply(self, instructions: list[PatchInstruction]) -> Self:
        # Validates ALL instructions first → raises on first invalidity
        # Only then mutates the held archive in place
        # Returns self for chaining
        # Caller's original reference points to the same mutated object
```

### PatchInstruction Types

```python
class SetMarketInstruction(BaseModel):
    symbol: str

class AddTimeframeInstruction(BaseModel):
    timeframe: str

class EnableBlockInstruction(BaseModel):
    block_key: str
    weight: int = 100

class DisableBlockInstruction(BaseModel):
    block_key: str

class SetGeneticInstruction(BaseModel):
    enabled: bool
    generations: int
    population: int

class SetDateRangeInstruction(BaseModel):
    start: str
    end: str

class AddRankingConditionInstruction(BaseModel):
    metric: str
    operator: str
    value: float

class EnableCrosscheckInstruction(BaseModel):
    wf_enabled: bool
    mc_enabled: bool
    wf_cycles: int = 50

PatchInstruction = Union[
    SetMarketInstruction, AddTimeframeInstruction,
    EnableBlockInstruction, DisableBlockInstruction,
    SetGeneticInstruction, SetDateRangeInstruction,
    AddRankingConditionInstruction, EnableCrosscheckInstruction,
]
```

### Domain Methods (8, per spec)

```python
# CfxPatcher exposes these convenience wrappers over apply():
# set_market(), add_timeframe(), enable_block(), disable_block(),
# set_genetic(), set_date_range(), add_ranking_condition(), enable_crosscheck()
# Each translates to its PatchInstruction and calls apply().
```

### Date Format Mapping

| Section Domain | Format | Type |
|----------------|--------|------|
| Data, Setups | `YYYY.MM.DD` | string attribute |
| Resources, Symbols, Sessions | Epoch milliseconds | integer |

The domain method reads the section type from context and applies the correct format.

### Validation Boundary

| Layer | Validates |
|-------|-----------|
| Translator | DSL field presence (market, timeframe, strategies) |
| CfxPatcher | Instruction semantics (valid block_key, type safety, cross-field rules) |
| CfxReader | File integrity, schema version, ZIP structure, no traversal |

Translator delegates model-level validation to CfxPatcher/CfxReader — no duplicate validation logic.

### Errors

```python
class CfxNotFoundError(QuantLabError): ...   # File missing
class CfxCorruptError(QuantLabError): ...     # Invalid ZIP/XML
class CfxParseError(QuantLabError): ...       # Schema violation
class VersionError(QuantLabError): ...         # Unsupported schema version
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Models (serialization, defaults, constraints) | Pydantic construct + dump round-trips |
| Unit | Reader (version gate, sections, traversal defense, type detection) | Fixture CFX files + synthetic XML |
| Unit | Writer (UTF-8 no-decl, ZIP structure, ZIP_UTF-8 flag, dry-run JSON) | Bytes comparison |
| Integration | Round-trip (read → modify → write → re-read identical) | Assert unchanged sections via model diff |
| Integration | Patcher (valid sequence applied, invalid rolls back) | Assert NO model changes on validation failure |
| Integration | Domain methods (all 8, date format per section type) | Assert model fields after each method |
| E2E | CLI load → Builder (`sqcli loadconfig` succeeds without error) | Manual with sqcli |

## Migration / Rollout

No data migration required. New `quantlab.cfx/` is fully additive — zero disruption until orchestrator switches.

## Open Questions

- [ ] Version range: confirm from real .cfx files before implementation (assume SQX v144.2953 → 140–145)
- [ ] Non-ASCII task names in ZIP filenames — verify ZIP_UTF-8 flag covers encoding edge cases with Python's zipfile
