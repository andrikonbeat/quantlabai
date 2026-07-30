package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDefaultConfig(t *testing.T) {
	cfg := DefaultConfig()
	if cfg.QLVersion != "0.1.0" {
		t.Fatalf("QLVersion = %q, want 0.1.0", cfg.QLVersion)
	}
	if cfg.SQX.CLIPath != "/opt/SQX/sqcli" {
		t.Fatalf("SQX.CLIPath = %q", cfg.SQX.CLIPath)
	}
	if cfg.JForex.Port != 19790 {
		t.Fatalf("JForex.Port = %d, want 19790", cfg.JForex.Port)
	}
}

func TestWriteAndReadConfig(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "config.yaml")

	cfg := DefaultConfig()
	cfg.APIKeys.OpenAI = "sk-test123"

	if err := WriteConfig(path, cfg); err != nil {
		t.Fatalf("WriteConfig() error = %v", err)
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
	got, err := ReadConfig(path)
	if err != nil {
		t.Fatalf("ReadConfig() error = %v", err)
	}
	if got.APIKeys.OpenAI != "sk-test123" {
		t.Fatalf("OpenAI key = %q, want sk-test123", got.APIKeys.OpenAI)
	}
}

func TestReadConfig_NotExist(t *testing.T) {
	cfg, err := ReadConfig("/nonexistent/path/config.yaml")
	if err != nil {
		t.Fatalf("ReadConfig() error = %v", err)
	}
	if cfg == nil {
		t.Fatal("ReadConfig() returned nil")
	}
	// Should return defaults
	if cfg.QLVersion != "0.1.0" {
		t.Fatalf("QLVersion = %q, want 0.1.0", cfg.QLVersion)
	}
}

func TestReadConfig_InvalidYAML(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "config.yaml")
	if err := os.WriteFile(path, []byte("invalid: [yaml\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	_, err := ReadConfig(path)
	if err == nil {
		t.Fatal("ReadConfig() expected error for invalid YAML")
	}
}

func TestConfigPath(t *testing.T) {
	p := ConfigPath("/home/user")
	expected := "/home/user/.quantlab/config.yaml"
	if p != expected {
		t.Fatalf("ConfigPath() = %q, want %q", p, expected)
	}
}

func TestConfigHash(t *testing.T) {
	cfg1 := DefaultConfig()
	cfg2 := DefaultConfig()

	h1 := ConfigHash(cfg1)
	h2 := ConfigHash(cfg2)

	if h1 == "" {
		t.Fatal("ConfigHash() returned empty")
	}
	if h1 != h2 {
		t.Fatal("ConfigHash() should be deterministic for same config")
	}

	cfg2.QLVersion = "0.2.0"
	h3 := ConfigHash(cfg2)
	if h3 == h1 {
		t.Fatal("ConfigHash() should change when config changes")
	}
}

func TestStateDir(t *testing.T) {
	d := StateDir("/home/user")
	if d != "/home/user/.quantlab" {
		t.Fatalf("StateDir() = %q", d)
	}
}

func TestWriteConfig_CreatesDir(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "sub", "nested", "config.yaml")

	cfg := DefaultConfig()
	if err := WriteConfig(path, cfg); err != nil {
		t.Fatalf("WriteConfig() error = %v", err)
	}

	if _, err := os.Stat(path); err != nil {
		t.Fatalf("file not created: %v", err)
	}
}
