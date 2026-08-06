package app

import (
	"fmt"
	"io"
	"os"
	"path/filepath"

	"github.com/ogzuz/quantlab/internal/config"
	"github.com/ogzuz/quantlab/internal/model"
	"github.com/ogzuz/quantlab/internal/opencode"
	"github.com/ogzuz/quantlab/internal/pipeline"
	"github.com/ogzuz/quantlab/internal/state"
	"github.com/ogzuz/quantlab/internal/tui/confirm"
)

// cmdUninstall implements the `quantlab uninstall` command. Removes all
// QuantLab components: agents, skills, prompts, SDK, and state.
func cmdUninstall(w io.Writer) error {
	home, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("home dir: %w", err)
	}

	qlDir := config.StateDir(home)

	// Check if QuantLab is installed
	st, err := state.LoadOrInit(qlDir)
	if err != nil {
		return fmt.Errorf("load state: %w", err)
	}

	if !st.HasComponent(model.ComponentSDK) && len(st.Agents) == 0 {
		fmt.Fprintf(w, "QuantLab is not installed. Nothing to uninstall.\n")
		return nil
	}

	// Ask for confirmation
	fmt.Fprintf(w, "\n⚠️  This will remove QuantLab AI and all its components.\n")
	confirmed, err := confirm.RunConfirm("Are you sure you want to uninstall?")
	if err != nil {
		return fmt.Errorf("confirm dialog: %w", err)
	}
	if !confirmed {
		fmt.Fprintf(w, "Uninstall cancelled.\n")
		return nil
	}

	opencodePath := opencode.DefaultSettingsPath()

	fmt.Fprintf(w, "\n🗑️  Uninstalling QuantLab AI...\n\n")

	plan := buildUninstallPlan(qlDir, opencodePath, st)

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
		fmt.Fprintf(w, "\n❌ Uninstall encountered errors: %v\n", err)
		return err
	}

	fmt.Fprintf(w, "\n✅ QuantLab AI has been removed.\n")
	return nil
}

// buildUninstallPlan constructs the pipeline for uninstallation.
func buildUninstallPlan(qlDir, opencodePath string, st *state.State) pipeline.StagePlan {
	steps := []pipeline.Step{
		// Step 1: Restore default_agent ownership
		&simpleStep{
			id: "Restore default_agent",
			fn: func() error {
				plan, err := opencode.PrepareUninstall(opencodePath)
				if err != nil {
					return fmt.Errorf("prepare ownership: %w", err)
				}
				_, _, err = plan.Apply()
				return err
			},
		},

		// Step 2: Remove agents from opencode.json
		&simpleStep{
			id: "Remove QuantLab agents",
			fn: func() error {
				cfg, err := opencode.ReadSettingsOrEmpty(opencodePath)
				if err != nil {
					return fmt.Errorf("read settings: %w", err)
				}
				changed, err := opencode.RemoveAgents(cfg)
				if err != nil {
					return fmt.Errorf("remove agents: %w", err)
				}
				if !changed {
					return nil
				}
				_, err = opencode.WriteSettings(opencodePath, cfg)
				return err
			},
		},

		// Step 3: Remove skills
		&simpleStep{
			id: "Remove skills",
			fn: func() error {
				skillsDir := opencode.DefaultSkillsDir()
				_, err := opencode.RemoveSkills(skillsDir)
				return err
			},
		},

		// Step 4: Remove prompts
		&simpleStep{
			id: "Remove prompts",
			fn: func() error {
				promptsDir := opencode.DefaultPromptsDir()
				_, err := opencode.RemovePrompts(promptsDir)
				return err
			},
		},

		// Step 5: Remove SDK venv
		&simpleStep{
			id: "Remove SDK venv",
			fn: func() error {
				venvPath := filepath.Join(qlDir, "venv")
				if _, err := os.Stat(venvPath); err == nil {
					return os.RemoveAll(venvPath)
				}
				return nil
			},
		},

		// Step 6: Remove .quantlab directory
		&simpleStep{
			id: "Remove .quantlab directory",
			fn: func() error {
				if _, err := os.Stat(qlDir); err == nil {
					return os.RemoveAll(qlDir)
				}
				return nil
			},
		},
	}

	return pipeline.StagePlan{Apply: steps}
}
