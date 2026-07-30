package app

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/ogzuz/quantlab/internal/config"
	"github.com/ogzuz/quantlab/internal/model"
	"github.com/ogzuz/quantlab/internal/opencode"
	"github.com/ogzuz/quantlab/internal/sdk"
	"github.com/ogzuz/quantlab/internal/state"
)

// cmdStatus implements the `quantlab status` command. It displays the current
// installation state, component health, and detects inconsistencies.
func cmdStatus(w io.Writer) error {
	home, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("home dir: %w", err)
	}

	qlDir := config.StateDir(home)
	opencodePath := opencode.DefaultSettingsPath()

	// --- Gather status ---
	fmt.Fprintf(w, "\n")
	printHeader(w, "QuantLab AI — Status")
	fmt.Fprintf(w, "\n")

	// Version
	printSection(w, "Version", fmt.Sprintf("%s", Version))

	// Load state
	st, stateErr := state.LoadOrInit(qlDir)
	if stateErr != nil {
		printSection(w, "Error", fmt.Sprintf("Cannot load state: %v", stateErr))
	}

	// Installation status
	installed := st != nil && st.HasComponent(model.ComponentSDK)
	if installed {
		printSection(w, "Installation", "✅ Installed")
		if st.InstalledAt.IsZero() {
			printSection(w, "Installed at", "Unknown")
		} else {
			printSection(w, "Installed at", st.InstalledAt.Format(time.RFC1123))
		}
		printSection(w, "Install ID", st.InstallID)
	} else {
		printSection(w, "Installation", "❌ Not installed")
	}

	fmt.Fprintf(w, "\n")

	// Components
	if st != nil && len(st.Components) > 0 {
		printHeader(w, "Components")
		for _, comp := range st.Components {
			statusIcon := "✅"
			if comp.Status != "installed" {
				statusIcon = "⚠️"
			}
			extra := ""
			if comp.Path != "" {
				extra = fmt.Sprintf("  (%s)", comp.Path)
			}
			if comp.Count > 0 {
				extra = fmt.Sprintf("  (%d items)", comp.Count)
			}
			printSection(w, fmt.Sprintf("  %s %s", statusIcon, comp.ID), strings.TrimSpace(extra))
		}
		fmt.Fprintf(w, "\n")
	}

	// SDK
	printHeader(w, "SDK")
	sdkInfo, sdkErr := sdk.DetectInstalledSDK()
	if sdkErr != nil || !sdkInfo.Installed {
		printSection(w, "  Status", "❌ Not detected")
	} else {
		printSection(w, "  Status", "✅ Installed")
		printSection(w, "  Version", sdkInfo.Version)
		printSection(w, "  Path", sdkInfo.Path)
		if sdkInfo.VenvPath != "" {
			printSection(w, "  Venv", sdkInfo.VenvPath)
		}
	}
	fmt.Fprintf(w, "\n")

	// OpenCode integration
	printHeader(w, "OpenCode Integration")
	ocCfg, ocErr := opencode.ReadSettingsOrEmpty(opencodePath)
	if ocErr != nil {
		printSection(w, "  Status", fmt.Sprintf("⚠ Error reading: %v", ocErr))
	} else {
		defaultAgent, hasDefault := ocCfg.GetDefaultAgent()
		if hasDefault {
			printSection(w, "  Default Agent", defaultAgent)
		} else {
			printSection(w, "  Default Agent", "Not set")
		}

		// Count QuantLab agents
		qlAgentCount := 0
		for _, name := range opencode.QuantLabAgentNames() {
			if ocCfg.HasAgent(name) {
				qlAgentCount++
			}
		}
		if qlAgentCount > 0 {
			printSection(w, "  QuantLab Agents", fmt.Sprintf("✅ %d installed", qlAgentCount))
		} else {
			printSection(w, "  QuantLab Agents", "⚠ None found")
		}
	}
	fmt.Fprintf(w, "\n")

	// Skills and prompts
	printHeader(w, "Assets")
	skillsDir := opencode.DefaultSkillsDir()
	promptsDir := opencode.DefaultPromptsDir()

	skillCount := countQuantLabDirs(skillsDir)
	promptCount := countFiles(promptsDir)

	if skillCount > 0 {
		printSection(w, "  Skills", fmt.Sprintf("✅ %d installed", skillCount))
	} else {
		printSection(w, "  Skills", "⚠ None found")
	}
	if promptCount > 0 {
		printSection(w, "  Prompts", fmt.Sprintf("✅ %d installed", promptCount))
	} else {
		printSection(w, "  Prompts", "⚠ None found")
	}
	fmt.Fprintf(w, "\n")

	// Config check
	printHeader(w, "Configuration")
	cfgPath := config.ConfigPath(home)
	cfg, cfgErr := config.ReadConfig(cfgPath)
	if cfgErr != nil {
		printSection(w, "  Config", fmt.Sprintf("⚠ Error: %v", cfgErr))
	} else {
		if cfg.APIKeys.OpenAI != "" || cfg.APIKeys.Anthropic != "" {
			printSection(w, "  API Keys", "✅ Configured")
			if cfg.APIKeys.OpenAI != "" {
				printSection(w, "    OpenAI", maskKey(cfg.APIKeys.OpenAI))
			}
			if cfg.APIKeys.Anthropic != "" {
				printSection(w, "    Anthropic", maskKey(cfg.APIKeys.Anthropic))
			}
		} else {
			printSection(w, "  API Keys", "⚠ Not configured")
		}
		printSection(w, "  SQX Path", cfg.SQX.CLIPath)
	}
	fmt.Fprintf(w, "\n")

	// Overall health
	printHeader(w, "Overall Health")
	issues := detectIssues(st, sdkInfo, ocCfg, skillCount, promptCount, qlDir)
	if len(issues) == 0 {
		if installed {
			printSection(w, "  Status", "✅ All systems ready")
		} else {
			printSection(w, "  Status", "⏹  Not installed")
		}
	} else {
		for _, issue := range issues {
			printSection(w, "  ⚠", issue)
		}
	}
	fmt.Fprintf(w, "\n")

	return nil
}

