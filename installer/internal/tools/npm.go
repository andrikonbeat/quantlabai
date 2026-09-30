package tools

import (
	"fmt"
	"os/exec"
)

// InstallOpenCode installs OpenCode via npm if writable. If npm is not
// writable or not available, it returns a display-only fallback message.
func InstallOpenCode(home string) (string, error) {
	if !DetectNpmWritable() {
		return displayFallback("opencode", "npm install -g --ignore-scripts opencode-ai@latest"), nil
	}
	cmd := exec.Command("npm", "install", "-g", "--ignore-scripts", "opencode-ai@latest")
	out, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("npm install opencode-ai: %w: %s", err, string(out))
	}
	return "", nil
}
