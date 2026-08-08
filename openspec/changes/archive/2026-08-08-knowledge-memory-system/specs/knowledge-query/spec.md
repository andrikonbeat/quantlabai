# Delta for Knowledge Query

Change: add an injected-context retrieval surface (composing prior-campaign memory into the next phase's Result Contract envelope) and an SQX KB query surface on top of the existing QueryBuilder/KnowledgeStore.

## ADDED Requirements

### Requirement: REQ-501 Injected-Context Retrieval Surface

The system MUST provide a context-composition API, e.g. `compose_prior_context(campaign_id, phase) -> str`, that combines QueryBuilder results and `find_similar_campaigns` embedding matches into a markdown context block for injection into the next phase's Result Contract envelope.

#### Scenario: Composes prior memory block

- GIVEN prior campaigns with metrics and stored decisions
- WHEN compose_prior_context runs for phase N+1
- THEN the returned markdown includes matched prior decisions, risks, and lessons
- AND similar campaigns are ranked by embedding similarity

#### Scenario: Empty lake returns placeholder

- GIVEN an empty Knowledge Lake
- WHEN compose_prior_context runs
- THEN a "no prior memory" placeholder is returned and no error is raised

### Requirement: REQ-502 KB Query Surface

The system MUST expose parameter lookup over the SQX KB: `get_parameter(tab, param, sqx_version)` and `list_parameters(tab=None, status=None, sqx_version=None)`, honoring version isolation and status filtering.

#### Scenario: Version-isolated lookup

- GIVEN params for both 144.2953 and a newer version
- WHEN `get_parameter("Ranking", "Ranking Criterium", "144.2953")` runs
- THEN the 144.2953 YAML is returned, not the other version

#### Scenario: Filter by status

- GIVEN seeded, verified, and needs_review params
- WHEN `list_parameters(status="needs_review")` runs
- THEN only needs_review params are returned
