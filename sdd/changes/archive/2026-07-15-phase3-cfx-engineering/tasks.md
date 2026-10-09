# Tasks: Phase 3 — CFX Engineering & Builder Control

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1000–1400 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Foundation + I/O → PR 2: Patcher + Domain + Translator |
| Delivery strategy | auto-forecast |
| Chain strategy | feature-branch-chain |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Foundation + I/O layer | PR 1 | Package init, models, errors, reader, writer, fixtures + reader/writer tests. Complete self-contained read/write cycle. |
| 2 | Patcher + Domain + Translator | PR 2 | CfxPatcher, 8 domain methods, translator rewrite using cfx-editor models + patcher/writer tests. Depends on PR 1. |

## Phase 1: Foundation — Package & Models

- [x] 1.1 Create `sdk/quantlab/cfx/__init__.py` with public exports
- [x] 1.2 Create `sdk/quantlab/cfx/errors.py` — CfxNotFoundError, CfxCorruptError, CfxParseError, VersionError
- [x] 1.3 Create `sdk/quantlab/cfx/models.py` — CfxArchive, BuildTask, CfxConfig, CfxProject, Section types (SettingsSection, RawXmlSection)
- [x] 1.4 Add complex section models: BlockConfig, AtmConfig, DataBankConfig, ResourceConfig
- [x] 1.5 Add PatchInstruction union — 8 typed instruction models (SetMarket, AddTimeframe, EnableBlock, DisableBlock, SetGenetic, SetDateRange, AddRankingCondition, EnableCrosscheck)

## Phase 2: Core I/O — Reader & Writer

- [x] 2.1 Create `sdk/quantlab/cfx/reader.py` — CfxReader.read() with ZIP traversal path sanitization
- [x] 2.2 Implement CFX type detection: single `<Task>` root → CfxConfig, multi-file `<Project>` root → CfxProject
- [x] 2.3 Implement schema version gate — VersionError for unsupported versions
- [x] 2.4 Create `sdk/quantlab/cfx/writer.py` — CfxWriter.write() with ZIP_DEFLATED + ZIP_UTF-8 flag
- [x] 2.5 Output UTF-8 XML without declaration, support dry-run JSON serialization

## Phase 3: Domain Logic — Patcher & Methods

- [x] 3.1 Create `sdk/quantlab/cfx/patcher.py` — CfxPatcher with validate-then-apply semantics
- [x] 3.2 Implement `validate_all()` — run all instruction validators before any mutation, raise on first invalid
- [x] 3.3 Create `sdk/quantlab/cfx/dom.py` — set_market(), add_timeframe(), enable_block(), disable_block()
- [x] 3.4 Add set_genetic(), set_date_range(), add_ranking_condition(), enable_crosscheck()
- [x] 3.5 Implement date format mapping per section domain (YYYY.MM.DD vs epoch ms)

## Phase 4: Integration — Translator Rewrite

- [x] 4.1 Rewrite `sdk/quantlab/translate/cfx.py` — CfxArchive.from_model() using cfx-editor Pydantic models
- [x] 4.2 Rewrite `sdk/quantlab/translate/translator.py` — generate_cfx_xml() via CfxPatcher + CfxWriter
- [x] 4.3 Add DSL field validation before translation (market, timeframe, strategies required)

## Phase 5: Testing

- [x] 5.1 Create `tests/cfx/__init__.py` + `tests/cfx/fixtures/` with symlinks to real .cfx files
- [x] 5.2 Write `tests/cfx/test_reader.py` — version gate, type detection, traversal defense, missing/corrupt files
- [x] 5.3 Write `tests/cfx/test_writer.py` — UTF-8 no-decl, ZIP structure, round-trip byte identity, dry-run
- [x] 5.4 Write `tests/cfx/test_patcher.py` — valid sequence applied, invalid rolled back, no partial mutation
- [x] 5.5 Write `tests/cfx/test_dom.py` — all 8 domain methods, date format per section, cross-field symbol updates
