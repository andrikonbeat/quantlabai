package app

import (
	"io/fs"
	"os"
	"path/filepath"
	"testing"

	"github.com/ogzuz/quantlab/internal/model"
	"github.com/ogzuz/quantlab/internal/state"
)

func TestBuildSyncPlan_Steps(t *testing.T) {
	home := t.TempDir()
	qlDir := filepath.Join(home, ".quantlab")
	opencodePath := filepath.Join(home, ".config", "opencode", "opencode.json")

	if err := os.MkdirAll(filepath.Dir(opencodePath), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(opencodePath, []byte("{}"), 0o644); err != nil {
		t.Fatal(err)
	}

	st := &state.State{}
	st.AddComponent(model.ComponentSDK, "installed", filepath.Join(qlDir, "venv"), 0)
	st.AddComponent(model.ComponentSkills, "installed", "", 3)
	st.AddComponent(model.ComponentPrompts, "installed", "", 2)
	st.Agents = append(st.Agents, "quantlab-orchestrator")

	plan := buildSyncPlan(qlDir, opencodePath, st)

	if len(plan.Apply) == 0 {
		t.Fatal("sync plan has no apply steps")
	}

	stepIDs := make([]string, len(plan.Apply))
	for i, s := range plan.Apply {
		stepIDs[i] = s.ID()
	}
	t.Logf("Sync steps: %v", stepIDs)

	hasSyncAgents := false
	hasSyncSkills := false
	hasSyncPrompts := false
	hasCheckSDK := false
	hasUpdateState := false

	for _, id := range stepIDs {
		switch id {
		case "Sync OpenCode agents":
			hasSyncAgents = true
		case "Sync skills":
			hasSyncSkills = true
		case "Sync prompts":
			hasSyncPrompts = true
		case "Check SDK version":
			hasCheckSDK = true
		case "Update state":
			hasUpdateState = true
		}
	}

	if !hasSyncAgents {
		t.Error("missing 'Sync OpenCode agents' step")
	}
	if !hasSyncSkills {
		t.Error("missing 'Sync skills' step")
	}
	if !hasSyncPrompts {
		t.Error("missing 'Sync prompts' step")
	}
	if !hasCheckSDK {
		t.Error("missing 'Check SDK version' step")
	}
	if !hasUpdateState {
		t.Error("missing 'Update state' step")
	}
}

func TestBuildSyncPlan_NotInstalled(t *testing.T) {
	home := t.TempDir()
	qlDir := filepath.Join(home, ".quantlab")
	opencodePath := filepath.Join(home, ".config", "opencode", "opencode.json")

	st := &state.State{} // Empty state - no components

	plan := buildSyncPlan(qlDir, opencodePath, st)
	if len(plan.Apply) == 0 {
		t.Fatal("sync plan should have steps even with empty state")
	}

	firstStep := plan.Apply[0]
	t.Logf("First step: %s", firstStep.ID())
}

func TestBuildSyncPlan_AssetsDir(t *testing.T) {
	// Verify the assetFS is accessible (needed by skills/prompts steps)
	assets := assetFS()
	if assets == nil {
		t.Fatal("assetFS() returned nil")
	}

	// Check that skills dir exists in assets
	entries, err := fs.ReadDir(assets, "skills")
	if err != nil {
		t.Logf("skills dir not found in assets: %v", err)
	} else {
		t.Logf("Found %d skill entries in assets", len(entries))
	}

	// Check that prompts dir exists in assets
	entries, err = fs.ReadDir(assets, "prompts")
	if err != nil {
		t.Logf("prompts dir not found in assets: %v", err)
	} else {
		t.Logf("Found %d prompt entries in assets", len(entries))
	}
}
