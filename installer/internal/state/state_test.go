package state

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/ogzuz/quantlab/installer/internal/model"
)

func TestLoadOrInit_NewState(t *testing.T) {
	dir := t.TempDir()
	stateDir := filepath.Join(dir, ".quantlab")

	s, err := LoadOrInit(stateDir)
	if err != nil {
		t.Fatalf("LoadOrInit() error = %v", err)
	}
	if s == nil {
		t.Fatal("LoadOrInit() returned nil")
	}
	if s.Version != StateVersion {
		t.Fatalf("Version = %q, want %q", s.Version, StateVersion)
	}
	if s.QLVersion != "0.1.0" {
		t.Fatalf("QLVersion = %q, want 0.1.0", s.QLVersion)
	}
	if !s.InstalledAt.IsZero() {
		t.Fatal("InstalledAt should be zero for new state")
	}
}

func TestSaveAndLoad(t *testing.T) {
	dir := t.TempDir()
	stateDir := filepath.Join(dir, ".quantlab")

	s, err := LoadOrInit(stateDir)
	if err != nil {
		t.Fatalf("LoadOrInit() error = %v", err)
	}

	s.MarkInstalled("test-id-123", "0.1.0")
	s.AddComponent(model.ComponentSDK, "installed", "/path/to/venv", 0)
	s.AddComponent(model.ComponentOpenCodeAgents, "installed", "", 4)
	s.AddAgent("quantlab-orchestrator")
	s.AddAgent("quantlab-campaign")

	changed, err := s.Save()
	if err != nil {
		t.Fatalf("Save() error = %v", err)
	}
	if !changed {
		t.Fatal("Save() changed = false, want true")
	}

	// Load again
	s2, err := LoadOrInit(stateDir)
	if err != nil {
		t.Fatalf("LoadOrInit() second error = %v", err)
	}
	if s2.InstallID != "test-id-123" {
		t.Fatalf("InstallID = %q, want test-id-123", s2.InstallID)
	}
	if !s2.HasComponent(model.ComponentSDK) {
		t.Fatal("ComponentSDK not found")
	}
	if !s2.HasComponent(model.ComponentOpenCodeAgents) {
		t.Fatal("ComponentOpenCodeAgents not found")
	}
	if len(s2.Agents) != 2 {
		t.Fatalf("Agents = %v, want 2", s2.Agents)
	}

	// Save again should be idempotent
	changed2, err := s2.Save()
	if err != nil {
		t.Fatalf("Save() second error = %v", err)
	}
	if changed2 {
		t.Fatal("Save() second changed = true (not idempotent)")
	}
}

func TestAddRemoveComponent(t *testing.T) {
	s := &State{}

	s.AddComponent(model.ComponentSDK, "installed", "~/.quantlab/venv", 0)
	if !s.HasComponent(model.ComponentSDK) {
		t.Fatal("HasComponent(ComponentSDK) = false after Add")
	}

	comp := s.GetComponent(model.ComponentSDK)
	if comp == nil {
		t.Fatal("GetComponent(ComponentSDK) = nil")
	}
	if comp.Status != "installed" {
		t.Fatalf("Status = %q, want installed", comp.Status)
	}

	// Add again (update)
	s.AddComponent(model.ComponentSDK, "upgraded", "~/.quantlab/venv", 0)
	comp = s.GetComponent(model.ComponentSDK)
	if comp.Status != "upgraded" {
		t.Fatalf("Status after update = %q, want upgraded", comp.Status)
	}

	s.RemoveComponent(model.ComponentSDK)
	if s.HasComponent(model.ComponentSDK) {
		t.Fatal("HasComponent(ComponentSDK) = true after Remove")
	}
}

func TestHasComponent(t *testing.T) {
	s := &State{}
	if s.HasComponent(model.ComponentSDK) {
		t.Fatal("HasComponent should be false for empty state")
	}
}

func TestAddRemoveAgent(t *testing.T) {
	s := &State{}

	s.AddAgent("quantlab-orchestrator")
	s.AddAgent("quantlab-campaign")
	s.AddAgent("quantlab-orchestrator") // duplicate

	if len(s.Agents) != 2 {
		t.Fatalf("Agents len = %d, want 2 (dedup)", len(s.Agents))
	}

	s.RemoveAgent("quantlab-orchestrator")
	if len(s.Agents) != 1 {
		t.Fatalf("Agents len after remove = %d, want 1", len(s.Agents))
	}
	if s.Agents[0] != "quantlab-campaign" {
		t.Fatalf("remaining agent = %q, want quantlab-campaign", s.Agents[0])
	}
}

func TestMarkInstalled(t *testing.T) {
	s := &State{}
	s.MarkInstalled("uuid-123", "0.2.0")

	if s.InstallID != "uuid-123" {
		t.Fatalf("InstallID = %q", s.InstallID)
	}
	if s.QLVersion != "0.2.0" {
		t.Fatalf("QLVersion = %q", s.QLVersion)
	}
	if s.InstalledAt.IsZero() {
		t.Fatal("InstalledAt should be set")
	}
}

func TestLoadOrInit_CorruptedState(t *testing.T) {
	dir := t.TempDir()
	stateDir := filepath.Join(dir, ".quantlab")
	statePath := filepath.Join(stateDir, StateFile)

	if err := os.MkdirAll(stateDir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(statePath, []byte(`{corrupted`), 0o644); err != nil {
		t.Fatal(err)
	}

	_, err := LoadOrInit(stateDir)
	if err == nil {
		t.Fatal("LoadOrInit() expected error for corrupted file")
	}
}

func TestPath(t *testing.T) {
	p := Path("/home/user/.quantlab")
	expected := "/home/user/.quantlab/state.json"
	if p != expected {
		t.Fatalf("Path() = %q, want %q", p, expected)
	}
}

func TestSaveWithoutPath(t *testing.T) {
	s := &State{}
	_, err := s.Save()
	if err == nil {
		t.Fatal("Save() expected error without state path")
	}
}

func TestRoundTripJSON(t *testing.T) {
	// Verify the JSON serialization matches the state schema
	s := &State{
		Version:   "1",
		InstallID: "test-uuid",
		QLVersion: "0.1.0",
		InstalledAt: time.Date(2026, 7, 30, 14, 0, 0, 0, time.UTC),
		Components: []model.Component{
			{ID: model.ComponentSDK, Status: "installed", Path: "~/.quantlab/venv"},
		},
		Agents: []string{"quantlab-orchestrator"},
	}

	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		t.Fatalf("marshal error = %v", err)
	}

	var decoded State
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("unmarshal error = %v", err)
	}

	if decoded.InstallID != "test-uuid" {
		t.Fatalf("InstallID after round-trip = %q", decoded.InstallID)
	}
	if len(decoded.Components) != 1 {
		t.Fatalf("Components after round-trip = %d", len(decoded.Components))
	}
}
