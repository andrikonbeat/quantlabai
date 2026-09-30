# Documentation Index

Every document in `docs/`, grouped by directory. Start with the
[PRD](#project-level) for what the product is, then follow the guide for
what you are trying to do.

New here? Read [Running Multi-Agent Campaigns](guides/running-campaigns.md) —
it is the shortest path from a campaign idea to a running 14-phase flow.

## Project-level

| Doc | What it contains |
|-----|------------------|
| [PRD.md](PRD.md) | Product requirements: the research engine as a trading-domain port of the Gentle-AI architecture, who it serves, and scope. Status: Draft v0.1.0. |
| [CHANGELOG.md](CHANGELOG.md) | Reverse-chronological record of notable changes, including the repository reorganization for GitHub readiness. |
| [STATE.md](STATE.md) | Point-in-time project status snapshot. Points at `git log` and CI for live state rather than restating counts. |

## Architecture

| Doc | What it contains |
|-----|------------------|
| [architecture/multi-agent-system.md](architecture/multi-agent-system.md) | Component-level architecture of the Multi-Agent Research System: `ResearchDirector` as orchestrator, the agent roles, and how they interact. |
| [multi-agent/agents.md](multi-agent/agents.md) | Per-agent reference — what each agent does, its config block, and how to register a new one. |
| [multi-agent/pipeline.md](multi-agent/pipeline.md) | Multi-Agent pipeline YAML: the `agents`, `gates`, and `memory` sections. Not to be confused with the [SDK pipeline schema](configuration/pipeline-yaml.md). |

## Configuration

| Doc | What it contains |
|-----|------------------|
| [configuration/pipeline-config.md](configuration/pipeline-config.md) | Pipeline configuration keys, value ranges, and the agent config blocks that consume them. |
| [configuration/pipeline-yaml.md](configuration/pipeline-yaml.md) | SDK pipeline YAML schema: top-level structure, stage types, and per-stage config. Used by `quantlab pipeline run`. |
| [multi-agent/gates.md](multi-agent/gates.md) | Configuring and using human gate checkpoints, gate philosophy, and what each gate blocks. |

## Guides

| Doc | What it contains |
|-----|------------------|
| [guides/running-campaigns.md](guides/running-campaigns.md) | **Start here.** Running the full 14-phase flow: command reference, the two gate decision channels, and exit status. |
| [guides/knowledge-query.md](guides/knowledge-query.md) | Querying, tagging, linking, and exporting campaigns from the Knowledge Lake. |
| [guides/reporting.md](guides/reporting.md) | Generating interactive HTML/JSON campaign reports with Plotly, matplotlib fallback, and Jinja2 templates. |
| [guides/review-lifecycle.md](guides/review-lifecycle.md) | The gentle-ai review lifecycle for `sdk/quantlab/` changes: 4R consent envelope, stop-reason continuation table, repair preflight. |

## Runbooks

| Doc | What it contains |
|-----|------------------|
| [runbooks/jforex-demo.md](runbooks/jforex-demo.md) | Operator guide from an SQX-exported `.jfx` to a monitored JForex4 deployment, demo and live, including fail-closed behavior. |
| [multi-agent/deployment.md](multi-agent/deployment.md) | Deployment phases, the `DeploymentAgent`, and live-trading risk practices. |

## Research and specs

| Doc | What it contains |
|-----|------------------|
| [research/exploration.md](research/exploration.md) | Exploration for the `multi-agent-research-system` change: current module inventory and the gaps the design had to close. |
| [specs/sdd-phase5f-consolidated.md](specs/sdd-phase5f-consolidated.md) | Consolidated SDD spec for phase 5f–5i production readiness: E2E smoke test, enhanced reporting, real pipeline execution, documentation. |

## SQX Builder reference

Source material for configuring StrategyQuant X. `SQX Builder Config.md` is the
pinned reference document — the KB seeder reads it as `DEFAULT_DOC_PATH` and
~15 `evidence_ref` entries under `knowledge/structured/sqx-kb/**` cite it, so
its filename is load-bearing and must not change.

| Doc | What it contains |
|-----|------------------|
| [SQX Builder Config.md](sqx-builder-config/SQX%20Builder%20Config.md) | **Pinned reference.** Every SQX setting the LLM agents must account for when configuring the builder, with worked examples. |
| [sqx-kb-seed-validation-plan.md](sqx-builder-config/sqx-kb-seed-validation-plan.md) | Plan for seeding and validating the SQX Parameter Knowledge Base for build 144.2953, including the seed-validation gate and educational dataset. |
| [1-estrategia-trading-algoritmico-jforex.md](sqx-builder-config/1-estrategia-trading-algoritmico-jforex.md) | Transcript: designing a JForex 4 algorithmic strategy, and what happens to open positions when the machine shuts down. |
| [2-fabrica-de-estrategias-automatizadas.md](sqx-builder-config/2-fabrica-de-estrategias-automatizadas.md) | Transcript: architecture of the strategy factory — generation, Builder filters, retest, and the selection funnel. |
| [3-analisis-de-rentabilidad-en-trading.md](sqx-builder-config/3-analisis-de-rentabilidad-en-trading.md) | Transcript: an honest assessment of whether this system can actually make a trader profitable, and where it breaks down. |
| [4-conectar-llm-a-trading.md](sqx-builder-config/4-conectar-llm-a-trading.md) | Transcript: connecting an LLM agent to a live trading platform as orchestrator rather than signal generator, plus data and analysis sources. |
| [5-analisis-herramienta-jesse-trade.md](sqx-builder-config/5-analisis-herramienta-jesse-trade.md) | Transcript: analysis of the Jesse framework and where it fits (and does not) in this trading stack. |
| [quantlab-ai.md](sqx-builder-config/quantlab-ai.md) | Raw working notes on the intended end-to-end QuantLab flow, the orchestrator layer, and the persistent memory system. |

> The numbered files are archived ChatGPT conversation transcripts, preserved
> as source material. They are in Spanish; only the H1 titles added for
> navigation are English.

## Not indexed here

| Path | What it is |
|------|------------|
| [`openspec/specs/`](../openspec/specs/) | Normative capability specs — the contract layer that `tests/` assert against. |
| [`openspec/changes/`](../openspec/changes/) | Change proposals and their lifecycle artifacts. Dated entries under `archive/` are completed history. |
| [`ai/opencode/`](../ai/opencode/) | Repo-canonical agent prompts and skills. This directory is the source of truth; the live copies under `~/.config/opencode/` are generated by the sync scripts and must not be hand-edited. |
