package app

import (
	"bytes"
	"path/filepath"
	"strings"
	"testing"

	"github.com/andrikonbeat/quantlabai/internal/config"
	"github.com/andrikonbeat/quantlabai/internal/state"
	"github.com/andrikonbeat/quantlabai/internal/tui/onboarding"
)

func TestOnboardingCommandRegistered(t *testing.T) {
	cmd := "onboarding"
	found := false
	for _, c := range validCommands {
		if c == cmd {
			found = true
			break
		}
	}
	if !found {
		t.Fatalf("onboarding command not registered in validCommands")
	}
}

func TestOnboardingHelpSummaryContainsOnboarding(t *testing.T) {
	summary := FormatHelpSummary()
	if len(summary) == 0 {
		t.Fatal("FormatHelpSummary returned empty string")
	}
}

func TestOnboardingStepsAssetLoaded(t *testing.T) {
	m := onboarding.NewModel(false)
	steps := m.Steps()
	if len(steps) == 0 {
		t.Fatal("expected onboarding steps to be loaded from asset, got empty")
	}
	hasCampaigns := false
	for _, s := range steps {
		if s.ID == "campaigns-folder" {
			hasCampaigns = true
			break
		}
	}
	if !hasCampaigns {
		t.Fatalf("expected steps.json to contain campaigns-folder step, got: %v", steps)
	}
}

func TestApplyOnboardingResult_PrintsReadinessAndWritesConfig(t *testing.T) {
	home := t.TempDir()

	var res onboarding.Result
	res.OpenCodeReady = true
	res.GentleAIReady = false
	res.SQX.InstallPath = "/opt/SQX"
	res.JForex.InstallPath = "/opt/JForex"
	res.JForex.AccountMode = "demo"
	res.PrimaryAgent = "quantlab-orchestrator"

	var buf bytes.Buffer
	if err := applyOnboardingResult(&buf, home, "", res); err != nil {
		t.Fatalf("applyOnboardingResult: %v", err)
	}

	out := buf.String()
	if !strings.Contains(out, "OpenCode") {
		t.Errorf("expected readiness output to mention OpenCode; got:\n%s", out)
	}
	if !strings.Contains(out, "gentle-ai") {
		t.Errorf("expected readiness output to mention gentle-ai; got:\n%s", out)
	}

	cfg, err := config.ReadConfig(config.ConfigPath(home, ""))
	if err != nil {
		t.Fatalf("read config: %v", err)
	}
	if cfg.SQX.InstallPath != "/opt/SQX" {
		t.Errorf("SQX path = %q, want /opt/SQX", cfg.SQX.InstallPath)
	}
	if cfg.JForex.InstallPath != "/opt/JForex" {
		t.Errorf("JForex path = %q, want /opt/JForex", cfg.JForex.InstallPath)
	}
}

func TestCmdOnboarding_UsesTUIResultWithoutInstalling(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)

	old := runOnboardingProgram
	runOnboardingProgram = func(m *onboarding.Model) (onboarding.Result, error) {
		var res onboarding.Result
		res.OpenCodeReady = true
		res.GentleAIReady = true
		res.PrimaryAgent = "quantlab-orchestrator"
		return res, nil
	}
	defer func() { runOnboardingProgram = old }()

	var buf bytes.Buffer
	if err := cmdOnboarding(&buf, nil); err != nil {
		t.Fatalf("cmdOnboarding: %v", err)
	}

	st, err := state.LoadOrInit(filepath.Join(home, ".quantlab"))
	if err != nil {
		t.Fatalf("load state: %v", err)
	}
	if !st.OnboardingCompleted {
		t.Error("expected onboarding state marked completed")
	}
}
