package opencode

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestMergeAgents_EmptyConfig(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "opencode.json")
	cfg := &Config{SettingsPath: path, Raw: map[string]any{}}

	changed, err := MergeAgents(cfg)
	if err != nil {
		t.Fatalf("MergeAgents() error = %v", err)
	}
	if !changed {
		t.Fatal("MergeAgents() changed = false, want true")
	}

	for _, name := range QuantLabAgentNames() {
		if !cfg.HasAgent(name) {
			t.Fatalf("missing agent %q after merge", name)
		}
	}

	// Idempotent: second merge should produce no change
	secondChanged, err := MergeAgents(cfg)
	if err != nil {
		t.Fatalf("MergeAgents() second error = %v", err)
	}
	if secondChanged {
		t.Fatal("MergeAgents() second changed = true, want false (idempotent)")
	}
}

func TestMergeAgents_PreservesExistingAgents(t *testing.T) {
	cfg := &Config{
		Raw: map[string]any{
			"agent": map[string]any{
				"gentle-orchestrator": map[string]any{
					"description": "Gentle AI orchestrator",
				},
			},
			"default_agent": "gentle-orchestrator",
		},
	}

	changed, err := MergeAgents(cfg)
	if err != nil {
		t.Fatalf("MergeAgents() error = %v", err)
	}
	if !changed {
		t.Fatal("MergeAgents() changed = false, want true")
	}

	// Existing agent must survive
	if !cfg.HasAgent("gentle-orchestrator") {
		t.Fatal("gentle-orchestrator agent was removed")
	}

	// QuantLab agents must be added
	for _, name := range QuantLabAgentNames() {
		if !cfg.HasAgent(name) {
			t.Fatalf("missing agent %q", name)
		}
	}

	// default_agent must be preserved
	da, ok := cfg.GetDefaultAgent()
	if !ok || da != "gentle-orchestrator" {
		t.Fatalf("default_agent = %q, %v; want gentle-orchestrator, true", da, ok)
	}
}

func TestRemoveAgents(t *testing.T) {
	cfg := &Config{
		Raw: map[string]any{
			"agent": map[string]any{
				"quantlab-orchestrator": map[string]any{"description": "test"},
				"gentle-orchestrator":   map[string]any{"description": "gentle"},
			},
		},
	}

	changed, err := RemoveAgents(cfg)
	if err != nil {
		t.Fatalf("RemoveAgents() error = %v", err)
	}
	if !changed {
		t.Fatal("RemoveAgents() changed = false, want true")
	}

	if cfg.HasAgent("quantlab-orchestrator") {
		t.Fatal("quantlab-orchestrator survived removal")
	}
	if !cfg.HasAgent("gentle-orchestrator") {
		t.Fatal("gentle-orchestrator was incorrectly removed")
	}

	// Second remove should be no-op
	changed, err = RemoveAgents(cfg)
	if err != nil {
		t.Fatalf("RemoveAgents() second error = %v", err)
	}
	if changed {
		t.Fatal("RemoveAgents() second changed = true, want false")
	}
}

func TestRemoveAgents_NoAgentKey(t *testing.T) {
	cfg := &Config{Raw: map[string]any{}}

	changed, err := RemoveAgents(cfg)
	if err != nil {
		t.Fatalf("RemoveAgents() error = %v", err)
	}
	if changed {
		t.Fatal("RemoveAgents() changed = true on empty config")
	}
}

func TestMergeAgents_Integration(t *testing.T) {
	// Simulate a real opencode.json with gentle-ai agents
	dir := t.TempDir()
	path := filepath.Join(dir, "opencode.json")

	initial := map[string]any{
		"agent": map[string]any{
			"gentle-orchestrator": map[string]any{
				"description": "Gentle AI SDD Orchestrator",
				"mode":        "primary",
			},
		},
		"default_agent": "gentle-orchestrator",
	}
	raw, _ := json.MarshalIndent(initial, "", "  ")
	if err := os.WriteFile(path, append(raw, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}

	cfg, err := ReadSettings(path)
	if err != nil {
		t.Fatalf("ReadSettings() error = %v", err)
	}

	changed, err := MergeAgents(cfg)
	if err != nil {
		t.Fatalf("MergeAgents() error = %v", err)
	}
	if !changed {
		t.Fatal("MergeAgents() changed = false")
	}

	written, err := WriteSettings(path, cfg)
	if err != nil {
		t.Fatalf("WriteSettings() error = %v", err)
	}
	if !written {
		t.Fatal("WriteSettings() changed = false")
	}

	// Read back and verify
	cfg2, err := ReadSettings(path)
	if err != nil {
		t.Fatalf("ReadSettings() after write error = %v", err)
	}

	// gentle-orchestrator preserved
	if !cfg2.HasAgent("gentle-orchestrator") {
		t.Fatal("gentle-orchestrator lost after merge")
	}

	// QuantLab agents present
	for _, name := range QuantLabAgentNames() {
		if !cfg2.HasAgent(name) {
			t.Fatalf("missing agent %q after write", name)
		}
	}

	// default_agent unchanged
	da, ok := cfg2.GetDefaultAgent()
	if !ok || da != "gentle-orchestrator" {
		t.Fatalf("default_agent = %q, %v; want gentle-orchestrator", da, ok)
	}

	// Re-reading and re-merging should be idempotent
	cfg3, _ := ReadSettings(path)
	changed2, err := MergeAgents(cfg3)
	if err != nil {
		t.Fatalf("MergeAgents() re-merge error = %v", err)
	}
	if changed2 {
		t.Fatal("MergeAgents() re-merge changed = true (not idempotent)")
	}
}
