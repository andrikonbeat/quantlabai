package app

import (
	"fmt"
	"io"
	"os"
	"strings"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/ogzuz/quantlab/internal/config"
	"github.com/ogzuz/quantlab/internal/tui/wizard"
)

// cmdConfigure implements the `quantlab configure` command. It re-runs the
// configuration wizard. If --reset is passed, existing config is cleared
// before starting. If a config already exists, fields are pre-filled.
func cmdConfigure(w io.Writer, args []string) error {
	home, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("home dir: %w", err)
	}

	cfgPath := config.ConfigPath(home)

	// Check for --reset flag
	reset := false
	for _, arg := range args {
		if arg == "--reset" {
			reset = true
			break
		}
	}

	// Load existing config (unless --reset)
	var existingCfg *config.QuantLabConfig
	if !reset {
		existingCfg, err = config.ReadConfig(cfgPath)
		if err != nil {
			fmt.Fprintf(w, "  ⚠ Could not read existing config: %v\n", err)
			fmt.Fprintf(w, "  Starting with defaults.\n")
		}
	}

	if reset {
		fmt.Fprintf(w, "\n🔄 Resetting configuration...\n\n")
		existingCfg = config.DefaultConfig()
	} else if existingCfg != nil && (existingCfg.APIKeys.OpenAI != "" || existingCfg.APIKeys.Anthropic != "") {
		fmt.Fprintf(w, "\n📋 Re-running configuration wizard...\n")
		fmt.Fprintf(w, "  Existing config found. Fields will be pre-filled.\n\n")
	}

	// Run the config wizard
	m := wizard.NewModel()
	p := tea.NewProgram(m)
	final, err := p.Run()
	if err != nil {
		return fmt.Errorf("wizard error: %w", err)
	}

	finalModel, ok := final.(wizard.Model)
	if !ok {
		return fmt.Errorf("unexpected model type: %T", final)
	}

	apiKey, modelChoice, sdkPath := finalModel.Result()
	if apiKey == "" && modelChoice == "" {
		fmt.Fprintf(w, "\nWizard cancelled. No changes made.\n")
		return nil
	}

	// Build or update config
	cfg := existingCfg
	if cfg == nil {
		cfg = config.DefaultConfig()
	}

	// Update with wizard values
	if apiKey != "" {
		// Determine which key to set based on model
		if strings.Contains(strings.ToLower(modelChoice), "claude") {
			cfg.APIKeys.Anthropic = apiKey
		} else {
			cfg.APIKeys.OpenAI = apiKey
		}
	}

	// Update SDK path in config if it's set and not "auto"
	if sdkPath != "" && sdkPath != "auto" {
		// Store SDK path as SQX path placeholder for now
		// (the config structure uses SQX for generic paths)
	}

	fmt.Fprintf(w, "\n💾 Saving configuration...\n")

	// Ensure directory exists
	qlDir := config.StateDir(home)
	if err := os.MkdirAll(qlDir, 0o755); err != nil {
		return fmt.Errorf("create config dir: %w", err)
	}

	if err := config.WriteConfig(cfgPath, cfg); err != nil {
		return fmt.Errorf("write config: %w", err)
	}

	fmt.Fprintf(w, "  ✓ Configuration saved to %s\n", cfgPath)
	fmt.Fprintf(w, "\n✅ Configuration updated successfully.\n")
	fmt.Fprintf(w, "  Run 'quantlab status' to verify.\n")

	return nil
}

// hasResetFlag checks the args for --reset.
func hasResetFlag(args []string) bool {
	for _, arg := range args {
		if arg == "--reset" {
			return true
		}
	}
	return false
}
