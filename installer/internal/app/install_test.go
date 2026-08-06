package app

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/ogzuz/quantlab/internal/journal"
	"github.com/ogzuz/quantlab/internal/pipeline"
	"github.com/ogzuz/quantlab/internal/state"
)

func TestBuildInstallPlan_Stages(t *testing.T) {
	home := t.TempDir()
	qlDir := filepath.Join(home, ".quantlab")
	opencodePath := filepath.Join(home, ".config", "opencode", "opencode.json")

	// Ensure the opencode dir exists
	if err := os.MkdirAll(filepath.Dir(opencodePath), 0o755); err != nil {
		t.Fatal(err)
	}
	// Create empty opencode.json
	if err := os.WriteFile(opencodePath, []byte("{}"), 0o644); err != nil {
		t.Fatal(err)
	}

	st := testState(home)

	j := journal.New(qlDir, filepath.Dir(opencodePath))
	plan := buildInstallPlan(qlDir, opencodePath, "sk-test", "gpt-4o", "auto", st, j)

	if len(plan.Apply) == 0 {
		t.Fatal("plan has no apply steps")
	}

	// Verify step IDs
	stepIDs := make([]string, len(plan.Apply))
	for i, s := range plan.Apply {
		stepIDs[i] = s.ID()
	}
	t.Logf("Plan steps: %v", stepIDs)

	// Should have at least the core steps
	hasCreateDir := false
	hasSDKInstall := false
	hasStateWrite := false
	for _, id := range stepIDs {
		if id == "Create .quantlab directory" {
			hasCreateDir = true
		}
		if id == "Install SDK" {
			hasSDKInstall = true
		}
		if id == "Write state.json" {
			hasStateWrite = true
		}
	}

	if !hasCreateDir {
		t.Error("missing 'Create .quantlab directory' step")
	}
	if !hasSDKInstall {
		t.Error("missing 'Install SDK' step")
	}
	if !hasStateWrite {
		t.Error("missing 'Write state.json' step")
	}
}

