package opencode

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestInstallSkills(t *testing.T) {
	dir := t.TempDir()
	skillsDir := filepath.Join(dir, "skills")

	// Use the real assets directory as the embedded FS for testing
	assets := os.DirFS("../assets")

	installed, err := InstallSkills(assets, skillsDir)
	if err != nil {
		t.Fatalf("InstallSkills() error = %v", err)
	}

	if len(installed) == 0 {
		t.Fatal("InstallSkills() installed nothing")
	}

	// Verify files exist
	for _, path := range installed {
		if _, err := os.Stat(path); err != nil {
			t.Fatalf("installed file %q not found: %v", path, err)
		}
	}

	// All installed files should be under skillsDir
	for _, path := range installed {
		if !strings.HasPrefix(path, skillsDir) {
			t.Fatalf("installed file %q outside skills dir %q", path, skillsDir)
		}
	}

	// Second install should be idempotent (no files reported as new)
	secondInstalled, err := InstallSkills(assets, skillsDir)
	if err != nil {
		t.Fatalf("InstallSkills() second error = %v", err)
	}
	if len(secondInstalled) != 0 {
		t.Fatalf("second InstallSkills() reported %d changes (want 0 idempotent)", len(secondInstalled))
	}
}

func TestInstallSkills_CustomSkillsDir(t *testing.T) {
	dir := t.TempDir()
	skillsDir := filepath.Join(dir, "custom", "skills", "path")
	assets := os.DirFS("../assets")

	installed, err := InstallSkills(assets, skillsDir)
	if err != nil {
		t.Fatalf("InstallSkills() error = %v", err)
	}
	if len(installed) == 0 {
		t.Fatal("InstallSkills() installed nothing")
	}
}

func TestInstallSkills_EmptySkillsDir(t *testing.T) {
	assets := os.DirFS("../assets")
	_, err := InstallSkills(assets, "")
	if err == nil {
		t.Fatal("InstallSkills() expected error for empty skills dir")
	}
}

func TestRemoveSkills(t *testing.T) {
	dir := t.TempDir()
	skillsDir := filepath.Join(dir, "skills")

	// Install first, then remove
	assets := os.DirFS("../assets")
	_, err := InstallSkills(assets, skillsDir)
	if err != nil {
		t.Fatalf("InstallSkills() error = %v", err)
	}

	removed, err := RemoveSkills(skillsDir)
	if err != nil {
		t.Fatalf("RemoveSkills() error = %v", err)
	}
	if len(removed) == 0 {
		t.Fatal("RemoveSkills() removed nothing")
	}

	// Verify directories are gone
	for _, path := range removed {
		if _, err := os.Stat(path); !os.IsNotExist(err) {
			t.Fatalf("removed dir %q still exists", path)
		}
	}

	// Second remove should be no-op
	secondRemoved, err := RemoveSkills(skillsDir)
	if err != nil {
		t.Fatalf("RemoveSkills() second error = %v", err)
	}
	if len(secondRemoved) != 0 {
		t.Fatalf("second RemoveSkills() removed %d dirs (want 0)", len(secondRemoved))
	}
}

func TestRemoveSkills_PreservesNonQuantLab(t *testing.T) {
	dir := t.TempDir()
	skillsDir := filepath.Join(dir, "skills")

	// Create some non-QuantLab skills
	nonQL := filepath.Join(skillsDir, "sdd-apply")
	if err := os.MkdirAll(nonQL, 0o755); err != nil {
		t.Fatal(err)
	}
	// Also create a quantlab skill
	qlDir := filepath.Join(skillsDir, "quantlab-run-campaign")
	if err := os.MkdirAll(qlDir, 0o755); err != nil {
		t.Fatal(err)
	}

	removed, err := RemoveSkills(skillsDir)
	if err != nil {
		t.Fatalf("RemoveSkills() error = %v", err)
	}
	if len(removed) != 1 {
		t.Fatalf("RemoveSkills() removed %d; want 1 (only quantlab-*)", len(removed))
	}

	// sdd-apply should survive
	if _, err := os.Stat(nonQL); err != nil {
		t.Fatal("non-quantlab skill dir was incorrectly removed")
	}
}

func TestInstallPrompts(t *testing.T) {
	dir := t.TempDir()
	promptsDir := filepath.Join(dir, "prompts", "quantlab")

	assets := os.DirFS("../assets")

	installed, err := InstallPrompts(assets, promptsDir)
	if err != nil {
		t.Fatalf("InstallPrompts() error = %v", err)
	}

	if len(installed) == 0 {
		t.Fatal("InstallPrompts() installed nothing")
	}

	// Verify files exist
	for _, path := range installed {
		if _, err := os.Stat(path); err != nil {
			t.Fatalf("installed prompt %q not found: %v", path, err)
		}
	}

	// Second install should be idempotent
	secondInstalled, err := InstallPrompts(assets, promptsDir)
	if err != nil {
		t.Fatalf("InstallPrompts() second error = %v", err)
	}
	if len(secondInstalled) != 0 {
		t.Fatalf("second InstallPrompts() reported %d changes (want 0)", len(secondInstalled))
	}
}

func TestInstallPrompts_EmptyDir(t *testing.T) {
	assets := os.DirFS("../assets")
	_, err := InstallPrompts(assets, "")
	if err == nil {
		t.Fatal("InstallPrompts() expected error for empty dir")
	}
}

func TestRemovePrompts(t *testing.T) {
	dir := t.TempDir()
	promptsDir := filepath.Join(dir, "prompts", "quantlab")

	assets := os.DirFS("../assets")
	_, err := InstallPrompts(assets, promptsDir)
	if err != nil {
		t.Fatalf("InstallPrompts() error = %v", err)
	}

	removed, err := RemovePrompts(promptsDir)
	if err != nil {
		t.Fatalf("RemovePrompts() error = %v", err)
	}
	if len(removed) == 0 {
		t.Fatal("RemovePrompts() removed nothing")
	}

	// Second remove should be no-op
	secondRemoved, err := RemovePrompts(promptsDir)
	if err != nil {
		t.Fatalf("RemovePrompts() second error = %v", err)
	}
	if len(secondRemoved) != 0 {
		t.Fatalf("second RemovePrompts() removed %d (want 0)", len(secondRemoved))
	}
}

func TestRemovePrompts_NonExistentDir(t *testing.T) {
	removed, err := RemovePrompts("/nonexistent/path")
	if err != nil {
		t.Fatalf("RemovePrompts() error = %v", err)
	}
	if len(removed) != 0 {
		t.Fatalf("RemovePrompts() removed %d from non-existent dir", len(removed))
	}
}

func TestRemoveSkills_NonExistentDir(t *testing.T) {
	dir := t.TempDir()
	skillsDir := filepath.Join(dir, "nonexistent")

	removed, err := RemoveSkills(skillsDir)
	if err != nil {
		t.Fatalf("RemoveSkills() error = %v", err)
	}
	if len(removed) != 0 {
		t.Fatalf("RemoveSkills() removed %d from non-existent dir", len(removed))
	}
}
