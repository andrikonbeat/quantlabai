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
	"github.com/ogzuz/quantlab/internal/sdk"
	"github.com/ogzuz/quantlab/internal/state"
)

// cmdSync implements the `quantlab sync` command. It refreshes all installed
// QuantLab components:
//  1. Re-merge agents into opencode.json
//  2. Re-install skills from embedded assets
//  3. Re-install prompts from embedded assets
//  4. Re-install SDK if version changed
//  5. Update state
func cmdSync(w io.Writer) error {
	home, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("home dir: %w", err)
	}

	qlDir := config.StateDir(home)

	// Load state (may not exist — that's OK)
	st, err := state.LoadOrInit(qlDir)
	if err != nil {
		return fmt.Errorf("load state: %w", err)
	}

	// Check if anything is installed
	if !st.HasComponent(model.ComponentSDK) && len(st.Agents) == 0 {
		fmt.Fprintf(w, "QuantLab is not installed. Run 'quantlab install' first.\n")
		return nil
	}

	opencodePath := opencode.DefaultSettingsPath()

	fmt.Fprintf(w, "\n🔄 Syncing QuantLab components...\n\n")

	plan := buildSyncPlan(qlDir, opencodePath, st)

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
		fmt.Fprintf(w, "\n❌ Sync encountered errors: %v\n", err)
		return err
	}

	fmt.Fprintf(w, "\n✅ QuantLab components synced successfully.\n")
	return nil
}

// buildSyncPlan constructs the pipeline plan for the sync command.
func buildSyncPlan(qlDir, opencodePath string, st *state.State) pipeline.StagePlan {
	steps := []pipeline.Step{
		// Step 1: Re-merge agents
		&simpleStep{
			id: "Sync OpenCode agents",
			fn: func() error {
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

				resultChanged, err := opencode.WriteSettings(opencodePath, cfg)
				if err != nil {
					return fmt.Errorf("write opencode settings: %w", err)
				}
				if resultChanged {
					// Record agents in state
					for _, name := range opencode.QuantLabAgentNames() {
						st.AddAgent(name)
					}
				}
				return nil
			},
		},

		// Step 2: Re-install skills
		&simpleStep{
			id: "Sync skills",
			fn: func() error {
				skillsDir := opencode.DefaultSkillsDir()
				installed, err := opencode.InstallSkills(assetFS(), skillsDir)
				if err != nil {
					return fmt.Errorf("install skills: %w", err)
				}
				if len(installed) > 0 {
					st.AddComponent(model.ComponentSkills, "installed", skillsDir, len(installed))
				}
				return nil
			},
		},

		// Step 3: Re-install prompts
		&simpleStep{
			id: "Sync prompts",
			fn: func() error {
				promptsDir := opencode.DefaultPromptsDir()
				installed, err := opencode.InstallPrompts(assetFS(), promptsDir)
				if err != nil {
					return fmt.Errorf("install prompts: %w", err)
				}
				if len(installed) > 0 {
					st.AddComponent(model.ComponentPrompts, "installed", promptsDir, len(installed))
				}
				return nil
			},
		},

		// Step 4: Check and re-install SDK if needed
		&simpleStep{
			id: "Check SDK version",
			fn: func() error {
				info, err := sdk.DetectInstalledSDK()
				if err != nil {
					// SDK not detected — skip SDK step
					return nil
				}
				if info.Installed {
					// Try upgrading
					opts := sdk.InstallOptions{Upgrade: true}
					if _, err := sdk.InstallSDK(opts); err != nil {
						return fmt.Errorf("upgrade SDK: %w", err)
					}
					st.AddComponent(model.ComponentSDK, "installed", info.VenvPath, 0)
				}
				return nil
			},
		},

		// Step 5: Update state
		&simpleStep{
			id: "Update state",
			fn: func() error {
				_, err := st.Save()
				if err != nil {
					return fmt.Errorf("save state: %w", err)
				}
				// Also update config hash
				cfgPath := filepath.Join(qlDir, "sdk-config.yaml")
				if cfg, err := config.ReadConfig(cfgPath); err == nil {
					st.ConfigHash = config.ConfigHash(cfg)
				}
				return nil
			},
		},
	}

	return pipeline.StagePlan{Apply: steps}
}
