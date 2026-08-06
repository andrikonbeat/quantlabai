// Package opencode manages OpenCode configuration file (opencode.json)
// installation and merge operations for QuantLab agents.
package opencode

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/ogzuz/quantlab/internal/filemerge"
)

// Config represents the top-level structure of an opencode.json settings file.
// Only fields relevant to QuantLab's merge operations are exposed.
type Config struct {
	SettingsPath string
	Raw          map[string]any
}

// ReadSettings reads and parses an opencode.json file. Returns an error if
// the file does not exist or cannot be parsed.
func ReadSettings(path string) (*Config, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read opencode settings %q: %w", path, err)
	}

	parsed, err := filemerge.UnmarshalJSONObject(raw)
	if err != nil {
		return nil, fmt.Errorf("parse opencode settings %q: %w", path, err)
	}

	return &Config{
		SettingsPath: path,
		Raw:          parsed,
	}, nil
}

// ReadSettingsOrEmpty reads opencode.json or returns an empty Config if the
// file does not exist. Other read errors are still propagated.
func ReadSettingsOrEmpty(path string) (*Config, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return &Config{
				SettingsPath: path,
				Raw:          map[string]any{},
			}, nil
		}
		return nil, fmt.Errorf("read opencode settings %q: %w", path, err)
	}

	parsed, err := filemerge.UnmarshalJSONObject(raw)
	if err != nil {
		return &Config{
			SettingsPath: path,
			Raw:          map[string]any{},
		}, nil
	}

	return &Config{
		SettingsPath: path,
		Raw:          parsed,
	}, nil
}

// WriteSettings writes the config back to disk using WriteFileAtomic.
// Returns whether the file was actually changed (compare-and-swap).
func WriteSettings(path string, cfg *Config) (bool, error) {
	data, err := json.MarshalIndent(cfg.Raw, "", "  ")
	if err != nil {
		return false, fmt.Errorf("marshal opencode settings: %w", err)
	}
	data = append(data, '\n')

	result, err := filemerge.WriteFileAtomic(path, data, 0o644)
	if err != nil {
		return false, fmt.Errorf("write opencode settings %q: %w", path, err)
	}
	return result.Changed, nil
}

// DefaultSettingsPath returns the default OpenCode settings path:
// ~/.config/opencode/opencode.json
func DefaultSettingsPath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	return filepath.Join(home, ".config", "opencode", "opencode.json")
}

// DefaultSettingsDir returns ~/.config/opencode
func DefaultSettingsDir() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	return filepath.Join(home, ".config", "opencode")
}

// DefaultSkillsDir returns ~/.config/opencode/skills
func DefaultSkillsDir() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	return filepath.Join(home, ".config", "opencode", "skills")
}

// DefaultPromptsDir returns ~/.config/opencode/prompts/quantlab
func DefaultPromptsDir() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	return filepath.Join(home, ".config", "opencode", "prompts", "quantlab")
}

// GetDefaultAgent returns the current default_agent value from the config.
func (c *Config) GetDefaultAgent() (string, bool) {
	v, ok := c.Raw["default_agent"]
	if !ok {
		return "", false
	}
	s, ok := v.(string)
	return s, ok
}

// SetDefaultAgent sets the default_agent field in the config.
func (c *Config) SetDefaultAgent(agent string) {
	c.Raw["default_agent"] = agent
}

// RemoveDefaultAgent removes the default_agent field from the config.
func (c *Config) RemoveDefaultAgent() {
	delete(c.Raw, "default_agent")
}

// GetAgent returns the agent definition for the given name, or nil if not present.
func (c *Config) GetAgent(name string) map[string]any {
	agents, ok := c.Raw["agent"].(map[string]any)
	if !ok {
		return nil
	}
	agent, _ := agents[name].(map[string]any)
	return agent
}

// HasAgent reports whether an agent with the given name exists.
func (c *Config) HasAgent(name string) bool {
	agents, ok := c.Raw["agent"].(map[string]any)
	if !ok {
		return false
	}
	_, exists := agents[name]
	return exists
}
