package app

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/andrikonbeat/quantlabai/internal/config"
	"github.com/andrikonbeat/quantlabai/internal/opencode"
	"github.com/andrikonbeat/quantlabai/internal/state"
	"github.com/andrikonbeat/quantlabai/internal/tools"
	"github.com/andrikonbeat/quantlabai/internal/tui/onboarding"
)

// cmdOnboarding runs the interactive onboarding flow.
func cmdOnboarding(w io.Writer, args []string) error {
	home, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("home dir: %w", err)
	}
	qlDir := filepath.Join(home, ".quantlab")

	st, err := state.LoadOrInit(qlDir)
	if err != nil {
		return fmt.Errorf("load state: %w", err)
	}

	model := onboarding.NewModel()
	prog := tea.NewProgram(&model)
	if _, err := prog.Run(); err != nil {
		return fmt.Errorf("onboarding TUI: %w", err)
	}
	res := model.Result()

	// Write config if SQX/JForex were provided.
	cfg, err := config.ReadConfig(config.ConfigPath(home))
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
	if err := config.WriteConfig(config.ConfigPath(home), cfg); err != nil {
		return fmt.Errorf("write config: %w", err)
	}

	// Install consented tools.
	if res.Consent.OpenCode {
		fmt.Fprintf(w, "\n📦 Instalando OpenCode...\n")
		display, err := tools.InstallOpenCode(home)
		if display != "" {
			fmt.Fprintf(w, "  ⚠ %s\n", display)
		}
		if err != nil {
			fmt.Fprintf(w, "  ⚠ OpenCode: %v\n", err)
		} else {
			fmt.Fprintf(w, "  ✓ OpenCode instalado\n")
		}
	}

	if res.Consent.GentleAI {
		fmt.Fprintf(w, "\n📦 Instalando gentle-ai...\n")
		display, err := tools.InstallGentleAI(home)
		if display != "" {
			fmt.Fprintf(w, "  ⚠ %s\n", display)
		}
		if err != nil {
			fmt.Fprintf(w, "  ⚠ gentle-ai: %v\n", err)
		} else {
			fmt.Fprintf(w, "  ✓ gentle-ai instalado\n")
		}
	}

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
