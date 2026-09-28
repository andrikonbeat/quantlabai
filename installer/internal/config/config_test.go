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

func TestResolveSQXCliPath(t *testing.T) {
	tests := []struct {
		name       string
		cfg        *SQXConfig
		want       string
		goos       string
	}{
		{
			name: "CLIPath override wins",
			cfg: &SQXConfig{
				InstallPath: "/opt/SQX",
				CLIPath:     "/usr/local/bin/sqcli",
			},
			want: "/usr/local/bin/sqcli",
		},
		{
			name: "derived from InstallPath on linux",
			cfg: &SQXConfig{
				InstallPath: "/opt/SQX",
			},
			want: "/opt/SQX/sqcli",
			goos: "linux",
		},
		{
			name: "nil config returns default",
			cfg:  nil,
			want: "/opt/SQX/sqcli",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.goos != "" {
				// We can't change runtime.GOOS, but we can test the public method
				// which uses runtime.GOOS. For cross-platform coverage, we test
				// the exported ResolveSQXCliPath which is deterministic on the
				// current OS.
			}
			got := tt.cfg.ResolveSQXCliPath()
			if got != tt.want {
				t.Errorf("ResolveSQXCliPath() = %q, want %q", got, tt.want)
			}
		})
	}
}

func TestValidateSQXPath(t *testing.T) {
	t.Run("empty path fails", func(t *testing.T) {
		err := ValidateSQXPath("")
		if err == nil {
			t.Fatal("expected error for empty path")
		}
	})

	t.Run("nonexistent path fails", func(t *testing.T) {
		err := ValidateSQXPath("/nonexistent/SQX")
		if err == nil {
			t.Fatal("expected error for nonexistent path")
		}
	})

	t.Run("valid path with sqcli in root", func(t *testing.T) {
		dir := t.TempDir()
		// Create sqcli binary in root
		bin := filepath.Join(dir, "sqcli")
		if err := os.WriteFile(bin, []byte{}, 0o755); err != nil {
			t.Fatal(err)
		}
		if err := ValidateSQXPath(dir); err != nil {
			t.Fatalf("expected valid path, got error: %v", err)
		}
	})

	t.Run("valid path with sqcli in bin", func(t *testing.T) {
		dir := t.TempDir()
		binDir := filepath.Join(dir, "bin")
		if err := os.MkdirAll(binDir, 0o755); err != nil {
			t.Fatal(err)
		}
		bin := filepath.Join(binDir, "sqcli")
		if err := os.WriteFile(bin, []byte{}, 0o755); err != nil {
			t.Fatal(err)
		}
		if err := ValidateSQXPath(dir); err != nil {
			t.Fatalf("expected valid path, got error: %v", err)
		}
	})
}

func TestNormalizeAccountMode(t *testing.T) {
	tests := []struct {
		input string
		want  string
		err   bool
	}{
		{"", "demo", false},
		{"demo", "demo", false},
		{"live", "live", false},
		{"invalid", "", true},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			got, err := NormalizeAccountMode(tt.input)
			if tt.err {
				if err == nil {
					t.Fatalf("expected error for %q", tt.input)
				}
			} else {
				if err != nil {
					t.Fatalf("unexpected error for %q: %v", tt.input, err)
				}
				if got != tt.want {
					t.Errorf("NormalizeAccountMode(%q) = %q, want %q", tt.input, got, tt.want)
				}
			}
		})
	}
}
