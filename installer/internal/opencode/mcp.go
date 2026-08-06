package opencode

import (
	"encoding/json"
	"fmt"

	"github.com/ogzuz/quantlab/internal/filemerge"
)

// MergeMCPServers merges MCP server definitions from the overlay into the
// given settings config. Only new MCP servers are added; existing servers are
// preserved untouched. For QuantLab v1.0, no MCP servers are injected — this
// is a placeholder for future QuantLab MCP integration.
func MergeMCPServers(cfg *Config, overlay map[string]any) (bool, error) {
	if cfg == nil {
		return false, fmt.Errorf("config is nil")
	}
	if len(overlay) == 0 {
		return false, nil
	}

	settingsJSON, err := json.Marshal(cfg.Raw)
	if err != nil {
		return false, fmt.Errorf("marshal settings: %w", err)
	}

	overlayJSON, err := json.Marshal(overlay)
	if err != nil {
		return false, fmt.Errorf("marshal overlay: %w", err)
	}

	merged, err := filemerge.MergeJSONObjects(settingsJSON, overlayJSON)
	if err != nil {
		return false, fmt.Errorf("merge mcp servers: %w", err)
	}

	var mergedMap map[string]any
	if err := json.Unmarshal(merged, &mergedMap); err != nil {
		return false, fmt.Errorf("unmarshal merged result: %w", err)
	}

	before, _ := json.Marshal(cfg.Raw)
	after, _ := json.Marshal(mergedMap)
	changed := string(before) != string(after)

	cfg.Raw = mergedMap
	return changed, nil
}
