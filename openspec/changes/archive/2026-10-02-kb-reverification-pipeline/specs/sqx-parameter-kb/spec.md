# Delta for sqx-parameter-kb

## MODIFIED Requirements

### Requirement: REQ-201 KB Schema

The system MUST store each parameter as YAML at `structured/sqx-kb/{sqx_version}/parameters/{tab}/{param}.yaml` with fields: `name`, `sqx_name`, `tab`, `section`, `type`, `default`, `range`, `what_it_does`, `how_it_works_in_sqx`, `quant_trading_role`, `hypothesis_relation`, `edge_relation`, `small_account_recommendation` + `reason`, `why_choose`, `when_choose`, `related_parameters`, `status` (`seeded|verified|needs_review`), `sqx_version`, `evidence_ref`, plus the optional XML traceability pair `xml_path` and `element_name`.

`xml_path` and `element_name` MUST be declared schema fields rather than accepted as unknown keys, and MUST be preserved unchanged by every store write (`verify`, `invalidate`, version-drift demotion). A write that drops either field MUST be treated as a defect.

(Previously: the field set ended at `evidence_ref`; `xml_path`/`element_name` present in stored YAML were silently dropped on every store write)

#### Scenario: Valid parameter file loads

- GIVEN a KB YAML with all required fields
- WHEN the loader parses it
- THEN the parameter is valid and queryable by tab and name

#### Scenario: Missing required field

- GIVEN a KB YAML missing `what_it_does`
- WHEN the loader parses it
- THEN validation fails listing the missing field

#### Scenario: XML anchors survive a store write

- GIVEN a `Cross checks` entry carrying `xml_path` and `element_name`
- WHEN the store writes it (promotion or drift demotion) and the file is reloaded
- THEN both fields are present and unchanged, because they are declared schema fields

### Requirement: REQ-208 Version-Invalidation Hook

On SQX version drift (sqx-version-detection REQ-305), the system MUST mark all KB parameters of the old version `needs_review` and MUST NOT serve them as verified for the new version until re-verified.

Re-verification MUST be evidence-first. An entry returns to `verified` only when an operator-supplied build artifact positively resolves its XML-anchored `xml_path`. An entry whose path resolves but whose element is absent MUST remain `needs_review`, and that absence MUST be treated as a terminal answer rather than a retry. An entry with no XML anchor MUST NOT be promoted by re-verification.

The system MUST discriminate entry kinds by the structural shape of `xml_path`, never by the `status` string: a drift-demoted entry and a pre-existing documentation gap share `status: needs_review` and are indistinguishable from status alone.

(Previously: the requirement ended at "until re-verified" — the re-verification path, its evidence, and its limits were unspecified)

#### Scenario: Drift invalidates KB

- GIVEN a detected change 144.2953 → 145.x
- WHEN the invalidation hook runs
- THEN all params under `sqx-kb/144.2953/` become needs_review

#### Scenario: XML evidence re-promotes a demoted entry

- GIVEN a demoted entry whose XML-anchored `xml_path` resolves in a supplied build artifact
- WHEN re-verification runs against that artifact
- THEN the entry becomes `verified` with an `evidence_ref` naming the artifact and anchor

#### Scenario: Absent field stays needs_review

- GIVEN a demoted entry whose `xml_path` root resolves but whose element is absent
- WHEN re-verification runs against the artifact
- THEN the entry stays `needs_review` and the verdict records field absence

#### Scenario: Documentation gap is never promoted

- GIVEN a `needs_review` entry whose `xml_path` is a documentation anchor, not an XML path
- WHEN re-verification runs
- THEN the entry is skipped and its status is unchanged, whatever its current status