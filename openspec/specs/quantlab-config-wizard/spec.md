# QuantLab Config Wizard Specification

## Purpose

Bubbletea TUI wizard for collecting and validating QuantLab configuration. Invoked by `quantlab configure` or as part of `quantlab install` first-run. Refer to `openspec/specs/quantlab-installer/spec.md` for the full installer context.

## Requirements

### CONFIGURE-WIZARD — Collect settings
The system MUST present sequential TUI steps for: SQX installation folder (install_path), JForex installation folder, JForex account mode (`demo|live`, default `demo`), JForex DAS host:port, JForex credentials, and API keys (OpenAI, Anthropic, etc.). Each step MUST have a text input with validation on submit. The password MUST be masked in the TUI, MUST be written only to `~/.quantlab/config.yaml` (0600), and MUST NOT be written to state.json nor logs.

### VALIDATE-PATH — SQX path check
The system MUST verify the provided SQX installation folder exists and contains the CLI binary (`sqcli`/`sqcli.exe`) at its root or in `bin/`. On failure, MUST show error and stay on the same step.

### VALIDATE-CONNECT — JForex reachability
The system SHOULD attempt a TCP connection to JForex host:port. On failure, SHOULD warn but allow proceeding (JForex may be offline).

### MASK-SECRETS — Credential display
The system MUST mask API keys and passwords in all TUI fields (show `••••••••`). MUST allow toggling visibility per field.

### PERSIST-CONFIG — Write configuration
The system MUST write validated config to `~/.quantlab/config.yaml` with 0600 permissions. MUST compute SHA-256 of the written config and store it in `state.json config_hash`.

## Scenarios

### W1: Wizard completes successfully
- GIVEN the user enters valid SQX path, JForex host:port, username, and a valid OpenAI API key
- WHEN the wizard reaches the confirmation screen and the user confirms
- THEN `~/.quantlab/config.yaml` is written with 0600 permissions
- AND `state.json config_hash` matches the written file's SHA-256

### W2: Invalid SQX path entered
- GIVEN the user enters `/nonexistent/sqcli` as SQX path
- WHEN the user submits the field
- THEN the system displays "Path /nonexistent/sqcli not found"
- AND the user stays on the SQX path step until entering a valid path

### W3: Invalid API key format
- GIVEN the user enters "not-a-key" as the OpenAI API key
- WHEN the user submits
- THEN the system displays "Key does not match expected format (sk-...)"
- AND the user may proceed or correct (warning, not blocking)

### W4: Wizard complete with install_path and account_mode
- GIVEN the user enters a valid SQX folder, JForex folder, account_mode=demo, credentials, and a valid API key
- WHEN the wizard reaches the confirmation screen and the user confirms
- THEN `~/.quantlab/config.yaml` is written with 0600 permissions including `sqx.install_path` and `jforex.account_mode=demo`
- AND `state.json config_hash` matches the written file's SHA-256

### W5: Password never in state
- GIVEN the user enters a JForex password
- WHEN the wizard persists the configuration
- THEN the password appears only in config.yaml (0600)
- AND it does not appear in state.json nor logs

### W6: Invalid SQX folder
- GIVEN the user enters `/nonexistent` as install_path
- WHEN the user submits the field
- THEN the system shows an error and stays on the step
- AND does not advance until a valid path is provided or the step is cancelled

### VALIDATE-MODE — Account mode restriction (REQ-WIZ-1)
The system MUST restrict `jforex.account_mode` to `demo` or `live`, with default `demo` when the field is empty. On invalid input, MUST show error and stay on the same step.

#### Scenario: Invalid mode rejected
- GIVEN the user enters account_mode=paper
- WHEN the field is submitted
- THEN the system shows an error
- AND stays on the step until `demo|live` is entered or the step is cancelled
