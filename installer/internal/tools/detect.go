package tools

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// DetectCommand checks whether a command exists in PATH.
func DetectCommand(name string) bool {
	_, err := exec.LookPath(name)
	return err == nil
}

// DetectOpenCode checks whether the OpenCode binary is available.
func DetectOpenCode() bool {
	return DetectCommand("opencode")
}

// DetectGentleAI checks whether the gentle-ai binary is available.
func DetectGentleAI() bool {
	return DetectCommand("gentle-ai")
}

// DetectNpmWritable checks whether npm global install is writable.
func DetectNpmWritable() bool {
	cmd := exec.Command("npm", "root", "-g")
	out, err := cmd.Output()
	if err != nil {
		return false
	}
	root := filepath.Join(strings.TrimSpace(string(out)))
	if root == "" {
		return false
	}
	info, err := os.Stat(root)
	if err != nil {
		return false
	}
	if !info.IsDir() {
		return false
	}
	tmp := filepath.Join(root, ".quantlab-write-test")
	f, err := os.Create(tmp)
	if err != nil {
		return false
	}
	f.Close()
	os.Remove(tmp)
	return true
}

// DetectSQX tries to find the StrategyQuantX installation in common locations.
// Returns empty string if not found.
func DetectSQX() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	candidates := []string{
		"/opt/StrategyQuantX",
		filepath.Join(home, "StrategyQuantX"),
		filepath.Join(home, "Applications", "StrategyQuantX"),
	}
	for _, p := range candidates {
		if info, err := os.Stat(p); err == nil && info.IsDir() {
			return p
		}
	}
	return ""
}
