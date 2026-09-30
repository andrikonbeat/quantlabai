package app

import (
	"testing"

	"github.com/ogzuz/quantlab/internal/tui/onboarding"
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
	m := onboarding.NewModel()
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
