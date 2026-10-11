// Package tools provides tool detection and installation for the QuantLab
// onboarding flow.
package tools

import (
	"context"
	"fmt"
	"os/exec"
	"runtime"
	"strings"
	"time"
)

// InstallOpenCode installs OpenCode using the official install script.
// Falls back to package managers on failure with bounded retry.
func InstallOpenCode(home string) (string, error) {
	// Try official install script first (Unix-like systems)
	if runtime.GOOS != "windows" {
		if _, err := runOfficialInstall(); err == nil {
			return "", nil
		}
	}

	// Fallback: try package managers based on OS
	fallbacks := fallbackInstallers()
	for _, fb := range fallbacks {
		if _, err := fb(); err == nil {
			return "", nil
		}
	}

	// All automated methods failed; return manual instructions
	return manualOpenCodeInstructions(), nil
}

func runOfficialInstall() (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "sh", "-c", "curl -fsSL https://opencode.ai/install | bash")
	if out, err := cmd.CombinedOutput(); err != nil {
		return "", fmt.Errorf("official install script: %w: %s", err, string(out))
	}
	return "", nil
}

func fallbackInstallers() []func() (string, error) {
	var fs []func() (string, error)

	// Homebrew (macOS/Linux)
	if DetectCommand("brew") {
		fs = append(fs, func() (string, error) {
			ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
			defer cancel()
			cmd := exec.CommandContext(ctx, "brew", "install", "anomalyco/tap/opencode")
			out, err := cmd.CombinedOutput()
			if err != nil {
				return "", fmt.Errorf("brew install: %w: %s", err, string(out))
			}
			return string(out), nil
		})
	}

	// npm (Node.js)
	if DetectCommand("npm") && DetectNpmWritable() {
		fs = append(fs, func() (string, error) {
			ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
			defer cancel()
			cmd := exec.CommandContext(ctx, "npm", "install", "-g", "--ignore-scripts", "opencode-ai@latest")
			out, err := cmd.CombinedOutput()
			if err != nil {
				return "", fmt.Errorf("npm install: %w: %s", err, string(out))
			}
			return string(out), nil
		})
	}

	// Bun
	if DetectCommand("bun") {
		fs = append(fs, func() (string, error) {
			ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
			defer cancel()
			cmd := exec.CommandContext(ctx, "bun", "add", "-g", "opencode-ai")
			out, err := cmd.CombinedOutput()
			if err != nil {
				return "", fmt.Errorf("bun add: %w: %s", err, string(out))
			}
			return string(out), nil
		})
	}

	// Chocolatey (Windows)
	if runtime.GOOS == "windows" && DetectCommand("choco") {
		fs = append(fs, func() (string, error) {
			ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
			defer cancel()
			cmd := exec.CommandContext(ctx, "choco", "install", "opencode", "-y")
			out, err := cmd.CombinedOutput()
			if err != nil {
				return "", fmt.Errorf("choco install: %w: %s", err, string(out))
			}
			return string(out), nil
		})
	}

	// Scoop (Windows)
	if runtime.GOOS == "windows" && DetectCommand("scoop") {
		fs = append(fs, func() (string, error) {
			ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
			defer cancel()
			cmd := exec.CommandContext(ctx, "scoop", "install", "opencode")
			out, err := cmd.CombinedOutput()
			if err != nil {
				return "", fmt.Errorf("scoop install: %w: %s", err, string(out))
			}
			return string(out), nil
		})
	}

	// Mise
	if DetectCommand("mise") {
		fs = append(fs, func() (string, error) {
			ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
			defer cancel()
			cmd := exec.CommandContext(ctx, "mise", "use", "-g", "github:anomalyco/opencode")
			out, err := cmd.CombinedOutput()
			if err != nil {
				return "", fmt.Errorf("mise use: %w: %s", err, string(out))
			}
			return string(out), nil
		})
	}

	return fs
}

func manualOpenCodeInstructions() string {
	var b strings.Builder
	b.WriteString("OpenCode no se instaló automáticamente.\n\n")
	b.WriteString("Métodos oficiales:\n")
	b.WriteString("  1) curl -fsSL https://opencode.ai/install | bash  (Linux/macOS/WSL)\n")
	b.WriteString("  2) brew install anomalyco/tap/opencode            (macOS/Linux con Homebrew)\n")
	b.WriteString("  3) choco install opencode                       (Windows con Chocolatey)\n")
	b.WriteString("  4) scoop install opencode                       (Windows con Scoop)\n")
	b.WriteString("  5) mise use -g github:anomalyco/opencode        (con Mise)\n")
	b.WriteString("  6) Descargá el binario desde https://github.com/anomalyco/opencode/releases\n\n")
	b.WriteString("Documentación: https://opencode.ai/docs/")
	return b.String()
}

const openCodeDocsURL = "https://opencode.ai/docs/"