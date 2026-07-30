// Package sdk manages the QuantLab Python SDK: detection, installation, and
// runtime configuration for SDK-to-OpenCode connectivity.
package sdk

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/ogzuz/quantlab/internal/filemerge"
	"gopkg.in/yaml.v3"
)

// SDKConfig holds the runtime configuration for the QuantLab SDK client.
// This is stored separately from the installer's config.yaml and defines
// how the SDK connects to the OpenCode API.
type SDKConfig struct {
	BaseURL      string `yaml:"base_url"`
	APIKey       string `yaml:"api_key"`
	Model        string `yaml:"model"`
	DefaultAgent string `yaml:"default_agent"`
	LogLevel     string `yaml:"log_level"`
}

// DefaultSDKConfig returns an SDKConfig with sensible defaults.
func DefaultSDKConfig() *SDKConfig {
	return &SDKConfig{
		BaseURL:      DefaultBaseURL,
		APIKey:       "",
		Model:        DefaultModel,
		DefaultAgent: "quantlab-orchestrator",
		LogLevel:     "info",
	}
}

// DefaultBaseURL is the default OpenCode API endpoint.
const DefaultBaseURL = "https://opencode.ai/zen/v1"

// DefaultModel is the default AI model for the SDK.
const DefaultModel = "deepseek-v4-flash-free"

// DefaultConfigPath returns the default path for the SDK config file:
// ~/.quantlab/sdk-config.yaml
func DefaultConfigPath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	return filepath.Join(home, ".quantlab", "sdk-config.yaml")
}

// ReadSDKConfig reads the SDK config from the given path. If the file does
// not exist, returns a default config.
func ReadSDKConfig(path string) (*SDKConfig, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return DefaultSDKConfig(), nil
		}
		return nil, fmt.Errorf("read sdk config %q: %w", path, err)
	}

	var cfg SDKConfig
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("parse sdk config %q: %w", path, err)
	}

	if cfg.BaseURL == "" {
		cfg.BaseURL = DefaultBaseURL
	}
	if cfg.Model == "" {
		cfg.Model = DefaultModel
	}
	if cfg.LogLevel == "" {
		cfg.LogLevel = "info"
	}

	return &cfg, nil
}

// WriteSDKConfig writes the SDK config to path with 0600 permissions using
// atomic file write.
func WriteSDKConfig(path string, cfg *SDKConfig) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("create sdk config dir %q: %w", dir, err)
	}

	data, err := yaml.Marshal(cfg)
	if err != nil {
		return fmt.Errorf("marshal sdk config: %w", err)
	}

	_, err = filemerge.WriteFileAtomic(path, data, 0o600)
	if err != nil {
		return fmt.Errorf("write sdk config %q: %w", path, err)
	}

	return nil
}
