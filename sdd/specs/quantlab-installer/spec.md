# QuantLab Installer Specification

## Purpose

Zero-dependency Go binary that installs, configures, and maintains QuantLab AI on a user machine. Provides Bubbletea TUI, atomic prepare→apply→rollback pipeline, deep-merge OpenCode integration, and guaranteed coexistence with Gentle AI. The config-wizard is a sub-command of this spec.

## Requirements

### Functional

#### INSTALL — Bootstrap QuantLab
The system MUST validate prerequisites (Python 3.11+, OpenCode installed), MUST capture before-images via mutation journal, MUST run config wizard when no config exists, MUST create venv + pip install SDK from wheel, MUST deep-merge `quantlab-orchestrator`, `guardian-orchestrator` and `quantlab-*` agents into opencode.json, MUST write skills under `~/.config/opencode/skills/quantlab-*`, MUST set ownership marker for `default_agent`, and MUST write state to `~/.quantlab/state.json`. On any step failure, MUST rollback all prior steps. The count of agents registered SHALL be derived from the overlay (single source of truth), not from a hardcoded list; if onboarding is not completed, install SHALL suggest `quantlab onboarding` at the end.

#### UNINSTALL — Complete removal
The system MUST read state.json to enumerate installed components, MUST restore `default_agent` from ownership marker, MUST remove `quantlab-*` agents from opencode.json via deep merge overlay, MUST remove `~/.config/opencode/skills/quantlab-*` and `~/.config/opencode/prompts/quantlab/`, MUST remove venv + SDK, and MUST delete `~/.quantlab/` directory.

#### SYNC — Refresh components
The system MUST update installed skills/prompts to latest versions, MUST match agents by ID (never by name) to avoid duplicates, and MUST NOT create duplicate agent entries in opencode.json.

#### UPDATE — Self-update binary
The system MUST download the latest release binary from GitHub, MUST verify SHA-256 checksum before replacing the running binary, MUST perform atomic swap (write new binary → chmod +x → rename), and MUST preserve `~/.quantlab/` state unchanged.

#### CONFIGURE — Settings wizard
The system MUST present a Bubbletea TUI collecting SQX CLI path, JForex DAS host:port, JForex credentials, and API keys (OpenAI, Anthropic, etc.). MUST validate each path exists and each connection is reachable. MUST mask secrets in TUI display. MUST store `~/.quantlab/config.yaml` with permissions 0600.

#### STATUS — Inspect state
The system MUST display installed version, list of components, configured services (SQX, JForex, API keys presence without revealing values), and detect inconsistencies (missing state, orphaned agents, partial install). `detectIssues` MUST emit the warning "SQX folder moved — run 'quantlab configure' to update" when `SQX.InstallPath` does not exist on disk; the warning SHALL be non-blocking.

#### DASHBOARD — Web UI shortcut
The system SHOULD open the QuantLab web dashboard URL in the default browser.

### Non-Functional

#### Cross-platform
The system MUST compile for linux/amd64 and linux/arm64. SHOULD compile for darwin/amd64 and darwin/arm64. Windows support MAY be added in a future release.

#### Atomicity
All file writes MUST use WriteFileAtomic (temp file + rename) to prevent partial writes. The mutation journal MUST capture file before-images and directory listings before any modification.

#### Idempotence
Re-running `install` or `sync` on an already-configured system MUST produce the same final state and MUST NOT duplicate agents, skills, or state entries.

#### Security
Config files MUST be stored with 0600 permissions. Secrets MUST be masked in all TUI output and MUST NOT appear in logs. API keys MUST NOT be stored in opencode.json — only a reference key.

#### Rollback
Every apply step MUST register a reverse step in the mutation journal. If any step fails, the system MUST replay the journal in reverse order. If the process is killed during apply, the next `install`/`sync`/`status` run MUST detect inconsistent state and offer rollback or continue.

## Scenarios

### S1: First install on clean machine (happy path)
- GIVEN a machine with Python 3.12 and OpenCode installed, no prior QuantLab installation
- WHEN the user runs `quantlab install`
- THEN the wizard collects SQX path and API keys
- AND the pipeline validates prerequisites, creates venv, installs SDK, merges agents into opencode.json, installs skills/prompts, writes state.json
- AND `quantlab status` shows all components as "installed"

### S2: Install with OpenCode + Gentle AI present
- GIVEN a machine with Gentle AI installed, `default_agent` set to `gentle-orchestrator`
- WHEN `quantlab install` completes
- THEN opencode.json contains both `gentle-orchestrator` and `quantlab-orchestrator` agents
- AND `default_agent` remains `gentle-orchestrator`
- AND ownership marker at `~/.quantlab/default-agent-backup.json` records the previous value

