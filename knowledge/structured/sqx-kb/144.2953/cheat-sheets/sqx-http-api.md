# SQX HTTP API cheat-sheet

Curated, original summary; NOT a copy of the licensed SQX User Manual
(REQ-KDI-01/04). Exact endpoint paths and payload schemas are version-pinned
in the installed distribution's docs — never guess them.

## Purpose

StrategyQuant X exposes strategy operations over HTTP endpoints. Agents use
this sheet to know the API *shape*; exact paths come from
`get_doc("api", "<endpoint-name>", "<version>")` against the ingested
`internal/autocomplete/docs.json` corpus.

## Endpoint categories (shape only)

| Category | Operation type | Example concern |
|----------|----------------|-----------------|
| Health | status probe | daemon up, version |
| Strategies | list / create / delete | strategy lifecycle over HTTP |
| Backtest | run / status / result | job submission and polling |
| Export | artifact retrieval | compiled strategies, reports |

## Rules

1. NEVER hardcode an endpoint path in agent code — paths are version-pinned.
2. Resolve the API doc first: `get_doc("api", name, version)`.
3. When the doc is missing, omit the call and log the gap; do not invent
   payloads.
4. Treat responses as opaque JSON; validate against the resolved doc schema.
5. The real SQX daemon (port 5050) is never bound in tests —
   `SQX_FORCE_MOCK=1` only.

## Provenance

- Source: public tool documentation + installed distribution shape, curated.
- License: project-authored summary; no licensed text reproduced.
- Version: SQX `144.2953`.