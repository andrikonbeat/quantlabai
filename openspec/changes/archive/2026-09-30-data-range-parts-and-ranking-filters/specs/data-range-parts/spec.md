# Data Range Parts Specification

## Purpose

Define a typed/configurable bridge for Data range parts in QuantLab CFX generation, preserving extensibility for future typed fields while handling unknown ranges via `raw_xml`.

## Requirements

### Requirement: Typed Data Range Parts Model

The system MUST provide a `DataRangeParts` model exposing stable typed fields for known concepts: IST, ISC, ISV1..ISV10, OOS1, OOS-Every, ISV-Every, validation/test split ratios, and date bounds. Each typed field MAY be omitted.

#### Scenario: Fully populated data range

- GIVEN all known typed fields are set with valid values
- WHEN serialized to XML
- THEN each typed field emits its corresponding element or attribute in the expected `<Data>` structure

#### Scenario: Partial typed fields with raw_xml fallback

- GIVEN only IST, ISC, and date bounds are set, with `raw_xml` containing additional custom sub-ranges
- WHEN serialized
- THEN typed fields emit alongside the preserved `raw_xml` content

#### Scenario: Unknown range passthrough

- GIVEN a CFX with an unrecognized `<Data>` sub-range type
- WHEN parsed through the bridge
- THEN the unknown content is preserved in `raw_xml` without loss

### Requirement: Configurable raw_xml Bridge

The system MUST accept a `raw_xml` string for any Data section content that lacks a typed field, and MUST include it verbatim during serialization.

#### Scenario: raw_xml override

- GIVEN `raw_xml` contains a complete custom `<Data>` block
- WHEN serialized with no typed fields set
- THEN the output contains exactly the `raw_xml` content

#### Scenario: raw_xml combined with typed fields

- GIVEN typed fields for IST/ISC plus `raw_xml` for a proprietary sub-range
- WHEN serialized
- THEN typed fields and `raw_xml` appear together without duplication or conflict

### Requirement: Validation and Test Split Semantics

The system MUST expose typed fields for validation/test split ratios and MUST NOT reinterpret them as training ratios.

#### Scenario: Split ratio preservation

- GIVEN validation ratio `0.2` and test ratio `0.1`
- WHEN serialized and re-parsed
- THEN the ratios remain unchanged and are distinguishable from training ratio
