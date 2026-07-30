package opencode

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

const (
	ownershipSchema  = "quantlab.opencode-default-agent"
	ownershipVersion = 1
)

// Ownership records the state of default_agent before QuantLab took ownership.
// Used to restore the original value on uninstall.
type Ownership struct {
	Schema               string `json:"schema"`
	Version              int    `json:"version"`
	State                string `json:"state"`
	PreviousState        string `json:"previous_state"`
	PreviousDefaultAgent string `json:"previous_default_agent,omitempty"`
	CapturedAt           string `json:"captured_at"`
}

// InstallPlan captures the current default_agent state so it can be restored later.
type InstallPlan struct {
	settingsPath string
	cfg          *Config
}

// UninstallPlan holds the information needed to restore default_agent on uninstall.
type UninstallPlan struct {
	settingsPath string
	owned        *Ownership
}

// OwnershipPath returns the path to the ownership marker file.
func OwnershipPath(settingsPath string) string {
	return filepath.Join(filepath.Dir(settingsPath), ".quantlab-default-agent.json")
}

// PrepareInstall captures the current default_agent value and checks if an
// ownership marker already exists. Returns an InstallPlan.
func PrepareInstall(settingsPath string) (*InstallPlan, error) {
	cfg, err := ReadSettingsOrEmpty(settingsPath)
	if err != nil {
		return nil, err
	}
	return &InstallPlan{
		settingsPath: settingsPath,
		cfg:          cfg,
	}, nil
}

// Apply writes the ownership marker if default_agent is not already managed
// by QuantLab. Does NOT change default_agent — QuantLab is a subagent, not
// the primary orchestrator. Returns whether the marker was written.
func (p *InstallPlan) Apply() (bool, error) {
	owned, err := readOwnership(OwnershipPath(p.settingsPath))
	if err != nil {
		return false, err
	}
	if owned != nil {
		// Already has ownership marker — skip
		return false, nil
	}

	current, present := p.cfg.GetDefaultAgent()
	prevState := "absent"
	if present {
		prevState = "value"
	}

	ownership := &Ownership{
		Schema:               ownershipSchema,
		Version:              ownershipVersion,
		State:                "managed",
		PreviousState:        prevState,
		PreviousDefaultAgent: current,
		CapturedAt:           time.Now().UTC().Format(time.RFC3339),
	}

	data, err := json.MarshalIndent(ownership, "", "  ")
	if err != nil {
		return false, fmt.Errorf("marshal ownership: %w", err)
	}
	data = append(data, '\n')

	ownerPath := OwnershipPath(p.settingsPath)
	dir := filepath.Dir(ownerPath)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return false, fmt.Errorf("create ownership dir: %w", err)
	}

	if err := os.WriteFile(ownerPath, data, 0o644); err != nil {
		return false, fmt.Errorf("write ownership marker: %w", err)
	}

	return true, nil
}

// PrepareUninstall reads the ownership marker and prepares to restore
// the previous default_agent.
func PrepareUninstall(settingsPath string) (*UninstallPlan, error) {
	owned, err := readOwnership(OwnershipPath(settingsPath))
	if err != nil {
		return nil, err
	}
	return &UninstallPlan{
		settingsPath: settingsPath,
		owned:        owned,
	}, nil
}

// Apply restores the previous default_agent value recorded in the ownership
// marker. Returns changed (if settings were modified), removed (if the
// ownership marker was deleted), and any error.
func (p *UninstallPlan) Apply() (changed bool, removed bool, err error) {
	cfg, err := ReadSettingsOrEmpty(p.settingsPath)
	if err != nil {
		return false, false, err
	}

	if p.owned != nil {
		switch p.owned.PreviousState {
		case "absent":
			cfg.RemoveDefaultAgent()
			changed = true
		case "value":
			cfg.SetDefaultAgent(p.owned.PreviousDefaultAgent)
			changed = true
		}

		// Delete the ownership marker
		ownerPath := OwnershipPath(p.settingsPath)
		if err := os.Remove(ownerPath); err != nil && !os.IsNotExist(err) {
			return changed, false, fmt.Errorf("remove ownership marker: %w", err)
		}
		removed = true
	}

	if changed {
		_, err := WriteSettings(p.settingsPath, cfg)
		if err != nil {
			return changed, removed, fmt.Errorf("write settings after restore: %w", err)
		}
	}

	return changed, removed, nil
}

func readOwnership(path string) (*Ownership, error) {
	raw, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("read ownership %q: %w", path, err)
	}

	var owned Ownership
	if err := json.Unmarshal(raw, &owned); err != nil {
		return nil, fmt.Errorf("parse ownership %q: %w", path, err)
	}

	if owned.Schema != ownershipSchema || owned.Version != ownershipVersion {
		return nil, nil
	}

	return &owned, nil
}
