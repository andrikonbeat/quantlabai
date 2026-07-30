package opencode

import (
	_ "embed"
	"encoding/json"
	"fmt"

	"github.com/ogzuz/quantlab/installer/internal/filemerge"
)

//go:embed overlay.json
var overlayJSON []byte

// QuantLabAgentNames returns the list of QuantLab agent names that the
// installer manages.
func QuantLabAgentNames() []string {
	return []string{
		"quantlab-orchestrator",
		"quantlab-campaign",
		"quantlab-deploy",
		"quantlab-monitor",
	}
}

// MergeAgents deep-merges the QuantLab agent definitions into the given
// settings config. Only agents under the "agent" key are merged; existing
// agents with the same name are updated (deep-merged), other agents are
// preserved untouched. Returns whether any change was made.
func MergeAgents(cfg *Config) (bool, error) {
	if cfg == nil {
		return false, fmt.Errorf("config is nil")
	}

	var overlay map[string]any
	if err := json.Unmarshal(overlayJSON, &overlay); err != nil {
		return false, fmt.Errorf("unmarshal embedded agent overlay: %w", err)
	}

	settingsJSON, err := json.Marshal(cfg.Raw)
	if err != nil {
		return false, fmt.Errorf("marshal settings: %w", err)
	}

	overlaySettingsJSON, err := json.Marshal(overlay)
	if err != nil {
		return false, fmt.Errorf("marshal overlay: %w", err)
	}

	merged, err := filemerge.MergeJSONObjects(settingsJSON, overlaySettingsJSON)
	if err != nil {
		return false, fmt.Errorf("merge agents: %w", err)
	}

	var mergedMap map[string]any
	if err := json.Unmarshal(merged, &mergedMap); err != nil {
		return false, fmt.Errorf("unmarshal merged result: %w", err)
	}

	// Check if anything actually changed
	before, _ := json.Marshal(cfg.Raw)
	after, _ := json.Marshal(mergedMap)
	changed := string(before) != string(after)

	cfg.Raw = mergedMap
	return changed, nil
}

// RemoveAgents removes all QuantLab-managed agents from the config by
// deleting each known agent key from the "agent" map. Returns whether
// any agent was actually removed.
func RemoveAgents(cfg *Config) (bool, error) {
	if cfg == nil {
		return false, fmt.Errorf("config is nil")
	}

	agents, ok := cfg.Raw["agent"].(map[string]any)
	if !ok || len(agents) == 0 {
		return false, nil
	}

	changed := false
	for _, name := range QuantLabAgentNames() {
		if _, exists := agents[name]; exists {
			delete(agents, name)
			changed = true
		}
	}

	if changed {
		cfg.Raw["agent"] = agents
	}
	return changed, nil
}
