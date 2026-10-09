package opencode

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"slices"

	"github.com/andrikonbeat/quantlabai/internal/assets"
	"github.com/andrikonbeat/quantlabai/internal/filemerge"
)

// LoadOverlay reads the embedded overlay.json and returns it as a generic map.
func LoadOverlay() (map[string]any, error) {
	b, err := readLocalOverlay()
	if err != nil {
		return nil, fmt.Errorf("read embedded overlay: %w", err)
	}
	var m map[string]any
	if err := json.Unmarshal(b, &m); err != nil {
		return nil, fmt.Errorf("parse overlay: %w", err)
	}
	return m, nil
}

// OverlayJSON returns the parsed overlay as a generic map. It is a thin
// wrapper around LoadOverlay for callers that need the raw JSON structure.
func OverlayJSON() (map[string]any, error) {
	return LoadOverlay()
}

// QuantLabAgentNames returns the QuantLab-managed agent names defined in
// the overlay. The order is stable: it follows the JSON object key order.
func QuantLabAgentNames() []string {
	ol, err := LoadOverlay()
	if err != nil {
		return []string{}
	}
	agents, ok := ol["agents"].(map[string]any)
	if !ok {
		return []string{}
	}
	names := make([]string, 0, len(agents))
	for name := range agents {
		names = append(names, name)
	}
	slices.Sort(names)
	return names
}

// MergeAgents adds QuantLab agents to the given config. It returns true if
// any changes were made.
func MergeAgents(cfg *Config) (bool, error) {
	if cfg == nil {
		return false, fmt.Errorf("config is nil")
	}

	ol, err := LoadOverlay()
	if err != nil {
		return false, err
	}

	agents, ok := ol["agents"].(map[string]any)
	if !ok {
		return false, fmt.Errorf("overlay missing agents map")
	}

	changed := false
	agentSection, ok := cfg.Raw["agent"].(map[string]any)
	if !ok {
		agentSection = map[string]any{}
		cfg.Raw["agent"] = agentSection
		changed = true
	}

	for name, def := range agents {
		if _, exists := agentSection[name]; !exists {
			agentSection[name] = def
			changed = true
		}
	}

	return changed, nil
}

// RemoveAgents removes QuantLab agents from the given config. It returns
// true if any changes were made.
func RemoveAgents(cfg *Config) (bool, error) {
	if cfg == nil {
		return false, fmt.Errorf("config is nil")
	}

	agentSection, ok := cfg.Raw["agent"].(map[string]any)
	if !ok || len(agentSection) == 0 {
		return false, nil
	}

	qlNames := QuantLabAgentNames()
	changed := false
	for _, name := range qlNames {
		if _, exists := agentSection[name]; exists {
			delete(agentSection, name)
			changed = true
		}
	}

	if len(agentSection) == 0 {
		delete(cfg.Raw, "agent")
	}

	return changed, nil
}

// InstallPromptAssets copies prompt files from the embedded FS to the
// OpenCode prompts directory.
func InstallPromptAssets(dstDir string) (int, error) {
	srcDir := "prompts"
	entries, err := assets.FS.ReadDir(srcDir)
	if err != nil {
		return 0, fmt.Errorf("read embedded prompts directory: %w", err)
	}

	if err := os.MkdirAll(dstDir, 0o755); err != nil {
		return 0, fmt.Errorf("create prompts dir: %w", err)
	}

	count := 0
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		srcPath := filepath.Join(srcDir, e.Name())
		dstPath := filepath.Join(dstDir, e.Name())
		data, err := assets.FS.ReadFile(srcPath)
		if err != nil {
			return count, fmt.Errorf("read %s: %w", srcPath, err)
		}
		_, err = filemerge.WriteFileAtomic(dstPath, data, 0o644)
		if err != nil {
			return count, fmt.Errorf("write %s: %w", dstPath, err)
		}
		count++
	}
	return count, nil
}

// InstallSkillAssets copies skill directories from the embedded FS to the
// OpenCode skills directory.
func InstallSkillAssets(dstDir string) (int, error) {
	srcRoot := "skills"
	entries, err := assets.FS.ReadDir(srcRoot)
	if err != nil {
		return 0, fmt.Errorf("read embedded skills directory: %w", err)
	}

	count := 0
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		srcDir := filepath.Join(srcRoot, e.Name())
		dstDirFull := filepath.Join(dstDir, e.Name())
		if err := copyEmbeddedDir(srcDir, dstDirFull); err != nil {
			return count, fmt.Errorf("copy skill %s: %w", e.Name(), err)
		}
		count++
	}
	return count, nil
}

func copyEmbeddedDir(src, dst string) error {
	if err := os.MkdirAll(dst, 0o755); err != nil {
		return err
	}
	entries, err := assets.FS.ReadDir(src)
	if err != nil {
		return err
	}
	for _, e := range entries {
		srcPath := filepath.Join(src, e.Name())
		dstPath := filepath.Join(dst, e.Name())
		if e.IsDir() {
			if err := copyEmbeddedDir(srcPath, dstPath); err != nil {
				return err
			}
			continue
		}
		data, err := assets.FS.ReadFile(srcPath)
		if err != nil {
			return err
		}
		_, err = filemerge.WriteFileAtomic(dstPath, data, 0o644)
		if err != nil {
			return err
		}
	}
	return nil
}

