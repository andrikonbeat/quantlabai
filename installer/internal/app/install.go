package app

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/ogzuz/quantlab/internal/config"
	"github.com/ogzuz/quantlab/internal/journal"
	"github.com/ogzuz/quantlab/internal/model"
	"github.com/ogzuz/quantlab/internal/opencode"
	"github.com/ogzuz/quantlab/internal/pipeline"
	"github.com/ogzuz/quantlab/internal/sdk"
	"github.com/ogzuz/quantlab/internal/state"
	"github.com/ogzuz/quantlab/internal/tui/wizard"
)

// cmdInstall implements the `quantlab install` command. It runs the full
// installation pipeline: validate prerequisites → run wizard → install SDK
// → merge agents → install skills/prompts → write state.
func cmdInstall(w io.Writer) error {
	home, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("home dir: %w", err)
	}

	qlDir := config.StateDir(home)
	st, err := state.LoadOrInit(qlDir)
	if err != nil {
		return fmt.Errorf("load state: %w", err)
	}

	// Check if already installed
	if st.HasComponent(model.ComponentSDK) {
		fmt.Fprintf(w, "QuantLab is already installed. Run 'quantlab sync' to update components.\n")
		return nil
	}

	// Check for journal residue: state exists but has no components (interrupted install)
	if st.StateFileExists() && !st.HasAnyComponent() {
		fmt.Fprintf(w, "⚠ Detected incomplete installation from a previous run.\n")
		fmt.Fprintf(w, "  Running 'quantlab uninstall' first to clean up...\n")
		if err := cmdUninstall(w); err != nil {
			return fmt.Errorf("cleanup failed: %w", err)
		}
		// Reload state after uninstall
		st, err = state.LoadOrInit(qlDir)
		if err != nil {
			return fmt.Errorf("reload state: %w", err)
		}
	}

	// --- Step 1: Validate prerequisites ---
	fmt.Fprintf(w, "\n🔍 Checking prerequisites...\n")

	if err := sdk.CheckPython311OrLater(); err != nil {
		return fmt.Errorf("prerequisite check failed: %w\nPython 3.11+ is required. Get it at https://python.org", err)
	}
	fmt.Fprintf(w, "  ✓ Python 3.11+\n")

	opencodePath := opencode.DefaultSettingsPath()
	if _, err := os.Stat(opencodePath); os.IsNotExist(err) {
		fmt.Fprintf(w, "  ⚠ OpenCode not found at %s\n", opencodePath)
		fmt.Fprintf(w, "    OpenCode is recommended for full QuantLab functionality.\n")
	}

	// --- Step 2: Run wizard ---
	fmt.Fprintf(w, "\n📋 Running configuration wizard...\n")

	wizModel, err := runWizard()
	if err != nil {
		return fmt.Errorf("wizard: %w", err)
	}

	apiKey, modelChoice, sdkPath := wizModel.Result()
	if apiKey == "" {
		fmt.Fprintf(w, "\nWizard cancelled. No changes made.\n")
		return nil
	}
	fmt.Fprintf(w, "  ✓ Configuration collected\n")

	// --- Step 3: Build and run pipeline ---
	fmt.Fprintf(w, "\n🚀 Installing QuantLab AI...\n\n")

	j := journal.New(qlDir, filepath.Dir(opencodePath))
	plan := buildInstallPlan(qlDir, opencodePath, apiKey, modelChoice, sdkPath, st, j)

	progress := func(ev pipeline.ProgressEvent) {
		status := "⋯"
		switch ev.Status {
		case "running":
			status = "→"
		case "completed":
			status = "✓"
		case "failed":
			status = "✗"
		}
		fmt.Fprintf(w, "  %s %s\n", status, ev.StepID)
	}

	if err := pipeline.Run(plan, progress); err != nil {
		fmt.Fprintf(w, "\n❌ Installation failed: %v\n", err)
		fmt.Fprintf(w, "  Rollback completed. System is unchanged.\n")
		return err
	}

	fmt.Fprintf(w, "\n✅ QuantLab AI installed successfully!\n")
	fmt.Fprintf(w, "  Run 'quantlab status' to verify.\n")
	return nil
}

// runWizard starts the config wizard TUI and returns the resulting model.
func runWizard() (*wizard.Model, error) {
	m := wizard.NewModel()
	p := tea.NewProgram(m)
	final, err := p.Run()
	if err != nil {
		return nil, err
	}
	finalModel, ok := final.(wizard.Model)
	if !ok {
		return nil, fmt.Errorf("unexpected model type: %T", final)
	}
	return &finalModel, nil
}

