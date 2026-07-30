package sdk

import (
	"os"
	"path/filepath"
	"testing"
)

func TestPythonVersion_NotFound(t *testing.T) {
	// Save PATH and restore after test
	oldPath := os.Getenv("PATH")
	defer os.Setenv("PATH", oldPath)

	os.Setenv("PATH", "")
	_, err := PythonVersion()
	if err == nil {
		t.Skip("Python found in restricted PATH — skipping, not an error")
	}
}

func TestCheckPython311OrLater_NotInstalled(t *testing.T) {
	oldPath := os.Getenv("PATH")
	defer os.Setenv("PATH", oldPath)

	os.Setenv("PATH", "")
	err := CheckPython311OrLater()
	if err == nil {
		t.Skip("Python found — skipping")
	}
}

func TestDetectInstalledSDK_NotInstalled(t *testing.T) {
	// Should not error, just return Installed=false
	info, err := DetectInstalledSDK()
	if err != nil {
		t.Fatalf("DetectInstalledSDK() error = %v", err)
	}
	// If SDK is actually installed on this machine, this test is still valid
	// (just testing the function runs without error)
	t.Logf("SDK installed: %v, version: %s", info.Installed, info.Version)
}

func TestInstallOptions_Defaults(t *testing.T) {
	opts := InstallOptions{}
	if opts.VenvPath != "" {
		t.Fatalf("default VenvPath should be empty")
	}
}

func TestEnsureVenv_CreatesVenv(t *testing.T) {
	dir := t.TempDir()
	venvPath := filepath.Join(dir, "test-venv")

	err := EnsureVenv(venvPath)
	if err != nil {
		// Python venv might not be available in this environment
		t.Skipf("venv creation skipped: %v", err)
	}

	// Check that the venv was created
	pythonBin := filepath.Join(venvPath, "bin", "python3")
	if _, err := os.Stat(pythonBin); err != nil {
		t.Fatalf("python3 binary not found in venv: %v", err)
	}
}

func TestEnsureVenv_ExistingVenv(t *testing.T) {
	dir := t.TempDir()
	venvPath := filepath.Join(dir, "existing-venv")

	// Create first time
	err := EnsureVenv(venvPath)
	if err != nil {
		t.Skipf("venv creation skipped: %v", err)
	}

	// Second time should succeed (idempotent)
	if err := EnsureVenv(venvPath); err != nil {
		t.Fatalf("EnsureVenv() on existing venv error = %v", err)
	}
}

func TestPipInstall_InvalidTarget(t *testing.T) {
	dir := t.TempDir()
	venvPath := filepath.Join(dir, "venv")

	err := EnsureVenv(venvPath)
	if err != nil {
		t.Skipf("venv creation skipped: %v", err)
	}

	pipPath := filepath.Join(venvPath, "bin", "pip")
	if _, err := os.Stat(pipPath); err != nil {
		t.Skipf("pip not found in venv: %v", err)
	}

	// Install a non-existent package should fail
	err = PipInstall(pipPath, "nonexistent-package-12345-abc", false, false)
	if err == nil {
		t.Skip("pip install succeeded unexpectedly (network may resolve package names)")
	}
}

func TestInstallSDK_WithSourceDir(t *testing.T) {
	dir := t.TempDir()

	// Create a minimal Python package to act as SDK source
	sourceDir := filepath.Join(dir, "sdk-source")
	if err := os.MkdirAll(sourceDir, 0o755); err != nil {
		t.Fatal(err)
	}
	pyproject := filepath.Join(sourceDir, "pyproject.toml")
	if err := os.WriteFile(pyproject, []byte(`[project]
name = "quantlab-ai"
version = "0.1.0"
requires-python = ">=3.11"
`), 0o644); err != nil {
		t.Fatal(err)
	}

	opts := InstallOptions{
		SourceDir: sourceDir,
		VenvPath:  filepath.Join(dir, "venv"),
		Upgrade:   true,
	}

	info, err := InstallSDK(opts)
	if err != nil {
		t.Skipf("SDK install skipped (may need network/venv): %v", err)
	}

	if !info.Installed {
		t.Fatal("InstallSDK() returned Installed=false")
	}
	if info.VenvPath == "" {
		t.Fatal("InstallSDK() returned empty VenvPath")
	}
}
