package tools

import (
	"fmt"
	"os/exec"
)

// InstallOpenCodeViaNpm installs OpenCode via npm. Used as a fallback.
func InstallOpenCodeViaNpm(home string) (string, error) {
	if !DetectNpmWritable() {
		return "", fmt.Errorf("npm global not writable")
	}
	cmd := exec.Command("npm", "install", "-g", "--ignore-scripts", "opencode-ai@latest")
	out, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("npm install opencode-ai: %w: %s", err, string(out))
	}
	return "", nil
}