// buildInstallPlan constructs the pipeline plan for installation.
func buildInstallPlan(qlDir, opencodePath, apiKey, modelChoice, sdkPath string, st *state.State, j *journal.Journal) pipeline.StagePlan {
	steps := []pipeline.Step{
		// Step 1: Create ~/.quantlab/ directory
		&simpleStep{
			id: "Create .quantlab directory",
			fn: func() error {
				return os.MkdirAll(qlDir, 0o755)
			},
			rollback: func() error {
				os.RemoveAll(qlDir)
				return nil
			},
		},

		// Step 2: Write SDK config (journal captures before-image for rollback)
		&writeStep{
			id:      "Write SDK config",
			path:    filepath.Join(qlDir, "sdk-config.yaml"),
			journal: j,
			fn: func() ([]byte, os.FileMode, error) {
				cfg := sdk.DefaultSDKConfig()
				cfg.APIKey = apiKey
				cfg.Model = modelChoice
				data, err := json.MarshalIndent(cfg, "", "  ")
				if err != nil {
					return nil, 0, err
				}
				return append(data, '\n'), 0o600, nil
			},
		},

		// Step 3: Create venv and install SDK
		&simpleStep{
			id: "Install SDK",
			fn: func() error {
				opts := sdk.InstallOptions{Upgrade: true}
				if sdkPath != "auto" {
					opts.SourceDir = sdkPath
				}
				_, err := sdk.InstallSDK(opts)
				return err
			},
		},

		// Step 4: Merge opencode.json overlay (journal captures before-image)
		&simpleStep{
			id: "Merge OpenCode agents",
			fn: func() error {
				// Capture before modifying opencode.json
				j.Capture(opencodePath)
				return mergeOpenCodeAgents(opencodePath)
			},
			rollback: func() error {
				return j.Restore()
			},
		},

		// Step 5: Install skills — track installed files for rollback
		&simpleStep{
			id: "Install skills",
			fn: func() error {
				skillsDir := opencode.DefaultSkillsDir()
				installed, err := opencode.InstallSkills(assetFS(), skillsDir)
				if err != nil {
					return err
				}
				// Capture installed files for rollback
				for _, f := range installed {
					j.Capture(f)
				}
				return nil
			},
			rollback: func() error {
				return j.Restore()
			},
		},

		// Step 6: Install prompts — track installed files for rollback
		&simpleStep{
			id: "Install prompts",
			fn: func() error {
				promptsDir := opencode.DefaultPromptsDir()
				installed, err := opencode.InstallPrompts(assetFS(), promptsDir)
				if err != nil {
					return err
				}
				// Capture installed files for rollback
				for _, f := range installed {
					j.Capture(f)
				}
				return nil
			},
			rollback: func() error {
				return j.Restore()
			},
		},

		// Step 7: Write ownership marker (journal captures before-image)
		&simpleStep{
			id: "Set ownership marker",
			fn: func() error {
				plan, err := opencode.PrepareInstall(opencodePath)
				if err != nil {
					return err
				}
				_, err = plan.Apply()
				return err
			},
		},

		// Step 8: Write state.json (journal captures before-image)
		&writeStep{
			id:      "Write state.json",
			path:    filepath.Join(qlDir, "state.json"),
			journal: j,
			fn: func() ([]byte, os.FileMode, error) {
				st.MarkInstalled("install-"+modelChoice, "0.1.0")
				st.AddComponent(model.ComponentSDK, "installed", filepath.Join(qlDir, "venv"), 0)
				st.AddComponent(model.ComponentOpenCodeAgents, "installed", "", 4)
				st.AddComponent(model.ComponentSkills, "installed", "", 3)
				st.AddComponent(model.ComponentPrompts, "installed", "", 2)
				st.AddComponent(model.ComponentConfig, "installed", filepath.Join(qlDir, "sdk-config.yaml"), 0)
				data, err := json.MarshalIndent(st, "", "  ")
				if err != nil {
					return nil, 0, err
				}
				return append(data, '\n'), 0o644, nil
			},
		},
	}

	return pipeline.StagePlan{Apply: steps}
}

// mergeOpenCodeAgents reads opencode.json, merges QuantLab agents, and writes
// the result atomically.
func mergeOpenCodeAgents(opencodePath string) error {
	cfg, err := opencode.ReadSettingsOrEmpty(opencodePath)
	if err != nil {
		return fmt.Errorf("read opencode settings: %w", err)
	}

	changed, err := opencode.MergeAgents(cfg)
	if err != nil {
		return fmt.Errorf("merge agents: %w", err)
	}
	if !changed {
		return nil
	}

	_, err = opencode.WriteSettings(opencodePath, cfg)
	if err != nil {
		return fmt.Errorf("write opencode settings: %w", err)
	}

	return nil
}

// ---- pipeline step types ----

// simpleStep runs a function with optional rollback support.
type simpleStep struct {
	id       string
	fn       func() error
	rollback func() error
}

func (s *simpleStep) ID() string     { return s.id }
func (s *simpleStep) Run() error     { return s.fn() }
func (s *simpleStep) Rollback() error {
	if s.rollback != nil {
		return s.rollback()
	}
	return nil
}

// writeStep uses the journal to write a file atomically with rollback support.
type writeStep struct {
	id      string
	path    string
	fn      func() ([]byte, os.FileMode, error)
	journal *journal.Journal
}

func (s *writeStep) ID() string { return s.id }

func (s *writeStep) Run() error {
	data, mode, err := s.fn()
	if err != nil {
		return err
	}
	if s.journal == nil {
		s.journal = journal.New()
	}
	_, err = s.journal.WriteWithMode(s.path, data, mode)
	return err
}

func (s *writeStep) Rollback() error {
	if s.journal == nil {
		return nil
	}
	return s.journal.Restore()
}
