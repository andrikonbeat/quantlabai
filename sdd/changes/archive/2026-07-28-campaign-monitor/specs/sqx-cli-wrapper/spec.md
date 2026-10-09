# Delta for SQX CLI Wrapper

## ADDED Requirements

### Requirement: extract_results_count Helper

The system MUST expose a public function `extract_results_count(status_text: str) -> int` that parses the "Strategies generated" line from SQX status plain text output and returns the integer count. If the pattern is not found, it SHALL return 0.

#### Scenario: Parses strategies generated count

- GIVEN status text containing "Strategies generated 255"
- WHEN extract_results_count is called
- THEN it returns 255

#### Scenario: Missing pattern returns zero

- GIVEN status text without "Strategies generated" (e.g., error message)
- WHEN extract_results_count is called
- THEN it returns 0

### Requirement: extract_error_patterns Helper

The system MUST expose a public function `extract_error_patterns(status_text: str) -> list[str]` that scans status text for SQX error patterns. The function SHALL detect: `Cannot start project`, `config errors`, `Error:`, and `Cannot get`. Each matched line (up to 3) SHALL be returned. If no patterns match, it SHALL return an empty list.

#### Scenario: Detects config error line

- GIVEN status text containing "Cannot start project 'X', it has config errors in task 'Build'"
- WHEN extract_error_patterns is called
- THEN it returns a list with one entry matching the error line

#### Scenario: Clean status returns empty list

- GIVEN a clean status response with strategies, running time, and databank
- WHEN extract_error_patterns is called
- THEN it returns an empty list

#### Scenario: Multiple errors detected

- GIVEN status text with multiple error lines
- WHEN extract_error_patterns is called
- THEN it returns up to 3 matched lines
- AND each line is the full text from the status response
