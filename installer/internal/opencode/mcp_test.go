package opencode

import (
	"testing"
)

func TestMergeMCPServers_EmptyOverlay(t *testing.T) {
	cfg := &Config{Raw: map[string]any{
		"mcp": map[string]any{
			"engram": map[string]any{
				"type":    "local",
				"command": "engram",
			},
		},
	}}

	changed, err := MergeMCPServers(cfg, nil)
	if err != nil {
		t.Fatalf("MergeMCPServers() error = %v", err)
	}
	if changed {
		t.Fatal("MergeMCPServers() changed with nil overlay")
	}

	changed, err = MergeMCPServers(cfg, map[string]any{})
	if err != nil {
		t.Fatalf("MergeMCPServers() error = %v", err)
	}
	if changed {
		t.Fatal("MergeMCPServers() changed with empty overlay")
	}
}

func TestMergeMCPServers_AddsNewServer(t *testing.T) {
	cfg := &Config{Raw: map[string]any{
		"mcp": map[string]any{
			"engram": map[string]any{"type": "local", "command": "engram"},
		},
	}}

	overlay := map[string]any{
		"mcp": map[string]any{
			"quantlab-db": map[string]any{
				"type": "local",
				"command": []any{"quantlab-mcp", "--db"},
			},
		},
	}

	changed, err := MergeMCPServers(cfg, overlay)
	if err != nil {
		t.Fatalf("MergeMCPServers() error = %v", err)
	}
	if !changed {
		t.Fatal("MergeMCPServers() changed = false, want true")
	}

	mcp, _ := cfg.Raw["mcp"].(map[string]any)
	if _, ok := mcp["quantlab-db"]; !ok {
		t.Fatal("quantlab-db MCP server not added")
	}
	// engram must still be there
	if _, ok := mcp["engram"]; !ok {
		t.Fatal("engram MCP server was removed")
	}
}

func TestMergeMCPServers_Idempotent(t *testing.T) {
	overlay := map[string]any{
		"mcp": map[string]any{
			"quantlab-db": map[string]any{"type": "local", "command": "quantlab-mcp"},
		},
	}

	cfg := &Config{Raw: map[string]any{}}

	first, err := MergeMCPServers(cfg, overlay)
	if err != nil {
		t.Fatalf("first merge error = %v", err)
	}
	if !first {
		t.Fatal("first merge changed = false")
	}

	second, err := MergeMCPServers(cfg, overlay)
	if err != nil {
		t.Fatalf("second merge error = %v", err)
	}
	if second {
		t.Fatal("second merge changed = true (not idempotent)")
	}
}

func TestMergeMCPServers_PreservesExisting(t *testing.T) {
	cfg := &Config{Raw: map[string]any{
		"mcp": map[string]any{
			"context7": map[string]any{"type": "remote", "url": "https://mcp.context7.com/mcp"},
			"engram":   map[string]any{"type": "local", "command": "engram"},
		},
	}}

	overlay := map[string]any{
		"mcp": map[string]any{
			"quantlab-db": map[string]any{"type": "local", "command": "quantlab-mcp"},
		},
	}

	_, err := MergeMCPServers(cfg, overlay)
	if err != nil {
		t.Fatalf("MergeMCPServers() error = %v", err)
	}

	mcp, _ := cfg.Raw["mcp"].(map[string]any)
	if len(mcp) != 3 {
		t.Fatalf("expected 3 MCP servers, got %d", len(mcp))
	}
}
