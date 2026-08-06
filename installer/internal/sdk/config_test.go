package sdk

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDefaultSDKConfig(t *testing.T) {
	cfg := DefaultSDKConfig()
	if cfg.BaseURL != DefaultBaseURL {
		t.Fatalf("BaseURL = %q, want %q", cfg.BaseURL, DefaultBaseURL)
	}
	if cfg.Model != DefaultModel {
		t.Fatalf("Model = %q, want %q", cfg.Model, DefaultModel)
	}
	if cfg.LogLevel != "info" {
		t.Fatalf("LogLevel = %q, want info", cfg.LogLevel)
	}
	if cfg.DefaultAgent != "quantlab-orchestrator" {
		t.Fatalf("DefaultAgent = %q", cfg.DefaultAgent)
	}
}

func TestWriteAndReadSDKConfig(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "sdk-config.yaml")

	cfg := DefaultSDKConfig()
	cfg.APIKey = "sk-test-key-12345"
	cfg.Model = "gpt-4o"

	if err := WriteSDKConfig(path, cfg); err != nil {
		t.Fatalf("WriteSDKConfig() error = %v", err)
	}

	// Check permissions
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("perms = %o, want 0600", info.Mode().Perm())
	}

	// Read back
	got, err := ReadSDKConfig(path)
	if err != nil {
		t.Fatalf("ReadSDKConfig() error = %v", err)
	}
	if got.APIKey != "sk-test-key-12345" {
		t.Fatalf("APIKey = %q", got.APIKey)
	}
	if got.Model != "gpt-4o" {
		t.Fatalf("Model = %q, want gpt-4o", got.Model)
	}
}

func TestReadSDKConfig_NotExist(t *testing.T) {
	cfg, err := ReadSDKConfig("/nonexistent/path.yaml")
	if err != nil {
		t.Fatalf("ReadSDKConfig() error = %v", err)
	}
	if cfg == nil {
		t.Fatal("ReadSDKConfig() returned nil")
	}
	if cfg.BaseURL != DefaultBaseURL {
		t.Fatalf("default BaseURL = %q", cfg.BaseURL)
	}
}

func TestReadSDKConfig_FillsDefaults(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "sdk-config.yaml")

	// Write partial config
	if err := os.WriteFile(path, []byte("api_key: sk-test\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	cfg, err := ReadSDKConfig(path)
	if err != nil {
		t.Fatalf("ReadSDKConfig() error = %v", err)
	}
	if cfg.BaseURL != DefaultBaseURL {
		t.Fatalf("BaseURL = %q after read, expected default", cfg.BaseURL)
	}
	if cfg.Model != DefaultModel {
		t.Fatalf("Model = %q after read, expected default", cfg.Model)
	}
	if cfg.APIKey != "sk-test" {
		t.Fatalf("APIKey = %q", cfg.APIKey)
	}
}

func TestDefaultConfigPath(t *testing.T) {
	p := DefaultConfigPath()
	if p == "" {
		t.Fatal("DefaultConfigPath() returned empty")
	}
	if filepath.Base(p) != "sdk-config.yaml" {
		t.Fatalf("DefaultConfigPath() basename = %q", filepath.Base(p))
	}
}

func TestWriteSDKConfig_CreatesDir(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "a", "b", "c.yaml")

	cfg := DefaultSDKConfig()
	if err := WriteSDKConfig(path, cfg); err != nil {
		t.Fatalf("WriteSDKConfig() error = %v", err)
	}
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("file not created: %v", err)
	}
}
