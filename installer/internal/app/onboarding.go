package app

import (
	"fmt"
	"io"
	"os"
		"time"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/andrikonbeat/quantlabai/internal/config"
	"github.com/andrikonbeat/quantlabai/internal/opencode"
	"github.com/andrikonbeat/quantlabai/internal/state"
	"github.com/andrikonbeat/quantlabai/internal/tui/onboarding"
)

// runOnboardingProgram runs the interactive TUI and returns the collected
// result. It is a package variable so tests can bypass the interactive loop.
var runOnboardingProgram = func(m *onboarding.Model) (onboarding.Result, error) {
	prog := tea.NewProgram(m, tea.WithAltScreen())
	if _, err := prog.Run(); err != nil {
		return onboarding.Result{}, err
	}
	return m.Result(), nil
}

// cmdOnboarding runs the interactive onboarding flow. Tool installation is
// owned by the TUI; this command only persists the resulting choices.
func cmdOnboarding(w io.Writer, args []string) error {
	home, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("home dir: %w", err)
	}
	stateDir := stateDirFlag(args)
	qlDir := config.StateDir(home, stateDir)

	st, err := state.LoadOrInit(qlDir)
	if err != nil {
		return fmt.Errorf("load state: %w", err)
	}

	// Parse --agent-driven flag
	agentDriven := false
	for _, arg := range args {
		if arg == "--agent-driven" {
			agentDriven = true
			break
		}
	}

	model := onboarding.NewModel(agentDriven)
	res, err := runOnboardingProgram(&model)
	if err != nil {
		return fmt.Errorf("onboarding TUI: %w", err)
	}

	if err := applyOnboardingResult(w, home, stateDir, res); err != nil {
		return err
	}

	// Mark onboarding completed.
	st.OnboardingCompleted = true
	now := time.Now().UTC()
	st.OnboardingCompletedAt = &now
	st.MarkInstalled("onboarding", "complete")
	if _, err := st.Save(); err != nil {
		return fmt.Errorf("save state: %w", err)
	}

	fmt.Fprintf(w, "\n✅ Onboarding completado.\n")
	fmt.Fprintf(w, "  Ahora ejecutá 'quantlab status' para verificar tu instalación.\n")
	return nil
}

// applyOnboardingResult writes the collected config, prints tool readiness
// from the TUI result, and applies the primary-agent selection. It no longer
// installs tools — the TUI owns install execution.
func applyOnboardingResult(w io.Writer, home, stateDir string, res onboarding.Result) error {
	cfg, err := config.ReadConfig(config.ConfigPath(home, stateDir))
	if err != nil {
		return fmt.Errorf("read config: %w", err)
	}

	if res.SQX.InstallPath != "" {
		cfg.SQX.InstallPath = res.SQX.InstallPath
	}
	if res.JForex.InstallPath != "" {
		cfg.JForex.InstallPath = res.JForex.InstallPath
	}
	if res.JForex.AccountMode != "" {
		cfg.JForex.AccountMode = res.JForex.AccountMode
	}
	if res.JForex.Username != "" {
		cfg.JForex.Username = res.JForex.Username
	}
	if res.JForex.Password != "" {
		cfg.JForex.Password = res.JForex.Password
	}
	if err := config.WriteConfig(config.ConfigPath(home, stateDir), cfg); err != nil {
		return fmt.Errorf("write config: %w", err)
	}

	fmt.Fprintf(w, "\nHerramientas:\n")
	fmt.Fprintf(w, "  %s OpenCode\n", readinessMark(res.OpenCodeReady))
	fmt.Fprintf(w, "  %s gentle-ai\n", readinessMark(res.GentleAIReady))

	// Set primary agent if chosen.
	if res.PrimaryAgent != "" && res.PrimaryAgent != "quantlab-orchestrator" {
		ocCfg, err := opencode.ReadSettings(opencode.DefaultSettingsPath())
		if err != nil {
			fmt.Fprintf(w, "  ⚠ No se pudo leer config de OpenCode: %v\n", err)
		} else {
			ocCfg.SetDefaultAgent(res.PrimaryAgent)
			if _, err := opencode.WriteSettings(opencode.DefaultSettingsPath(), ocCfg); err != nil {
				fmt.Fprintf(w, "  ⚠ No se pudo cambiar el agente primario: %v\n", err)
			} else {
				fmt.Fprintf(w, "  ✓ Agente primario: %s\n", res.PrimaryAgent)
			}
		}
	}
	return nil
}

func readinessMark(ready bool) string {
	if ready {
		return "✓"
	}
	return "⚠"
}