// detectIssues checks for common problems and inconsistencies.
func detectIssues(st *state.State, sdkInfo *sdk.SDKInfo, ocCfg *opencode.Config, skillCount, promptCount int, qlDir string) []string {
	var issues []string

	if st == nil {
		issues = append(issues, "State file could not be loaded")
		return issues
	}

	// Check for installed components in state but missing on disk
	if st.HasComponent(model.ComponentSkills) && skillCount == 0 {
		issues = append(issues, "Skills recorded in state but not found on disk")
	}
	if st.HasComponent(model.ComponentPrompts) && promptCount == 0 {
		issues = append(issues, "Prompts recorded in state but not found on disk")
	}

	// Check for orphaned agents (agents in opencode.json but not in state)
	if ocCfg != nil {
		stateAgentMap := make(map[string]bool)
		for _, a := range st.Agents {
			stateAgentMap[a] = true
		}
		for _, name := range opencode.QuantLabAgentNames() {
			if ocCfg.HasAgent(name) && !stateAgentMap[name] {
				issues = append(issues, fmt.Sprintf("Orphaned agent %q found (not in state)", name))
			}
		}
	}

	// Check for missing SDK when other components exist
	if st.HasComponent(model.ComponentSDK) && (sdkInfo == nil || !sdkInfo.Installed) {
		issues = append(issues, "SDK recorded as installed but not detected by pip")
	}

	// Check for incomplete state (state file exists but no components)
	if _, err := os.Stat(qlDir); err == nil {
		entries, _ := os.ReadDir(qlDir)
		hasStateFile := false
		for _, e := range entries {
			if e.Name() == "state.json" {
				hasStateFile = true
				break
			}
		}
		if hasStateFile && len(st.Components) == 0 && len(st.Agents) == 0 {
			issues = append(issues, "Incomplete installation detected (state exists but no components recorded)")
		}
	}

	// Check for journal residue (incomplete apply from a previous run)
	journalPath := filepath.Join(qlDir, ".journal")
	if _, err := os.Stat(journalPath); err == nil {
		issues = append(issues, "Residual journal found — a previous operation may have been interrupted")
	}

	return issues
}

// countQuantLabDirs counts directories with "quantlab-" prefix in the given path.
func countQuantLabDirs(dir string) int {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return 0
	}
	count := 0
	for _, e := range entries {
		if e.IsDir() && strings.HasPrefix(e.Name(), "quantlab-") {
			count++
		}
	}
	return count
}

// countFiles counts non-directory entries in the given path.
func countFiles(dir string) int {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return 0
	}
	count := 0
	for _, e := range entries {
		if !e.IsDir() {
			count++
		}
	}
	return count
}

// maskKey shows only the first 4 and last 4 characters of a key.
func maskKey(key string) string {
	if len(key) <= 8 {
		return "••••••••"
	}
	return key[:4] + "••••" + key[len(key)-4:]
}

// printHeader prints a section header.
func printHeader(w io.Writer, title string) {
	fmt.Fprintf(w, "━━━ %s ━━━\n", title)
}

// printSection prints a key-value status line.
func printSection(w io.Writer, key, value string) {
	fmt.Fprintf(w, "  %-22s  %s\n", key, value)
}
