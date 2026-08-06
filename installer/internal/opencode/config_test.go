package opencode

import (
	"os"
	"path/filepath"
	"testing"
)

func TestReadSettings(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "opencode.json")
	content := `{
  "agent": {
    "gentle-orchestrator": {
      "description": "test"
    }
  },
  "default_agent": "gentle-orchestrator"
}`
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}

	cfg, err := ReadSettings(path)
	if err != nil {
		t.Fatalf("ReadSettings() error = %v", err)
	}
	if cfg.SettingsPath != path {
		t.Fatalf("SettingsPath = %q, want %q", cfg.SettingsPath, path)
	}

	defaultAgent, ok := cfg.GetDefaultAgent()
	if !ok || defaultAgent != "gentle-orchestrator" {
		t.Fatalf("GetDefaultAgent() = %q, %v; want gentle-orchestrator, true", defaultAgent, ok)
	}

	agent := cfg.GetAgent("gentle-orchestrator")
	if agent == nil {
		t.Fatal("GetAgent(gentle-orchestrator) returned nil")
	}
	if agent["description"] != "test" {
		t.Fatalf("description = %v, want test", agent["description"])
	}
}

func TestReadSettings_FileNotFound(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "nonexistent.json")

	_, err := ReadSettings(path)
	if err == nil {
		t.Fatal("ReadSettings() expected error for missing file")
	}
}

func TestReadSettingsOrEmpty(t *testing.T) {
	t.Run("file not found returns empty", func(t *testing.T) {
		dir := t.TempDir()
		path := filepath.Join(dir, "nonexistent.json")

		cfg, err := ReadSettingsOrEmpty(path)
		if err != nil {
			t.Fatalf("ReadSettingsOrEmpty() error = %v", err)
		}
		if cfg == nil {
			t.Fatal("ReadSettingsOrEmpty() returned nil")
		}
		if len(cfg.Raw) != 0 {
			t.Fatalf("expected empty config, got %#v", cfg.Raw)
		}
	})

	t.Run("malformed file returns empty", func(t *testing.T) {
		dir := t.TempDir()
		path := filepath.Join(dir, "bad.json")
		if err := os.WriteFile(path, []byte(`{bad`), 0o644); err != nil {
			t.Fatal(err)
		}

		cfg, err := ReadSettingsOrEmpty(path)
		if err != nil {
			t.Fatalf("ReadSettingsOrEmpty() error = %v", err)
		}
		if len(cfg.Raw) != 0 {
			t.Fatalf("expected empty config for malformed file")
		}
	})
}

func TestWriteSettings(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "opencode.json")

	cfg := &Config{
		SettingsPath: path,
		Raw: map[string]any{
			"default_agent": "quantlab-orchestrator",
			"agent": map[string]any{
				"quantlab-orchestrator": map[string]any{
					"description": "QuantLab AI orchestrator",
				},
			},
		},
	}

	changed, err := WriteSettings(path, cfg)
	if err != nil {
		t.Fatalf("WriteSettings() error = %v", err)
	}
	if !changed {
		t.Fatal("WriteSettings() changed = false, want true")
	}

	// Read back
	read, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if len(read) == 0 {
		t.Fatal("written file is empty")
	}

	// Second write should be no-op (idempotent)
	changed, err = WriteSettings(path, cfg)
	if err != nil {
		t.Fatalf("WriteSettings() second error = %v", err)
	}
	if changed {
		t.Fatal("WriteSettings() second changed = true, want false (idempotent)")
	}
}

func TestConfigAgentAccessors(t *testing.T) {
	cfg := &Config{
		Raw: map[string]any{
			"agent": map[string]any{
				"quantlab-orchestrator": map[string]any{
					"description": "test",
				},
			},
		},
	}

	if !cfg.HasAgent("quantlab-orchestrator") {
		t.Fatal("HasAgent() = false, want true")
	}
	if cfg.HasAgent("nonexistent") {
		t.Fatal("HasAgent(nonexistent) = true, want false")
	}

	agent := cfg.GetAgent("quantlab-orchestrator")
	if agent == nil || agent["description"] != "test" {
		t.Fatalf("GetAgent() = %#v", agent)
	}

	cfg.SetDefaultAgent("quantlab-orchestrator")
	da, ok := cfg.GetDefaultAgent()
	if !ok || da != "quantlab-orchestrator" {
		t.Fatalf("GetDefaultAgent() after Set = %q, %v", da, ok)
	}

	cfg.RemoveDefaultAgent()
	_, ok = cfg.GetDefaultAgent()
	if ok {
		t.Fatal("GetDefaultAgent() after Remove = true, want false")
	}
}