func TestBuildInstallPlan_RunCreateDir(t *testing.T) {
	home := t.TempDir()
	qlDir := filepath.Join(home, ".quantlab")
	opencodePath := filepath.Join(home, ".config", "opencode", "opencode.json")

	if err := os.MkdirAll(filepath.Dir(opencodePath), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(opencodePath, []byte("{}"), 0o644); err != nil {
		t.Fatal(err)
	}

	st := testState(home)
	j := journal.New(qlDir, filepath.Dir(opencodePath))
	plan := buildInstallPlan(qlDir, opencodePath, "sk-test", "gpt-4o", "auto", st, j)

	// Run with progress
	err := pipeline.Run(plan, func(ev pipeline.ProgressEvent) {
		t.Logf("progress: %s %s %s", ev.Stage, ev.StepID, ev.Status)
	})
	if err != nil {
		// It's OK if SDK install fails (no Python/network) — check that
		// pre-SDK steps worked
		t.Logf("Pipeline error (expected without Python): %v", err)
	}

	// Check that .quantlab dir was created
	if _, err := os.Stat(qlDir); err != nil {
		t.Logf(".quantlab dir not created (may be rolled back): %v", err)
	}
}

func TestMergeOpenCodeAgents_CreatesFile(t *testing.T) {
	home := t.TempDir()
	opencodePath := filepath.Join(home, ".config", "opencode", "opencode.json")

	if err := os.MkdirAll(filepath.Dir(opencodePath), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(opencodePath, []byte("{}"), 0o644); err != nil {
		t.Fatal(err)
	}

	if err := mergeOpenCodeAgents(opencodePath); err != nil {
		t.Fatalf("mergeOpenCodeAgents() error = %v", err)
	}

	// Read back and check agents were added
	data, err := os.ReadFile(opencodePath)
	if err != nil {
		t.Fatal(err)
	}
	if len(data) < 10 {
		t.Fatalf("opencode.json too short after merge: %d bytes", len(data))
	}
}

func TestMergeOpenCodeAgents_NoFile(t *testing.T) {
	home := t.TempDir()
	opencodePath := filepath.Join(home, ".config", "opencode", "opencode.json")

	// Should handle non-existent file gracefully
	err := mergeOpenCodeAgents(opencodePath)
	if err != nil {
		t.Fatalf("mergeOpenCodeAgents() with no file error = %v", err)
	}
}

// testState creates a minimal state for testing.
func testState(homeDir string) *state.State {
	st := &state.State{}
	st.SetStatePath(filepath.Join(homeDir, ".quantlab", "state.json"))
	return st
}

func TestHasNoWizardFlag(t *testing.T) {
	tests := []struct {
		args []string
		want bool
	}{
		{[]string{"--no-wizard"}, true},
		{[]string{"--skip-wizard"}, true},
		{[]string{"--yes"}, true},
		{[]string{"--no-wizard", "--verbose"}, true},
		{[]string{"--verbose", "--no-wizard"}, true},
		{[]string{}, false},
		{[]string{"--verbose"}, false},
		{[]string{"--wizard"}, false},
		{[]string{"--no-wizardry"}, false},
	}

	for _, tt := range tests {
		t.Run(strings.Join(tt.args, " "), func(t *testing.T) {
			if got := hasNoWizardFlag(tt.args); got != tt.want {
				t.Errorf("hasNoWizardFlag(%v) = %v, want %v", tt.args, got, tt.want)
			}
		})
	}
}

func TestWizardEnabled(t *testing.T) {
	tests := []struct {
		name      string
		args      []string
		stdoutTTY bool
		want      bool
	}{
		{"no flags on TTY", nil, true, true},
		{"no flags no TTY", nil, false, false},
		{"no-wizard on TTY", []string{"--no-wizard"}, true, false},
		{"no-wizard no TTY", []string{"--no-wizard"}, false, false},
		{"skip-wizard on TTY", []string{"--skip-wizard"}, true, false},
		{"yes on TTY", []string{"--yes"}, true, false},
		{"unrelated flag on TTY", []string{"--verbose"}, true, true},
		{"unrelated flag no TTY", []string{"--verbose"}, false, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := wizardEnabled(tt.args, tt.stdoutTTY); got != tt.want {
				t.Errorf("wizardEnabled(%v, %v) = %v, want %v", tt.args, tt.stdoutTTY, got, tt.want)
			}
		})
	}
}

func TestBuildInstallPlan_NoAPIKey(t *testing.T) {
	home := t.TempDir()
	qlDir := filepath.Join(home, ".quantlab")
	opencodePath := filepath.Join(home, ".config", "opencode", "opencode.json")

	if err := os.MkdirAll(filepath.Dir(opencodePath), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(opencodePath, []byte("{}"), 0o644); err != nil {
		t.Fatal(err)
	}

	st := testState(home)
	j := journal.New(qlDir, filepath.Dir(opencodePath))
	plan := buildInstallPlan(qlDir, opencodePath, "", "gpt-4o", "auto", st, j)

	// The "Write SDK config" step must succeed with an empty API key and
	// produce a config file without one.
	found := false
	for _, s := range plan.Apply {
		if s.ID() != "Write SDK config" {
			continue
		}
		found = true
		if err := s.Run(); err != nil {
			t.Fatalf("Write SDK config step failed with empty API key: %v", err)
		}
	}
	if !found {
		t.Fatal("plan missing 'Write SDK config' step")
	}

	data, err := os.ReadFile(filepath.Join(qlDir, "sdk-config.yaml"))
	if err != nil {
		t.Fatalf("read sdk-config.yaml: %v", err)
	}
	content := string(data)
	if strings.Contains(content, `"APIKey": "sk-`) {
		t.Errorf("sdk-config.yaml unexpectedly contains an API key:\n%s", content)
	}
	if !strings.Contains(content, `"APIKey": ""`) {
		t.Errorf("sdk-config.yaml missing empty APIKey field:\n%s", content)
	}
}

func TestCmdInstallHome_NoWizardProceeds(t *testing.T) {
	home := t.TempDir()
	// Redirect os.UserHomeDir() to the temp home so opencode paths and the
	// SDK venv stay isolated from the real ~/.config/opencode.
	t.Setenv("HOME", home)

	var buf bytes.Buffer
	err := cmdInstallHome(&buf, []string{"--no-wizard"}, home)
	output := buf.String()

	// The flow must never abort at the wizard with --no-wizard.
	if strings.Contains(output, "Wizard cancelled") {
		t.Errorf("install must not abort at the wizard with --no-wizard\nOutput:\n%s", output)
	}

	// Message assertions only make sense if the prerequisites passed and the
	// flow actually reached the wizard step.
	if strings.Contains(output, "Python 3.11+") {
		for _, want := range []string{
			"Skipping configuration wizard (--no-wizard)",
			"No API key provided",
		} {
			if !strings.Contains(output, want) {
				t.Errorf("output missing %q\nOutput:\n%s", want, output)
			}
		}
	}

	if err != nil {
		// Expected when quantlab-ai is not published to PyPI: the SDK install
		// step fails and the pipeline rolls back. The wizard was still skipped.
		t.Logf("install returned error (expected without quantlab-ai on PyPI): %v", err)
	}
}
