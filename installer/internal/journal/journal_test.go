package journal_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/ogzuz/quantlab/internal/journal"
)

func TestNewJournal(t *testing.T) {
	j := journal.New()
	if j == nil {
		t.Fatal("New() returned nil")
	}

	j2 := journal.New("/tmp/test-root")
	if j2 == nil {
		t.Fatal("New(path) returned nil")
	}
}

func TestCapture_NonExistentFile(t *testing.T) {
	dir := t.TempDir()
	j := journal.New(dir)
	err := j.Capture(filepath.Join(dir, "nonexistent.json"))
	if err != nil {
		t.Fatalf("Capture(nonexistent) = %v, want nil", err)
	}
}

func TestCapture_ExistingFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "test.txt")
	original := []byte("hello world")
	if err := os.WriteFile(path, original, 0644); err != nil {
		t.Fatal(err)
	}

	j := journal.New(dir)
	if err := j.Capture(path); err != nil {
		t.Fatalf("Capture(existing) = %v, want nil", err)
	}

	// Now overwrite the file
	if err := os.WriteFile(path, []byte("modified"), 0644); err != nil {
		t.Fatal(err)
	}

	// Restore should bring back original
	if err := j.Restore(); err != nil {
		t.Fatalf("Restore() = %v, want nil", err)
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(data) != string(original) {
		t.Errorf("after restore: content = %q, want %q", string(data), string(original))
	}
}

func TestCapture_RestoreCreatedFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "created.txt")

	j := journal.New(dir)

	// Capture a file that doesn't exist yet
	if err := j.Capture(path); err != nil {
		t.Fatalf("Capture(not yet created) = %v, want nil", err)
	}

	// Create the file
	if err := os.WriteFile(path, []byte("new content"), 0644); err != nil {
		t.Fatal(err)
	}

	// Restore should remove it
	if err := j.Restore(); err != nil {
		t.Fatalf("Restore() = %v, want nil", err)
	}

	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Errorf("after restore: file should not exist, got err = %v", err)
	}
}

func TestWriteWithMode_NewFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "new.txt")
	j := journal.New(dir)

	result, err := j.WriteWithMode(path, []byte("fresh"), 0644)
	if err != nil {
		t.Fatalf("WriteWithMode(new) = %v, want nil", err)
	}
	if !result.Changed {
		t.Error("WriteWithMode(new).Changed = false, want true")
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(data) != "fresh" {
		t.Errorf("content = %q, want %q", string(data), "fresh")
	}
}

func TestWriteWithMode_IdenticalContent(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "same.txt")
	content := []byte("identical")

	if err := os.WriteFile(path, content, 0644); err != nil {
		t.Fatal(err)
	}

	j := journal.New(dir)
	result, err := j.WriteWithMode(path, content, 0644)
	if err != nil {
		t.Fatalf("WriteWithMode(identical) = %v, want nil", err)
	}
	if result.Changed {
		t.Error("WriteWithMode(identical).Changed = true, want false — compare-and-swap should skip")
	}
}

func TestWriteWithMode_ExistingFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "update.txt")
	original := []byte("original content")
	if err := os.WriteFile(path, original, 0644); err != nil {
		t.Fatal(err)
	}

	j := journal.New(dir)

	// Write new content
	result, err := j.WriteWithMode(path, []byte("updated content"), 0644)
	if err != nil {
		t.Fatalf("WriteWithMode(update) = %v, want nil", err)
	}
	if !result.Changed {
		t.Error("WriteWithMode(update).Changed = false, want true")
	}

	// Restore should bring back original
	if err := j.Restore(); err != nil {
		t.Fatalf("Restore() = %v, want nil", err)
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(data) != string(original) {
		t.Errorf("after restore: content = %q, want %q", string(data), string(original))
	}
}

func TestRemove_ExistingFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "remove-me.txt")
	content := []byte("to be removed")
	if err := os.WriteFile(path, content, 0644); err != nil {
		t.Fatal(err)
	}

	j := journal.New(dir)
	result, err := j.Remove(path)
	if err != nil {
		t.Fatalf("Remove(existing) = %v, want nil", err)
	}
	if !result.Removed {
		t.Error("Remove(existing).Removed = false, want true")
	}

	// File should be gone
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Errorf("after remove: file should not exist, got err = %v", err)
	}

	// Restore should bring it back
	if err := j.Restore(); err != nil {
		t.Fatalf("Restore() = %v, want nil", err)
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(data) != string(content) {
		t.Errorf("after restore: content = %q, want %q", string(data), string(content))
	}
}

func TestRemove_NonExistentFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "nonexistent.txt")

	j := journal.New(dir)
	result, err := j.Remove(path)
	if err != nil {
		t.Fatalf("Remove(nonexistent) = %v, want nil", err)
	}
	if result.Removed {
		t.Error("Remove(nonexistent).Removed = true, want false")
	}
}

func TestRestore_MultipleFiles(t *testing.T) {
	dir := t.TempDir()
	j := journal.New(dir)

	// Create three files with different patterns
	files := map[string]string{
		"a.txt": "file a content",
		"b.txt": "file b content",
		"c.txt": "file c content",
	}
	for name, content := range files {
		path := filepath.Join(dir, name)
		if err := os.WriteFile(path, []byte(content), 0644); err != nil {
			t.Fatal(err)
		}
		if err := j.Capture(path); err != nil {
			t.Fatal(err)
		}
	}

	// Overwrite all three
	for name := range files {
		path := filepath.Join(dir, name)
		if err := os.WriteFile(path, []byte("modified "+name), 0644); err != nil {
			t.Fatal(err)
		}
	}

	// Restore all at once
	if err := j.Restore(); err != nil {
		t.Fatalf("Restore() = %v, want nil", err)
	}

	// Verify all restored
	for name, want := range files {
		path := filepath.Join(dir, name)
		data, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		if string(data) != want {
			t.Errorf("%s: after restore content = %q, want %q", name, string(data), want)
		}
	}
}
