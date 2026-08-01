# QuantLab Config Wizard Specification

## Purpose

Bubbletea TUI wizard for collecting and validating QuantLab configuration. Invoked by `quantlab configure` or as part of `quantlab install` first-run. Refer to `openspec/specs/quantlab-installer/spec.md` for the full installer context.

## Requirements

### CONFIGURE-WIZARD — Collect settings
The system MUST present sequential TUI steps for: SQX CLI path, JForex DAS host:port, JForex credentials, API keys (OpenAI, Anthropic, etc.). Each step MUST have a text input with validation on submit.

### VALIDATE-PATH — SQX path check
The system MUST verify the provided SQX path exists and is executable. On failure, MUST show error and stay on the same step.

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
