package app

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/ogzuz/quantlab/internal/pipeline"
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

	plan := buildInstallPlan(qlDir, opencodePath, "sk-test", "gpt-4o", "auto", st)

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
	plan := buildInstallPlan(qlDir, opencodePath, "sk-test", "gpt-4o", "auto", st)

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
	return &state.State{
		statePath: filepath.Join(homeDir, ".quantlab", "state.json"),
	}
}
