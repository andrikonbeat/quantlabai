# Delta for sqx-translator

## ADDED Requirements

### Requirement: Legacy Dialect Flag Guard (G2)

The legacy single-task generator `generate_cfx_archive` (translate/translator.py:133) MUST remain available and MUST be the flow default while `QUANTLAB_CUSTOM_PROJECT` is off. Golden migration (`tests/customproject/`, `tests/cfx/`) MUST land BEFORE the flag flips. Rollback SHALL flip the flag back to the legacy dialect.

#### Scenario: Legacy default preserved

- GIVEN the flag unset or "0"
- WHEN the builder translates a research model
- THEN the single-task `.cfx` is produced unchanged
- AND the `BuildConfig` field surface is preserved

#### Scenario: Flip requires re-based goldens

- GIVEN goldens not yet re-based
- WHEN the flag is flipped
- THEN the byte-identity tests fail loudly
- AND the change reverts to legacy until goldens are re-based