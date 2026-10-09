# SQX Parameter KB Specification

## Purpose

Evidence-based Knowledge Base of SQX builder parameters: seeded from documentation, verified against real configs, consumed by `builder_agent` and `config_reviewer`, invalidated on SQX version drift.

## Requirements

### Requirement: REQ-201 KB Schema

The system MUST store each parameter as YAML at `structured/sqx-kb/{sqx_version}/parameters/{tab}/{param}.yaml` with fields: `name`, `sqx_name`, `tab`, `section`, `type`, `default`, `range`, `what_it_does`, `how_it_works_in_sqx`, `quant_trading_role`, `hypothesis_relation`, `edge_relation`, `small_account_recommendation` + `reason`, `why_choose`, `when_choose`, `related_parameters`, `status` (`seeded|verified|needs_review`), `sqx_version`, `evidence_ref`.

#### Scenario: Valid parameter file loads

- GIVEN a KB YAML with all required fields
- WHEN the loader parses it
- THEN the parameter is valid and queryable by tab and name

#### Scenario: Missing required field

- GIVEN a KB YAML missing `what_it_does`
- WHEN the loader parses it
- THEN validation fails listing the missing field

### Requirement: REQ-202 Storage Layout

The system MUST isolate KB by SQX version (`structured/sqx-kb/{sqx_version}/`). Parameters SHALL be grouped by tab — What to build, Genetic options, Data, Trading options, Building blocks, Money management, Cross checks, Ranking — under `parameters/{tab}/{param}.yaml`.

#### Scenario: Version-isolated lookup

- GIVEN params seeded for 144.2953
- WHEN an agent queries `tab=Ranking, param=Ranking Criterium`
- THEN the 144.2953 YAML is returned, not any other version

### Requirement: REQ-203 Seed and Verify Process

The system MUST seed all 8 tabs from `doc_dev/SQX Builder Config.md` with `status: seeded` and `evidence_ref` to the doc. Parameters MUST be verified against real `.cfx`/config evidence, promoting to `verified`. Doc gaps MUST become `needs_review`; the system MUST NOT invent parameter semantics.

#### Scenario: Seed from documentation

- GIVEN `doc_dev/SQX Builder Config.md`
- WHEN the seed command runs
- THEN one YAML per documented parameter is created with status seeded

#### Scenario: Doc gap becomes needs_review

- GIVEN a parameter mentioned but unexplained (e.g., ATM tab)
- WHEN seeding
- THEN a YAML with status needs_review is created, with no invented content

#### Scenario: Verification against real config

- GIVEN a real campaign config using ATR-based Stop Loss
- WHEN verify runs
- THEN matching params update to status verified with an evidence_ref

### Requirement: REQ-204 Consumption by Agents

`builder_agent` MUST consult the KB when configuring the builder and MUST NOT configure a parameter without a KB entry (or explicit needs_review justification). `config_reviewer` MUST validate builder configs against the KB.

#### Scenario: Builder uses KB guidance

- GIVEN builder_agent configuring Stop Loss
- WHEN it consults the KB
- THEN it uses `what_it_does` and `small_account_recommendation`
- AND records the chosen value with its why/when rationale

#### Scenario: Missing entry blocks configuration

- GIVEN a parameter with no KB entry
- WHEN builder_agent attempts to configure it
- THEN configuration is blocked pending a needs_review entry or explicit user override

### Requirement: REQ-205 Reviewer Teaching Table

`config_reviewer` MUST return a structured teaching table per configured parameter: tab/section, parameter, what-it-does and how-it-works-in-SQX, quant-trading/edge role, chosen config, why, and for-what.

#### Scenario: Teaching table emitted

- GIVEN config_reviewer passing a builder config
- WHEN the review succeeds
- THEN the summary table covers every configured parameter with why/for-what rationale

### Requirement: REQ-206 Small-Account Guidance

Every parameter SHALL include `small_account_recommendation` with `reason`, reflecting nano-capital constraints (e.g., a $100 account): recommended value, default alternative, rationale.

#### Scenario: Recommendation present

- GIVEN the KB entry for Maximum Trades Per Day
- WHEN queried
- THEN it returns recommendation 1, default 0, and the overtrading/commission rationale

### Requirement: REQ-207 KB CLI

The system MUST provide `quantlab sqx kb` with subcommands: `list [--tab] [--status]`, `get {tab}/{param}`, `seed`, `verify {tab}/{param}`, `status`.

#### Scenario: List parameters by tab

- GIVEN a seeded KB
- WHEN `quantlab sqx kb list --tab Ranking`
- THEN all Ranking params are listed with status, exit 0

#### Scenario: Get single parameter

- GIVEN a seeded parameter
- WHEN `quantlab sqx kb get "Trading options/Maximum Trades Per Day"`
- THEN the full YAML is printed, exit 0

#### Scenario: Missing parameter

- GIVEN an unknown param name
- WHEN `quantlab sqx kb get Unknown`
- THEN exit code 1 with a "not found" message

### Requirement: REQ-208 Version-Invalidation Hook

On SQX version drift (sqx-version-detection REQ-305), the system MUST mark all KB parameters of the old version `needs_review` and MUST NOT serve them as verified for the new version until re-verified.

#### Scenario: Drift invalidates KB

- GIVEN a detected change 144.2953 → 145.x
- WHEN the invalidation hook runs
- THEN all params under `sqx-kb/144.2953/` become needs_review
