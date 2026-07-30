package app

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/ogzuz/quantlab/internal/model"
	"github.com/ogzuz/quantlab/internal/state"
)

func TestBuildUninstallPlan_Stages(t *testing.T) {
	home := t.TempDir()
	qlDir := filepath.Join(home, ".quantlab")
	opencodePath := filepath.Join(home, ".config", "opencode", "opencode.json")

	// Set up a fake installation
	if err := os.MkdirAll(qlDir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Dir(opencodePath), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(opencodePath, []byte("{}"), 0o644); err != nil {
		t.Fatal(err)
	}

	// Create a state file with components
	st := &state.State{}
	st.AddComponent(model.ComponentSDK, "installed", filepath.Join(qlDir, "venv"), 0)
	st.AddComponent(model.ComponentOpenCodeAgents, "installed", "", 4)
	st.AddAgent("quantlab-orchestrator")
	st.Agents = append(st.Agents, "quantlab-campaign")

	plan := buildUninstallPlan(qlDir, opencodePath, st)

	if len(plan.Apply) == 0 {
		t.Fatal("uninstall plan has no apply steps")
	}

	// Verify all expected steps
	stepIDs := make([]string, len(plan.Apply))
	for i, s := range plan.Apply {
		stepIDs[i] = s.ID()
	}
	t.Logf("Uninstall steps: %v", stepIDs)

	hasRestore := false
	hasRemoveAgents := false
	hasRemoveSkills := false
	hasRemovePrompts := false
	hasRemoveVenv := false
	hasRemoveDir := false

	for _, id := range stepIDs {
		switch id {
		case "Restore default_agent":
			hasRestore = true
		case "Remove QuantLab agents":
			hasRemoveAgents = true
		case "Remove skills":
			hasRemoveSkills = true
		case "Remove prompts":
			hasRemovePrompts = true
		case "Remove SDK venv":
			hasRemoveVenv = true
		case "Remove .quantlab directory":
			hasRemoveDir = true
		}
	}

	if !hasRestore {
		t.Error("missing 'Restore default_agent' step")
	}
	if !hasRemoveAgents {
		t.Error("missing 'Remove QuantLab agents' step")
	}
	if !hasRemoveSkills {
		t.Error("missing 'Remove skills' step")
	}
	if !hasRemovePrompts {
		t.Error("missing 'Remove prompts' step")
	}
	if !hasRemoveVenv {
		t.Error("missing 'Remove SDK venv' step")
	}
	if !hasRemoveDir {
		t.Error("missing 'Remove .quantlab directory' step")
	}
}

func TestBuildUninstallPlan_EmptyState(t *testing.T) {
	home := t.TempDir()
	qlDir := filepath.Join(home, ".quantlab")
	opencodePath := filepath.Join(home, ".config", "opencode", "opencode.json")

	st := &state.State{}

	plan := buildUninstallPlan(qlDir, opencodePath, st)
	if len(plan.Apply) == 0 {
		t.Fatal("plan should have steps even with empty state")
	}
}
