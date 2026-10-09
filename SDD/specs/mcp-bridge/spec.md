# MCP Bridge Specification

Expose QuantLab subsystems as callable AI tools via MCP.

## Requirements

### Server Bootstrap

The server MUST start from `python -m quantlab.mcp` and register all domain tools.

- GIVEN the entry point
- WHEN the server boots
- THEN pipeline, evolution, health tools are registered
- AND `list_tools` returns their descriptions

### Domain Tools

`run_backtest`, `list_pipelines`, `get_pipeline_run` MUST wrap PipelineRunner. `generate_candidates`, `query_pool`, `promote_candidate` MUST wrap EvolutionOrchestrator/CandidatePool. `evaluate_strategy`, `get_health_metrics`, `compute_fitness` MUST wrap HealthScoreCalculator/MetaGuardian.

- GIVEN valid parameters for any domain tool
- WHEN the tool is invoked
- THEN the underlying subsystem executes and returns JSON results

### Serialization

All tool outputs MUST return valid JSON via `model_dump(mode="json")`.

- GIVEN any MCP tool response
- WHEN serialized
- THEN the output is valid JSON with no non-serializable types

### Error Handling

Exceptions MUST be caught and returned as `{"error": type, "message": detail}`. The server MUST NOT crash.

- GIVEN a tool raising an exception
- WHEN invoked
- THEN a structured error is returned
- AND the server continues serving

### Tool Discovery

`list_tools` MUST return all registered tools with name, description, and input schema.

- GIVEN a running server
- WHEN `list_tools` is called
- THEN each tool is listed with metadata

### Concurrency

The server SHOULD handle concurrent requests without blocking.

- GIVEN two simultaneous tool requests
- WHEN both require computation
- THEN both complete without blocking each other
