package onboarding

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
)

// runRune sends a single rune key press and returns the updated model.
func runRune(t *testing.T, m *Model, r rune) (*Model, tea.Cmd) {
	t.Helper()
	mm, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
	next, ok := mm.(*Model)
	if !ok {
		t.Fatalf("Update returned %T, want *Model", mm)
	}
	return next, cmd
}

// runEnter sends an Enter key press and returns the updated model.
func runEnter(t *testing.T, m *Model) (*Model, tea.Cmd) {
	t.Helper()
	mm, cmd := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	next, ok := mm.(*Model)
	if !ok {
		t.Fatalf("Update returned %T, want *Model", mm)
	}
	return next, cmd
}

// runMsg feeds a non-key message (e.g. installDoneMsg) to the model.
func runMsg(t *testing.T, m *Model, msg tea.Msg) (*Model, tea.Cmd) {
	t.Helper()
	mm, cmd := m.Update(msg)
	next, ok := mm.(*Model)
	if !ok {
		t.Fatalf("Update returned %T, want *Model", mm)
	}
	return next, cmd
}

// newTestModel returns a model with deterministic detection and no real
// network installs. The injectable runners record calls and return the
// configured result.
func newTestModel(t *testing.T) *Model {
	t.Helper()
	m := NewModel(false)
	m.openCodeInstalled = false
	m.gentleAIInstalled = false
	m.result.OpenCodeReady = false
	m.result.GentleAIReady = false
	m.homeFn = func() (string, error) { return "/home/test", nil }
	m.installOpenCodeFn = func(home string) (string, error) { return "", nil }
	m.installGentleAIFn = func(home string) (string, error) { return "", nil }
	m.sdkDetectFn = func() (bool, error) { return true, nil }
	return &m
}

func TestOnboarding_Flow(t *testing.T) {
	m := newTestModel(t)
	// Both tools already installed: consent steps are informational.
	m.openCodeInstalled = true
	m.gentleAIInstalled = true

	// OSDetect -> Enter -> Intro
	m, cmd := runEnter(t, m)
	if m.step != StepIntro {
		t.Fatalf("step = %d, want %d", m.step, StepIntro)
	}
	if cmd != nil {
		t.Fatalf("expected nil cmd after os detect enter")
	}
	// Intro -> Enter -> ConsentOpenCode
	m, cmd = runEnter(t, m)
	if m.step != StepConsentOpenCode {
		t.Fatalf("step = %d, want %d", m.step, StepConsentOpenCode)
	}
	if cmd != nil {
		t.Fatalf("expected nil cmd after intro enter")
	}
	// ConsentOpenCode -> Enter (detected) -> ConsentGentleAI
	m, cmd = runEnter(t, m)
	if m.step != StepConsentGentleAI {
		t.Fatalf("step = %d, want %d", m.step, StepConsentGentleAI)
	}
	if cmd != nil {
		t.Fatalf("expected nil cmd after detected opencode consent")
	}
	// ConsentGentleAI -> Enter (detected) -> SQX (no installs queued)
	m, cmd = runEnter(t, m)
	if m.step != StepSQX {
		t.Fatalf("step = %d, want %d", m.step, StepSQX)
	}
	if cmd != nil {
		t.Fatalf("expected no install cmd when nothing consented")
	}

	// SQX -> Enter -> JForex (use a temp dir with fake sqcli)
	sqxDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(sqxDir, "sqcli"), []byte("#!/bin/sh\n"), 0o755); err != nil {
		t.Fatal(err)
	}
	m.sqxInput.SetValue(sqxDir)
	m, _ = runEnter(t, m)
	if m.step != StepJForex {
		t.Fatalf("step = %d, want %d", m.step, StepJForex)
	}
	if m.sqxError != "" {
		t.Fatalf("unexpected sqxError: %s", m.sqxError)
	}

	// JForex -> Enter -> Verify
	m.jforexPathInput.SetValue("/opt/JForex")
	m.jforexUserInput.SetValue("user")
	m.jforexPassInput.SetValue("pass")
	m, _ = runEnter(t, m)
	if m.step != StepVerify {
		t.Fatalf("step = %d, want %d", m.step, StepVerify)
	}
	if m.result.JForex.AccountMode != "demo" {
		t.Errorf("account mode = %q, want demo", m.result.JForex.AccountMode)
	}

	// Verify -> Enter -> PostInstall (non-blocking)
	m, _ = runEnter(t, m)
	if m.step != StepPostInstall {
		t.Fatalf("step = %d, want %d", m.step, StepPostInstall)
	}

	// PostInstall -> Enter -> quit
	m, _ = runEnter(t, m)
	if !m.quitting {
		t.Error("expected model to quit")
	}
	if m.result.PrimaryAgent != "quantlab-orchestrator" {
		t.Errorf("primary agent = %q, want quantlab-orchestrator", m.result.PrimaryAgent)
	}
}

