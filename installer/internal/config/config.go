// Package config manages the QuantLab installer configuration stored in
// ~/.quantlab/config.yaml. This captures user preferences such as SQX path,
// JForex connection details, and external API keys.
package config

import (
	"crypto/sha256"
	"fmt"
	"os"
	"path/filepath"

	"github.com/ogzuz/quantlab/internal/filemerge"
	"gopkg.in/yaml.v3"
)

// SQXConfig holds SQX CLI configuration.
type SQXConfig struct {
	CLIPath string `yaml:"cli_path"`
}

// JForexConfig holds JForex DAS connection settings.
type JForexConfig struct {
	Host     string `yaml:"host"`
	Port     int    `yaml:"port"`
	Username string `yaml:"username"`
	Password string `yaml:"password"`
}

// APIKeysConfig holds external API keys (OpenAI, Anthropic, etc.).
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
			CLIPath: "/opt/SQX/sqcli",
		},
		JForex: JForexConfig{
			Host: "localhost",
			Port: 19790,
		},
		APIKeys: APIKeysConfig{},
	}
}

// ConfigPath returns the expected path for config.yaml relative to the
// given home directory (e.g., /home/user/.quantlab/config.yaml).
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

// ConfigHash computes a SHA-256 hex digest of the config file for state
// tracking. Returns empty string on marshal failure.
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
