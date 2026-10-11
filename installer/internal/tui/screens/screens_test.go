package screens

import (
	"strings"
	"testing"

	"github.com/andrikonbeat/quantlabai/internal/tui/theme"
)

func assertContains(t *testing.T, label, out string, wants ...string) {
	t.Helper()
	if strings.TrimSpace(out) == "" {
		t.Fatalf("%s: rendered empty output", label)
	}
	for _, want := range wants {
		if !strings.Contains(out, want) {
			t.Errorf("%s: output missing %q\n---\n%s", label, want, out)
		}
	}
}

func TestRenderOptions(t *testing.T) {
	out := RenderOptions([]string{"One", "Two", "Three"}, 1)
	assertContains(t, "RenderOptions", out, "One", "Two", "Three", "Two")
	if strings.Contains(out, "One"+"\x1b") {
		t.Fatal("unexpected escape sequence")
	}
}

func TestRenderCheckbox(t *testing.T) {
	checked := RenderCheckbox("Auto-detect", true, true)
	assertContains(t, "RenderCheckbox/checked", checked, "[x]", "Auto-detect")

	unchecked := RenderCheckbox("Auto-detect", false, false)
	assertContains(t, "RenderCheckbox/unchecked", unchecked, "[ ]", "Auto-detect")
	if strings.Contains(unchecked, "[x]") {
		t.Error("unchecked checkbox must not render [x]")
	}
}

func TestRenderRadio(t *testing.T) {
	selected := RenderRadio("demo", true, true)
	assertContains(t, "RenderRadio/selected", selected, "(*)", "demo")

	plain := RenderRadio("live", false, false)
	assertContains(t, "RenderRadio/plain", plain, "( )", "live")
}

func TestRenderOperationRunning(t *testing.T) {
	out := RenderOperationRunning("Installing OpenCode", "npm install -g opencode-ai", "⠋")
	assertContains(t, "RenderOperationRunning", out, "Installing OpenCode", "npm install -g opencode-ai", "⠋")
}

func TestRenderBarClampsPercent(t *testing.T) {
	if bar := RenderBar(-10); !strings.Contains(bar, theme.ProgressEmpty.Render(strings.Repeat("░", 30))) {
		t.Errorf("RenderBar(-10) should render an empty bar, got %q", bar)
	}
	if bar := RenderBar(500); !strings.Contains(bar, theme.ProgressFilled.Render(strings.Repeat("█", 30))) {
		t.Errorf("RenderBar(500) should clamp to a full bar, got %q", bar)
	}
	half := RenderBar(50)
	if !strings.Contains(half, strings.Repeat("█", 15)) || !strings.Contains(half, strings.Repeat("░", 15)) {
		t.Errorf("RenderBar(50) should be half filled, got %q", half)
	}
}

func TestRenderInstalling(t *testing.T) {
	out := RenderInstalling(InstallProgress{
		Percent:     40,
		CurrentStep: "Install SDK",
		Items: []ProgressItem{
			{Label: "Create .quantlab directory", Status: "succeeded"},
			{Label: "Install SDK", Status: "running"},
			{Label: "Install prompts", Status: "skipped"},
			{Label: "Write state.json", Status: "pending"},
		},
		Logs: []string{"pip install quantlab"},
	}, "⠙")
	assertContains(t, "RenderInstalling", out, "Install SDK", "40%", "Create .quantlab directory", "Install prompts (skipped)", "Logs", "pip install quantlab")
	if strings.Contains(out, "✗") {
		t.Error("no failed step was supplied, so no ✗ mark should appear")
	}
}

func TestRenderInstallingDoneSummary(t *testing.T) {
	ok := RenderInstalling(InstallProgress{
		Percent: 100,
		Done:    true,
		Items: []ProgressItem{
			{Label: "Install SDK", Status: "succeeded"},
		},
	}, " ")
	assertContains(t, "RenderInstalling/done", ok, "All 1 steps completed successfully.", "Press Enter to continue.")

	mixed := RenderInstalling(InstallProgress{
		Percent: 100,
		Done:    true,
		Failed:  true,
		Items: []ProgressItem{
			{Label: "Install SDK", Status: "succeeded"},
			{Label: "Install prompts", Status: "failed"},
		},
	}, " ")
	assertContains(t, "RenderInstalling/failed", mixed, "Completed with errors", "1 failed", "✗")

	skipped := RenderInstalling(InstallProgress{
		Percent: 100,
		Done:    true,
		Items: []ProgressItem{
			{Label: "Install prompts", Status: "skipped"},
			{Label: "Install SDK", Status: "succeeded"},
		},
	}, " ")
	assertContains(t, "RenderInstalling/skipped", skipped, "1 skipped")
}

func TestRenderCompleteSuccess(t *testing.T) {
	out := RenderComplete(CompletePayload{
		ConfiguredAgents:    2,
		InstalledComponents: 5,
		MissingDeps:         []MissingDep{{Name: "StrategyQuantX", InstallHint: "https://strategyquant.com/"}},
		ManualActions:       []string{"Instalá OpenCode manualmente"},
		Footer:              "Press Enter to exit.",
	})
	assertContains(t, "RenderComplete/success", out,
		"Configured agents", "2",
		"Installed components", "5",
		"StrategyQuantX", "https://strategyquant.com/",
		"Instalá OpenCode manualmente",
		"Next steps", "quantlab-orchestrator",
		"Press Enter to exit.")
	if strings.Contains(out, "GGA") {
		t.Error("QuantLab completion screen must not carry the gentle-ai GGA block")
	}
}

func TestRenderCompleteFailed(t *testing.T) {
	out := RenderComplete(CompletePayload{
		FailedSteps:       []FailedStep{{ID: "Install SDK", Error: "No module named quantlab"}},
		RollbackPerformed: true,
		RollbackComplete:  false,
		Footer:            "Press Enter to exit.",
	})
	assertContains(t, "RenderComplete/failed", out,
		"Installation completed with errors.",
		"Failed steps", "Install SDK", "No module named quantlab",
		"Rollback partially completed", "What to do")
}

func TestRenderCompleteOverridesNextSteps(t *testing.T) {
	out := RenderComplete(CompletePayload{
		Checklist: []CompleteCheckItem{
			{Label: "Abrí OpenCode", Done: true},
			{Label: "Elegí el agente primario", Done: false},
		},
		NextSteps: []string{"1. cd \"<campañas>/\" && opencode"},
	})
	assertContains(t, "RenderComplete/override", out, "Abrí OpenCode", "cd \"<campañas>/\" && opencode")
}
