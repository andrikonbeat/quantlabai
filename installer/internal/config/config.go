// Package config manages the QuantLab installer configuration stored in
// ~/.quantlab/config.yaml. This captures user preferences such as SQX path,
// JForex connection details, and external API keys.
package config

import (
	"crypto/sha256"
	"fmt"
	"os"
	"path/filepath"
	"runtime"

	"github.com/ogzuz/quantlab/internal/filemerge"
	"gopkg.in/yaml.v3"
)

// DefaultSQXCliPath is the fallback CLI path used when neither InstallPath
// nor CLIPath is configured.
const DefaultSQXCliPath = "/opt/SQX/sqcli"

// SQXConfig holds SQX installation configuration. InstallPath is the
// canonical install folder; CLIPath is an optional override.
type SQXConfig struct {
	InstallPath string `yaml:"install_path"`
	CLIPath     string `yaml:"cli_path"`
}

// ResolveSQXCliPath returns the effective SQX CLI binary path. An explicit
// CLIPath override wins; otherwise the path is derived from InstallPath.
func (c *SQXConfig) ResolveSQXCliPath() string {
	return c.resolveSQXCliPath(runtime.GOOS)
}

func (c *SQXConfig) resolveSQXCliPath(goos string) string {
	if c == nil {
		return DefaultSQXCliPath
	}
	if c.CLIPath != "" {
		return c.CLIPath
	}
	if c.InstallPath != "" {
		return filepath.Join(c.InstallPath, sqxBinaryName(goos))
	}
	return DefaultSQXCliPath
}

func sqxBinaryName(goos string) string {
	if goos == "windows" {
		return "sqcli.exe"
	}
	return "sqcli"
}

// ValidateSQXPath accepts the SQX install folder only if the sqcli binary
// exists at the folder root or in bin/.
func ValidateSQXPath(dir string) error {
	return validateSQXPath(dir, runtime.GOOS)
}

func validateSQXPath(dir, goos string) error {
	if dir == "" {
		return fmt.Errorf("SQX install path is empty")
	}
	info, err := os.Stat(dir)
	if err != nil {
		return fmt.Errorf("SQX install path %q: %w", dir, err)
	}
	if !info.IsDir() {
		return fmt.Errorf("SQX install path %q is not a directory", dir)
	}

	name := sqxBinaryName(goos)
	root := filepath.Join(dir, name)
	bin := filepath.Join(dir, "bin", name)
	for _, candidate := range []string{root, bin} {
		if fi, err := os.Stat(candidate); err == nil && !fi.IsDir() {
			return nil
		}
	}
	return fmt.Errorf("SQX CLI binary %q not found in %q or %q", name, root, bin)
}

// JForexConfig holds JForex DAS connection settings. AccountMode is
// restricted to demo|live.
type JForexConfig struct {
	InstallPath string `yaml:"install_path"`
	AccountMode string `yaml:"account_mode"`
	Host        string `yaml:"host"`
	Port        int    `yaml:"port"`
	Username    string `yaml:"username"`
	Password    string `yaml:"password"`
}

// NormalizeAccountMode validates a JForex account mode. Empty defaults to "demo".
func NormalizeAccountMode(mode string) (string, error) {
	switch mode {
	case "":
		return "demo", nil
	case "demo", "live":
		return mode, nil
	default:
		return "", fmt.Errorf("account mode must be 'demo' or 'live', got %q", mode)
	}
}

// APIKeysConfig holds external API keys.
type APIKeysConfig struct {
	OpenAI    string `yaml:"openai"`
	Anthropic string `yaml:"anthropic"`
}

// QuantLabConfig represents the ~/.quantlab/config.yaml structure.
type QuantLabConfig struct {
	QLVersion string        `yaml:"quantlab_version"`
	SQX       SQXConfig     `yaml:"sqx"`
	JForex    JForexConfig  `yaml:"jforex"`
	APIKeys   APIKeysConfig `yaml:"api_keys"`
}

// DefaultConfig returns a QuantLabConfig with sensible defaults.
func DefaultConfig() *QuantLabConfig {
	return &QuantLabConfig{
		QLVersion: "0.1.0",
		SQX: SQXConfig{
			CLIPath: DefaultSQXCliPath,
		},
		JForex: JForexConfig{
			AccountMode: "demo",
			Host:        "localhost",
			Port:        19790,
		},
		APIKeys: APIKeysConfig{},
	}
}

// ConfigPath returns the expected path for config.yaml.
func ConfigPath(homeDir string) string {
	return filepath.Join(homeDir, ".quantlab", "config.yaml")
}

// ReadConfig reads and parses the config file at path. If the file does not
// exist, a default config is returned with no error.
func ReadConfig(path string) (*QuantLabConfig, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return DefaultConfig(), nil
		}
		return nil, fmt.Errorf("read config %q: %w", path, err)
	}

	var cfg QuantLabConfig
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("parse config %q: %w", path, err)
	}

	return &cfg, nil
}

// WriteConfig writes the config to path with 0600 permissions using atomic
// file write (temp file + rename).
func WriteConfig(path string, cfg *QuantLabConfig) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("create config dir %q: %w", dir, err)
	}

	data, err := yaml.Marshal(cfg)
	if err != nil {
		return fmt.Errorf("marshal config: %w", err)
	}

	_, err = filemerge.WriteFileAtomic(path, data, 0o600)
	if err != nil {
		return fmt.Errorf("write config %q: %w", path, err)
	}

	return nil
}

// ConfigHash computes a SHA-256 hex digest of the config file.
func ConfigHash(cfg *QuantLabConfig) string {
	data, err := yaml.Marshal(cfg)
	if err != nil {
		return ""
	}
	h := sha256.Sum256(data)
	return fmt.Sprintf("%x", h)
}

// StateDir returns the ~/.quantlab directory path for a given home.
func StateDir(homeDir string) string {
	return filepath.Join(homeDir, ".quantlab")
}
