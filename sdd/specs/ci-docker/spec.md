# CI & Docker Specification

## Purpose

Repairs the deploy path: CI installs via the build-system with a coverage artifact, the phantom docs job is removed, the Dockerfile runs a working entrypoint, and docker-compose validates.

## Requirements

### Requirement: CID-01 CI install + coverage

CI MUST install via `pip install -e "sdk[dev]"` (poetry removed everywhere) and run pytest with `--cov --cov-report=xml:coverage.xml` so `sdk/coverage.xml` exists for the codecov upload.

#### Scenario: Coverage artifact produced
- GIVEN the CI test job
- WHEN pytest runs with the cov flags
- THEN `sdk/coverage.xml` is generated and uploaded

**Acceptance**: CI green + coverage.xml generated (proposal success criterion).

### Requirement: CID-02 CI docs job

The docs job MUST either use a real mkdocs setup (`mkdocs.yml` + a `docs` extra) or be removed; it MUST NOT reference the nonexistent `--with docs` extra.

#### Scenario: Docs build succeeds or job removed
- GIVEN ci.yml docs job
- WHEN it runs
- THEN `mkdocs build` succeeds, or the job is deleted from the workflow

**Acceptance**: no failing phantom job in ci.yml.

### Requirement: CID-03 Dockerfile CMD + install path

The Dockerfile MUST install via `[build-system]` (not poetry), set PYTHONPATH where needed, and set both broken CMDs (L122, L157) to a working entrypoint (`quantlab api`).

#### Scenario: Image builds and serves
- GIVEN the fixed Dockerfile
- WHEN `docker build` then the container starts
- THEN `quantlab api` runs and `GET /api/health` returns 200

**Acceptance**: docker build valid (proposal success criterion).

### Requirement: CID-04 Compose defects fixed

`docker-compose.yml` MUST fix all 9 defects: correct build contexts (L10, L47), dedupe `container_name` (L44/49) and `deploy` blocks (L66/80), point nginx/init-schema at `docker/`, drop or create `certs/` and `data/sqx`, and remove the nonexistent `Dockerfile.sqx` build block.

#### Scenario: Compose validates
- GIVEN the fixed compose file
- WHEN `docker compose config` runs
- THEN it validates without errors

**Acceptance**: compose config valid (proposal success criterion).