### S3: Complete uninstall
- GIVEN QuantLab is installed with `default_agent` set to `quantlab-orchestrator`
- WHEN the user runs `quantlab uninstall`
- THEN `default_agent` is restored to its pre-install value
- AND `~/.quantlab/` is removed
- AND opencode.json no longer has `quantlab-*` agents
- AND `~/.config/opencode/skills/quantlab-*` is removed

### S4: Apply failure mid-way → rollback
- GIVEN a network failure during the pip install step of `quantlab install`
- WHEN the Apply pipeline fails after the opencode.json merge but before venv creation
- THEN the mutation journal replays rollback steps in reverse
- AND opencode.json is restored to its before-image
- AND no files remain under `~/.quantlab/`

### S5: Python 3.11+ not installed
- GIVEN a machine without Python 3.11 or later
- WHEN the user runs `quantlab install`
- THEN the system SHALL detect missing Python during Prepare
- AND SHALL display a clear error with download URL
- AND SHALL NOT proceed to Apply

### S6: Sync updates skills without duplicating agents
- GIVEN QuantLab v1.0 installed, a new skill `quantlab-prompt-optimizer` released in v1.1
- WHEN the user runs `quantlab sync`
- THEN the new skill is written to `~/.config/opencode/skills/quantlab-prompt-optimizer/`
- AND opencode.json still has exactly one `quantlab-orchestrator` agent entry
- AND no duplicate agent entries exist

### S7: Config wizard with invalid SQX/JForex paths
- GIVEN the user enters a non-existent `/invalid/sqcli` path in the config wizard
- WHEN the user proceeds past the SQX path field
- THEN the system SHALL validate the path exists
- AND display a validation error ("Path /invalid/sqcli does not exist")
- AND SHALL NOT advance to the next step until a valid path is provided

### S8: In-place binary update
- GIVEN QuantLab v1.0 binary at `/usr/local/bin/quantlab`
- WHEN the user runs `quantlab update`
- THEN the system downloads the v1.1 binary to a temp file
- AND verifies its SHA-256 matches the release checksum
- AND atomically replaces the running binary
- AND `quantlab version` outputs v1.1 after restart

### S9: Kill during Apply → inconsistent state recovery
- GIVEN the user kills `quantlab install` (SIGKILL) during the venv creation step
- WHEN `quantlab install` is run again
- THEN the system MUST detect the incomplete state journal
- AND display "Detected incomplete installation. Rollback (y/N)?"
- AND if confirmed, replay rollback steps from the journal

### S10: Uninstall with modified state
- GIVEN the user manually deleted `~/.quantlab/state.json` but skills remain installed
- WHEN `quantlab uninstall` is run
- THEN the system MUST still remove all skills matching `quantlab-*` prefix
- AND restore `default_agent` from the ownership marker
- AND report "State file missing — removed by component scan"

### S11: Agent count matches overlay
- GIVEN the overlay.json is updated
- WHEN install registers the agents component
- THEN the registered count equals the number of agents defined in the overlay
- AND every managed agent has a definition (no ghost names)

### S12: SQX folder moved detection
- GIVEN `sqx.install_path` points to a deleted folder
- WHEN `quantlab status` runs detectIssues
- THEN the warning "SQX folder moved — run 'quantlab configure' to update" is emitted
- AND status completes successfully (warning is non-blocking)

### S13: SQX configured and present
- GIVEN a valid SQX install_path
- WHEN status prints configured services
- THEN SQX is shown as configured
- AND no folder-moved warning is emitted

## Data Dictionary

### `~/.quantlab/state.json`
```json
{
  "version": "1.0",
  "install_id": "uuid",
  "installed_at": "2026-07-30T14:00:00Z",
  "quantlab_version": "1.0.0",
  "components": [
    {"id": "sdk", "status": "installed", "path": "~/.quantlab/venv"},
    {"id": "agents", "status": "installed", "count": 5},
    {"id": "skills", "status": "installed", "count": 3},
    {"id": "prompts", "status": "installed", "count": 2}
  ],
  "config_hash": "sha256-of-config",
  "opencode_agents_created": [
    "quantlab-orchestrator",
    "quantlab-run",
    "quantlab-monitor"
  ]
}
```

### `~/.quantlab/config.yaml`
```yaml
sqx:
  cli_path: "/opt/SQX/sqcli"
jforex:
  host: "localhost"
  port: 19790
  username: "trader"
  password: ""  # never stored if empty
api_keys:
  openai: "sk-..."   # stored with 0600 permissions
  anthropic: "sk-..."
```