func TestOnboarding_Escape(t *testing.T) {
	m := newTestModel(t)
	mm, _ := m.Update(tea.KeyMsg{Type: tea.KeyEsc})
	got := mm.(*Model)
	if !got.quitting {
		t.Error("expected model to quit on escape")
	}
}

func TestOnboarding_JForexLiveMode(t *testing.T) {
	m := newTestModel(t)
	m.step = StepJForex
	m.accountModeIndex = 1
	m.jforexPathInput.SetValue("/opt/JForex")
	m.jforexUserInput.SetValue("user")
	m.jforexPassInput.SetValue("pass")
	m, _ = runEnter(t, m)
	if m.result.JForex.AccountMode != "live" {
		t.Errorf("account mode = %q, want live", m.result.JForex.AccountMode)
	}
}

func TestConsentNotDetected_YesQueuesInstall(t *testing.T) {
	m := newTestModel(t)
	m.step = StepConsentOpenCode

	m, cmd := runRune(t, m, 's')
	if m.step != StepConsentGentleAI {
		t.Fatalf("step = %d, want %d", m.step, StepConsentGentleAI)
	}
	if !m.consentOpenCode {
		t.Error("expected opencode consent recorded")
	}
	if cmd != nil {
		t.Fatalf("expected no install cmd before both consents collected")
	}

	m, cmd = runRune(t, m, 'n')
	if m.step != StepInstalling {
		t.Fatalf("step = %d, want %d", m.step, StepInstalling)
	}
	if m.consentGentleAI {
		t.Error("expected gentle-ai consent false")
	}
	if cmd == nil {
		t.Fatal("expected install cmd for consented opencode")
	}
}

func TestConsentNotDetected_NoSkipsWithoutInstall(t *testing.T) {
	m := newTestModel(t)
	m.step = StepConsentOpenCode

	m, cmd := runRune(t, m, 'n')
	if m.step != StepConsentGentleAI {
		t.Fatalf("step = %d, want %d", m.step, StepConsentGentleAI)
	}
	if m.consentOpenCode {
		t.Error("expected opencode consent false after skip")
	}
	if cmd != nil {
		t.Fatal("expected no cmd after skip")
	}

	m, cmd = runRune(t, m, 'n')
	if m.step != StepSQX {
		t.Fatalf("step = %d, want %d", m.step, StepSQX)
	}
	if cmd != nil {
		t.Fatal("expected no install cmd when nothing consented")
	}
}

func TestConsentDetected_ShowsDelegationAndAdvances(t *testing.T) {
	m := newTestModel(t)
	m.openCodeInstalled = true
	m.step = StepConsentOpenCode

	view := m.View()
	if !strings.Contains(view, "ya") && !strings.Contains(view, "instalado") {
		t.Errorf("detected branch should say the tool is already installed; got:\n%s", view)
	}
	if !strings.Contains(view, "opencode.ai") {
		t.Errorf("detected branch should include docs link; got:\n%s", view)
	}
	if strings.Contains(view, "¿Instalar OpenCode") {
		t.Errorf("detected branch must not prompt for installation; got:\n%s", view)
	}

	m, cmd := runEnter(t, m)
	if m.step != StepConsentGentleAI {
		t.Fatalf("step = %d, want %d", m.step, StepConsentGentleAI)
	}
	if cmd != nil {
		t.Fatalf("expected nil cmd on detected enter")
	}
}

func TestConsentNotDetected_ViewPrompts(t *testing.T) {
	m := newTestModel(t)
	m.step = StepConsentOpenCode
	view := m.View()
	if !strings.Contains(view, "OpenCode") {
		t.Errorf("consent view should name OpenCode; got:\n%s", view)
	}
	if !strings.Contains(view, "[S/N]") {
		t.Errorf("consent view should prompt [S/N]; got:\n%s", view)
	}
}

func TestInstallSuccessAdvances(t *testing.T) {
	m := newTestModel(t)
	m.step = StepConsentOpenCode

	m, _ = runRune(t, m, 's')    // opencode yes
	m, cmd := runRune(t, m, 'n') // gentle-ai no -> installing
	if cmd == nil {
		t.Fatal("expected install cmd")
	}
	done := cmd()
	if _, ok := done.(installDoneMsg); !ok {
		t.Fatalf("cmd produced %T, want installDoneMsg", done)
	}

	m, cmd = runMsg(t, m, done)
	if m.step != StepSQX {
		t.Fatalf("step = %d, want %d after successful install", m.step, StepSQX)
	}
	if !m.result.OpenCodeReady {
		t.Error("expected OpenCodeReady true after success")
	}
	if cmd != nil {
		t.Error("expected no further cmd when queue empty")
	}
}

