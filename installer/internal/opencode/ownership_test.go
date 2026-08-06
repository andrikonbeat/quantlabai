package opencode

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestPrepareInstall_NoExistingMarker(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "opencode.json")

	// Create a minimal opencode.json with a default_agent
	initial := map[string]any{
		"default_agent": "gentle-orchestrator",
		"agent": map[string]any{
			"gentle-orchestrator": map[string]any{"description": "test"},
		},
	}
	raw, _ := json.MarshalIndent(initial, "", "  ")
	if err := os.WriteFile(path, append(raw, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}

	plan, err := PrepareInstall(path)
	if err != nil {
		t.Fatalf("PrepareInstall() error = %v", err)
	}
	if plan == nil {
		t.Fatal("PrepareInstall() returned nil")
	}

	changed, err := plan.Apply()
	if err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if !changed {
		t.Fatal("Apply() changed = false, want true")
	}

	// Verify marker file exists
	markerPath := OwnershipPath(path)
	if _, err := os.Stat(markerPath); err != nil {
		t.Fatalf("ownership marker not created: %v", err)
	}

	// Read and verify content
	data, err := os.ReadFile(markerPath)
	if err != nil {
		t.Fatal(err)
	}
	var marker Ownership
	if err := json.Unmarshal(data, &marker); err != nil {
		t.Fatalf("unmarshal marker: %v", err)
	}
	if marker.Schema != ownershipSchema {
		t.Fatalf("schema = %q, want %q", marker.Schema, ownershipSchema)
	}
	if marker.PreviousState != "value" {
		t.Fatalf("previous_state = %q, want value", marker.PreviousState)
	}
	if marker.PreviousDefaultAgent != "gentle-orchestrator" {
		t.Fatalf("previous_default_agent = %q", marker.PreviousDefaultAgent)
	}
}

func TestPrepareInstall_ExistingMarker(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "opencode.json")

	// Create marker first
	markerPath := OwnershipPath(path)
	marker := Ownership{
		Schema:               ownershipSchema,
		Version:              ownershipVersion,
		State:                "managed",
		PreviousState:        "value",
		PreviousDefaultAgent: "gentle-orchestrator",
		CapturedAt:           "2026-07-30T00:00:00Z",
	}
	data, _ := json.MarshalIndent(marker, "", "  ")
	if err := os.WriteFile(markerPath, append(data, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}

	plan, err := PrepareInstall(path)
	if err != nil {
		t.Fatalf("PrepareInstall() error = %v", err)
	}

	changed, err := plan.Apply()
	if err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if changed {
		t.Fatal("Apply() changed = true when marker already exists")
	}
}

func TestPrepareInstall_NoDefaultAgent(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "opencode.json")

	cfg := &Config{SettingsPath: path, Raw: map[string]any{}}
	raw, _ := json.MarshalIndent(cfg.Raw, "", "  ")
	if err := os.WriteFile(path, append(raw, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}

	plan, err := PrepareInstall(path)
	if err != nil {
		t.Fatalf("PrepareInstall() error = %v", err)
	}

	changed, err := plan.Apply()
	if err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if !changed {
		t.Fatal("Apply() should write marker even without default_agent")
	}

	// Verify marker records "absent"
	markerPath := OwnershipPath(path)
	data, _ := os.ReadFile(markerPath)
	var marker Ownership
	json.Unmarshal(data, &marker)
	if marker.PreviousState != "absent" {
		t.Fatalf("previous_state = %q, want absent", marker.PreviousState)
	}
}

func TestUninstallPlan_RestorePrevious(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "opencode.json")

	// Set up: config with gentle-orchestrator, quantlab management took over
	initial := map[string]any{
		"default_agent": "gentle-orchestrator",
		"agent": map[string]any{
			"gentle-orchestrator": map[string]any{"description": "test"},
			"quantlab-orchestrator": map[string]any{"description": "quantlab"},
		},
	}
	raw, _ := json.MarshalIndent(initial, "", "  ")
	if err := os.WriteFile(path, append(raw, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}

	// Create ownership marker
	markerPath := OwnershipPath(path)
	ownership := Ownership{
		Schema:               ownershipSchema,
		Version:              ownershipVersion,
		State:                "managed",
		PreviousState:        "value",
		PreviousDefaultAgent: "gentle-orchestrator",
		CapturedAt:           "2026-07-30T00:00:00Z",
	}
	data, _ := json.MarshalIndent(ownership, "", "  ")
	if err := os.WriteFile(markerPath, append(data, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}

	plan, err := PrepareUninstall(path)
	if err != nil {
		t.Fatalf("PrepareUninstall() error = %v", err)
	}

	changed, removed, err := plan.Apply()
	if err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if !changed {
		t.Fatal("Apply() changed = false, want true")
	}
	if !removed {
		t.Fatal("Apply() removed = false, want true")
	}

	// Marker should be deleted
	if _, err := os.Stat(markerPath); !os.IsNotExist(err) {
		t.Fatal("ownership marker should be deleted")
	}

	// Read config back
	cfg, _ := ReadSettings(path)
	da, ok := cfg.GetDefaultAgent()
	if !ok || da != "gentle-orchestrator" {
		t.Fatalf("default_agent after restore = %q, %v; want gentle-orchestrator", da, ok)
	}
}

func TestUninstallPlan_RestoreAbsent(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "opencode.json")

	initial := map[string]any{
		"agent": map[string]any{
			"quantlab-orchestrator": map[string]any{"description": "quantlab"},
		},
	}
	raw, _ := json.MarshalIndent(initial, "", "  ")
	if err := os.WriteFile(path, append(raw, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}

	// Marker says previous was absent
	markerPath := OwnershipPath(path)
	ownership := Ownership{
		Schema:        ownershipSchema,
		Version:       ownershipVersion,
		State:         "managed",
		PreviousState: "absent",
		CapturedAt:    "2026-07-30T00:00:00Z",
	}
	data, _ := json.MarshalIndent(ownership, "", "  ")
	if err := os.WriteFile(markerPath, append(data, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}

	plan, err := PrepareUninstall(path)
	if err != nil {
		t.Fatalf("PrepareUninstall() error = %v", err)
	}

	changed, removed, err := plan.Apply()
	if err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if !changed {
		t.Fatal("Apply() should have removed default_agent")
	}
	if !removed {
		t.Fatal("Apply() should have deleted marker")
	}

	cfg, _ := ReadSettings(path)
	_, ok := cfg.GetDefaultAgent()
	if ok {
		t.Fatal("default_agent should be absent after restore")
	}
}

func TestUninstallPlan_NoMarker(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "opencode.json")

	plan, err := PrepareUninstall(path)
	if err != nil {
		t.Fatalf("PrepareUninstall() error = %v", err)
	}
	if plan.owned != nil {
		t.Fatal("PrepareUninstall() should return nil ownership when no marker exists")
	}

	changed, removed, err := plan.Apply()
	if err != nil {
		t.Fatalf("Apply() error = %v", err)
	}
	if changed || removed {
		t.Fatalf("Apply() changed=%v, removed=%v; want both false", changed, removed)
	}
}

func TestOwnershipPath(t *testing.T) {
	path := OwnershipPath("/home/user/.config/opencode/opencode.json")
	expected := "/home/user/.config/opencode/.quantlab-default-agent.json"
	if path != expected {
		t.Fatalf("OwnershipPath() = %q, want %q", path, expected)
	}
}
