package opencode

import (
	"io/fs"
	"os"
	"path/filepath"
	"testing"
	"testing/fstest"
)

func TestRecordAndReadManagedPrompts(t *testing.T) {
	dir := t.TempDir()

	if err := RecordManagedPrompts(dir, []string{"guardian-orchestrator.md"}); err != nil {
		t.Fatalf("RecordManagedPrompts() error = %v", err)
	}
	// Second writer merges (python sync side) without dropping Go entries.
	if err := RecordManagedPrompts(dir, []string{"quantlab/campaign.md", "guardian-orchestrator.md"}); err != nil {
		t.Fatalf("RecordManagedPrompts() merge error = %v", err)
	}

	got, err := ReadManagedPrompts(dir)
	if err != nil {
		t.Fatalf("ReadManagedPrompts() error = %v", err)
	}
	want := []string{"guardian-orchestrator.md", "quantlab/campaign.md"}
	if len(got) != len(want) {
		t.Fatalf("ReadManagedPrompts() = %v, want %v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("ReadManagedPrompts() = %v, want %v", got, want)
		}
	}
}

func TestReadManagedPrompts_MissingIsEmpty(t *testing.T) {
	got, err := ReadManagedPrompts(t.TempDir())
	if err != nil {
		t.Fatalf("missing manifest must not error, got %v", err)
	}
	if len(got) != 0 {
		t.Fatalf("missing manifest must read empty, got %v", got)
	}
}

func TestEmbeddedPromptNames(t *testing.T) {
	assets := fstest.MapFS{
		"prompts/guardian-orchestrator.md": {Data: []byte("# g")},
		"prompts/subdir":                   {Mode: fs.ModeDir},
	}
	got, err := EmbeddedPromptNames(assets)
	if err != nil {
		t.Fatalf("EmbeddedPromptNames() error = %v", err)
	}
	if len(got) != 1 || got[0] != "guardian-orchestrator.md" {
		t.Fatalf("EmbeddedPromptNames() = %v, want [guardian-orchestrator.md]", got)
	}
}

func TestRemoveManagedPrompts_KeepsForeign(t *testing.T) {
	dir := t.TempDir()
	// Ours.
	if err := os.MkdirAll(filepath.Join(dir, "quantlab"), 0o755); err != nil {
		t.Fatal(err)
	}
	managedFiles := []string{"guardian-orchestrator.md", "quantlab/campaign.md"}
	for _, rel := range managedFiles {
		if err := os.WriteFile(filepath.Join(dir, filepath.FromSlash(rel)), []byte("# ours"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	// Theirs: top-level user prompt + foreign file inside our subdir.
	if err := os.WriteFile(filepath.Join(dir, "mis-prompts.md"), []byte("# mine"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "quantlab", "notas-personales.md"), []byte("# mine"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := RecordManagedPrompts(dir, managedFiles); err != nil {
		t.Fatal(err)
	}

	recorded, err := ReadManagedPrompts(dir)
	if err != nil {
		t.Fatal(err)
	}
	removed, err := RemoveManagedPrompts(dir, recorded)
	if err != nil {
		t.Fatalf("RemoveManagedPrompts() error = %v", err)
	}
	if len(removed) != 2 {
		t.Fatalf("removed = %v, want the 2 managed files", removed)
	}
	for _, rel := range []string{"mis-prompts.md", "quantlab/notas-personales.md"} {
		if _, err := os.Stat(filepath.Join(dir, filepath.FromSlash(rel))); err != nil {
			t.Fatalf("foreign file %q must survive, stat err = %v", rel, err)
		}
	}
	if err := RemovePromptManifest(dir); err != nil {
		t.Fatalf("RemovePromptManifest() error = %v", err)
	}
	if _, err := os.Stat(ManagedPromptsPath(dir)); !os.IsNotExist(err) {
		t.Fatal("manifest must be gone after RemovePromptManifest")
	}
}

func TestRemoveManagedPrompts_TraversalSkipped(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "victima.md"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	removed, err := RemoveManagedPrompts(dir, []string{"../victima.md", "/abs.md", ".quantlab-managed.json"})
	if err != nil {
		t.Fatalf("RemoveManagedPrompts() error = %v", err)
	}
	if len(removed) != 0 {
		t.Fatalf("escaping entries must be skipped, removed = %v", removed)
	}
	if _, err := os.Stat(filepath.Join(dir, "victima.md")); err != nil {
		t.Fatal("traversal must not delete outside the dir")
	}
}

func TestCountForeignPrompts(t *testing.T) {
	dir := t.TempDir()
	for _, name := range []string{"guardian-orchestrator.md", "mio-1.md", "mio-2.md"} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte("x"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	n, err := CountForeignPrompts(dir, []string{"guardian-orchestrator.md"})
	if err != nil {
		t.Fatalf("CountForeignPrompts() error = %v", err)
	}
	if n != 2 {
		t.Fatalf("CountForeignPrompts() = %d, want 2", n)
	}
}
