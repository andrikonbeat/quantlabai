// Package tools provides tool detection and installation for the QuantLab
// onboarding flow.
package tools

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// InstallGentleAI installs gentle-ai using the official install script.
// Falls back to go install if Go is available.
func InstallGentleAI(home string) (string, error) {
	// Try official install script first (Unix-like systems)
	if runtime.GOOS != "windows" {
		if err := runOfficialGentleAIInstall(); err == nil {
			return "", nil
		}
	}

	// Fallback: go install if Go is available
	if DetectCommand("go") {
		if err := runGoInstall(); err == nil {
			return "", nil
		}
	}

	// All automated methods failed; return manual instructions
	return manualGentleAIInstructions(), nil
}

func runOfficialGentleAIInstall() error {
	ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "sh", "-c", "curl -fsSL https://raw.githubusercontent.com/Gentleman-Programming/gentle-ai/main/scripts/install.sh | bash")
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("official gentle-ai install script: %w: %s", err, string(out))
	}
	return nil
}

func runGoInstall() error {
	ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "go", "install", "github.com/gentleman-programming/gentle-ai/v4/cmd/gentle-ai@latest")
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("go install gentle-ai: %w: %s", err, string(out))
	}
	return nil
}

func manualGentleAIInstructions() string {
	var b strings.Builder
	b.WriteString("gentle-ai no se instaló automáticamente.\n\n")
	b.WriteString("Métodos oficiales:\n")
	b.WriteString("  1) curl -fsSL https://raw.githubusercontent.com/Gentleman-Programming/gentle-ai/main/scripts/install.sh | bash  (Linux/macOS/WSL)\n")
	b.WriteString("  2) go install github.com/gentleman-programming/gentle-ai/v4/cmd/gentle-ai@latest  (requiere Go 1.25+)\n")
	b.WriteString("  3) brew install gentleman-programming/tap/gentle-ai  (macOS/Linux con Homebrew)\n")
	b.WriteString("  4) Descargá el binario desde https://github.com/Gentleman-Programming/gentle-ai/releases\n\n")
	b.WriteString("Documentación: https://github.com/Gentleman-Programming/gentle-ai")
	return b.String()
}

// DetectEngram checks whether the Engram memory system is available.
// Engram is installed by gentle-ai and provides persistent memory for agents.
func DetectEngram() bool {
	// Check for engram binary in PATH
	if DetectCommand("engram") {
		return true
	}
	// Check for engram config/data in common locations
	home, err := os.UserHomeDir()
	if err != nil {
		return false
	}
	commonPaths := []string{
		filepath.Join(home, ".config", "engram"),
		filepath.Join(home, ".local", "share", "engram"),
		filepath.Join(home, ".engram"),
	}
	for _, p := range commonPaths {
		if info, err := os.Stat(p); err == nil && info.IsDir() {
			return true
		}
	}
	return false
}

// DetectGentleAIWithEngram checks both gentle-ai and engram presence.
func DetectGentleAIWithEngram() (gentleAI, engram bool) {
	return DetectGentleAI(), DetectEngram()
}