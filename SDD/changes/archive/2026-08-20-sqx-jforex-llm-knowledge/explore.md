# Exploration: SQX + JForex 4 official knowledge for LLM agents

**Status**: success
**Date**: 2026-08-19
**Project**: quantlabai
**Change**: sqx-jforex-llm-knowledge
**Artifact store**: hybrid (OpenSpec filesystem + Engram)

---

## Executive Summary

QuantLab's LLM agents today know SQX only through (a) per-parameter YAML (82
entries, 74 verified / 8 `needs_review`), (b) hardcoded indicator ranges injected
into `LLMResearchAgent.build_prompt`, and (c) a KB teaching table injected into
campaign prompts. There is ZERO official-documentation knowledge: `knowledge/raw/`
is empty, `knowledge/embeddings/` and `knowledge/datasets/` are empty stubs, and
there is no RAG pipeline (only token/3-gram cosine fallback; no
`sentence-transformers`). Critically, a huge official source already sits on disk:
the SQX install (`assets/SQX_144_2953_linux_20260601/`) contains
`internal/autocomplete/docs.json` (2,533 StrategyQuant API reference entries),
`Extending_SQX.pdf`, 605 JForex export templates, and 931 Java block snippets.
JForex 4 has public official docs (Dukascopy wiki, Javadoc, SDK/Maven) but nothing
local. Recommended direction: a **hybrid ingestion pipeline** — extract the
on-disk official sources (API ref, block snippets, templates) + crawl the public
wikis into version-pinned Markdown under `knowledge/raw/` (gitignored), convert to
`knowledge/structured/`, add a semantic docs query to the Knowledge store, and
inject curated cheat-sheets (ABL→JForex API, block→snippet mappings) into agent
prompts. Full manuals are license/account-gated — do not redistribute; keep raw
content repo-local.

---

## Current State

### 1. How `knowledge/` is populated today

| Area | State |
|------|-------|
| `knowledge/raw/` | **Empty** (`.gitkeep` only). Gitignored (`knowledge/raw/*`), designed for raw external material. |
| `knowledge/structured/sqx-kb/144.2953/parameters/` | 82 parameter YAML files across 8 tabs (What to build, Genetic options, Data, Trading options, Building blocks, Money management, Cross checks, Ranking). Each has `type/range/enum/description/what_it_does/how_it_works_in_sqx/status/evidence_ref`. |
| `knowledge/structured/sqx-kb/144.2953/educational/` | `educational-dataset.yaml` (82 records; 74 verified, 8 `needs_review`) + `educational-table.md` teaching table. Doc gaps are explicitly marked "Not documented — no invented content". |
| `knowledge/embeddings/`, `datasets/`, `graph/` | **Empty stubs**. No RAG, no dataset cache, no graph. |
| `knowledge/index.yaml` | Indexes `kb_parameters` (82), `agent_memory`, `version_events`, `campaigns`. `directories: {}` — no campaign directories indexed. |

The KB is seeded by `sdk/quantlab/knowledge/kb/seeder.py` (REQ-203) from
`docs/sqx-builder-config/SQX Builder Config.md` (a **Spanish, hand-curated**
builder-config guide, 293 lines) with `SEED_SPEC` doc-key verification and
`evidence_ref` pointing at the real `project.cfx`. The seeder NEVER invents
semantics — gaps become `needs_review`. `educational.py` builds the educational
dataset/table from the KB.

### 2. What `query.py` / `context.py` retrieve today