### Ownership marker (`~/.quantlab/default-agent-backup.json`)
```json
{
  "previous_default_agent": "gentle-orchestrator",
  "previous_value_present": true,
  "captured_at": "2026-07-30T14:00:00Z"
}
```

## Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| Kill during Apply | Inconsistent state journal → detect on next run → offer rollback |
| Corrupted state.json | Treat as uninstalled, offer fresh install. Ownership marker survives independently |
| Reinstall over existing | Idempotent: detect installed components, skip SDK if intact, update skills, regenerate agents |
| Permission denied on ~/.config/opencode/ | Fail during Prepare with actionable error message |
| Paths with spaces | MUST quote paths in shell commands, test with `/home/user/QuantLab Stuff/` |
| Network failure during SDK install | Mutation journal rollback restores all prior changes |
| opencode.json with JSONC | NormalizeJSON before merge; preserve comments on write if input had them |
| Multiple users same machine | Each user has their own `~/.quantlab/` — no cross-user state |
| arm64 vs amd64 binary | UPDATE command MUST detect architecture and download matching asset |

### SQX/JForex config model (REQ-INS-1)

The model MUST define `SQXConfig{InstallPath, CLIPath}` (`InstallPath` = folder; `CLIPath` = optional override). `ResolveSQXCliPath()` MUST return `InstallPath + "/sqcli"` (or `sqcli.exe` on Windows) unless a `CLIPath` override is set, which MUST win (existing `cli_path` values remain valid). `ValidateSQXPath()` MUST accept the folder only if `sqcli`/`sqcli.exe` exists at its root or in `bin/`. The model MUST also define `JForexConfig{InstallPath, AccountMode, Host, Port, Username, Password}` with `AccountMode` restricted to `demo|live` and default `demo`. The password MUST be stored only in `~/.quantlab/config.yaml` (0600) and MUST NOT appear in logs or state.

#### Scenario: Resolution with override
- GIVEN config with `install_path=/opt/SQX` and `cli_path=/custom/sqcli`
- WHEN `ResolveSQXCliPath()` runs
- THEN it returns `/custom/sqcli`

#### Scenario: Derived resolution
- GIVEN config with only `install_path=/opt/SQX`
- WHEN `ResolveSQXCliPath()` runs
- THEN it returns `/opt/SQX/sqcli` (or `sqcli.exe` on Windows)

#### Scenario: Folder validation
- GIVEN `/opt/SQX/bin` contains `sqcli`
- WHEN `ValidateSQXPath("/opt/SQX")` runs
- THEN it accepts the folder
- AND rejects folders without the binary at root or in `bin/`

#### Scenario: Default AccountMode
- GIVEN config without account_mode
- WHEN JForexConfig is read
- THEN account_mode is `demo`

### Overlay as single source of truth (REQ-INS-2)

`QuantLabAgentNames()` MUST derive its list from the overlay (not hardcoded) and include `guardian-orchestrator` (mode primary, deny-first mirror of `quantlab-orchestrator` — REQ-822) and delegates `quantlab-guardian`, `quantlab-guardian-alert`, `quantlab-replacement`. The agent count reported by install/status MUST derive from the same overlay. `uninstall`/`sync` MUST use the derived list for removal and matching (no duplicates).

#### Scenario: Overlay contains guardian
- GIVEN the updated overlay.json
- WHEN managed agents are enumerated
- THEN `guardian-orchestrator` is present with mode primary
- AND `quantlab-guardian`, `quantlab-guardian-alert`, and `quantlab-replacement` are defined
- AND `QuantLabAgentNames()` matches the overlay

#### Scenario: Uninstall cleans derived set
- WHEN `quantlab uninstall` runs
- THEN it removes all agents from `QuantLabAgentNames()`
- AND no orphan guardian agents remain

## Acceptance Criteria

| Command | Criterion |
|---------|-----------|
| **install** | `quantlab install` completes wizard and leaves QuantLab usable in < 5 min. opencode.json contains `agent.quantlab-orchestrator` without losing existing configs. |
| **uninstall** | Removes all created artifacts, restores `default_agent`, no trace of QuantLab remains in OpenCode config. |
| **sync** | Updates skills without duplicating agents. Re-running sync produces identical state. |
| **update** | Replaces binary atomically. Version output reflects new version. Rollback possible via saved checksum. |
| **configure** | All 3 config screens (SQX, JForex, API keys) accept valid input. Invalid paths are rejected with specific error. |
| **status** | Prints version, component list, service health. Detects missing state or orphaned agents. |
| **dashboard** | Opens URL (or prints URL if browser unavailable). |
