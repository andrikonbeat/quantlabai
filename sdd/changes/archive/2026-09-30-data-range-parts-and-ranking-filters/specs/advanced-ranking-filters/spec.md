# Advanced Ranking Filters Specification

## Purpose

Define typed models and patcher behavior for nested `<Rankings><Conditions>` structures in QuantLab CFX generation, matching the verified SQX 144/2953 Retester schema.

## Requirements

### Requirement: Advanced Ranking Condition Model

The system MUST provide an `AdvancedRankingCondition` model representing one nested `<Condition use="...">` element with typed fields for `resultType`, `sampleType`, `direction`, `pctRatio`, `confidenceLevel`, `market`, `plType`, `subresult`, `class`, and optional `name`, plus a list of `ColumnValue` child elements.

#### Scenario: Full attribute round-trip

- GIVEN a condition with `resultType="main"`, `sampleType="127"`, `direction="desc"`, and two `ColumnValue` entries
- WHEN the model serializes to XML and parses back
- THEN all attributes and children are preserved exactly

#### Scenario: Minimal valid condition

- GIVEN a condition with only `use="true"` and one `ColumnValue`
- WHEN serialized
- THEN optional attributes are omitted and parsing succeeds

#### Scenario: CrossCheck block compatibility

- GIVEN a `<Conditions CrossCheck="...">` parent with multiple conditions
- WHEN each condition is rendered
- THEN each `<Condition>` remains nested under the same parent block

### Requirement: Simple Ranking Compatibility

The system MUST NOT alter the existing simple `AddRankingConditionInstruction` path when advanced filters are present.

#### Scenario: Mixed simple and advanced conditions

- GIVEN a project with both simple and advanced ranking instructions
- WHEN the CFX is generated
- THEN both simple and advanced `<Condition>` blocks appear correctly

### Requirement: DSL Expression

The system MUST accept a DSL representation of advanced ranking filters and translate it to the typed model without data loss.

#### Scenario: DSL round-trip

- GIVEN a DSL block defining `resultType`, `sampleType`, `pctRatio`, and nested `ColumnValue` filters
- WHEN translated through the DSL → model → XML pipeline
- THEN the emitted XML matches the expected nested `<Rankings>` structure
