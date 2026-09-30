package onboarding

import (
	"os"
	"path/filepath"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
)

func TestOnboarding_Flow(t *testing.T) {
	m := NewModel()
	// Intro -> Enter -> Consent
	mm, cmd := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = *mm.(*Model)
	if m.step != StepConsent {
		t.Fatalf("step = %d, want %d", m.step, StepConsent)
	}
	if cmd != nil {
		t.Fatalf("expected nil cmd after intro enter")
	}
	// Consent -> Enter -> SQX
	m.consentOpenCode = true
	m.consentGentleAI = false
	m.consentSDK = true
	mm, cmd = m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = *mm.(*Model)
	if m.step != StepSQX {
		t.Fatalf("step = %d, want %d", m.step, StepSQX)
	}
	if m.result.Consent.OpenCode != true {
		t.Error("expected OpenCode consent true")
	}
	if m.result.Consent.SDK != true {
		t.Error("expected SDK consent true")
	}
	// SQX -> Enter -> JForex (use a temp dir with fake sqcli)
	sqxDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(sqxDir, "sqcli"), []byte("#!/bin/sh\n"), 0o755); err != nil {
		t.Fatal(err)
	}
	m.sqxInput.SetValue(sqxDir)
	mm, cmd = m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = *mm.(*Model)
	if m.step != StepJForex {
		t.Fatalf("step = %d, want %d", m.step, StepJForex)
	}
	if m.sqxError != "" {
		t.Fatalf("unexpected sqxError: %s", m.sqxError)
	}
	// JForex -> Enter -> PostInstall
	m.jforexPathInput.SetValue("/opt/JForex")
	m.jforexUserInput.SetValue("user")
	m.jforexPassInput.SetValue("pass")
	mm, cmd = m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = *mm.(*Model)
	if m.step != StepPostInstall {
		t.Fatalf("step = %d, want %d", m.step, StepPostInstall)
	}
	if m.result.JForex.AccountMode != "demo" {
		t.Errorf("account mode = %q, want demo", m.result.JForex.AccountMode)
	}
	// PostInstall -> Enter -> quit
	mm, cmd = m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = *mm.(*Model)
	if !m.quitting {
		t.Error("expected model to quit")
	}
	if m.result.PrimaryAgent != "quantlab-orchestrator" {
		t.Errorf("primary agent = %q, want quantlab-orchestrator", m.result.PrimaryAgent)
	}
}

func TestOnboarding_Escape(t *testing.T) {
	m := NewModel()
	mm, _ := m.Update(tea.KeyMsg{Type: tea.KeyEsc})
	m = *mm.(*Model)
	if !m.quitting {
		t.Error("expected model to quit on escape")
	}
}

func TestOnboarding_JForexLiveMode(t *testing.T) {
	m := NewModel()
	m.step = StepJForex
	m.accountModeIndex = 1
	m.jforexPathInput.SetValue("/opt/JForex")
	m.jforexUserInput.SetValue("user")
	m.jforexPassInput.SetValue("pass")
	mm, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = *mm.(*Model)
	if m.result.JForex.AccountMode != "live" {
		t.Errorf("account mode = %q, want live", m.result.JForex.AccountMode)
	}
}