func TestInstallFailureOffersRetryThenForcesManual(t *testing.T) {
	m := newTestModel(t)
	m.installOpenCodeFn = func(home string) (string, error) {
		return "", fmt.Errorf("boom")
	}
	m.step = StepConsentOpenCode

	m, _ = runRune(t, m, 's')
	m, cmd := runRune(t, m, 'n')
	if cmd == nil {
		t.Fatal("expected install cmd")
	}

	// First failure -> StepInstallFailed, one attempt recorded.
	m, _ = runMsg(t, m, cmd())
	if m.step != StepInstallFailed {
		t.Fatalf("step = %d, want %d after first failure", m.step, StepInstallFailed)
	}
	if m.installAttempts != 1 {
		t.Fatalf("attempts = %d, want 1", m.installAttempts)
	}
	if m.currentTool != "opencode" {
		t.Fatalf("currentTool = %q, want opencode", m.currentTool)
	}
	if view := m.View(); !strings.Contains(view, "[R]") {
		t.Errorf("failure view should offer retry; got:\n%s", view)
	}

	// Retry -> second failure.
	m, cmd = runRune(t, m, 'r')
	if m.step != StepInstalling {
		t.Fatalf("step = %d, want %d after retry", m.step, StepInstalling)
	}
	if cmd == nil {
		t.Fatal("expected retry install cmd")
	}
	m, _ = runMsg(t, m, cmd())
	if m.step != StepInstallFailed {
		t.Fatalf("step = %d, want %d after second failure", m.step, StepInstallFailed)
	}
	if m.installAttempts != 2 {
		t.Fatalf("attempts = %d, want 2", m.installAttempts)
	}

	// Retry -> third failure forces manual mode.
	m, cmd = runRune(t, m, 'r')
	if cmd == nil {
		t.Fatal("expected third retry cmd")
	}
	m, _ = runMsg(t, m, cmd())
	if m.step != StepInstallManual {
		t.Fatalf("step = %d, want %d after third failure", m.step, StepInstallManual)
	}
	if m.manualTool != "opencode" {
		t.Fatalf("manualTool = %q, want opencode", m.manualTool)
	}
}

func TestInstallFailedManualKeyEntersManualMode(t *testing.T) {
	m := newTestModel(t)
	m.installOpenCodeFn = func(home string) (string, error) { return "", fmt.Errorf("boom") }
	m.step = StepConsentOpenCode
	m, _ = runRune(t, m, 's')
	m, cmd := runRune(t, m, 'n')
	m, _ = runMsg(t, m, cmd())

	if m.step != StepInstallFailed {
		t.Fatalf("step = %d, want %d", m.step, StepInstallFailed)
	}
	m, _ = runRune(t, m, 'm')
	if m.step != StepInstallManual {
		t.Fatalf("step = %d, want %d after [M]", m.step, StepInstallManual)
	}
}

func TestInstallFailedSkipKeyContinues(t *testing.T) {
	m := newTestModel(t)
	m.installOpenCodeFn = func(home string) (string, error) { return "", fmt.Errorf("boom") }
	m.step = StepConsentOpenCode
	m, _ = runRune(t, m, 's')
	m, cmd := runRune(t, m, 'n')
	m, _ = runMsg(t, m, cmd())

	m, _ = runRune(t, m, 'o')
	if m.step != StepSQX {
		t.Fatalf("step = %d, want %d after [O]", m.step, StepSQX)
	}
}

func TestManualModeContinuesAndShowsURL(t *testing.T) {
	m := newTestModel(t)
	m.step = StepInstallManual
	m.manualTool = "opencode"

	view := m.View()
	if !strings.Contains(view, "opencode.ai") {
		t.Errorf("manual view should show the official URL; got:\n%s", view)
	}

	m, cmd := runEnter(t, m)
	if m.step != StepSQX {
		t.Fatalf("step = %d, want %d after manual continue", m.step, StepSQX)
	}
	if !m.manualTools["opencode"] {
		t.Error("expected opencode marked as manual/pending")
	}
	if cmd != nil {
		t.Error("expected no cmd when install queue is empty")
	}
}

func TestManualModeRunsNextJob(t *testing.T) {
	m := newTestModel(t)
	m.installQueue = []string{"gentle-ai"}
	m.step = StepInstallManual
	m.manualTool = "opencode"

	m, cmd := runEnter(t, m)
	if m.step != StepInstalling {
		t.Fatalf("step = %d, want %d after manual continue to next job", m.step, StepInstalling)
	}
	if cmd == nil {
		t.Fatal("expected cmd for the queued next job")
	}
	if m.currentTool != "gentle-ai" {
		t.Fatalf("currentTool = %q, want gentle-ai", m.currentTool)
	}
}

