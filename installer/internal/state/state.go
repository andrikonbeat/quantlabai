// Package state manages the QuantLab installation state persisted to
// ~/.quantlab/state.json.
package state

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/ogzuz/quantlab/internal/filemerge"
	"github.com/ogzuz/quantlab/internal/model"
)

// State represents the persisted installation state of QuantLab.
type State struct {
	statePath string

	Version     string          `json:"version"`
	InstallID   string          `json:"install_id"`
	InstalledAt time.Time       `json:"installed_at"`
	QLVersion   string          `json:"quantlab_version"`
	Components  []model.Component `json:"components"`
	ConfigHash  string          `json:"config_hash"`
	Agents      []string        `json:"opencode_agents_created"`
}

// ComponentID identifies a QuantLab component.
type ComponentID string

// Default state directory constants.
const (
	StateDir   = ".quantlab"
	StateFile  = "state.json"
	StateVersion = "1"
)

// Path returns the absolute path to the state file for the given state directory.
func Path(stateDir string) string {
	return filepath.Join(stateDir, StateFile)
}

// LoadOrInit reads the state file from the given directory, or returns a
// default state if the file does not exist. If the file is corrupted, an
// error is returned.
func LoadOrInit(stateDir string) (*State, error) {
	if err := os.MkdirAll(stateDir, 0o755); err != nil {
		return nil, fmt.Errorf("create state dir %q: %w", stateDir, err)
	}

	path := Path(stateDir)
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return &State{
				statePath: path,
				Version:   StateVersion,
				QLVersion: "0.1.0",
			}, nil
		}
		return nil, fmt.Errorf("read state file %q: %w", path, err)
	}

	var s State
	if err := json.Unmarshal(data, &s); err != nil {
		return nil, fmt.Errorf("parse state file %q: %w", path, err)
	}
	s.statePath = path

	return &s, nil
}

// Save writes the state to disk using WriteFileAtomic. Returns whether the
// file was actually changed (compare-and-swap).
func (s *State) Save() (bool, error) {
	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return false, fmt.Errorf("marshal state: %w", err)
	}
	data = append(data, '\n')

	if s.statePath == "" {
		return false, fmt.Errorf("state path is empty — LoadOrInit must be called first")
	}

	result, err := filemerge.WriteFileAtomic(s.statePath, data, 0o644)
	if err != nil {
		return false, fmt.Errorf("write state file %q: %w", s.statePath, err)
	}
	return result.Changed, nil
}

// SetStatePath sets the internal state path. Used when constructing a State
// manually without LoadOrInit.
func (s *State) SetStatePath(path string) {
	s.statePath = path
}

// AddComponent adds a component to the state if not already present.
func (s *State) AddComponent(id model.ComponentID, status, compPath string, count int) {
	for i, c := range s.Components {
		if c.ID == id {
			s.Components[i] = model.Component{
				ID:     id,
				Status: status,
				Path:   compPath,
				Count:  count,
			}
			return
		}
	}
	s.Components = append(s.Components, model.Component{
		ID:     id,
		Status: status,
		Path:   compPath,
		Count:  count,
	})
}

// RemoveComponent removes a component from the state by ID.
func (s *State) RemoveComponent(id model.ComponentID) {
	filtered := make([]model.Component, 0, len(s.Components))
	for _, c := range s.Components {
		if c.ID != id {
			filtered = append(filtered, c)
		}
	}
	s.Components = filtered
}

// HasComponent returns true if the given component ID exists in the state.
func (s *State) HasComponent(id model.ComponentID) bool {
	for _, c := range s.Components {
		if c.ID == id {
			return true
		}
	}
	return false
}

// GetComponent returns the component by ID, or nil if not found.
func (s *State) GetComponent(id model.ComponentID) *model.Component {
	for _, c := range s.Components {
		if c.ID == id {
			return &c
		}
	}
	return nil
}

// AddAgent records an OpenCode agent name as created by QuantLab.
func (s *State) AddAgent(name string) {
	for _, a := range s.Agents {
		if a == name {
			return
		}
	}
	s.Agents = append(s.Agents, name)
}

// RemoveAgent removes an agent name from the state.
func (s *State) RemoveAgent(name string) {
	filtered := make([]string, 0, len(s.Agents))
	for _, a := range s.Agents {
		if a != name {
			filtered = append(filtered, a)
		}
	}
	s.Agents = filtered
}

// StateFileExists returns true if the state file exists on disk.
func (s *State) StateFileExists() bool {
	if s.statePath == "" {
		return false
	}
	_, err := os.Stat(s.statePath)
	return err == nil
}

// HasAnyComponent returns true if the state has at least one component.
func (s *State) HasAnyComponent() bool {
	return len(s.Components) > 0
}

// MarkInstalled sets the InstallID, InstalledAt, and QLVersion fields to
// indicate a completed installation.
func (s *State) MarkInstalled(installID, qlVersion string) {
	s.InstallID = installID
	s.InstalledAt = time.Now().UTC()
	s.QLVersion = qlVersion
}
