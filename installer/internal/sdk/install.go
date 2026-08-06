package sdk

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// InstallOptions configures the SDK installation.
type InstallOptions struct {
	// SourceDir points to a local SDK source directory for editable installs.
	// When empty, installs from PyPI.
	SourceDir string

	// Version specifies the SDK version to install (used for pip install
	// quantlab-ai==version). When empty, installs the latest.
	Version string

	// Upgrade indicates whether to upgrade an existing installation.
	Upgrade bool

	// VenvPath is the path to the Python virtual environment. When empty,
	// defaults to ~/.quantlab/venv.
	VenvPath string
}

// SDKInfo describes a detected or installed QuantLab SDK.
type SDKInfo struct {
	Version   string `json:"version"`
	Path      string `json:"path"`
	Installed bool   `json:"installed"`
	VenvPath  string `json:"venv_path,omitempty"`
}

// DetectInstalledSDK checks whether the quantlab-ai SDK is installed in the
// active Python environment by running `pip show quantlab-ai`. Returns
// SDKInfo with Installed=false if not found.
func DetectInstalledSDK() (*SDKInfo, error) {
	// Try pip directly first, then python3 -m pip
	cmds := [][]string{
		{"pip", "show", "quantlab-ai"},
		{"python3", "-m", "pip", "show", "quantlab-ai"},
		{"python", "-m", "pip", "show", "quantlab-ai"},
	}

	for _, cmdArgs := range cmds {
		cmd := exec.Command(cmdArgs[0], cmdArgs[1:]...)
		output, err := cmd.Output()
		if err != nil {
			continue
		}

		info := &SDKInfo{Installed: true}
		for _, line := range bytes.Split(bytes.TrimSpace(output), []byte("\n")) {
			parts := strings.SplitN(string(line), ":", 2)
			if len(parts) == 2 {
				key := strings.TrimSpace(parts[0])
				value := strings.TrimSpace(parts[1])
				switch key {
				case "Version":
					info.Version = value
				case "Location":
					info.Path = value
				}
			}
		}
		return info, nil
	}

	return &SDKInfo{Installed: false}, nil
}

// InstallSDK creates a virtual environment (if needed) and installs the SDK.
// If SourceDir is set, installs in editable mode from that directory.
// Otherwise, installs from PyPI.
func InstallSDK(opts InstallOptions) (*SDKInfo, error) {
	if opts.VenvPath == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return nil, fmt.Errorf("get home dir: %w", err)
		}
		opts.VenvPath = filepath.Join(home, ".quantlab", "venv")
	}

	if err := EnsureVenv(opts.VenvPath); err != nil {
		return nil, fmt.Errorf("ensure venv: %w", err)
	}

	pipPath := filepath.Join(opts.VenvPath, "bin", "pip")

	// Determine install target
	target := "quantlab-ai"
	if opts.SourceDir != "" {
		target = opts.SourceDir
		if err := PipInstall(pipPath, target, opts.Upgrade, true); err != nil {
			return nil, fmt.Errorf("pip install editable: %w", err)
		}
	} else {
		if opts.Version != "" {
			target = "quantlab-ai==" + opts.Version
		}
		if err := PipInstall(pipPath, target, opts.Upgrade, false); err != nil {
			return nil, fmt.Errorf("pip install quantlab-ai: %w", err)
		}
	}

	version := opts.Version
	if version == "" {
		version = "latest"
	}

	return &SDKInfo{
		Installed: true,
		Version:   version,
		VenvPath:  opts.VenvPath,
	}, nil
}

// EnsureVenv creates a Python virtual environment at the given path if one
// does not already exist.
func EnsureVenv(path string) error {
	pythonBin := filepath.Join(path, "bin", "python3")
	if _, err := os.Stat(pythonBin); err == nil {
		return nil // venv already exists
	}

	// Try python3 then python
	pythonCmds := []string{"python3", "python"}
	var lastErr error
	for _, py := range pythonCmds {
		cmd := exec.Command(py, "-m", "venv", path)
		if output, err := cmd.CombinedOutput(); err != nil {
			lastErr = fmt.Errorf("create venv with %q: %w\nOutput: %s", py, err, string(output))
			continue
		}
		return nil
	}

	return fmt.Errorf("cannot create venv: %w", lastErr)
}

// PipInstall runs pip install with the given arguments inside the specified
// pip binary path.
func PipInstall(pipPath, target string, upgrade, editable bool) error {
	args := []string{"install"}
	if upgrade {
		args = append(args, "--upgrade")
	}
	if editable {
		args = append(args, "-e")
	}
	args = append(args, target)

	cmd := exec.Command(pipPath, args...)
	if output, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("pip install failed: %w\nOutput: %s", err, string(output))
	}

	return nil
}

// PythonVersion checks if Python 3.11+ is available by running
// `python3 --version`. Returns the version string or an error if not found.
func PythonVersion() (string, error) {
	cmds := [][]string{
		{"python3", "--version"},
		{"python", "--version"},
	}

	for _, cmdArgs := range cmds {
		cmd := exec.Command(cmdArgs[0], cmdArgs[1:]...)
		output, err := cmd.Output()
		if err != nil {
			continue
		}
		return strings.TrimSpace(string(output)), nil
	}

	return "", fmt.Errorf("python3 not found in PATH")
}

// CheckPython311OrLater checks whether the system has Python 3.11+.
func CheckPython311OrLater() error {
	ver, err := PythonVersion()
	if err != nil {
		return fmt.Errorf("python check: %w", err)
	}

	// Parse "Python 3.12.1" -> major, minor
	var major, minor int
	if _, err := fmt.Sscanf(ver, "Python %d.%d", &major, &minor); err != nil {
		return fmt.Errorf("parse python version %q: %w", ver, err)
	}

	if major < 3 || (major == 3 && minor < 11) {
		return fmt.Errorf("Python 3.11+ required, found %s", ver)
	}

	return nil
}
