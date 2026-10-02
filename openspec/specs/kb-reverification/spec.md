# KB Re-verification Specification

## Purpose

Resolve the SQX parameter KB against operator-supplied build XML after drift demotes entries to `needs_review`. Per-entry verdicts; promotion only on positive XML resolution.

## Requirements

### Requirement: Evidence Loading

The system MUST accept an operator-supplied archive (`.cfx`, `.sqx-template`) or bare XML file as evidence, preferring `Build-Task1.xml` over `config.xml`. Evidence MUST be explicit; the system MUST NOT auto-discover it. Missing or unreadable evidence MUST be reported as unreadable.

#### Scenario: Member preference

- GIVEN an archive holding `Build-Task1.xml` and `config.xml`
- WHEN the evidence is loaded
- THEN `Build-Task1.xml` is parsed, and `config.xml` only when it is absent

#### Scenario: Unreadable evidence

- GIVEN a missing, truncated, or non-archive path
- WHEN the evidence is loaded
- THEN unreadable evidence is reported and nothing is written

#### Scenario: Tracked fixture suffices

- GIVEN the tracked `sdk/quantlab/sqx/templates/default-project.sqx-template`
- WHEN evidence is loaded from it
- THEN loading succeeds, so tests need no untracked install assets

### Requirement: Four-Outcome Verdict Contract

Every entry MUST receive exactly one verdict: `verified` (promoted), `field_absent` (stays `needs_review`), `not_xml_backed` (skipped, never promoted), or `evidence_unreadable` (run-level, zero writes). Only `verified` MAY mutate the store. Verdicts MUST be assigned by the structural shape of `xml_path`, never by the `status` string. A promoted entry's `evidence_ref` MUST record the artifact with the resolved XML anchor, in the `path#anchor` form the seed-validation gate already strips.

#### Scenario: Positive resolution promotes

- GIVEN an entry whose XML-anchored `xml_path` resolves with its element present
- WHEN verdicts are computed
- THEN the verdict is `verified` and promotion is permitted
- AND the resulting `evidence_ref` resolves to the artifact, anchor after `#`

#### Scenario: Absent element is terminal

- GIVEN an entry whose path root resolves but whose element is absent
- WHEN verdicts are computed
- THEN the verdict is `field_absent` and the entry stays `needs_review`

#### Scenario: Documentation anchor is skipped

- GIVEN an entry whose `xml_path` is a documentation anchor
- WHEN verdicts are computed
- THEN the verdict is `not_xml_backed` and the entry is never promoted

#### Scenario: Mixed population

- GIVEN a population where some entries resolve and some do not
- WHEN verdicts are computed
- THEN every entry carries its own verdict

### Requirement: Re-verification Entry Point

`KbStore.reverify_against_build(evidence, *, tab=None, sqx_version=None, apply=False)` MUST default to dry-run, MUST take its population from the existing list read, MUST route every promotion through the existing verify write path, and MUST return verdicts regardless of `apply`. `tab` MUST scope the population; an unknown version bucket MUST be refused.

#### Scenario: Dry-run is the default

- GIVEN `apply` is omitted
- WHEN re-verification runs
- THEN verdicts are returned and no YAML is modified

#### Scenario: Single write path

- GIVEN `apply=True` and one entry resolving positively
- WHEN re-verification runs
- THEN that entry's status and `evidence_ref` change through the existing verify path

#### Scenario: Tab scoping narrows the population

- GIVEN `tab="Cross checks"`
- WHEN re-verification runs
- THEN only that tab's entries receive verdicts

### Requirement: Re-verification CLI

`quantlab sqx kb reverify --evidence <path> [--tab T] [--apply]` MUST be a `sqx kb` subcommand, MUST be dry-run unless `--apply` is passed, and MUST print per-outcome counts on stdout. Unreadable evidence MUST return a distinct non-zero exit code and MUST NOT write. The run MUST fail open on dispatch, leaving every `needs_review` in place.

#### Scenario: Dry-run reports

- GIVEN `reverify --evidence <path>` without `--apply`
- WHEN the command runs
- THEN per-outcome counts print, exit is 0, and no YAML is modified

#### Scenario: Unreadable evidence exits distinctly

- GIVEN an unreadable `--evidence` path
- WHEN the command runs
- THEN a distinct non-zero exit is returned, no YAML is modified, and the dispatch completes

## Non-Goals

- A report file under `structured/sqx-version/{old}→{new}/` is deferred; stdout is the only report surface.
- Auto-discovery of artifacts, point-version detection, drift-workflow wiring, reviewer-table gating, XML anchors beyond current entries.