func TestInstallFallbackDisplayGoesManual(t *testing.T) {
	m := newTestModel(t)
	m.installOpenCodeFn = func(home string) (string, error) {
		return "npm no disponible: instalá manualmente", nil
	}
	m.step = StepConsentOpenCode

	m, _ = runRune(t, m, 's')    // opencode yes
	m, cmd := runRune(t, m, 'n') // gentle-ai no -> installing
	if cmd == nil {
		t.Fatal("expected install cmd")
	}
	m, _ = runMsg(t, m, cmd())

	if m.step != StepInstallManual {
		t.Fatalf("step = %d, want %d when the installer returns a manual fallback", m.step, StepInstallManual)
	}
	if m.result.OpenCodeReady {
		t.Error("OpenCode must not be marked ready when the installer fell back to manual")
	}
	if !m.manualTools["opencode"] {
		t.Error("expected opencode marked as manual/pending")
	}
	if view := m.View(); !strings.Contains(view, "instalá manualmente") {
		t.Errorf("manual view should surface the installer note; got:\n%s", view)
	}
}

func TestStepsAssetLoadsEmbeddedGuide(t *testing.T) {
	m := NewModel(false)
	found := false
	for _, s := range m.Steps() {
		if s.ID == "gentle-ai" {
			found = true
			break
		}
	}
	if !found {
		t.Fatalf("expected the embedded onboarding/steps.json guide (with a gentle-ai step) to load; got: %v", m.Steps())
	}
}

func TestVerifyShowsItemsAndDoesNotBlock(t *testing.T) {
	m := newTestModel(t)
	m.sdkDetectFn = func() (bool, error) { return false, nil }
	m.step = StepVerify
	m.verifyBuilt = false

	view := m.View()
	for _, want := range []string{"OpenCode", "gentle-ai", "SQX", "JForex", "SDK"} {
		if !strings.Contains(view, want) {
			t.Errorf("verify view missing %q; got:\n%s", want, view)
		}
	}
	if !strings.Contains(view, "✗") {
		t.Errorf("verify view should show a missing mark; got:\n%s", view)
	}
	if !strings.Contains(view, "agente OpenCode") {
		t.Errorf("verify view should recommend the OpenCode agent; got:\n%s", view)
	}

	m, _ = runEnter(t, m)
	if m.step != StepPostInstall {
		t.Fatalf("step = %d, want %d (verify must not block)", m.step, StepPostInstall)
	}
}

func TestVerifyAllReadyHasNoRecommendation(t *testing.T) {
	m := newTestModel(t)
	m.openCodeInstalled = true
	m.gentleAIInstalled = true
	m.sdkDetectFn = func() (bool, error) { return true, nil }
	sqxDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(sqxDir, "sqcli"), []byte("#!/bin/sh\n"), 0o755); err != nil {
		t.Fatal(err)
	}
	m.result.SQX.InstallPath = sqxDir
	m.result.JForex.InstallPath = "/opt/JForex"
	m.step = StepVerify
	m.verifyBuilt = false

	view := m.View()
	if strings.Contains(view, "✗") {
		t.Errorf("all-ready verify view should not show missing marks; got:\n%s", view)
	}
	if strings.Contains(view, "agente OpenCode") {
		t.Errorf("all-ready verify view should not recommend delegation; got:\n%s", view)
	}
}

func TestPostInstallClosingMessage(t *testing.T) {
	m := newTestModel(t)
	m.step = StepPostInstall
	view := m.View()
	for _, want := range []string{
		"quantlab-orchestrator",
		"Comienza una campaña para un portafolio de 100USD",
		"cd",
		"opencode",
	} {
		if !strings.Contains(view, want) {
			t.Errorf("post-install view missing %q; got:\n%s", want, view)
		}
	}
}

func TestInstallQueueRespectsConsent(t *testing.T) {
	m := newTestModel(t)
	// Only gentle-ai consented.
	m.consentOpenCode = false
	m.consentGentleAI = true
	m.step = StepInstalling
	cmd := m.beginInstalls()
	if cmd == nil {
		t.Fatal("expected a cmd for consented gentle-ai")
	}
	if m.currentTool != "gentle-ai" {
		t.Fatalf("currentTool = %q, want gentle-ai", m.currentTool)
	}
	done := cmd()
	m, _ = runMsg(t, m, done)
	if !m.result.GentleAIReady {
		t.Error("expected GentleAIReady true")
	}
	if m.result.OpenCodeReady {
		t.Error("opencode was not consented and must not be ready")
	}
}