- `query.py` (`QueryBuilder`): campaign metrics/фильтры, tags, agent-memory
  full-text search (`search_agent_memory`), and `search_similar_campaigns`
  (token + char-3-gram **cosine only** — "embedding-based path may be added
  later when sentence-transformers is available"). **No docs query.**
- `context.py`: composes the "Prior Context" block from `agent-memory/*/*/memory.yaml`
  + `find_similar_campaigns` ranking, injected into phase envelopes. **No
  official-docs context.**
- `store.py` (`KnowledgeStore`): read/write/delete, index rebuild, `cache_dataset`,
  `save_pipeline_run`, `find_similar_campaigns`, KB parameter index. 54.9K.

### 3. How agents consume SQX/JForex knowledge today

| Agent | Mechanism | Coverage |
|-------|-----------|----------|
| `llm_research_agent.py` | `SQXDocProvider` (instantiated but ranges are **hardcoded** in `build_prompt` F2 block: RSI [2,200], BB [2,200]/[0.1,5.0], EMA/SMA [2,500], ATR [2,200], MACD [2,200]) + Dukascopy zone labels (`_market_context`) | Parameter bounds only |
| `hypothesis_builder/rule.py`, `parameter_validator.py` | `SQXDocProvider` range/enum validation | Parameter bounds only |
| `builder_agent.py` | `KbStore.consult` per tab; `strict_kb` warnings; `generate_parameter_matrix` | KB tab coverage |
| `config_reviewer.py` | teaching table (KB-derived) | KB guidance |
| `deployment_agent.py` | JForex packaging (JAR/WAR), JCloud config — **no official API knowledge** | Ops only |
| `research_director.py` | `compose_prior_context` injection | Prior campaigns only |
| `prompts.py` | Only 4 templates: fundamental/technical/macro/news | **No SQX/JForex template** |

Gap: **"parameter YAML" ≠ "full official knowledge"**. Nothing in the system
knows: what a block *is*, what the StrategyQuant API offers, how block semantics
translate to JForex Java, what JForex API interfaces exist, platform behaviors,
cross-check semantics, etc. `config_reviewer.py` has zero KB/SQX references.

### 4. What official documentation exists and what is local

**SQX — already on disk (assets/SQX_144_2953_linux_20260601, symlinked, NOT git-tracked):**

| Source | Size/Count | Content |
|--------|-----------|---------|
| `internal/autocomplete/docs.json` | 488.7K / **2,533 entries** | Full StrategyQuant tradinglib API reference (Javadoc-style descriptions: StrategyBase, indicators, backtest, results stats, dukascopy job, GP engine...) |
| `Extending_SQX.pdf` (+ `_es.pdf`) | 116.8K | Official "Extending StrategyQuant" manual (C#/Java plugin development, block API) |
| `SQ_License_and_Service_Terms.pdf` | — | License terms (redistribution constraints) |
| `internal/extend/Code/JForex/` | **605 files** | Official SQX→JForex Java export templates (Main.tpl, Blocks.inc, SQIndicators.java, ExitMethods/*, MoneyManagement/*) — the literal codegen for `.java` export |
| `internal/extend/Snippets/SQ/Blocks/` | **931 files** | Java implementation of every block (52 indicator families incl. CCI, RSI, MACD, BollingerBands...; signals: BarAndTime, CandlePatterns, Comparisons, Price, Order...) |
| `internal/extend/Code/PseudoCode/`, `global/`, `EasyLanguage/`, `MT4/MT5/` | — | Other export targets |
| `internal/langs/` | — | Localization files (English.csv etc.) |
| `internal/plugins/` | App* dirs | AppHelp, AppStrategyQuant, ResultsSourceCode, PortfolioMaster/Composer, Retester... |

**SQX — online:**
- `https://strategyquant.com/doc/` — **public** wiki: introduction, installation,
  program layout, cross-checks, tutorials, changelog articles.
- `https://www.strategyquant.com/manuals/` — User Manual — **license-gated**
  (noted in `docs/multi-agent/deployment.md`).
- Official changelog (referenced by the docs; needed for continuous sync).

**JForex 4 — local: NONE.** No jforex content in `knowledge/`, no JForex 4
install known (prior discovery #1011: manual download; Dukascopy offers demo
accounts, official MCP at ai.dukascopy.com, JForex API/FIX API Java, JCloud).

**JForex 4 — online (all public except the user manual):**
- `https://www.dukascopy.com/wiki/en/development/...` — **public** wiki: Strategy
  API (introduction, simple strategy, strategy tutorial, SDK client, feeds...).
- `https://www.dukascopy.com/client/javadoc3/` — **public** Javadoc (JForex API
  2.13.99: IStrategy, IContext, IEngine, IHistory, IIndicators...).
- JForex SDK (Maven public repo) with examples; `@Configurable`/`@JFXInject`
  patterns; `IStrategy` lifecycle (onStart/onTick/onBar/onMessage/onAccount/onStop).
- `https://www.dukascopy.com/support/manuals/` — JForex User Manual —
  **account-gated** (noted in `docs/multi-agent/deployment.md`).

### 5. Existing related changes

- `web-research-for-llm-agent` (archived): wired `WebSearchProvider` +
  `RSSNewsProvider` into `LLMResearchAgent.fetch_data()` — web knowledge is
  **market news only**, never tool documentation.
- `research-agent-enhancements` / `research-agent-improvements`: built
  `SQXDocProvider`, `ParameterValidator`, `SemanticSimilarityQuery` idea, KB
  feedback; "Knowledge Lake as real knowledge base" intent — realized only as
  parameter validation, not documentation.
- `jforex4-integration` (archived): JForex deploy/monitor pipeline (reads local
  filesystem state; `JForexStrategyBridge` compiles via HTTP API). No official
  API knowledge layer.
- `phase4-jforex-portfolio-optimizer`: exploration documents SQX HTTP API
  endpoints (`sourcecode/print` for JForex `.java` export, PortfolioComposer
  endpoints) — valuable operational knowledge already captured in a change, not
  in the knowledge lake.

---

## Affected Areas

| Area | Why |
|------|-----|
| `knowledge/raw/` | New home for crawled/extracted official docs (gitignored, repo-local). |
| `knowledge/structured/` | New `docs/` (or `sqx-kb/{ver}/docs/` + `jforex-kb/`) normalized Markdown + version-pinned metadata. |
| `sdk/quantlab/knowledge/kb/` | Extend seeding: block/indicator/signals knowledge from `docs.json` + snippets; `educational.py` could ingest Extending_SQX. |
| `sdk/quantlab/knowledge/query.py` | New doc-retrieval surface (semantic/token search over official docs). |
| `sdk/quantlab/knowledge/store.py` | Index new `docs/` directory; `cache_dataset` for doc corpus; index `directories`. |
| `sdk/quantlab/knowledge/sqX_doc_provider.py` | Currently parameters-only; could grow a general doc lookup (blocks, API). |
| `sdk/quantlab/agents/llm_research_agent.py` | Replace hardcoded F2 ranges with KB-driven docs; add official-docs context section. |
| `sdk/quantlab/agents/builder_agent.py`, `config_reviewer.py`, `hypothesis_builder/`, `deployment_agent.py` | Consume official docs (block semantics, ABL→JForex mappings, JForex API). |
| `sdk/quantlab/agents/prompts.py` | New prompt template(s) for official-tool knowledge. |
| `sdk/quantlab/jforex/`, `sdk/quantlab/compiler/jfx.py` | Ground truth for JForex API usage (IStrategy lifecycle, @Configurable, submitOrder). |
| `sdk/quantlab/sqx/` (cli_wrapper, blocks_bridge) | Block validation can reference snippet ground truth. |
| `docs/` | Optionally document the ingestion pipeline + legal boundaries (runbook). |
| `.gitignore` | Confirm `knowledge/raw/*` stays ignored; do NOT commit licensed material. |

---

## Approaches

### A. Structured ingestion pipeline (extract + normalize)

Crawl/extract official sources → normalize to Markdown → store raw under
`knowledge/raw/{sqx|jforex}/{ver}/` and normalized under `knowledge/structured/`
with provenance + version pinning.

- Sources: SQX install (`docs.json`→Markdown, `Extending_SQX.pdf`→text,
  JForex templates, snippets), public wikis (strategyquant.com/doc,
  dukascopy.com/wiki), Javadoc.
- Legal: public wiki = crawlable; manuals/gated = local-personal-use only
  (extract from the licensed install, never distribute).
- Pros: durable offline corpus; version-pinned to SQX 144.2953; reuses existing
  `knowledge/` layout; seeder/validation patterns already exist.
- Cons: ingestion tooling is new (no crawler exists; only
  `WebSearchProvider`/DuckDuckGo); effort in normalization; PDF extraction
  quality varies.
- Effort: **High** (but foundational — everything else depends on it).

### B. RAG / embeddings over the docs

Extend `query.py` + `embeddings/` so agents semantic-search official docs.

- Pros: natural-language Q&A over docs ("how does SQX handle ATR stops?"); the
  store already has `find_similar_campaigns` plumbing and `embeddings/` dir.
- Cons: `sentence-transformers` is NOT a dependency (token/3-gram cosine is the
  current fallback — weak for docs); adds model download + storage; embedding
  cache invalidation on version updates.
- Effort: **Medium** (depends on A; standalone embedding step).

### C. Agent context provider (curated injection)

Curated official-knowledge reference blocks injected into prompts / MCP
resource (cheat-sheets: block→Java snippet, IStrategy lifecycle, @Configurable,
SQX HTTP API endpoints, indicator families).

- Pros: instant agent impact; no new retrieval infra; small, reviewable.
- Cons: static (doesn't scale to full docs); token cost per prompt; curation
  effort; hardcoded ranges in `llm_research_agent.py` show this pattern's limits.
- Effort: **Low-Medium**.

### D. Hybrid (RECOMMENDED): structured YAML params + RAG docs + curated cheat-sheets

A: ingest + normalize → B: semantic docs query → C: curated cheat-sheets
(ABL→Python/JForex mappings, API references) injected where high-value.

- Pros: grounded params (existing KB) + broad docs (RAG) + sharp references
  (cheat-sheets); each layer cheap to maintain; the 2,533-entry `docs.json` and
  931 snippets make block/API knowledge *free* to extract from the licensed
  install.
- Cons: largest scope; needs phased delivery (cheat-sheets first, ingestion
  second, RAG third).
- Effort: **High** total, phased.

### E. Continuous sync (updater for new SQX/JForex versions)

Watch official changelogs (strategyquant.com changelog, Dukascopy release notes),
detect new versions, re-run ingestion, diff KB, notify user.

- Pros: matches the seeder's own stated aspiration (SQX Builder Config.md: "sistema
  que detecte versiones nuevas... revise el changelog oficial"); prevents rot.
- Cons: changelog crawling is fragile; gated content; scope creep for v1.
- Effort: **Medium** (as a follow-up change, not v1).

### Legal / ToS notes per approach

- **Public wikis** (strategyquant.com/doc, dukascopy.com/wiki, Javadoc): public
  web content; crawling for personal/internal use is standard practice — store
  raw under gitignored `knowledge/raw/`, keep provenance/URLs.
- **SQX install artifacts** (`docs.json`, `Extending_SQX.pdf`, templates,
  snippets): part of a **licensed** installation (SQ_License_and_Service_Terms).
  Personal-use extraction is fine; **redistribution in the repo is NOT** —
  keep raw outside git, commit only derived *facts* (ranges, mappings) and
  provenance pointers.
- **Gated manuals** (SQX User Manual — license; JForex User Manual — Dukascopy
  account): do not crawl/scrape behind gates; use the public wiki/Javadoc/SDK
  instead and document the boundary.
- **Dukascopy MCP (ai.dukascopy.com)**: official AI access point — candidate
  runtime integration for live JForex knowledge, but not a docs corpus.

---

## Recommendation

**Approach D (Hybrid), delivered in phases:**

1. **Phase 1 (Low-Medium effort)**: Curated cheat-sheets + provider —
   extract block→Java-snippet mappings from `internal/extend/Snippets/SQ/Blocks/`
   and `Code/JForex/` (local, licensed, personal use); IStrategy lifecycle +
   @Configurable reference from public Javadoc; inject into agent prompts
   (`prompts.py` new templates, `llm_research_agent` F2 section, builder/config
   reviewer). Replace hardcoded F2 ranges with KB-driven values.
2. **Phase 2 (High effort)**: Ingestion pipeline — crawl public wikis + extract
   `docs.json`/`Extending_SQX.pdf` → normalized Markdown in
   `knowledge/structured/sqx-kb/{ver}/docs/` + `jforex-kb/`, raw under gitignored
   `knowledge/raw/`, version-pinned; new `DocIndexer` + index section.
3. **Phase 3 (Medium effort)**: Docs query surface — extend `query.py` with doc
   retrieval (start token/3-gram, optionally add sentence-transformers as an
   optional extra); wire into research/config-reviewer agents.
4. **Phase 4 (follow-up change)**: Continuous version sync + changelog watcher.

Rationale: the highest-value, lowest-cost knowledge (block semantics, API
reference, export templates) is **already on disk** in the licensed install —
extraction is a personal-use transformation, not redistribution. The public
wikis fill the general-docs gap legally. RAG is worth it only after the corpus
exists (Phase 3), and the existing `find_similar_campaigns` plumbing + empty
`embeddings/` dir mean the extension surface is already anticipated.

---

## Risks

| Severity | Risk | Mitigation |
|----------|------|------------|
| CRITICAL | Redistributing licensed/gated material in git (SQX install artifacts, gated manuals) → ToS/license breach | Keep raw under gitignored `knowledge/raw/*`; commit only derived facts + provenance; document legal boundary in the design |
| CRITICAL | JForex 4 User Manual is account-gated and SQX User Manual is license-gated → "full official knowledge" is unattainable in-repo | Scope to public wiki + Javadoc + SDK + licensed-install extraction; state the boundary explicitly to the user |
| WARNING | Crawling public wikis can break (structure/ToS changes, rate limits) | Version-pin corpora; store raw snapshots; re-crawl is a maintenance task, not a runtime dependency |
| WARNING | `sentence-transformers` not a dependency; embedding models add size + offline concerns | Keep token/3-gram fallback as default; embeddings as optional extra |
| WARNING | Docs growth (2,533 API entries + wiki pages + snippets) can bloat prompts if injected wholesale | Retrieval (RAG) + curated cheat-sheets only; never inject full corpora |
| WARNING | Version drift (SQX 144.2953 pinned; new versions change blocks/params) | Version-pinned dirs; continuous-sync as follow-up change |
| INFO | JForex 4 install location unknown (manual download per discovery #1011) | JForex knowledge comes from public docs/SDK; local install not required for the knowledge base |
| INFO | Docs are English-only; existing KB docs are Spanish (SQX Builder Config.md) | Bilingual surface if needed; normalized Markdown is language-neutral |

---

## Ready for Proposal

**Yes.** The orchestrator should tell the user:
- The gap is real and confirmed: zero official-docs knowledge today; parameter
  YAML + hardcoded ranges are all agents have.
- A large official corpus already exists locally (2,533-entry API ref, 931 block
  snippets, 605 JForex templates, Extending_SQX.pdf) inside the licensed SQX
  install — personal-use extraction is legal; redistribution is not.
- JForex 4 official knowledge is public (wiki, Javadoc, SDK) except the
  account-gated User Manual.
- Recommended: phased hybrid (cheat-sheets → ingestion → docs query → sync),
  propose as `sqx-jforex-llm-knowledge`.