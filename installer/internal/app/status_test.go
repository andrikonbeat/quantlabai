package app

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/ogzuz/quantlab/internal/model"
	"github.com/ogzuz/quantlab/internal/opencode"
	"github.com/ogzuz/quantlab/internal/sdk"
	"github.com/ogzuz/quantlab/internal/state"
)

func TestDetectIssues_NoIssues(t *testing.T) {
	home := t.TempDir()
	qlDir := filepath.Join(home, ".quantlab")
	if err := os.MkdirAll(qlDir, 0o755); err != nil {
		t.Fatal(err)
	}

	// Create a state with components
	st := &state.State{}
	st.AddComponent(model.ComponentSDK, "installed", filepath.Join(qlDir, "venv"), 0)
	st.AddComponent(model.ComponentSkills, "installed", "", 3)
	st.AddComponent(model.ComponentPrompts, "installed", "", 2)
	st.Agents = append(st.Agents, "quantlab-orchestrator")

	// Create skills dir with quantlab-* dirs
	skillsDir := filepath.Join(home, "skills")
	if err := os.MkdirAll(filepath.Join(skillsDir, "quantlab-agent"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(skillsDir, "quantlab-orchestrate"), 0o755); err != nil {
		t.Fatal(err)
	}

	// Create prompts dir with files
	promptsDir := filepath.Join(home, "prompts")
	if err := os.MkdirAll(promptsDir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(promptsDir, "orchestrator.md"), []byte("test"), 0o644); err != nil {
		t.Fatal(err)
	}

	issues := detectIssues(st, &sdk.SDKInfo{Installed: true}, &opencode.Config{Raw: map[string]any{
		"agent": map[string]any{
			"quantlab-orchestrator": map[string]any{},
		},
	}}, 2, 1, qlDir)

	if len(issues) != 0 {
		t.Errorf("expected no issues, got: %v", issues)
	}
}

func TestDetectIssues_MissingSkills(t *testing.T) {
	home := t.TempDir()
	qlDir := filepath.Join(home, ".quantlab")

	st := &state.State{}
	st.AddComponent(model.ComponentSkills, "installed", "", 3)

	issues := detectIssues(st, nil, nil, 0, 0, qlDir)

	found := false
	for _, issue := range issues {
		if issue == "Skills recorded in state but not found on disk" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected 'Skills recorded in state but not found on disk', got: %v", issues)
	}
}

func TestDetectIssues_MissingPrompts(t *testing.T) {
	home := t.TempDir()
	qlDir := filepath.Join(home, ".quantlab")

	st := &state.State{}
	st.AddComponent(model.ComponentPrompts, "installed", "", 2)

	issues := detectIssues(st, nil, nil, 0, 0, qlDir)

	found := false
	for _, issue := range issues {
		if issue == "Prompts recorded in state but not found on disk" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected 'Prompts recorded in state but not found on disk', got: %v", issues)
	}
}

func TestDetectIssues_MissingSDK(t *testing.T) {
	home := t.TempDir()
	qlDir := filepath.Join(home, ".quantlab")

	st := &state.State{}
	st.AddComponent(model.ComponentSDK, "installed", filepath.Join(qlDir, "venv"), 0)

	issues := detectIssues(st, &sdk.SDKInfo{Installed: false}, nil, 0, 0, qlDir)

	found := false
	for _, issue := range issues {
		if issue == "SDK recorded as installed but not detected by pip" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected 'SDK recorded as installed but not detected by pip', got: %v", issues)
	}
}

func TestDetectIssues_OrphanedAgent(t *testing.T) {
	home := t.TempDir()
	qlDir := filepath.Join(home, ".quantlab")

	st := &state.State{}
	// No agents in state

	ocCfg := &opencode.Config{Raw: map[string]any{
		"agent": map[string]any{
			"quantlab-orchestrator": map[string]any{},
		},
	}}

	issues := detectIssues(st, nil, ocCfg, 0, 0, qlDir)

	found := false
	for _, issue := range issues {
		if issue == `Orphaned agent "quantlab-orchestrator" found (not in state)` {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected orphaned agent issue, got: %v", issues)
	}
}

func TestDetectIssues_NilState(t *testing.T) {
	issues := detectIssues(nil, nil, nil, 0, 0, "")
	if len(issues) == 0 {
		t.Error("expected issues for nil state")
	}
}

func TestDetectIssues_JournalResidue(t *testing.T) {
	home := t.TempDir()
	qlDir := filepath.Join(home, ".quantlab")
	if err := os.MkdirAll(qlDir, 0o755); err != nil {
		t.Fatal(err)
	}

	// Create .journal file to simulate residue
	journalPath := filepath.Join(qlDir, ".journal")
	if err := os.WriteFile(journalPath, []byte("residue"), 0o644); err != nil {
		t.Fatal(err)
	}

	st := &state.State{}
	issues := detectIssues(st, nil, nil, 0, 0, qlDir)

	found := false
	for _, issue := range issues {
		if issue == "Residual journal found — a previous operation may have been interrupted" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected journal residue issue, got: %v", issues)
	}
}

func TestCountQuantLabDirs(t *testing.T) {
	dir := t.TempDir()

	// Create quantlab-* dirs
	if err := os.MkdirAll(filepath.Join(dir, "quantlab-agent"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(dir, "quantlab-orchestrate"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(dir, "quantlab-trading"), 0o755); err != nil {
		t.Fatal(err)
	}
	// Non-quantlab dir should be ignored
	if err := os.MkdirAll(filepath.Join(dir, "other"), 0o755); err != nil {
		t.Fatal(err)
	}

	count := countQuantLabDirs(dir)
	if count != 3 {
		t.Errorf("count = %d, want 3", count)
	}
}

func TestCountQuantLabDirs_Empty(t *testing.T) {
	count := countQuantLabDirs("/nonexistent/path")
	if count != 0 {
		t.Errorf("count = %d, want 0 for nonexistent path", count)
	}
}

func TestCountFiles(t *testing.T) {
	dir := t.TempDir()

	if err := os.WriteFile(filepath.Join(dir, "file1.md"), []byte("a"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "file2.md"), []byte("b"), 0o644); err != nil {
		t.Fatal(err)
	}
	// Subdirectory should be ignored
	if err := os.MkdirAll(filepath.Join(dir, "subdir"), 0o755); err != nil {
		t.Fatal(err)
	}

	count := countFiles(dir)
	if count != 2 {
		t.Errorf("count = %d, want 2", count)
	}
}

func TestCountFiles_Empty(t *testing.T) {
	count := countFiles("/nonexistent")
	if count != 0 {
		t.Errorf("count = %d, want 0 for nonexistent path", count)
	}
}

func TestMaskKey(t *testing.T) {
	tests := []struct {
		input string
		want  string
	}{
		{"sk-abc123def456", "sk-a••••f456"},
		{"short", "••••••••"},
		{"", "••••••••"},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			got := maskKey(tt.input)
			if got != tt.want {
				t.Errorf("maskKey(%q) = %q, want %q", tt.input, got, tt.want)
			}
		})
	}
}

func TestPrintHeader(t *testing.T) {
	var buf bytes.Buffer
	printHeader(&buf, "Test Header")
	output := buf.String()
	if !strings.Contains(output, "Test Header") {
		t.Errorf("output = %q, want it to contain 'Test Header'", output)
	}
}

func TestPrintSection(t *testing.T) {
	var buf bytes.Buffer
	printSection(&buf, "Key", "Value")
	output := buf.String()
	if !strings.Contains(output, "Key") {
		t.Errorf("output = %q, want it to contain 'Key'", output)
	}
	if !strings.Contains(output, "Value") {
		t.Errorf("output = %q, want it to contain 'Value'", output)
	}
}
