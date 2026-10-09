# Design: QuantLab Installer

## Technical Approach

Go binary (Bubbletea TUI) replicating Gentle AI's prepare→apply→rollback pipeline. Deep-merge JSON overlay for opencode.json, mutation journal for atomic rollback, ownership pattern for `default_agent`. Python venv + pip install for SDK. Assets (skills, prompts) embedded via `embed.FS`. Each component uses a standalone `internal/` package with zero external coupling.

## Architecture Decisions

| Decision | Options | Tradeoff | Choice |
|---|---|---|---|
| CLI framework | Cobra vs manual flag parse | Cobra adds dep but gives subcommands + help for free | Manual dispatch (match Gentle AI's `app.go` pattern) |
| TUI library | Bubbletea vs promptui/huh | Bubbletea gives full TUI control (progress bars, spinners, keyboard nav) | Bubbletea + Bubbles + Lipgloss |
| Config format | YAML vs JSON vs TOML | YAML is human-readable + supports comments; same as Gentle AI | YAML (via gopkg.in/yaml.v3) |
| Merge strategy | Deep merge vs JSON patch | Deep merge preserves existing keys; JSON Patch is more complex | Deep merge (reuse Gentle AI's `filemerge.MergeJSONObjects`) |
| State tracking | Single file vs SQLite | SQLite is overkill for ~5 fields | `~/.quantlab/state.json` |
| SDK install | pip from GitHub vs wheel | Wheel is deterministic, no git clone dep at runtime | PyPI wheel (future) → fallback to `.whl` from release asset |
| Concurrent journal roots | Single dir vs multi-dir | Multi-dir (`~/.quantlab/`, `~/.config/opencode/`) covers all mutation targets | Multi-dir: `~/.quantlab` and `~/.config/opencode/` |
| Self-update strategy | Direct binary replace + restart | Atomic rename; verifying SHA-256 before swap prevents corruption | Download → temp → verify → chmod +x → rename → restart |

## Data Flow

```
quantlab install
  │
  ├─ PREPARE
  │   ├─ Detect: Python 3.11+, OpenCode, existing QuantLab state
  │   ├─ Capture: opencode.json before-image via mutation journal
  │   └─ Capture: ownership marker (current default_agent)
  │
  ├─ WIZARD (if no config exists)
  │   ├─ SQX CLI path → validate exists + executable
  │   ├─ JForex host:port → TCP ping (optional)
  │   └─ API keys (OpenAI, Anthropic) → mask input
  │
  ├─ APPLY (each step registers reverse in journal)
  │   ├─ 1. Create ~/.quantlab/
  │   ├─ 2. Write config.yaml (0600)
  │   ├─ 3. Create venv → pip install SDK
  │   ├─ 4. Merge opencode.json overlay (quantlab-* agents)
  │   ├─ 5. Write skills: ~/.config/opencode/skills/quantlab-*/
  │   ├─ 6. Write prompts: ~/.config/opencode/prompts/quantlab/
  │   ├─ 7. Write ownership marker
  │   └─ 8. Write state.json
  │
  ├─ VERIFY
  │   ├─ opencode.json has quantlab-orchestrator agent
  │   ├─ SDK import works (python -c "import quantlab")
  │   └─ Skills exist on disk
  │
  └─ COMPLETE (or journal.Restore() on failure)
```

**Rollback**: Apply steps are ordered so that journal.Restore() reverses safely. Step 3 (SDK) is the highest-risk network operation — if it fails, steps 1–2 are rolled back, leaving no trace.

**Update flow**: `quantlab update` → fetch `https://github.com/{owner}/quantlab/releases/latest/download/quantlab-{os}-{arch}.tar.gz` → extract → SHA-256 verify → temp file → chmod +x → `os.Rename(temp, selfPath)` → exec new binary.

**Uninstall flow**: Read state.json → for each component: remove files, remove agents via overlay merge (empty overlay for quantlab-* keys), restore default_agent from ownership marker, delete `~/.quantlab/`.

## OpenCode Integration Detail

### Agents to inject
- `quantlab-orchestrator` (mode: subagent, delegates to `quantlab-run`, `quantlab-monitor`, `quantlab-compare`, `quantlab-status`)
- Reference: existing `quantlab-orchestrator` in opencode.json already has this structure. The installer overlay will define it canonically.

### Overlay JSON structure
```json
{
  "agent": {
    "quantlab-orchestrator": {
      "description": "QuantLab AI orchestrator — routes retail user requests to SDD, CLI, or dashboard",
      "mode": "subagent",
      "permission": {
        "task": { "*": "deny", "sdd-*-quantlab": "allow",
                  "quantlab-run": "allow", "quantlab-monitor": "allow",
                  "quantlab-compare": "allow", "quantlab-status": "allow" },
        "bash": { "*": "deny", "quantlab-run": "allow", "quantlab-monitor": "allow",
                  "quantlab-compare": "allow", "quantlab-status": "allow",
                  "sdk/pipeline/*": "allow", "knowledge/*": "allow" }
      },
      "prompt": "{file:~/.config/opencode/prompts/quantlab/orchestrator.md}",
      "tools": { "bash": true, "edit": true, "read": true,
                 "task": true, "write": true, "question": true }
    }
  }
}
```

### default_agent ownership
- **Install**: Capture `default_agent` → write `~/.quantlab/default-agent-backup.json` → do NOT change value (QuantLab is a subagent, not primary)
- **Uninstall**: Read backup → restore if QuantLab was set as default → delete backup
- **Sync**: Preserve existing default; never override

### Skills to install
- `quantlab-agent` — quantlab-orchestrator agent instructions
- `quantlab-orchestrate` — SDD phases for QuantLab changes
- `quantlab-trading` — trading-specific instructions

## File Changes

| File | Action | Description |
|---|---|---|
| `installer/cmd/quantlab/main.go` | Create | Entry point: version ldflags, dispatch to app |
| `installer/internal/app/app.go` | Create | CLI dispatch: install/uninstall/sync/configure/update/status/dashboard |
| `installer/internal/pipeline/stages.go` | Create | Step interface, StagePlan, FailurePolicy, ProgressFunc |
| `installer/internal/pipeline/runner.go` | Create | Execute steps with progress callbacks, auto-rollback on failure |
| `installer/internal/filemerge/json_merge.go` | Create | Deep merge JSON objects (port from Gentle AI) |
| `installer/internal/filemerge/writer.go` | Create | WriteFileAtomic (temp + rename, no symlink) |
| `installer/internal/opencode/merge.go` | Create | Read opencode.json → MergeJSONObjects → WriteFileAtomic |
| `installer/internal/opencode/ownership.go` | Create | Capture/restore default_agent via backup file |
| `installer/internal/skills/inject.go` | Create | Write embedded skills to ~/.config/opencode/skills/ |
| `installer/internal/prompts/inject.go` | Create | Write embedded prompts to ~/.config/opencode/prompts/ |
| `installer/internal/sdk/install.go` | Create | Create venv, pip install from wheel/GitHub |
| `installer/internal/state/state.go` | Create | Read/write ~/.quantlab/state.json |
| `installer/internal/journal/journal.go` | Create | Before-image capture + restore (port from Gentle AI) |
| `installer/internal/config/wizard.go` | Create | Bubbletea TUI wizard (SQX, JForex, API keys) |
| `installer/internal/config/config.go` | Create | Read/write ~/.quantlab/config.yaml |
| `installer/internal/update/update.go` | Create | Self-update: download, verify SHA-256, atomic swap |
| `installer/internal/model/types.go` | Create | ComponentID, SkillID, Config types |
| `installer/go.mod` | Create | Dependencies |
| `installer/assets/skills/` | Create | Embedded skill markdown files |
| `installer/assets/prompts/` | Create | Embedded prompt files |
| `installer/assets/templates/config.yaml` | Create | Default config template |
| `.github/workflows/release-installer.yml` | Create | GoReleaser build + release |
| `~/.config/opencode/opencode.json` | Modify | Deep merge: add quantlab-* agents |
| `~/.quantlab/state.json` | Create | Installation state (new file, not git-tracked) |
| `~/.quantlab/config.yaml` | Create | User config (0600 permissions, not git-tracked) |

## Interfaces / Contracts

```go
// pipeline/stages.go
type Stage string
const ( StagePrepare Stage = "prepare"; StageApply Stage = "apply"; StageRollback Stage = "rollback" )

type Step interface {
    ID() string
    Run() error
}
type RollbackStep interface {
    Step
    Rollback() error
}
type ProgressFunc func(ProgressEvent)
type StagePlan struct { Prepare []Step; Apply []Step }

// filemerge/json_merge.go
func MergeJSONObjects(baseJSON, overlayJSON []byte) ([]byte, error)
func InjectMarkdownSection(content, sectionID, sectionContent string) string

// filemerge/writer.go
type WriteResult struct { Changed bool; Created bool }
func WriteFileAtomic(path string, content []byte, perm fs.FileMode) (WriteResult, error)

// journal/journal.go
type Journal struct { roots []string; before map[string]*journalEntry }
func New(roots ...string) *Journal
func (j *Journal) Capture(path string) error
func (j *Journal) Write(path string, data []byte) (OwnedFile, error)
func (j *Journal) Remove(path string) (bool, error)
func (j *Journal) Restore() error

// state/state.go
type InstallState struct {
    Version     string      `json:"version"`
    InstallID   string      `json:"install_id"`
    InstalledAt time.Time   `json:"installed_at"`
    QLVersion   string      `json:"quantlab_version"`
    Components  []Component `json:"components"`
    ConfigHash  string      `json:"config_hash"`
    Agents      []string    `json:"opencode_agents_created"`
}
type Component struct {
    ID     string `json:"id"`
    Status string `json:"status"`
    Path   string `json:"path,omitempty"`
    Count  int    `json:"count,omitempty"`
}
func Path(homeDir string) string
func Read(homeDir string) (InstallState, error)
func Write(homeDir string, s InstallState) error

// opencode/ownership.go
func InstallPlan(settingsPath string) (*InstallPlan, error)
func (p *InstallPlan) Apply() (bool, error)
func UninstallPlan(settingsPath string) (*UninstallPlan, error)
func (p *UninstallPlan) Apply(cleaned []byte, settingsExist bool) (changed, removed bool, err error)
```

## Wizard Screens

| Screen | Fields | Validation |
|---|---|---|
| 1. SQX Path | `sqx.cli_path` text input | `os.Stat(path)` → must exist + executable |
| 2. JForex Host | `jforex.host`, `jforex.port` | TCP dial (warn, allow proceed) |
| 3. JForex Creds | `jforex.username`, `jforex.password` (masked) | Non-empty username |
| 4. API Keys | `api_keys.openai`, `api_keys.anthropic` (masked, toggleable) | Format check (sk-... prefix, warning) |
| 5. Confirm | Summary of all values | User confirms to proceed |

## State Schema

**`~/.quantlab/state.json`**:
```json
{
  "version": "1",
  "install_id": "a1b2c3d4-...",
  "installed_at": "2026-07-30T14:00:00Z",
  "quantlab_version": "0.1.0",
  "components": [
    {"id": "sdk", "status": "installed", "path": "~/.quantlab/venv"},
    {"id": "agents", "status": "installed", "count": 5},
    {"id": "skills", "status": "installed", "count": 3},
    {"id": "prompts", "status": "installed", "count": 2}
  ],
  "config_hash": "sha256-of-config",
  "opencode_agents_created": [
    "quantlab-orchestrator", "quantlab-run",
    "quantlab-monitor", "quantlab-compare", "quantlab-status"
  ]
}
```

**`~/.quantlab/config.yaml`** (0600):
```yaml
quantlab_version: "0.1.0"
sqx:
  cli_path: "/opt/SQX/sqcli"
jforex:
  host: "localhost"
  port: 19790
  username: "trader"
  password: ""
api_keys:
  openai: "sk-..."
  anthropic: "sk-..."
```

**Ownership marker** (`~/.quantlab/default-agent-backup.json`):
```json
{
  "previous_default_agent": "gentle-orchestrator",
  "previous_value_present": true,
  "captured_at": "2026-07-30T14:00:00Z"
}
```

## Dependencies

| Dependency | Version | Purpose |
|---|---|---|
| `github.com/charmbracelet/bubbletea` | v1 | TUI framework |
| `github.com/charmbracelet/bubbles` | v1 | TUI components (textinput, spinner, progress) |
| `github.com/charmbracelet/lipgloss` | v1 | TUI styling |
| `gopkg.in/yaml.v3` | v3 | Config YAML parsing |
| `golang.org/x/sys` | latest | Platform detection, file operations |

No runtime dependencies for end users — only Go build-time modules. Same pattern as Gentle AI.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | MergeJSONObjects, WriteFileAtomic, state.Read/Write, journal.Capture/Restore | Table-driven tests with temp dirs, golden files |
| Unit | Ownership install/uninstall cycle | Fake settings file, verify backup + restore |
| Unit | Config wizard validators | Validate SQX path, JForex TCP, API key format |
| Unit | SDK install wrapper | Mock exec.Command, verify venv + pip args |
| Integration | Pipeline with mock journal | Verify rollback restores before-images |
| Integration | Full install cycle in temp home | Create fake Python, fake opencode.json, run pipeline |
| E2E | Self-update with local binary | Build temp binary, serve fake release, verify swap |
| E2E | Cross-platform binary operations | Test on linux/amd64, linux/arm64 in CI |

## Threat Matrix

| Boundary | Applicability | Design response | Planned RED tests |
|---|---|---|---|
| Documentation-like paths | N/A — installer reads no user-provided scripts as documentation; config templates are embedded, not user-supplied | N/A | N/A |
| Git repository selection | N/A — installer never runs git -C or references git repos | N/A | N/A |
| Commit state | N/A — installer never creates commits | N/A | N/A |
| Push state | N/A — installer never pushes | N/A | N/A |
| PR commands | N/A — installer never creates PRs | N/A | N/A |

Shell-command safety (subprocess boundary): all `exec.Command` calls use Go's os/exec with explicit args (no shell wrappers). Python and pip invocations use pre-validated paths. The self-update binary is verified by SHA-256 before atomic swap. These are contract-level guarantees, not VCS-tool threats; they translate to `sdk.install` and `update.apply` validation steps in the pipeline, not threat-matrix rows.

## Migration / Rollout

No migration required — first release has no users. Initial `v0.1.0` binary published via GitHub Release. Future versions use `quantlab update` for self-upgrade.

## Open Questions

- [ ] Should the overlay force `default_agent` to `quantlab-orchestrator` or respect existing? Spec says "do not change" — confirmed.
- [ ] Wheel vs GitHub tag for SDK install: MVP uses GitHub release asset `.whl`, future PyPI
- [ ] Should `quantlab configure` be accessible standalone or only during install? Both: `quantlab configure` runs the wizard independently
- [ ] Is `quantlab dashboard` simply `open(URL)` or should it start a local server? The SDK already has a Flask dashboard — `open` the URL
